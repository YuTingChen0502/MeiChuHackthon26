"""Synthetic metadata/PCM fixtures only; never evidence of a trained model."""
import copy
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from analyzers.bundles import BackendRegistry, BundleAcceptance
from core.audio.types import AudioWindow

MODEL = {"model_bundle_id": "unit-test-only", "frontend_id": "test-front",
         "taxonomy_id": "test-tax", "level_scale_id": "test-scale",
         "execution_profile_id": "test-cpu"}
GROUPS = {"train": ["train-parent"], "validation": ["val-parent"],
          "calibration": ["cal-parent"], "test": ["test-parent"]}


def write_bundle(root: Path, *, site="nano4", declared_material="synthetic", with_results=False):
    root.mkdir(parents=True, exist_ok=True)
    files = {}
    def put(key, value, binary=False):
        path = key + (".bin" if binary else ".json")
        payload = value if binary else (json.dumps(value, sort_keys=True) + "\n").encode()
        (root / path).write_bytes(payload)
        files[key] = {"path": path, "sha256": hashlib.sha256(payload).hexdigest(),
                      "kind": "binary" if binary else "json"}
    put("weights", b"unit-test-placeholder-not-trained-weights", True)
    put("front", {"frontend_id": MODEL["frontend_id"]})
    put("tax", {"taxonomy_id": MODEL["taxonomy_id"], "families": ["guitar", "bass", "drums"]})
    put("scale", {"level_scale_id": MODEL["level_scale_id"],
                  "quantity": "source_level_before_common_mode_removal", "source_level_units": "dBFS_rms",
                  "delta_units": "dB", "amplitude_policy": "preserve_common_scale"})
    put("config", {"seed": 42, "test_only": True})
    put("env", {"execution_site": site, "environment_id": "test-env",
                "python": "test", "framework": "test", "runtime": "test"})
    origin = {"git_sha": "a" * 40, "config_sha256": files["config"]["sha256"],
              "environment_sha256": files["env"]["sha256"], "execution_site": site,
              "run_id": "test-only", "seed": 42}
    step = dict(origin, checkpoint_sha256=files["weights"]["sha256"], parent_checkpoint_sha256="b" * 64,
                adaptation="partial_backbone", changed_pretrained_parameter_count=1, optimizer_steps=1)
    put("training", {"origin": origin, "checkpoint_sha256": files["weights"]["sha256"],
                     "lineage_step": step})
    components = {"checkpoint": "weights", "runtime_model": "weights", "frontend": "front",
                  "taxonomy": "tax", "level_scale": "scale", "training_config": "config",
                  "environment": "env", "training_report": "training", "benchmark_reports": [],
                  "parity_report": None, "calibration_report": None}
    if with_results:
        common = {
            "schema_version": "1.0", "model": MODEL, "runtime_artifact_sha256": files["weights"]["sha256"],
            "git_sha": "a" * 40, "config_sha256": files["config"]["sha256"],
            "dataset_manifest_sha256": "d" * 64, "material_class": declared_material,
            "example_only": declared_material != "real_recorded", "split_groups": GROUPS,
        }
        mapping = {
            "magnitude_tolerance_db": 2.0, "score_feature": {"name": "raw_score", "unit": "score"},
            "endpoint_policy": "left_closed_right_open_last_closed",
            "interval_semantics": "true_balance_minus_predicted_balance",
            "bins": [{"lower": 0, "upper": 1, "count": 4, "success_count": 4,
                      "probability": 1.0, "residual_interval_db": [-1, 1]}],
        }
        put("calibration", dict(common, record_type="CalibrationCandidate", status="candidate",
                               calibration_id="test-cal", operating_envelope_id="test-envelope",
                               evidence_hashes={"rows": "e" * 64}, metrics={},
                               mappings={"joint_anomaly_numeric_correct": mapping,
                                         "normal_within_envelope": copy.deepcopy(mapping)}))
        put("benchmark", dict(common, record_type="BenchmarkResult", status="evaluated",
                             evaluation_split="test", metrics={"eligible_count": 4}))
        put("parity", dict(common, record_type="ExportParityReport", status="evaluated",
                          metrics={"passed": True, "case_count": 4}))
        components.update(benchmark_reports=["benchmark"], parity_report="parity", calibration_report="calibration")
    manifest = {
        "schema_version": "1.0", "bundle_id": MODEL["model_bundle_id"],
        "backend": {"adapter_id": "test-only-adapter", "kind": "direct"}, "model": MODEL,
        "evidence_mode": "source_level_deltas", "units": "dB", "candidate_families": ["guitar", "bass", "drums"],
        "input": {"sample_rate_hz": 8, "channels": 1, "min_window_samples": 8, "max_window_samples": 8},
        "comparison_regimes": ["matched_excerpt"], "uncertainty_features": [{"name": "raw_score", "unit": "score"}],
        "origin": origin, "lineage": [dict(step, evidence="training")], "files": files, "components": components,
        "dataset": {"manifest_sha256": "d" * 64, "provenance": "generated fixture, no real data",
                    "split_groups": GROUPS, "material_class": declared_material},
    }
    save_manifest(root, manifest)
    return manifest


def save_manifest(root, manifest):
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")


def window(window_id="window-1"):
    return AudioWindow(window_id, "session", "run", "uploaded_file", "audio", "clock",
                       8, 0, 8, 1.0, (0.1,) * 8)


def config():
    return {"instrument_config_version": 1, "instruments": [
        {"instrument_id": family, "family": family} for family in ("guitar", "bass", "drums")]}


def context(model=MODEL, asset="test-context"):
    return {
        "record_type": "AnalyzerContext", "schema_version": "1.0", "model": copy.deepcopy(model),
        "observation": window().identity(), "instrument_config": config(),
        "target": {"target_kind": "reference", "reference": {"reference_id": "ref", "source_asset_hash": "sha256:test"},
                   "baseline": None},
        "comparison_regime": "matched_excerpt", "model_specific_context_asset": asset,
        "observation_purpose": "rehearsal", "probe_instrument_id": None,
    }


class TestBackend:
    """Explicit test backend; never registered by production entrypoints."""
    def __init__(self, bundle, cache):
        self.m = bundle.manifest
        self.cache = cache
        self.closed = False

    def capabilities(self):
        return {"provider": "test-only", "example_only": False, "supported_families": self.m["candidate_families"],
                "evidence_modes": [self.m["evidence_mode"]], "model": self.m["model"]}

    def prepare_reference(self, windows, instrument_config):
        asset = "test-" + uuid4().hex
        self.cache[asset] = windows[0].window_id
        return {"model_specific_context_asset": asset}

    def analyze(self, audio, ctx):
        return {
            "record_type": "AnalyzerEvidence", "schema_version": "1.0", "example_only": False,
            **{k: copy.deepcopy(ctx[k]) for k in ("model", "observation", "target", "comparison_regime",
                                                 "model_specific_context_asset")},
            "instrument_config_version": ctx["instrument_config"]["instrument_config_version"],
            "matched_context_window_id": self.cache[ctx["model_specific_context_asset"]],
            "evidence_mode": "source_level_deltas", "units": "dB",
            "measurements": [dict(x, activity="active", observability="observable", validity="valid",
                                 reason_codes=[], uncertainty_features=[{"name": "raw_score", "unit": "score", "value": 0.8}],
                                 source_level_delta_db=0.0) for x in ctx["instrument_config"]["instruments"]],
        }

    def close(self):
        self.closed = True


def registry(*, context_store=None, cache=None):
    result = BackendRegistry(context_store=context_store)
    cache = {} if cache is None else cache
    result.register("test-only-adapter", lambda bundle: TestBackend(bundle, cache))
    return result


def acceptance(bundle, *, use="engineering"):
    m = bundle.manifest
    ids = m["components"]["benchmark_reports"] + [
        m["components"]["parity_report"], m["components"]["calibration_report"]]
    return BundleAcceptance(bundle.manifest_sha256, "test-host-reviewer", use,
                            tuple(m["candidate_families"]), ("matched_excerpt",),
                            "test-envelope", "test-cal", {i: m["files"][i]["sha256"] for i in ids},
                            1, 0.9, 3.0)
