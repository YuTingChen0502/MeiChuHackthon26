"""Typed views of PA_ANALYZER_V1.schema.json (the structural authority).

These are JSON-compatible evidence records, not canonical instrument states.
Use validation.validate_analyzer_pair at adapter boundaries in contract tests.
"""

from typing import Literal, TypedDict


class ReferenceBinding(TypedDict):
    reference_id: str
    source_asset_hash: str


class BaselineBinding(TypedDict):
    baseline_id: str
    baseline_version: int


class ReferenceTarget(TypedDict):
    target_kind: Literal["reference"]
    reference: ReferenceBinding
    baseline: None


class BaselineTarget(TypedDict):
    target_kind: Literal["baseline"]
    reference: ReferenceBinding
    baseline: BaselineBinding


ComparisonTarget = ReferenceTarget | BaselineTarget
ComparisonRegime = Literal["matched_excerpt", "stable_texture", "unvalidated"]


class ModelIdentity(TypedDict):
    model_bundle_id: str
    frontend_id: str
    taxonomy_id: str
    execution_profile_id: str
    level_scale_id: str


class WindowIdentity(TypedDict):
    window_id: str
    session_id: str
    analysis_run_id: str
    input_kind: Literal["uploaded_file", "live_microphone"]
    input_asset_or_device_id: str
    clock_id: str
    sample_rate_hz: int
    sample_start: int
    sample_end: int
    capture_end_monotonic_s: float


class ConfiguredInstrument(TypedDict):
    instrument_id: str
    family: str


class InstrumentConfig(TypedDict):
    instrument_config_version: int
    instruments: list[ConfiguredInstrument]


class UncertaintyFeature(TypedDict):
    name: str
    value: float
    unit: str


class _Measurement(TypedDict):
    instrument_id: str
    family: str
    activity: Literal["active", "inactive", "unknown", "unsupported"]
    observability: Literal["observable", "not_observable", "unknown"]
    validity: Literal["valid", "invalid"]
    reason_codes: list[str]
    uncertainty_features: list[UncertaintyFeature]


class SourceLevelMeasurement(_Measurement):
    source_level_db: float | None
    target_source_level_db: float | None


class SourceDeltaMeasurement(_Measurement):
    source_level_delta_db: float | None


class AnalyzerContext(TypedDict):
    record_type: Literal["AnalyzerContext"]
    schema_version: Literal["1.0"]
    observation: WindowIdentity
    model: ModelIdentity
    instrument_config: InstrumentConfig
    target: ComparisonTarget
    comparison_regime: ComparisonRegime
    model_specific_context_asset: str
    observation_purpose: Literal["rehearsal", "guided_probe", "verification", "live"]
    probe_instrument_id: str | None


class _Evidence(TypedDict):
    record_type: Literal["AnalyzerEvidence"]
    schema_version: Literal["1.0"]
    example_only: bool
    observation: WindowIdentity
    model: ModelIdentity
    instrument_config_version: int
    target: ComparisonTarget
    comparison_regime: ComparisonRegime
    model_specific_context_asset: str
    matched_context_window_id: str | None


class SourceLevelsEvidence(_Evidence):
    evidence_mode: Literal["source_levels"]
    units: Literal["dBFS_rms"]
    measurements: list[SourceLevelMeasurement]


class SourceLevelDeltasEvidence(_Evidence):
    evidence_mode: Literal["source_level_deltas"]
    units: Literal["dB"]
    measurements: list[SourceDeltaMeasurement]


AnalyzerEvidence = SourceLevelsEvidence | SourceLevelDeltasEvidence
