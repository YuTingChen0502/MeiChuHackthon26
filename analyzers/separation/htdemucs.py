"""Lazy, amplitude-preserving adapter for the approved HTDemucs 6-source path."""

from __future__ import annotations

import importlib.util
from importlib.metadata import version

import numpy as np

from analyzers.separation.base import SeparationResult


class SeparationRuntimeUnavailable(RuntimeError):
    pass


class HTDemucs6sSeparator:
    backend_id = "htdemucs_6s"
    checkpoint_id = "facebookresearch-demucs:htdemucs_6s"
    checkpoint_sha256 = "34c22ccb381c6f9fdbf324f04e1e2fe21aaaf293f5ded163a162697ff9a02ddd"

    @staticmethod
    def runtime_status() -> dict[str, object]:
        missing = [name for name in ("torch", "demucs") if importlib.util.find_spec(name) is None]
        versions = (
            {name: version(name) for name in ("torch", "demucs", "torchaudio")}
            if not missing
            else {}
        )
        return {"available": not missing, "missing_modules": missing, "versions": versions}

    def __init__(
        self, *, device: str = "cpu", segment_s: float | None = None, seed: int = 0
    ) -> None:
        status = self.runtime_status()
        if not status["available"]:
            raise SeparationRuntimeUnavailable(
                f"HTDemucs runtime unavailable; missing {status['missing_modules']}"
            )
        import torch
        from demucs.pretrained import get_model

        self._torch = torch
        self._device = device
        self._seed = int(seed)
        torch.manual_seed(self._seed)
        torch.use_deterministic_algorithms(True)
        torch.set_num_threads(1)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            # PyTorch only permits setting this before inter-op work starts. A
            # long-lived host must pin it during process initialization instead.
            pass
        self._model = get_model(self.backend_id)
        self._model.to(device)
        self._model.eval()
        if segment_s is not None:
            self._model.segment = segment_s

    def separate(self, mixture: np.ndarray, sample_rate_hz: int) -> SeparationResult:
        from demucs.apply import apply_model

        if sample_rate_hz != int(self._model.samplerate):
            raise ValueError(
                f"Expected {self._model.samplerate} Hz; deterministic resampling belongs in the adapter caller"
            )
        signal = np.asarray(mixture, dtype=np.float32)
        if signal.ndim == 1:
            signal = np.stack([signal, signal])
        if signal.ndim != 2 or signal.shape[0] not in (1, 2):
            raise ValueError("Expected mono or channel-first stereo waveform")
        if signal.shape[0] == 1:
            signal = np.repeat(signal, 2, axis=0)
        tensor = self._torch.from_numpy(signal).unsqueeze(0).to(self._device)
        with self._torch.inference_mode():
            # apply_model restores the model's common normalization.  We consume
            # in-memory tensors and do not invoke the CLI's per-stem save rescaling.
            estimates = apply_model(
                self._model,
                tensor,
                device=self._device,
                split=True,
                overlap=0.25,
                shifts=0,
                progress=False,
            )[0]
        arrays = estimates.detach().cpu().numpy().astype(np.float64, copy=False)
        sources = {name: arrays[index] for index, name in enumerate(self._model.sources)}
        return SeparationResult(
            sources=sources,
            sample_rate_hz=sample_rate_hz,
            backend_id=self.backend_id,
            checkpoint_id=self.checkpoint_id,
        )

    @property
    def execution_settings(self) -> dict[str, object]:
        return {
            "device": self._device,
            "split": True,
            "overlap": 0.25,
            "shifts": 0,
            "seed": self._seed,
            "deterministic_algorithms": True,
            "torch_num_threads": self._torch.get_num_threads(),
            "torch_num_interop_threads": self._torch.get_num_interop_threads(),
        }
