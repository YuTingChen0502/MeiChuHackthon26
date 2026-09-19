"""Non-executing validation of ML-internal remote artifact bundles.

No checkpoint is deserialized and no module name from a manifest is imported.
Hash/provenance validity is distinct from empirical acceptance.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

def sha256_file(path):
    """Stream artifact identity with only stdlib dependencies (also on PN54)."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


MODEL_KEYS = {"model_bundle_id", "frontend_id", "taxonomy_id",
              "level_scale_id", "execution_profile_id"}
COMPONENT_KEYS = {"checkpoint", "runtime_model", "frontend", "taxonomy", "level_scale",
                  "training_config", "environment", "training_report",
                  "benchmark_reports", "parity_report", "calibration_report"}
LINEAGE_KEYS = {"checkpoint_sha256", "parent_checkpoint_sha256", "git_sha", "config_sha256",
                "environment_sha256", "execution_site", "run_id", "adaptation",
                "changed_pretrained_parameter_count", "optimizer_steps", "seed", "evidence"}
PROBABILITY_EVENT = "joint_anomaly_numeric_correct"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(value, length=64):
    require(isinstance(value, str) and re.fullmatch("[0-9a-f]{" + str(length) + "}", value),
            f"Expected lowercase {length}-character hash")
    return value


def nonempty(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"{label} must be a nonempty string")


def strings(value, label, *, empty=False):
    require(isinstance(value, list) and (empty or bool(value)), f"{label} must be a list")
    require(all(isinstance(x, str) and bool(x.strip()) for x in value), f"Invalid {label}")
    require(len(set(value)) == len(value), f"Duplicate {label}")


def strict_json_bytes(raw: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError(f"Nonfinite JSON number: {value}")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid_constant)
    # Reject overflow such as 1e999, too.
    json.dumps(value, allow_nan=False)
    return value


def read_json(path: Path):
    require(path.stat().st_size <= 32 * 1024 ** 2, "JSON metadata exceeds size limit")
    return strict_json_bytes(path.read_bytes())


def safe_relative(value: str) -> PurePosixPath:
    nonempty(value, "file path")
    p = PurePosixPath(value)
    require("\\" not in value and ":" not in value and not p.is_absolute()
            and value == p.as_posix() and ".." not in p.parts
            and value not in {".", ""}, "Unsafe bundle path")
    reserved = {"con", "prn", "aux", "nul"} | {f"{kind}{n}" for kind in ("com", "lpt") for n in range(1, 10)}
    for part in p.parts:
        require(not part.endswith((".", " ")) and part.split(".")[0].lower() not in reserved,
                "Nonportable bundle path")
    return p


def contained_file(root: Path, relative: str) -> Path:
    parts = safe_relative(relative).parts
    root = root.resolve()
    path = root
    for part in parts:
        path = path / part
        require(not path.is_symlink(), "Symlinks are forbidden in bundles")
        # Windows junctions may not report as symlinks.
        if hasattr(path, "is_junction"):
            require(not path.is_junction(), "Junctions are forbidden in bundles")
    require(path.resolve().is_relative_to(root), "Bundle file escaped its root")
    require(path.is_file(), f"Missing bundle file: {relative}")
    return path


@dataclass(frozen=True)
class ValidatedBundle:
    root: Path
    manifest_sha256: str
    _manifest_json: str

    @property
    def manifest(self):
        return json.loads(self._manifest_json)

    def artifact_path(self, file_id: str) -> Path:
        entry = self.manifest["files"][file_id]
        path = contained_file(self.root, entry["path"])
        require(sha256_file(path) == entry["sha256"], f"Artifact changed after validation: {file_id}")
        return path

    def component_json(self, name):
        file_id = self.manifest["components"][name]
        return None if file_id is None else read_json(self.artifact_path(file_id))

    def revalidate(self):
        fresh = validate_bundle(self.root)
        require(fresh.manifest_sha256 == self.manifest_sha256, "Manifest changed after validation")
        return fresh


def validate_result_record(record, *, model, artifact_sha256=None):
    require(isinstance(record, dict), "Result must be an object")
    require(record.get("schema_version") == "1.0", "Unsupported result version")
    require(record.get("record_type") in {"BenchmarkResult", "ExportParityReport", "CalibrationCandidate"},
            "Unknown evidence record type")
    require(record.get("model") == model, "Result model identity mismatch")
    sha(record.get("git_sha"), 40)
    sha(record.get("config_sha256"))
    sha(record.get("dataset_manifest_sha256"))
    if artifact_sha256 is not None:
        require(record.get("runtime_artifact_sha256") == artifact_sha256, "Result artifact mismatch")
    else:
        sha(record.get("runtime_artifact_sha256"))
    require(record.get("material_class") in {"real_recorded", "synthetic", "unknown"},
            "Declare result material class")
    require(record.get("status") in {"diagnostic", "candidate", "evaluated"}, "Result cannot self-approve")
    splits = record.get("split_groups")
    require(isinstance(splits, dict) and set(splits) == {"train", "validation", "calibration", "test"},
            "Result requires four grouped splits")
    seen = set()
    for name, groups in splits.items():
        strings(groups, f"{name} groups", empty=True)
        require(not seen.intersection(groups), "Evidence split leakage")
        seen.update(groups)
    require(isinstance(record.get("metrics"), dict), "Result requires metrics with denominators")
    json.dumps(record, allow_nan=False)


def _read_bundle(root: Path, *, verify_binary: bool):
    root = Path(root).resolve()
    manifest_path = contained_file(root, "manifest.json")
    require(manifest_path.stat().st_size <= 2 * 1024 ** 2, "Manifest too large")
    raw = manifest_path.read_bytes()
    m = strict_json_bytes(raw)
    required = {"schema_version", "bundle_id", "backend", "model", "evidence_mode", "units",
                "candidate_families", "input", "comparison_regimes", "uncertainty_features",
                "origin", "lineage", "files", "components", "dataset"}
    require(isinstance(m, dict) and set(m) == required, "Unexpected/missing bundle manifest fields")
    require(m["schema_version"] == "1.0", "Unsupported bundle version")
    nonempty(m["bundle_id"], "bundle_id")
    require(set(m["backend"]) == {"adapter_id", "kind"}, "Invalid backend declaration")
    nonempty(m["backend"]["adapter_id"], "adapter_id")
    require(m["backend"]["kind"] in {"separation", "direct", "hybrid"}, "Unknown backend kind")
    require(isinstance(m["model"], dict) and set(m["model"]) == MODEL_KEYS, "Invalid model identity")
    for value in m["model"].values():
        nonempty(value, "model identity")
    require(m["model"]["model_bundle_id"] == m["bundle_id"], "Bundle/model identity differs")
    require(m["evidence_mode"] in {"source_levels", "source_level_deltas"}, "Invalid evidence mode")
    require(m["units"] == ("dBFS_rms" if m["evidence_mode"] == "source_levels" else "dB"),
            "Evidence units mismatch")
    strings(m["candidate_families"], "candidate families")
    strings(m["comparison_regimes"], "comparison regimes")
    require(set(m["comparison_regimes"]) <= {"matched_excerpt", "stable_texture"}, "Invalid comparison regime")
    inp = m["input"]
    require(set(inp) == {"sample_rate_hz", "channels", "min_window_samples", "max_window_samples"},
            "Invalid input settings")
    require(all(type(v) is int and v > 0 for v in inp.values()), "Input settings must be positive integers")
    require(inp["channels"] == 1 and inp["max_window_samples"] >= inp["min_window_samples"],
            "Expected mono input and ordered window limits")
    features = m["uncertainty_features"]
    require(isinstance(features, list), "uncertainty_features must be a list")
    for feature in features:
        require(set(feature) == {"name", "unit"}, "Invalid uncertainty feature declaration")
        for v in feature.values():
            nonempty(v, "uncertainty feature")
    require(len({x["name"] for x in features}) == len(features), "Duplicate uncertainty feature")
    files = m["files"]
    require(isinstance(files, dict) and files, "files must be a nonempty mapping")
    paths = set()
    for file_id, entry in files.items():
        nonempty(file_id, "file_id")
        require(set(entry) == {"path", "sha256", "kind"}, "Invalid file descriptor")
        sha(entry["sha256"])
        require(entry["kind"] in {"binary", "json"}, "Invalid file kind")
        safe_relative(entry["path"])
        key = entry["path"].casefold()
        require(key != "manifest.json" and key not in paths, "Duplicate/reserved bundle file path")
        paths.add(key)
        if entry["kind"] == "json":
            require(entry["path"].endswith(".json"), "JSON metadata must have a .json suffix")
        if verify_binary or entry["kind"] == "json":
            path = contained_file(root, entry["path"])
            require(sha256_file(path) == entry["sha256"], f"Artifact hash mismatch: {file_id}")
            if entry["kind"] == "json":
                read_json(path)
    c = m["components"]
    require(set(c) == COMPONENT_KEYS, "Invalid component references")
    require(isinstance(c["benchmark_reports"], list), "benchmark_reports must be a list")
    refs = [v for k, v in c.items() if k != "benchmark_reports" and v is not None] + c["benchmark_reports"]
    require(all(isinstance(x, str) and x in files for x in refs), "Unknown component file reference")
    for key in COMPONENT_KEYS - {"benchmark_reports", "parity_report", "calibration_report"}:
        require(c[key] is not None, f"Missing required component: {key}")
    def component(name):
        file_id = c[name]
        require(files[file_id]["kind"] == "json", f"{name} must be JSON")
        return read_json(contained_file(root, files[file_id]["path"]))
    for name, identity_key in (("frontend", "frontend_id"), ("taxonomy", "taxonomy_id"),
                               ("level_scale", "level_scale_id")):
        require(component(name).get(identity_key) == m["model"][identity_key], f"{name} identity mismatch")
    tax = component("taxonomy")
    strings(tax.get("families"), "taxonomy families")
    require(set(m["candidate_families"]) <= set(tax["families"]), "Candidate family outside taxonomy")
    scale = component("level_scale")
    require(scale.get("quantity") == "source_level_before_common_mode_removal"
            and scale.get("source_level_units") == "dBFS_rms" and scale.get("delta_units") == "dB"
            and scale.get("amplitude_policy") == "preserve_common_scale",
            "Incompatible source-level convention")
    origin = m["origin"]
    require(set(origin) == {"git_sha", "config_sha256", "environment_sha256", "execution_site", "run_id", "seed"},
            "Invalid origin record")
    sha(origin["git_sha"], 40)
    require(type(origin["seed"]) is int, "Origin random seed is required")
    require(origin["execution_site"] in {"nano4", "mi300", "local"}, "Unknown execution site")
    nonempty(origin["run_id"], "run_id")
    for name, field in (("training_config", "config_sha256"), ("environment", "environment_sha256")):
        require(origin[field] == files[c[name]]["sha256"], f"Origin {field} mismatch")
    env = component("environment")
    require(env.get("execution_site") == origin["execution_site"], "Environment/site mismatch")
    for key in ("environment_id", "python", "framework", "runtime"):
        nonempty(env.get(key), key)
    component("training_config")
    report = component("training_report")
    require(report.get("origin") == origin and report.get("checkpoint_sha256") == files[c["checkpoint"]]["sha256"],
            "Training report origin/checkpoint mismatch")
    dataset = m["dataset"]
    require(set(dataset) == {"manifest_sha256", "provenance", "split_groups", "material_class"},
            "Invalid dataset provenance")
    sha(dataset["manifest_sha256"])
    nonempty(dataset["provenance"], "dataset provenance evidence")
    validate_result_record({
        "schema_version": "1.0", "record_type": "BenchmarkResult", "model": m["model"],
        "git_sha": origin["git_sha"], "config_sha256": origin["config_sha256"],
        "runtime_artifact_sha256": files[c["runtime_model"]]["sha256"],
        "dataset_manifest_sha256": dataset["manifest_sha256"],
        "material_class": dataset["material_class"], "status": "diagnostic",
        "split_groups": dataset["split_groups"], "metrics": {},
    }, model=m["model"])
    lineage = m["lineage"]
    require(isinstance(lineage, list) and lineage, "Checkpoint lineage required")
    last = None
    seen = set()
    for step in lineage:
        require(set(step) == LINEAGE_KEYS, "Invalid lineage entry")
        for key in ("checkpoint_sha256", "parent_checkpoint_sha256", "config_sha256", "environment_sha256"):
            sha(step[key])
        sha(step["git_sha"], 40)
        require(type(step["seed"]) is int, "Lineage random seed required")
        require(step["checkpoint_sha256"] not in seen
                and step["checkpoint_sha256"] != step["parent_checkpoint_sha256"], "Cyclic/duplicate lineage")
        if last is not None:
            require(step["parent_checkpoint_sha256"] == last, "Broken checkpoint lineage")
        seen.add(step["checkpoint_sha256"])
        require(step["execution_site"] in {"nano4", "mi300", "local"}, "Unknown lineage site")
        require(step["adaptation"] in {"head_only", "partial_backbone", "full_backbone"}, "Invalid adaptation kind")
        require(type(step["optimizer_steps"]) is int and step["optimizer_steps"] > 0
                and type(step["changed_pretrained_parameter_count"]) is int
                and step["changed_pretrained_parameter_count"] >= 0, "Invalid adaptation counts")
        nonempty(step["run_id"], "lineage run_id")
        require(step["evidence"] in files and files[step["evidence"]]["kind"] == "json",
                "Lineage requires a hashed JSON evidence file")
        proof = read_json(contained_file(root, files[step["evidence"]]["path"]))
        require(proof.get("lineage_step") == {k: v for k, v in step.items() if k != "evidence"},
                "Lineage evidence mismatch")
        last = step["checkpoint_sha256"]
    require(last == files[c["checkpoint"]]["sha256"], "Lineage does not end at supplied checkpoint")
    require(all(lineage[-1][key] == origin[key] for key in origin), "Origin is not final lineage step")
    for name in ("benchmark_reports", "parity_report", "calibration_report"):
        ids = c[name] if name == "benchmark_reports" else ([] if c[name] is None else [c[name]])
        expected_type = {"benchmark_reports": "BenchmarkResult", "parity_report": "ExportParityReport",
                         "calibration_report": "CalibrationCandidate"}[name]
        for file_id in ids:
            require(files[file_id]["kind"] == "json", "Result reference must be JSON")
            record = read_json(contained_file(root, files[file_id]["path"]))
            validate_result_record(record, model=m["model"],
                                   artifact_sha256=files[c["runtime_model"]]["sha256"])
            require(record["record_type"] == expected_type, "Evidence reference type mismatch")
            if name == "calibration_report":
                from analyzers.calibration_metadata import validate_calibration
                validate_calibration(record, model=m["model"],
                                     artifact_sha256=files[c["runtime_model"]]["sha256"],
                                     declared_features=m["uncertainty_features"])
            require(record["dataset_manifest_sha256"] == dataset["manifest_sha256"]
                    and record["split_groups"] == dataset["split_groups"], "Result/dataset provenance mismatch")
    require(set(files) == set(refs) | {step["evidence"] for step in lineage},
            "Unreferenced files are forbidden (no datasets, caches or optimizer state)")
    return raw, m


def validate_bundle(root: Path) -> ValidatedBundle:
    root = Path(root).resolve()
    try:
        raw, manifest = _read_bundle(root, verify_binary=True)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Malformed bundle manifest or evidence metadata") from error
    return ValidatedBundle(root, hashlib.sha256(raw).hexdigest(), json.dumps(manifest, allow_nan=False))


def inspect_remote_metadata(root: Path) -> dict:
    """Validate metadata only. This result is NEVER a loadable ValidatedBundle."""
    try:
        raw, manifest = _read_bundle(Path(root).resolve(), verify_binary=False)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Malformed bundle manifest or evidence metadata") from error
    return {
        "record_type": "RemoteBundleMetadata", "status": "ARTIFACT_BYTES_NOT_VERIFIED",
        "manifest_sha256": hashlib.sha256(raw).hexdigest(), "manifest": manifest,
        "external_artifacts": {key: value for key, value in manifest["files"].items()
                               if value["kind"] == "binary"},
    }
