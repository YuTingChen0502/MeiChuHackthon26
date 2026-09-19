# Internal trained-artifact seam for MVP_PRE_MODEL_READY

Lead-approved coordination record. This does not alter any frozen schema in
`contracts/` or `core/contracts/`. ML owns concrete serialization/validation under
`analyzers/`, `models/`, `training/` and `benchmarks/`; Runtime owns downstream policy.
Those tested implementations and their templates provide the exact CLI examples.

`analyzers.bundles.load_bundle(bundle_path, *, registry, expected_model=None,
acceptance=None)` returns the existing InstrumentAnalyzer surface: capabilities,
prepare_reference, analyze and close. The host supplies an allowlisted adapter
registry; a manifest never chooses an executable import. Backend-specific tensor
conversion/context matching stays behind this adapter. Missing/invalid bundles fail
closed; no implicit Fake substitution. Unaccepted candidates emit invalid/null
diagnostic evidence, not actionable confidence.

Bundle intake binds source Nano4/MI300 execution, originating repository SHA, config,
dataset/split provenance, checkpoint/runtime SHA-256, frontend/taxonomy/level-scale/
execution identity, supported families, sample/window requirements and evidence.
All imported paths must stay inside the supplied bundle/cache. Partial, modified or
incompatible content is rejected. Remote machines execute origin commits, not edits.

`calibration_metadata()` returns a separately validated CalibrationCandidate or None.
Keys: schema_version, record_type, calibration_id, model (five frozen IDs),
runtime_artifact_sha256, git_sha, config_sha256, dataset_manifest_sha256,
split_groups (train/validation/calibration/test), material_class, example_only,
status=candidate, evidence_hashes, metrics and mappings. Mappings use existing events
joint_anomaly_numeric_correct and separately fitted normal_within_envelope. Missing
event support is abstention, not inferred normality.

Each mapping has magnitude_tolerance_db=2.0, score_feature{name,unit}, endpoint_policy
left_closed_right_open_last_closed, interval_semantics=true_balance_minus_predicted_balance,
and finite nonoverlapping bins of lower/upper/count/success_count/probability/
residual_interval_db. Gaps, insufficient sample counts, unknown units or unsupported
regimes abstain. Core translates residual bounds around the current balance estimate;
the analyzer never publishes InstrumentState, ConfidenceState or PA actions.

Host-reviewed `acceptance_metadata()` binds manifest_sha256, reviewed_by,
intended_use (engineering/competition), accepted_families, comparison_regimes,
operating_envelope_id, calibration_id, evidence_sha256, minimum_bin_count,
minimum_probability and maximum_interval_width_db. Host capture/provider/quality and
baseline-envelope policy is additional Runtime-owned context. An imported bundle
cannot self-approve. Synthetic candidates never enable numerical production behavior.
Later empirical acceptance supplies values; no current fixture is fitted evidence.

Reference and accepted baseline context reuse prepare_reference over legitimate PCM
windows. Opaque context assets must be compatible and durable across analyzer instances
in the declared local cache, or explicitly rejected as unavailable. Runtime bounds
retained PCM and refuses expired baseline intervals; it never fabricates a model
context or silently accepts a baseline. Changed bundle/profile requires revalidation.

Either Nano4 or MI300 may supply the first engineering candidate. Competition
acceptance additionally requires auditable meaningful MI300 adaptation lineage for
the actual runtime artifact. Replacing the bundle must not change UI/workflow.
