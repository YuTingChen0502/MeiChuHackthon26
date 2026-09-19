"""Exact upstream HTDemucs plus frozen output projections; no downloads/training."""
import hashlib
import io
import json
import os
import threading
from contextlib import contextmanager
from fractions import Fraction
from importlib.metadata import version

import numpy as np

from analyzers.bundle_validation import require
from analyzers.separation.levels import rms_dbfs

_EXECUTION_LOCK = threading.RLock()
_MODULES = {"decoder.3.conv_tr", "tdecoder.3.conv_tr"}


def module_hash(name, module):
    digest = hashlib.sha256()
    for key, value in sorted(module.state_dict().items()):
        digest.update((name + "." + key).encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def dual_mono(samples):
    signal = np.asarray(samples, dtype=np.float32)
    require(signal.ndim == 1 and signal.size == 176400 and np.isfinite(signal).all(),
            "Expected finite mono 44.1 kHz, four-second PCM")
    return np.stack((signal, signal))  # No normalization, rescaling or saved-stem path.


class P1Runner:
    def __init__(self, bundle, *, device="cpu"):
        import torch
        from demucs.htdemucs import HTDemucs
        from demucs.states import load_model
        from demucs.apply import BagOfModels

        require(version("demucs") == "4.0.1", "Frozen adapter requires demucs 4.0.1")
        self.torch = torch
        self.device = torch.device(device)
        require(self.device.type in {"cpu", "cuda"}, "P1 execution supports CPU or Torch CUDA/ROCm devices")
        if self.device.type == "cuda":
            require(torch.cuda.is_available(), "Requested GPU backend is unavailable")
            self.device = torch.device("cuda", self.device.index or 0)
            if torch.version.hip is None:
                os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        self.closed = False
        m = bundle.manifest
        with self.execution():
            with torch.serialization.safe_globals([HTDemucs, Fraction]):
                package = torch.load(io.BytesIO(bundle.data(m["upstream_pretrained_checkpoint"]["path"])),
                                     map_location="cpu", weights_only=True)
            require(package["klass"] is HTDemucs, "Upstream checkpoint is not HTDemucs")
            network = load_model(package, strict=True)
            del package
            require(sum(p.numel() for p in network.parameters()) == m["parameter_counts"]["upstream_model_total"],
                    "Upstream model size mismatch")
            require(list(network.sources) == bundle.json(m["taxonomy"])["model_source_order"]
                    and network.samplerate == 44100 and network.audio_channels == 2, "Upstream profile mismatch")
            self.base_hashes = {name: module_hash(name, network.get_submodule(name)) for name in sorted(_MODULES)}
            require(self.base_hashes == m["adaptation_identity"]["expected_upstream_module_sha256"],
                    "Upstream projection identity mismatch")
            subset = torch.load(io.BytesIO(bundle.data(m["bundled_adapted_checkpoint"]["path"])),
                                map_location="cpu", weights_only=True)
            require(subset["base_checkpoint_sha256"] == m["upstream_pretrained_checkpoint"]["sha256"],
                    "Adapted subset parent mismatch")
            require(set(subset["state"]) == _MODULES, "Unexpected adapted module set")
            count = 0
            for name, state in subset["state"].items():
                module = network.get_submodule(name)
                require(set(state) == set(module.state_dict()) == {"weight", "bias"},
                        "Unexpected adapted tensor set")
                for key, value in state.items():
                    require(value.shape == module.state_dict()[key].shape and torch.isfinite(value).all().item(),
                            "Invalid adapted tensor")
                    count += value.numel()
                module.load_state_dict(state, strict=True)
            require(count == m["parameter_counts"]["optimizer_visible_adapted_subset"], "Adapted size mismatch")
            self.adapted_hashes = {name: module_hash(name, network.get_submodule(name)) for name in sorted(_MODULES)}
            require(self.adapted_hashes == m["adaptation_identity"]["expected_adapted_module_sha256"],
                    "Adapted projection identity mismatch")
            require(all(self.base_hashes[k] != self.adapted_hashes[k] for k in _MODULES),
                    "Adaptation did not change upstream parameters")
            # Match the published single-network bag exactly. Its bag.segment assignment
            # does not override the checkpoint network's training segment in Demucs 4.0.1.
            self.model = BagOfModels([network])
            self.model.segment = 4.0
            self.model.to(self.device).eval()
            for parameter in self.model.parameters():
                parameter.requires_grad_(False)
        self.profile = {
            "adapter": "p1-output-projections-v1", "device": str(self.device), "dtype": "float32",
            "python_framework": "torch", "torch": str(torch.__version__), "demucs": version("demucs"),
            "numpy": np.__version__, "cuda": torch.version.cuda, "rocm": torch.version.hip,
            "sample_rate_hz": 44100, "window_samples": 176400, "split": True, "overlap": 0.25,
            "shifts": 0, "seed": 260920, "deterministic_algorithms": True, "intraop_threads": 1,
            "interop_threads": torch.get_num_interop_threads(),
            "network_segment": str(network.segment),
        }
        self.profile_id = "p1-" + hashlib.sha256(
            json.dumps(self.profile, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @contextmanager
    def execution(self):
        torch = self.torch
        with _EXECUTION_LOCK:
            threads = torch.get_num_threads()
            deterministic = torch.are_deterministic_algorithms_enabled()
            warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
            devices = [self.device.index] if self.device.type == "cuda" else []
            with torch.random.fork_rng(devices=devices):
                try:
                    torch.set_num_threads(1)
                    torch.use_deterministic_algorithms(True)
                    # shifts=0; scoped seed also protects future upstream stochastic operations.
                    torch.random.default_generator.manual_seed(260920)
                    if devices:
                        with torch.cuda.device(self.device):
                            torch.cuda.manual_seed(260920)
                    yield
                finally:
                    torch.use_deterministic_algorithms(deterministic, warn_only=warn_only)
                    torch.set_num_threads(threads)

    def levels(self, samples):
        require(not self.closed, "Model is closed")
        from demucs.apply import apply_model
        signal = dual_mono(samples)
        with self.execution(), self.torch.inference_mode():
            tensor = self.torch.from_numpy(signal).unsqueeze(0).to(self.device)
            estimates = apply_model(self.model, tensor, device=self.device, split=True,
                                    overlap=0.25, shifts=0, progress=False)[0]
            arrays = estimates.detach().cpu().numpy().astype(np.float64, copy=False)
        require(arrays.shape == (6, 2, 176400) and np.isfinite(arrays).all(), "Invalid separator output")
        return {name: rms_dbfs(arrays[i], activity_floor_dbfs=-70.0)
                for i, name in enumerate(self.model.sources)}

    def close(self):
        if not self.closed:
            self.closed = True
            del self.model
