"""Host-allowlisted model loading behind the frozen InstrumentAnalyzer boundary."""
from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping

from analyzers.bundle_validation import ValidatedBundle, require, validate_bundle
from analyzers.calibration_metadata import validate_calibration
from analyzers.reference_contexts import ReferenceContextStore
from core.contracts.validation import ANALYZER, PUBLIC, validate_analyzer_pair, validate_record


class BackendUnavailable(RuntimeError):
    """Adapter reports unavailable model/device/context; output must abstain."""


@dataclass(frozen=True)
class BundleAcceptance:
    """Host-owned reviewed decision; NEVER parsed from the remote manifest."""
    manifest_sha256: str
    reviewed_by: str
    intended_use: str
    accepted_families: tuple[str, ...]
    comparison_regimes: tuple[str, ...]
    operating_envelope_id: str
    calibration_id: str
    evidence_sha256: Mapping[str, str]
    minimum_bin_count: int
    minimum_probability: float
    maximum_interval_width_db: float


class BackendRegistry:
    def __init__(self, *, context_store=None):
        self.context_store = context_store or ReferenceContextStore()
        self._factories = {}
        self._exporters = {}

    def register(self, adapter_id: str, factory: Callable, *, exporter: Callable | None = None):
        require(isinstance(adapter_id, str) and adapter_id and callable(factory), "Invalid host registration")
        require(adapter_id not in self._factories, "Adapter already registered")
        require(exporter is None or callable(exporter), "Invalid exporter")
        self._factories[adapter_id] = factory
        self._exporters[adapter_id] = exporter

    def instantiate(self, bundle: ValidatedBundle):
        adapter_id = bundle.manifest["backend"]["adapter_id"]
        require(adapter_id in self._factories, "Backend adapter is not host-allowlisted")
        bundle.revalidate()  # Verify all files immediately before invoking trusted host code.
        return self._factories[adapter_id](bundle)

    def exporter(self, adapter_id):
        require(adapter_id in self._exporters and self._exporters[adapter_id] is not None,
                "Backend-specific exporter is not registered")
        return self._exporters[adapter_id]


def _acceptance(bundle, acceptance):
    if acceptance is None:
        return None
    require(isinstance(acceptance, BundleAcceptance), "Acceptance must be host-supplied reviewed data")
    a = copy.deepcopy(asdict(acceptance))
    a["accepted_families"] = list(a["accepted_families"])
    a["comparison_regimes"] = list(a["comparison_regimes"])
    m = bundle.manifest
    require(a["manifest_sha256"] == bundle.manifest_sha256, "Acceptance manifest mismatch")
    require(isinstance(a["reviewed_by"], str) and a["reviewed_by"].strip(), "Host reviewer required")
    require(a["intended_use"] in {"engineering", "competition"}, "Unknown accepted use")
    require(a["accepted_families"] and len(set(a["accepted_families"])) == len(a["accepted_families"])
            and set(a["accepted_families"]) <= set(m["candidate_families"]), "Unsupported accepted families")
    require(a["comparison_regimes"] and set(a["comparison_regimes"]) <= set(m["comparison_regimes"]),
            "Unsupported accepted comparison regime")
    require(type(a["minimum_bin_count"]) is int and a["minimum_bin_count"] > 0, "Invalid minimum bin count")
    require(type(a["minimum_probability"]) in (int, float) and math.isfinite(a["minimum_probability"])
            and 0 <= a["minimum_probability"] <= 1, "Invalid minimum probability")
    require(type(a["maximum_interval_width_db"]) in (int, float)
            and math.isfinite(a["maximum_interval_width_db"]) and a["maximum_interval_width_db"] > 0,
            "Invalid interval width policy")
    c = m["components"]
    require(c["benchmark_reports"] and c["parity_report"] and c["calibration_report"],
            "Acceptance requires evaluation, parity and calibration evidence")
    evidence_ids = c["benchmark_reports"] + [c["parity_report"], c["calibration_report"]]
    require(set(a["evidence_sha256"]) == set(evidence_ids), "Acceptance evidence references differ")
    for file_id in evidence_ids:
        require(a["evidence_sha256"][file_id] == m["files"][file_id]["sha256"],
                "Acceptance evidence hash mismatch")
    calibration = bundle.component_json("calibration_report")
    validate_calibration(calibration, model=m["model"],
                         artifact_sha256=m["files"][c["runtime_model"]]["sha256"],
                         declared_features=m["uncertainty_features"])
    require(m["dataset"]["material_class"] == "real_recorded"
            and calibration["material_class"] == "real_recorded" and not calibration["example_only"],
            "Synthetic/unknown evidence cannot enable numerical production")
    require(calibration["calibration_id"] == a["calibration_id"]
            and calibration["operating_envelope_id"] == a["operating_envelope_id"],
            "Acceptance calibration/envelope mismatch")
    require(calibration["split_groups"]["calibration"] and calibration["split_groups"]["test"],
            "Separate calibration and held-out groups required")
    for mapping in calibration["mappings"].values():
        require(any(b["count"] >= a["minimum_bin_count"] for b in mapping["bins"]),
                "Insufficient calibration support")
    from analyzers.bundle_validation import read_json
    for file_id in c["benchmark_reports"] + [c["parity_report"]]:
        result = read_json(bundle.artifact_path(file_id))
        require(result["material_class"] == "real_recorded" and result.get("example_only") is False,
                "Example evidence cannot enable production")
    parity = bundle.component_json("parity_report")
    require(parity["metrics"].get("passed") is True and parity["metrics"].get("case_count", 0) > 0,
            "No passing export parity evidence")
    require(any(
        read_json(bundle.artifact_path(file_id)).get("evaluation_split") == "test"
        and read_json(bundle.artifact_path(file_id))["metrics"].get("eligible_count", 0) > 0
        for file_id in c["benchmark_reports"]), "Held-out evaluation with denominators required")
    if a["intended_use"] == "competition":
        require(any(step["execution_site"] == "mi300"
                    and step["adaptation"] in {"partial_backbone", "full_backbone"}
                    and step["changed_pretrained_parameter_count"] > 0
                    for step in m["lineage"]), "Competition requires meaningful MI300 ancestor")
    return a


class RealAnalyzer:
    """Generic shell. Unaccepted bundles produce invalid/null evidence only.

    Backend reference matching/perception remain explicit trusted implementation
    responsibilities. This class never constructs public state/confidence/actions.
    """
    def __init__(self, bundle, backend, acceptance=None, *, context_store=None):
        self.bundle = bundle
        self._manifest = bundle.manifest
        self._backend = backend
        self._acceptance = _acceptance(bundle, acceptance)
        self._closed = False
        self._unavailable = False
        self._context_store = context_store or ReferenceContextStore()
        caps = backend.capabilities()
        require(caps.get("model") == self._manifest["model"], "Backend model identity mismatch")
        require(caps.get("example_only") is False, "Real backend cannot masquerade as Fake")
        require(caps.get("evidence_modes") == [self._manifest["evidence_mode"]], "Backend mode mismatch")
        require(set(caps.get("supported_families", [])) == set(self._manifest["candidate_families"]),
                "Backend taxonomy declaration mismatch")
        require(isinstance(caps.get("provider"), str) and caps["provider"], "Actual backend provider required")
        self._provider = caps["provider"]

    def capabilities(self):
        return {
            "provider": self._provider, "example_only": False,
            "supported_families": list(self._acceptance["accepted_families"]) if self._acceptance else [],
            "candidate_families": copy.deepcopy(self._manifest["candidate_families"]),
            "evidence_modes": [self._manifest["evidence_mode"]],
            "model": copy.deepcopy(self._manifest["model"]),
            "input": copy.deepcopy(self._manifest["input"]),
            "manifest_sha256": self.bundle.manifest_sha256,
            "numerical_evidence_accepted": self._acceptance is not None,
            "state": "closed" if self._closed else "unavailable" if self._unavailable else "loaded",
        }

    def calibration_metadata(self):
        value = self.bundle.component_json("calibration_report")
        if value is not None:
            validate_calibration(value, model=self._manifest["model"],
                                 artifact_sha256=self._manifest["files"][
                                     self._manifest["components"]["runtime_model"]]["sha256"],
                                 declared_features=self._manifest["uncertainty_features"])
        return copy.deepcopy(value)

    def acceptance_metadata(self):
        return copy.deepcopy(self._acceptance)

    def _window(self, window):
        inp = self._manifest["input"]
        require(window.sample_rate_hz == inp["sample_rate_hz"], "Backend sample rate mismatch")
        require(len(window.samples) == window.sample_end - window.sample_start
                and inp["min_window_samples"] <= len(window.samples) <= inp["max_window_samples"],
                "Window PCM span/size mismatch")
        require(all(math.isfinite(x) for x in window.samples), "Nonfinite PCM")

    def prepare_reference(self, windows, instrument_config):
        require(not self._closed, "Analyzer is closed")
        material = list(windows)
        require(material, "Reference preparation requires windows")
        for window in material:
            self._window(window)
        configured = instrument_config["instruments"]
        require(len({x["instrument_id"] for x in configured}) == len(configured) and configured,
                "Invalid instrument configuration")
        prepared = self._backend.prepare_reference(material, copy.deepcopy(instrument_config))
        asset = prepared.get("model_specific_context_asset")
        require(isinstance(asset, str) and asset, "Backend must return opaque context identity")
        result = {"model_specific_context_asset": asset, "window_count": len(material), "example_only": False}
        if self._acceptance is not None and prepared.get("coverage") is not None:
            coverage = copy.deepcopy(prepared["coverage"])
            require(isinstance(coverage, list), "Reference coverage must be a list")
            for row in coverage:
                validate_record(row, PUBLIC, "Coverage")
            by_id = {row["instrument_id"]: row for row in coverage}
            require(len(by_id) == len(coverage)
                    and set(by_id) == {x["instrument_id"] for x in configured},
                    "Reference coverage/configuration mismatch")
            # Bound declarations by the union of observed PCM, never double-count overlap.
            groups = {}
            for w in material:
                key = (w.session_id, w.analysis_run_id, w.input_asset_or_device_id, w.clock_id)
                groups.setdefault(key, []).append((w.sample_start, w.sample_end))
            total_samples, maximum_nonoverlap = 0, 0
            for spans in groups.values():
                start, end = sorted(spans)[0]
                for a, b in sorted(spans)[1:]:
                    if a > end:
                        total_samples += end - start
                        start, end = a, b
                    else:
                        end = max(end, b)
                total_samples += end - start
                previous_end = None
                for a, b in sorted(spans, key=lambda span: span[1]):
                    if previous_end is None or a >= previous_end:
                        maximum_nonoverlap += 1
                        previous_end = b
            seconds = total_samples / self._manifest["input"]["sample_rate_hz"]
            for item in configured:
                row = by_id[item["instrument_id"]]
                require(row["valid_active_seconds"] <= seconds + 1e-9
                        and row["qualified_nonoverlap_windows"] <= maximum_nonoverlap,
                        "Reference coverage exceeds observed PCM")
                if item["family"] not in self._acceptance["accepted_families"]:
                    require(row["valid_active_seconds"] == 0
                            and row["qualified_nonoverlap_windows"] == 0 and row["status"] == "insufficient",
                            "Reference coverage claims an unaccepted family")
            result["coverage"] = coverage
        self._context_store.add(self.bundle.manifest_sha256, asset, instrument_config,
                                [w.window_id for w in material])
        return result

    def _invalid(self, context, reason):
        measurements = []
        supported = set(self._manifest["candidate_families"])
        for item in context["instrument_config"]["instruments"]:
            unsupported = item["family"] not in supported
            row = dict(item, activity="unsupported" if unsupported else "unknown",
                       observability="not_observable" if unsupported else "unknown",
                       validity="invalid", reason_codes=["unsupported_source" if unsupported else reason],
                       uncertainty_features=[])
            if self._manifest["evidence_mode"] == "source_levels":
                row.update(source_level_db=None, target_source_level_db=None)
            else:
                row["source_level_delta_db"] = None
            measurements.append(row)
        return {
            "record_type": "AnalyzerEvidence", "schema_version": "1.0", "example_only": False,
            **{k: copy.deepcopy(context[k]) for k in (
                "observation", "model", "target", "comparison_regime", "model_specific_context_asset")},
            "instrument_config_version": context["instrument_config"]["instrument_config_version"],
            "matched_context_window_id": None, "evidence_mode": self._manifest["evidence_mode"],
            "units": self._manifest["units"], "measurements": measurements,
        }

    def analyze(self, window, context):
        require(not self._closed, "Analyzer is closed")
        validate_record(context, ANALYZER, "AnalyzerContext")
        self._window(window)
        require(window.identity() == context["observation"], "PCM/window identity mismatch")
        require(context["model"] == self._manifest["model"], "Analyzer model identity mismatch")
        registered, reason = self._context_store.lookup_and_bind(
            self.bundle.manifest_sha256, context["model_specific_context_asset"],
            context["instrument_config"], context["target"])
        if reason is not None:
            pass
        elif context["comparison_regime"] not in self._manifest["comparison_regimes"]:
            reason = "comparison_regime_unsupported"
        elif self._unavailable:
            reason = "backend_unavailable"
        elif self._acceptance is None:
            reason = "artifact_not_accepted"
        elif context["comparison_regime"] not in self._acceptance["comparison_regimes"]:
            reason = "comparison_regime_not_accepted"
        elif any(abs(x) >= 1 for x in window.samples):
            reason = "clipping"
        if reason:
            evidence = self._invalid(context, reason)
        else:
            try:
                evidence = self._backend.analyze(window, copy.deepcopy(context))
            except BackendUnavailable:
                self._unavailable = True
                evidence = self._invalid(context, "backend_unavailable")
            validate_analyzer_pair(context, evidence)
            require(evidence["example_only"] is False, "Backend returned simulated evidence")
            require(evidence["evidence_mode"] == self._manifest["evidence_mode"], "Backend changed evidence mode")
            if context["comparison_regime"] == "matched_excerpt":
                require(evidence["matched_context_window_id"] in registered["window_ids"]
                        or all(x["validity"] == "invalid" for x in evidence["measurements"]),
                        "Backend matched unknown context content")
            declared = self._manifest["uncertainty_features"]
            for row in evidence["measurements"]:
                for f in row["uncertainty_features"]:
                    require({"name": f["name"], "unit": f["unit"]} in declared, "Undeclared uncertainty feature")
                if row["family"] not in self._acceptance["accepted_families"]:
                    row.update(activity="unsupported", observability="not_observable", validity="invalid",
                               reason_codes=["family_not_accepted"], uncertainty_features=[])
                    for key in ("source_level_delta_db", "source_level_db", "target_source_level_db"):
                        if key in row:
                            row[key] = None
        validate_analyzer_pair(context, evidence)
        return copy.deepcopy(evidence)

    def close(self):
        if not self._closed:
            self._closed = True
            self._backend.close()


def load_bundle(bundle_path, *, registry, expected_model=None, acceptance=None):
    bundle = validate_bundle(Path(bundle_path))
    if expected_model is not None:
        require(bundle.manifest["model"] == expected_model, "Requested model identity mismatch")
    _acceptance(bundle, acceptance)  # Reject approval before running backend code.
    backend = registry.instantiate(bundle)
    try:
        bundle.revalidate()
        return RealAnalyzer(bundle, backend, acceptance, context_store=registry.context_store)
    except BaseException:
        backend.close()
        raise
