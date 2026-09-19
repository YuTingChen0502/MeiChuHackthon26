# CP2 model-independent integration

Status: IMPLEMENTED / TESTED integration infrastructure. No fitted model, selected backend,
calibrated confidence, supported instrument claim or real-audio feasibility result is supplied here.
The internal bundle format below does not change public/shared contracts.

## Remote bundle contract: version 1.0

A bundle is a directory (or ZIP for full intake) with `manifest.json` at its root.
Files are relative to that root. Remote producers supply actual identities/hashes; never substitute
this document's placeholders for provenance. Metadata-only delivery may omit binary bytes.
No remote file is imported as executable Python.

Required top-level manifest fields (unknown fields rejected):

| Field | Exact content |
| --- | --- |
| schema_version | `"1.0"` |
| bundle_id | Unique immutable bundle identity |
| backend | `{adapter_id, kind}`; kind is separation, direct or hybrid |
| model | `{model_bundle_id, frontend_id, taxonomy_id, execution_profile_id, level_scale_id}`; model_bundle_id equals bundle_id |
| evidence_mode / units | source_levels / dBFS_rms OR source_level_deltas / dB |
| candidate_families | Unique taxonomy family strings declared by adapter; these are NOT accepted support claims |
| input | `{sample_rate_hz, channels:1, min_window_samples, max_window_samples}`, positive integers |
| comparison_regimes | Nonempty subset of matched_excerpt, stable_texture |
| uncertainty_features | Unique `{name, unit}` declarations; raw features, not calibrated confidence |
| origin | `{git_sha, config_sha256, environment_sha256, execution_site, run_id, seed}` |
| lineage | Ordered adaptation entries described below |
| files | Mapping file ID to `{path, sha256, kind: "binary" or "json"}` |
| components | Exact component references below |
| dataset | `{manifest_sha256, provenance, split_groups, material_class}` |

Git SHAs are full lowercase 40-character hashes; all file/config/dataset hashes are lowercase
64-character SHA-256. execution_site is nano4, mi300 or local. seed is an integer.
material_class is real_recorded, synthetic or unknown.
split_groups is exactly `{train:[], validation:[], calibration:[], test:[]}`, with globally disjoint
parent-group identities. provenance identifies the reviewed dataset/rights record; it is a supplied
assertion requiring review, not a license granted by this tooling. The dataset manifest hash plus
the exact grouped lists identify the split without adding another opaque split label.

Required component keys:

- checkpoint: file ID of inference checkpoint (no optimizer state).
- runtime_model: file ID of runtime artifact; may equal checkpoint until export.
- frontend: JSON file with frontend_id; include actual preprocessing/configuration details.
- taxonomy: JSON file with taxonomy_id and families.
- level_scale: JSON file with level_scale_id, quantity=`source_level_before_common_mode_removal`,
  source_level_units=`dBFS_rms`, delta_units=`dB`, amplitude_policy=`preserve_common_scale`.
- training_config: exact JSON used for the originating run, bound to origin.config_sha256.
- environment: JSON with execution_site, environment_id, python, framework, runtime;
  include real device/library/Slurm account/partition/resource details where applicable.
- training_report: JSON with origin identical to manifest.origin and checkpoint_sha256.
- benchmark_reports: list of BenchmarkResult JSON file IDs; may be empty at unaccepted intake.
- parity_report: ExportParityReport JSON file ID or null.
- calibration_report: CalibrationCandidate JSON file ID or null.

Every file must be referenced by a component or lineage entry. No arbitrary datasets, raw audio,
source files, caches or optimizer-state sidecars are copied. JSON file names must end in .json.
Hashes establish byte identity, not the truth of scientific/provenance assertions. Review the
checkpoint format and use the selected backend's safe non-executable weight loader.

Each lineage entry has exactly:
`checkpoint_sha256, parent_checkpoint_sha256, git_sha, config_sha256, environment_sha256,
execution_site, run_id, seed, adaptation, changed_pretrained_parameter_count, optimizer_steps, evidence`.
Adaptation is head_only, partial_backbone or full_backbone. Counts are nonnegative changed
pretrained parameters and positive optimizer steps. evidence names a hashed JSON file containing
`lineage_step` equal to that entry without evidence. The ordered parent hashes form a continuous
chain ending at the supplied checkpoint; the last entry's origin equals manifest.origin.
Remote proof must actually substantiate these assertions. Meaningful MI300 ancestry is required
for competition acceptance; a Nano4-first artifact may be reviewed for engineering use.

Large binaries can remain at the remote location, with their intended relative path and hash
recorded in files. Preserve the remote transfer location in the training report. Metadata-only
import explicitly leaves those bytes UNVERIFIED and cannot instantiate a model.

## Intake commands

Run from the repository using its normal Python environment:

```text
python -m benchmarks.import_remote_evidence REMOTE_METADATA_DIR --evidence-root benchmarks/results/imported --manifest-sha256 EXACT_SHA256
python -m benchmarks.import_bundle BUNDLE_DIR_OR_ZIP --store EXTERNAL_MODEL_STORE --manifest-sha256 EXACT_SHA256
```

The first command copies manifest and referenced JSON only; binary_bytes_copied is always zero.
The second verifies all bytes and publishes an immutable content-addressed directory.
Both revalidate staged content before publication, refuse unsafe paths/links/duplicates, reject
hash drift, and never edit source. Full intake defaults to an 8 GiB transfer limit; use its explicit
--max-bytes option for a reviewed larger artifact. JSON documents are capped at 32 MiB, manifests
at 2 MiB. Keep bulky prediction traces separately hashed; use compact evidence summaries for intake.
Repository evidence import rejects recognized credential keys, private-key/Bearer material and signed
or authenticated URLs without printing values. It never silently changes hashed bytes; producers must
redact and rehash a new bundle. This narrow disclosure check is not an exhaustive secret detector.
No automatic download, deserialization, remote command, Git source update or model registration occurs.

## Host registration and production lifecycle

```python
from analyzers.bundles import BackendRegistry, BundleAcceptance, load_bundle
from analyzers.reference_contexts import ReferenceContextStore

registry = BackendRegistry(context_store=ReferenceContextStore(host_cache_directory))
registry.register(adapter_id, trusted_factory, exporter=trusted_export_callback)
analyzer = load_bundle(bundle_directory, registry=registry,
                       expected_model=expected_five_id_model,
                       acceptance=reviewed_host_acceptance_or_none)
prepared = analyzer.prepare_reference(retained_audio_windows, instrument_config)
# Put prepared["model_specific_context_asset"] in the frozen AnalyzerContext.
evidence = analyzer.analyze(audio_window, analyzer_context)
analyzer.close()
```

The host supplies a BackendRegistry object, not a mapping. Each factory receives a ValidatedBundle
and uses artifact_path(file_id) to access verified bytes. Its capabilities must match the bundle's
five identities, candidate families and evidence mode, with actual provider and example_only=False.
The backend implements the existing InstrumentAnalyzer methods. It must validate its execution
profile/platform and fail explicitly on incompatible devices, formats or unavailable dependencies.
BackendUnavailable during analysis becomes invalid/null evidence; other programming/contract
errors propagate for Runtime's error boundary. Constructor failures do not produce a Fake fallback.

The shell validates reference/window/context identities and returned AnalyzerEvidence, bounds input
sample rate/span, rejects undeclared uncertainty features, and checks matched reference window IDs.
prepare_reference returns opaque model_specific_context_asset plus window_count and example_only.
The shell generates no coverage. Optional backend-supplied coverage is forwarded only with host
acceptance, validated against existing Coverage fields, configured IDs, accepted families and the
union/nonoverlap bounds of actual reference PCM. Missing coverage stays absent.
Backend matching and durable reference features remain backend
responsibilities. The generic store persists only hash-bound context/config/window identities, not PCM.
Use the same host-owned store and backend feature cache across reloads. Missing, mismatched, expired
or concurrently locked contexts fail closed. A context is bound to its target on first use and cannot
be silently rebound. Baseline preparation uses actual retained human-accepted PCM through this same method.

No acceptance means capabilities.supported_families=[] and invalid/null analysis. Candidate families
remain separately identifiable. RealAnalyzer owns neither canonical state nor confidence publication.

Reviewed acceptance must be a host-created BundleAcceptance with these fields:
`manifest_sha256, reviewed_by, intended_use, accepted_families, comparison_regimes,
operating_envelope_id, calibration_id, evidence_sha256, minimum_bin_count, minimum_probability,
maximum_interval_width_db`. intended_use is engineering or competition; evidence_sha256 is the exact
mapping of benchmark/parity/calibration file IDs to hashes. Never instantiate this from remote approval
claims. Runtime owns capture/quality envelopes and applying the reviewed probability/interval gates.
calibration_metadata() and acceptance_metadata() return separate copied dictionaries.
The source/config/evidence identity must be frozen again after any model/profile/export/calibration change.

## Evaluation, calibration, comparison and export

Host startup invokes `benchmarks.evaluate_artifact.main(argv, registry=registry)` or its evaluate()
function. The module CLI intentionally has an empty registry; no arbitrary module-import flag exists.
Arguments: --bundle, --cases, --provenance, --thresholds, --output.

Cases are a JSON list with case_id, split (validation/calibration/test), parent_group_id,
reference_windows (AudioWindow dictionaries including samples), observation (AudioWindow),
instrument_config, target, comparison_regime, and labels keyed by instrument_id.
Labels have raw_source_delta_db, balance_deviation_db (nullable if ineligible) and
attribution_evaluable. Ground truth never enters the backend call. All cases in a report use one split.
Do not commit case PCM or restricted audio; metadata output contains only identities/hashes.

Provenance requires git_sha, config_sha256, dataset_manifest_sha256, split_groups, material_class,
example_only, seed, gain_intervention, noise_type, snr_db (null for clean),
augmentation, label_procedure, environment. Thresholds require alert_db and
missing_prediction_penalty_db, finite and positive. Record actual environments and interventions.
Outputs contain raw evidence, PCM hashes, denominators, coverage/abstention/sign/attribution/dB
diagnostics and measured latency. Centering follows the existing median rule with at least three
valid sources. These are paired diagnostics, not independent live event guarantees.

```text
python -m benchmarks.compare_artifacts REPORT_A REPORT_B --output comparison.json
python -m training.prepare_calibration_rows --report REPORT --labels EVENT_LABELS --settings SETTINGS --output rows.json
python -m training.calibration fit --rows CALIBRATION_ROWS --config FIT_CONFIG --output candidate.json
python -m training.calibration evaluate --rows TEST_ROWS --candidate candidate.json --output heldout-calibration.json
python -m benchmarks.export_parity compare --reference EAGER_REPORT --candidate EXPORTED_REPORT --atol-db REVIEWED_TOLERANCE --rtol REVIEWED_TOLERANCE --output parity.json
```

Comparison requires identical populations, PCM, labels, protocols and semantics and emits NOT_SELECTED.
prepare_calibration_rows requires settings {operating_envelope_id, label_procedure, score_features},
where score_features maps event name to {name,unit}. Event labels cover every measured
pair/instrument/event exactly once: pair_id, instrument_id, probability_event, eligible,
attribution_correct, target_within_normal_envelope. No event truths are inferred or fabricated.
Unavailable scores/predictions remain null for abstention.

Calibration rows contain schema_version=1.0, record_type=CalibrationRows, model, runtime_artifact_sha256,
git_sha, dataset_manifest_sha256, split_groups, material_class, example_only, operating_envelope_id,
label_procedure, score_features and rows. Each row has sample_id, split, parent_group_id,
probability_event, eligible, attribution_correct, target_within_normal_envelope,
target_balance_db, predicted_balance_db and score.

Fit config has magnitude_tolerance_db=2.0, interval_mass in (0,1),
mappings={event:{score_feature:{name,unit}, score_edges:[finite increasing edges]}}.
Edges and interval mass are supplied by the experiment, not invented defaults.
Fit uses calibration groups only; evaluation uses test groups only.
Supported events: joint_anomaly_numeric_correct and normal_within_envelope, independently.
Empty bins/events remain unsupported. Outputs are unaccepted empirical frequency/residual-quantile
candidates, not distribution-free coverage guarantees. Candidate mappings use
left_closed_right_open_last_closed bins and true_balance_minus_predicted_balance intervals.
Runtime requires explicit reviewed support, probability, interval-width and envelope policy.

All evidence records include record_type, schema_version=1.0, five-ID model, runtime_artifact_sha256,
git_sha, config_sha256, dataset_manifest_sha256, split_groups, material_class, example_only,
status (diagnostic/candidate/evaluated only), metrics with relevant denominators.
CalibrationCandidate additionally has calibration_id, operating_envelope_id, evidence_hashes,
and mappings. Each mapping has magnitude_tolerance_db, score_feature, endpoint_policy,
interval_semantics and bins. Each bin has lower, upper, count, success_count, probability,
residual_interval_db. No unsupported score/event is extrapolated.

Export uses `benchmarks.export_parity.main(argv, registry=registry)` with operation export,
--bundle and --destination. The host exporter receives (backend, staging_directory), returns
the absolute selected runtime-model path within staging, and owns framework-specific serialization.
Only that file plus an unverified receipt is published; incidental caches are discarded.
Parity compares matched measured eager/export outputs and uncertainty/mask semantics;
no numerical comparison means no passing parity. Changed exports require a new manifest/profile
binding and artifact-bound evaluation/calibration before production.

## Remaining trained-artifact work

1. Implement the selected backend's actual model loading, frontend execution, numerical perception,
   reference feature persistence/matching and framework exporter behind the registered callbacks.
2. Run measured held-out evaluation/export parity on real authorized inputs and intended hardware.
3. Fit and evaluate calibration, establish the actual accepted envelope/families/coverage.
4. Review and freeze the complete model/evidence bundle and host acceptance; publish AnalyzerEvidence
   through the existing Runtime gate.

No additional public/shared contract design is needed for those steps. CPU/CUDA/ROCm specifics stay
inside trusted backend implementations; the generic code introduces no CUDA-only dependency.
