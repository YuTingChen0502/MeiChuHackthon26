"""Offline, hash-pinned intake for the published P1 projection-subset bundle."""
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import tarfile
from types import MappingProxyType

from analyzers.bundle_validation import contained_file, read_json, require, safe_relative, sha, strict_json_bytes


DEFAULT_SPEC = Path(__file__).resolve().parents[2] / "models" / "p1_frozen_spec.json"
MAX_BUNDLE_BYTES = 64 * 1024 ** 2


@dataclass(frozen=True)
class FrozenP1Bundle:
    _files: object
    _spec_json: str

    @property
    def spec(self):
        return json.loads(self._spec_json)

    def data(self, name):
        data = self._files[name]
        require(hashlib.sha256(data).hexdigest() == self.spec["files"][name], "Frozen artifact hash mismatch")
        return data

    def json(self, name):
        return strict_json_bytes(self.data(name))

    @property
    def manifest(self):
        return self.json("manifest.json")

    @property
    def identity_hash(self):
        return hashlib.sha256(self._spec_json.encode()).hexdigest()


def validate_p1_bundle(path, *, trusted_spec=None):
    """trusted_spec is host-owned configuration, never taken from the remote bundle."""
    spec = read_json(DEFAULT_SPEC) if trusted_spec is None else json.loads(json.dumps(trusted_spec))
    require(spec["schema_version"] == "1.0", "Unsupported P1 trust-spec version")
    inventory = spec["files"]
    require(isinstance(inventory, dict) and inventory, "Frozen inventory required")
    for name, digest in inventory.items():
        safe_relative(name)
        sha(digest)
    source = Path(path)
    if source.is_dir() and (source / "results" / "model_bundle.tar.gz").is_file():
        source = source / "results" / "model_bundle.tar.gz"
    files = {}
    if source.is_dir():
        for name in inventory:
            file = contained_file(source, name)
            require(file.stat().st_size <= MAX_BUNDLE_BYTES, "Oversized candidate artifact")
            files[name] = file.read_bytes()
    else:
        require(source.is_file() and not source.is_symlink(), "Candidate archive missing or linked")
        require(source.stat().st_size <= MAX_BUNDLE_BYTES, "Oversized candidate archive")
        raw = source.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == spec["archive_sha256"], "Frozen archive hash mismatch")
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            total = 0
            seen = set()
            for member in archive:
                safe_relative(member.name)
                require(member.name not in seen, "Duplicate candidate archive path")
                seen.add(member.name)
                require(member.isdir() or member.isfile(), "Candidate archive links/special files forbidden")
                if member.isdir():
                    continue
                require(member.name.startswith("model_bundle/"), "Invalid candidate archive root")
                name = member.name[len("model_bundle/"):]
                require(name in inventory, "Unexpected candidate archive file")
                total += member.size
                require(total <= MAX_BUNDLE_BYTES, "Candidate archive exceeds size limit")
                files[name] = archive.extractfile(member).read()
    require(set(files) == set(inventory), "Missing candidate artifact")
    for name, data in files.items():
        require(hashlib.sha256(data).hexdigest() == inventory[name], "Frozen candidate file hash mismatch: " + name)
    bundle = FrozenP1Bundle(MappingProxyType(files), json.dumps(spec, sort_keys=True, separators=(",", ":")))
    m = bundle.manifest
    front, tax = bundle.json(m["frontend"]), bundle.json(m["taxonomy"])
    require(m["bundle_id"] == spec["bundle_id"], "Frozen bundle identity mismatch")
    require(m["production_real_analyzer_authorized"] is False, "This loader cannot authorize production")
    require(m["supported_families"] == spec["supported_candidate_families"] == ["bass"],
            "P1 candidate support must remain bass-only")
    require(m["upstream_pretrained_checkpoint"]["identity"] == "facebookresearch-demucs:htdemucs_6s",
            "Unsupported upstream architecture")
    for key in ("bundled_adapted_checkpoint", "upstream_pretrained_checkpoint"):
        record = m[key]
        require(record["sha256"] == inventory[record["path"]] and record["bytes"] == len(files[record["path"]]),
                "Checkpoint descriptor mismatch")
    require(front["sample_rate_hz"] == m["sample_rate_hz"] == 44100
            and front["window_samples"] == 176400
            and front["window_duration_seconds"] == m["window_duration_seconds"] == 4.0,
            "Incompatible P1 frontend")
    norm = front["normalization"]
    require(all(norm[k] is False for k in ("independent_peak_normalization", "independent_rms_normalization",
                                           "automatic_clipping_rescale")), "Incompatible level-scale normalization")
    require(front["separator_execution"] == {"split": True, "overlap": 0.25, "shifts": 0,
                                              "seed": 260920, "deterministic_algorithms": True},
            "Frozen separator execution differs")
    require(tax["model_source_order"] == ["drums", "bass", "other", "vocals", "guitar", "piano"],
            "Incompatible model taxonomy")
    require([k for k,v in tax["families"].items() if v["status"] == "SUPPORTED"] == ["bass"],
            "Unsupported family claim")
    thresholds = bundle.json(m["thresholds"])
    require(front["activity_floor_dbfs"] == thresholds["activity_floor_dbfs"] == -70.0,
            "Frozen activity floor differs")
    require(thresholds["confidence"]["probability_output_permitted"] is False, "Calibration is unavailable")
    return bundle
