"""Uncalibrated bass-only evidence after actual file/microphone P1 execution."""
import copy
import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4

from analyzers.bundle_validation import contained_file, require, strict_json_bytes
from analyzers.reference_contexts import ReferenceContextStore
from analyzers.separation.p1_bundle import validate_p1_bundle
from analyzers.separation.p1_runner import P1Runner
from core.contracts.validation import ANALYZER, validate_analyzer_pair, validate_record

P1_ADAPTER_ID = "htdemucs6s-p1-output-projections-v1"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class P1CandidateAnalyzer:
    def __init__(self, bundle, runner, *, cache_dir=None, candidate_mode=False):
        require(type(candidate_mode) is bool, "candidate_mode must be host-selected boolean")
        self.bundle, self.runner = bundle, runner
        self._candidate_mode = candidate_mode
        self._closed = False
        self._cache = {}
        self._root = Path(cache_dir).resolve() if cache_dir is not None else None
        if self._root:
            self._root.mkdir(parents=True, exist_ok=True)
        self._bindings = ReferenceContextStore(self._root / "bindings" if self._root else None)
        m = bundle.manifest
        self._model = {
            "model_bundle_id": m["bundle_id"], "frontend_id": bundle.json(m["frontend"])["frontend_id"],
            "taxonomy_id": bundle.json(m["taxonomy"])["taxonomy_id"],
            "execution_profile_id": runner.profile_id, "level_scale_id": bundle.spec["level_scale_id"],
        }
        self._taxonomy = bundle.json(m["taxonomy"])["families"]

    def capabilities(self):
        return {
            "provider": P1_ADAPTER_ID, "example_only": False,
            "supported_families": ["bass"] if self._candidate_mode else [],
            "candidate_families": ["bass"], "candidate_mode": self._candidate_mode,
            "production_authorized": False, "confidence_status": "UNCALIBRATED",
            "comparison_regimes": ["matched_excerpt"], "evidence_modes": ["source_levels"],
            "model": copy.deepcopy(self._model), "execution_profile": copy.deepcopy(self.runner.profile),
            "input": {"sample_rate_hz": 44100, "channels": 1, "min_window_samples": 176400,
                      "max_window_samples": 176400},
            "state": "closed" if self._closed else "loaded",
        }

    def calibration_metadata(self):
        return None

    def acceptance_metadata(self):
        return None

    def _window(self, window):
        require(window.sample_rate_hz == 44100 and len(window.samples) == 176400
                and window.sample_end - window.sample_start == 176400, "P1 frontend/window mismatch")
        require(all(math.isfinite(x) for x in window.samples), "Nonfinite PCM")
        require(math.isfinite(window.input_clipped_fraction) and 0 <= window.input_clipped_fraction <= 1,
                "Invalid PCM clipping metadata")

    def prepare_reference(self, windows, instrument_config):
        require(not self._closed, "Analyzer is closed")
        validate_record(instrument_config, ANALYZER, "InstrumentConfig")
        configured = instrument_config["instruments"]
        require(len({x["instrument_id"] for x in configured}) == len(configured), "Duplicate instrument IDs")
        records, seen, origin = [], set(), None
        for window in windows:
            require(len(records) < 1024, "Reference exceeds bounded 1024-window cache")
            self._window(window)
            require(window.input_kind == "uploaded_file", "Only matched digital reference is supported")
            require(not window.input_clipped_fraction and max(abs(x) for x in window.samples) < 1,
                    "Clipped reference is outside candidate envelope")
            current_origin = (window.session_id, window.analysis_run_id,
                              window.input_asset_or_device_id, window.clock_id)
            if origin is None:
                origin = current_origin
            require(current_origin == origin, "Reference windows span incompatible input timelines")
            span = (window.sample_start, window.sample_end)
            require(span not in seen, "Ambiguous reference sample spans")
            seen.add(span)
            levels = self.runner.levels(window.samples)
            import numpy as np
            records.append({
                "window_id": window.window_id, "sample_start": window.sample_start, "sample_end": window.sample_end,
                "pcm_sha256": hashlib.sha256(np.asarray(window.samples, dtype="<f4").tobytes()).hexdigest(),
                "bass_dbfs": levels["bass"],
            })
        require(records, "Reference windows required")
        require(len({x["window_id"] for x in records}) == len(records), "Duplicate reference window IDs")
        payload = {"version": 1, "model": self._model, "bundle_pin": self.bundle.identity_hash,
                   "instrument_config": instrument_config, "windows": records, "context_nonce": uuid4().hex}
        raw = _canonical(payload)
        key = hashlib.sha256(raw).hexdigest()
        asset = "p1-reference:" + key
        if self._root:
            with (self._root / (key + ".json")).open("xb") as handle:
                handle.write(raw)
        else:
            self._cache[key] = raw
        self._bindings.add(self.bundle.identity_hash, asset, instrument_config, [r["window_id"] for r in records])
        # No coverage inferred from configuration, duration or separated-source activity alone.
        return {"model_specific_context_asset": asset, "window_count": len(records), "example_only": False}

    def _reference(self, asset, config, target):
        if not isinstance(asset, str) or not asset.startswith("p1-reference:"):
            return None, "reference_context_unavailable"
        key = asset[len("p1-reference:"):]
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
            return None, "reference_context_unavailable"
        if self._root:
            path = self._root / (key + ".json")
            if not path.exists():
                return None, "reference_context_unavailable"
            raw = contained_file(self._root, key + ".json").read_bytes()
        else:
            raw = self._cache.get(key)
            if raw is None:
                return None, "reference_context_unavailable"
        require(hashlib.sha256(raw).hexdigest() == key, "Reference cache hash mismatch")
        record = strict_json_bytes(raw)
        require(record["model"] == self._model and record["bundle_pin"] == self.bundle.identity_hash,
                "Incompatible reference model/profile")
        require(record["instrument_config"] == config, "Incompatible reference instrument configuration")
        _, reason = self._bindings.lookup_and_bind(self.bundle.identity_hash, asset, config, target)
        return (record, None) if reason is None else (None, reason)

    def analyze(self, window, context):
        require(not self._closed, "Analyzer is closed")
        validate_record(context, ANALYZER, "AnalyzerContext")
        self._window(window)
        require(window.identity() == context["observation"], "PCM/window identity mismatch")
        require(context["model"] == self._model, "Candidate model/profile identity mismatch")
        config = context["instrument_config"]
        configured = config["instruments"]
        reference, reason = self._reference(context["model_specific_context_asset"], config, context["target"])
        matched = None
        if reason is None:
            if context["comparison_regime"] != "matched_excerpt":
                reason = "comparison_regime_unsupported"
            elif window.input_clipped_fraction or max(abs(x) for x in window.samples) >= 1:
                reason = "clipping_outside_candidate_envelope"
            else:
                matches = [r for r in reference["windows"] if
                           (r["sample_start"], r["sample_end"]) == (window.sample_start, window.sample_end)]
                if len(matches) != 1:
                    reason = "matched_reference_span_unavailable"
                else:
                    matched = matches[0]
        bass_count = sum(x["family"] == "bass" for x in configured)
        # Acquisition kind, configured support and target activity never suppress
        # compatible inference. All six sources are produced before publication masks.
        observation_levels = self.runner.levels(window.samples) if reason is None else None
        obs_level = observation_levels["bass"] if observation_levels is not None else None
        if reason is None and not self._candidate_mode:
            reason = "candidate_mode_not_enabled"
        rows = []
        for item in configured:
            row = dict(item, activity="unknown", observability="unknown", validity="invalid",
                       reason_codes=[], uncertainty_features=[], source_level_db=None, target_source_level_db=None)
            family = item["family"]
            if family not in self._taxonomy:
                row["reason_codes"] = ["INSUFFICIENT_EVIDENCE"]
            elif family != "bass":
                row.update(activity="unsupported", observability="not_observable", reason_codes=["unsupported_family"])
            elif reason is not None:
                row["reason_codes"] = [reason]
            elif bass_count != 1:
                row["reason_codes"] = ["ambiguous_same_family_sources"]
            elif matched["bass_dbfs"] is None or obs_level is None:
                row["reason_codes"] = ["source_below_activity_floor"]
                row["observability"] = "not_observable"
            else:
                row.update(activity="active", observability="observable", validity="valid",
                           source_level_db=obs_level, target_source_level_db=matched["bass_dbfs"],
                           reason_codes=["uncalibrated_candidate"] + (
                               ["real_room_not_validated"] if window.input_kind == "live_microphone" else []))
            rows.append(row)
        evidence = {
            "record_type": "AnalyzerEvidence", "schema_version": "1.0", "example_only": False,
            **{k: copy.deepcopy(context[k]) for k in
               ("model", "observation", "target", "comparison_regime", "model_specific_context_asset")},
            "instrument_config_version": config["instrument_config_version"],
            "matched_context_window_id": matched["window_id"] if matched else None,
            "evidence_mode": "source_levels", "units": "dBFS_rms", "measurements": rows,
        }
        validate_analyzer_pair(context, evidence)
        return evidence

    def execution_diagnostics(self):
        """Bounded model-call diagnostics, separate from public evidence/confidence."""
        return self.runner.execution_diagnostics()

    def close(self):
        if not self._closed:
            self._closed = True
            self.runner.close()
            self._cache.clear()


def load_p1_candidate(bundle_path, *, cache_dir=None, candidate_mode=False, device="cpu",
                      expected_model=None, acceptance=None, trusted_spec=None):
    """Explicit host candidate selection, separate from generic production acceptance."""
    require(acceptance is None, "Frozen P1 is uncalibrated; production acceptance is unavailable")
    bundle = validate_p1_bundle(bundle_path, trusted_spec=trusted_spec)
    runner = P1Runner(bundle, device=device)
    try:
        analyzer = P1CandidateAnalyzer(bundle, runner, cache_dir=cache_dir, candidate_mode=candidate_mode)
        if expected_model is not None:
            require(analyzer.capabilities()["model"] == expected_model, "Requested model/profile mismatch")
        return analyzer
    except BaseException:
        runner.close()
        raise


def make_p1_candidate_loader(*, cache_dir, candidate_mode=False, device="cpu", trusted_spec=None):
    """Host callback compatible with apps.api.config.runtime_options(loader=...)."""
    def loader(bundle_path, *, registry=None, expected_model=None, acceptance=None):
        return load_p1_candidate(bundle_path, cache_dir=cache_dir, candidate_mode=candidate_mode,
                                 device=device, expected_model=expected_model, acceptance=acceptance,
                                 trusted_spec=trusted_spec)
    return loader
