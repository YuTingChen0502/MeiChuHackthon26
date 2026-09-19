# PA shared interfaces V1

Status: frozen for the first parallel implementation checkpoint, 2026-09-19.
Owner: engineering Lead. Changes follow the escalation procedure in
`docs/implementation/IMPLEMENTATION_PLAN_V1.md`.

This companion makes technical-design sections L1/L2 concrete. It does not change
`PA_CONTRACTS_V1.schema.json`, its nine public records, product scope, or measurement
definitions. Existing authority order remains in force.

## Files and authority

- `PA_ANALYZER_V1.schema.json`: normative internal analyzer payload structure.
- `core/contracts/analyzer.py`: Python TypedDict views of that schema, Python 3.10+.
- `PA_SESSION_WIRE_V1.schema.json`: normative session command/snapshot/event structure.
- This document: normative units, binding, clock, retry and lifecycle invariants.
- `core/contracts/validation.py`: shared structural/identity validation helpers.
- `examples/pa_shared_v1.json`: illustrative fixtures, never benchmark evidence.

Schemas use Draft 2020-12. Resolve their URN `$id` references from local files,
including the original public schema; do not fetch schemas over the network.
Objects are closed. Unknown fields, NaN, infinity and mixed evidence modes are invalid.
Adding a field to a closed record requires a Lead-integrated contract revision.

## Analyzer -> Core

`AnalyzerContext` is supplied by Core to `InstrumentAnalyzer.analyze(window, context)`.
The PCM `window` must correspond exactly to `context.observation`; the JSON contract
contains metadata, not samples. Both input adapters feed this same boundary.
At this boundary, the window contains a contiguous mono float PCM span at the
declared sample rate and amplitude scale, with exactly `sample_end - sample_start`
samples. Any model-specific resampling is deterministic and preserves the observation
identity and original-scale level convention; samples must not carry semantic labels.
Reference preparation remains the L1 `prepare_reference` operation; these contracts
describe subsequent comparison calls, not reference ingestion or tensor storage.

`AnalyzerEvidence` echoes the observation, model identity, configuration version,
target, comparison regime and context asset from the request. A mismatched response
is rejected, not attached to whichever song/profile is currently active.

### Instrument values and masks

Return exactly one measurement per configured instrument ID, including inactive or
unsupported families. IDs identify configured families/groups, not inferred physical
mixer channels. Families must match the configuration. Array order is not meaningful.

- `activity`: active, inactive, unknown or unsupported.
- `observability`: observable, not_observable or unknown. Configured is not observable.
- `validity`: whether this numerical source measurement is usable, not whether a PA
  action is justified. Valid requires active + observable and finite numeric values.
- Invalid measurements require reason codes and null numeric values. A numerical
  floor must not turn silence into a large negative deviation.

Exactly one representation applies to the entire response:

| Mode | Fields per source | Normative interpretation |
|---|---|---|
| `source_levels` | `source_level_db`, `target_source_level_db` | Estimated observed and comparable target `20*log10(RMS(source))`, referenced to PCM amplitude 1.0 (`dBFS_rms`). Core subtracts target from observation once. |
| `source_level_deltas` | `source_level_delta_db` | Already conditioned `L_observation - L_target` in dB. Core must not subtract a target again. |

`target_source_level_db` exposes a cached compatible target level so Core need not
parse an analyzer-specific context asset. It is not a second authoritative mode.
The analyzer restores common input scaling and does not independently normalize
stems or pair members. `level_scale_id` identifies the versioned amplitude/normalization
convention. Both levels in a pair must use that convention; it is not an SPL unit.

Both modes provide **source** deltas before common-mode removal. Core computes
common mode and centered balance according to design H. A direct backend predicting
only centered balance cannot mislabel that result as a source delta; its adapter
must supply the defined quantity or return invalid evidence. Observed mix level is
measured by the shared raw-audio branch, not fabricated from source estimates.

### Targets, versions and comparison

- Reference target: immutable `reference_id` + `source_asset_hash`, with null baseline.
- Baseline target: that reference binding plus exact `baseline_id` + `baseline_version`.
- Existing ReferenceProfile has no numeric version. Its immutable ID/content hash,
  model/frontend/taxonomy and context asset identify the analyzed revision. Reanalysis
  replaces its identity; no `reference_version` is added to the public record.
- `model_specific_context_asset` is an opaque local asset identifier resolved by the
  responsible adapter/store, never a user-supplied arbitrary filesystem path.
- `matched_excerpt` requires `matched_context_window_id` for valid measurements.
  Matching must use audio content, never demo-player labels. For pooled
  `stable_texture`, this field may be null. `unvalidated` yields invalid measurements.
- Matching chooses comparable evidence; it never changes the fixed accepted target
  into a section-dependent target schedule.

`model_bundle_id`, `frontend_id`, `taxonomy_id`, `execution_profile_id` and
`level_scale_id` identify the exact evidence convention. Execution profile includes
precision/runtime configuration. Compatibility and calibrated confidence remain Core
responsibilities. Returning numerically valid evidence does not bypass those gates.

`uncertainty_features` is a list of unique named finite values with explicit units.
Names/units/interpretation are versioned by model bundle; examples include raw error
scale or attribution margin. They are **not** calibrated probabilities, public
ConfidenceState, InstrumentState, recommendations or actions. An empty list is
allowed when the backend cannot provide such evidence; Core cannot infer confidence
from the absence of uncertainty. `example_only=true` must propagate to public frames
for FakeInstrumentAnalyzer and illustrative fixtures.

`observation_purpose` is rehearsal, guided_probe, verification or live. A guided
probe also names one configured `probe_instrument_id`; other purposes use null.
This is PA-requested calibration context, never a ground-truth activity label. The
analyzer must still establish activity from audio. Probes use the same pipeline and
may have too few active sources for common-mode attribution. Live requires a baseline
target; rehearsal verification may still use a reference target.

### Sample and time convention

Sample spans are half-open `[sample_start, sample_end)` at `sample_rate_hz` in one
analysis run. No window straddles a gap or rate/clock change. The timestamp of the
sample-end boundary is `capture_end_monotonic_s`; window start time is that timestamp
minus `(sample_end - sample_start) / sample_rate_hz`. All values are finite.

The application owns the monotonic clock identified by `clock_id`; a restart creates
a new session/clock. File replay maps sample positions onto this same session clock
using a recorded run origin. Offline rechecks use newly selected/replayed observations
after the command boundary, never old evidence relabeled as fresh. Original capture
provenance is separate from replay timing. Clock changes reset persistence and require
fresh evidence. Client wall-clock timestamps are not accepted as adjustment cutoffs.

## UI -> Application

### Snapshot and event stream

`GET /v1/sessions/{id}` returns a `SessionSnapshot` directly. It includes the existing
SongState (`song.workflow_state`), orthogonal `session_mode` and `incident_state`,
source/clock, actual execution provider, complete active reference/baseline profiles,
current incident/version/target, adjustment, latest frame, recommendations and latest
verification. Null means unavailable, not zero/normal. Arrays of recommendations may
be empty. The snapshot carries current session state, not the entire audit history.
`session_mode` persists through adjustment, suspension and verification. Rehearsal
workflow states remain rehearsal; LIVE_MONITORING, LIVE_ANOMALY and VERIFY_RECOVERY
are live. `incident_state` describes the current incident/adjustment phase: none,
active, adjusting, verifying, resolved, inconclusive or dismissed. A proactive
rehearsal adjustment may be adjusting/verifying with a null incident. An inconclusive
verification remains unresolved; only verified recovery yields resolved.
After changing the active comparison target, clear completed/dismissed incident,
adjustment, recommendation, verification and old-frame pointers atomically; preserve
their immutable historical bindings in the audit store. Do not change target while
an incident/adjustment is unresolved.

`state_version` starts at zero and increases on every accepted state-changing command
and every autonomous workflow/incident/compatibility change relevant to command
validity. Ordinary frame publication does not by itself increment state_version.
The first checkpoint uses one current incident and one adjustment at a time.
`event_version` starts at one and increases when that public AnomalyEvent changes.
Baseline and reference revisions remain immutable.

`event_sequence` is session-wide: zero before publication, then strictly increasing
by one per emitted `SessionEvent`, across all payload types. It is distinct from
`AnalysisFrame.sequence`, which is scoped to an analysis run. State-transition events
carry the complete SessionSnapshot; its version/sequence equal the envelope values.
An event referencing a new or revised incident/profile binding is published only
after a snapshot transition establishes that binding, including the event_version.

On reconnect, obtain an atomic snapshot with sequence N, then subscribe with
`after_sequence=N` on `WS /v1/sessions/{id}/events`. The server must replay buffered
events after N, or deliver a fresh snapshot event if retention cannot cover the gap.
It must not silently skip the gap. The client discards duplicates at or below its
cursor, requests a fresh snapshot on an unexplained gap, and never reconstructs
baseline state from a previously displayed card. Snapshots and event publication
share the same serialization boundary.

### Command envelope and responses

`SessionCommand` always includes session ID, idempotency key, expected state version,
current reference binding, current active baseline binding (nullable), and current
incident binding (nullable). Baseline binding is required even during rehearsal when
a prior accepted baseline exists. These bindings guard the state the human saw; the
incident's separate comparison target may still be the ideal reference.

| Action | Endpoint | Payload |
|---|---|---|
| `accept_baseline` | POST `/v1/sessions/{id}/baseline` | Selected run/clock/sample interval, accepted_by, explicit reference-difference choice and nullable note |
| `start_adjustment` | POST `/v1/sessions/{id}/actions` | Empty object; response snapshot supplies authoritative adjustment ID/start time |
| `complete_adjustment` | same | Exact adjustment_id; response snapshot supplies completion and verification cutoff |
| `recheck` | same | Adjustment ID, or null for a fresh rehearsal recheck without an adjustment |
| `dismiss`, `pause`, `resume`, `stop`, `start_live` | same | Empty object |

The URL session ID must equal the command body. `start_live` concretizes the design's
explicit Live request; acceptance alone never enters Live. Session creation/upload
and reference-job APIs remain the existing L2 surface and may be implemented by the
Runtime owner before UI integrates those setup endpoints; no alternate product flow
is introduced by this session contract.

`CommandResponse` carries the idempotency key, session ID, outcome and HTTP status.
Success is HTTP 200 with the resulting authoritative snapshot and null error.
Failure is HTTP 409 (stale binding/version, invalid state or idempotency conflict),
422 (invalid payload/interval), or 503 (unavailable runtime/device), with structured
error code/message/retryability and a current snapshot when available. The HTTP
status must equal `http_status`. Transport-level malformed requests lacking a usable
envelope can use the API framework's 422 response; never invent an idempotency key.

For each `(session_id, idempotency_key)`, store canonical parsed command content and
the final response atomically with the mutation. Check this ledger **before** stale
version validation. An identical retry returns the original response with no second
mutation/event/version increment. Reusing the key with different content returns 409.
Rejected valid envelopes are also recorded; a revised/retried attempt after resolving
a failure uses a new key. Retain the ledger for the stored session, including restart
recovery of completed commands. In-flight duplicate requests serialize against it.

Acceptance is an explicit human action, rehearsal-only, and validates selected audio
coverage, quality, provenance, comparison support and model compatibility before an
atomic immutable baseline save. The selected interval cannot span runs/clocks/gaps.
An aesthetic reference difference can be accepted; corrupt/missing audio cannot.
Successful acceptance returns the new baseline in the snapshot, leaves session mode
rehearsal, and never rewrites an incident's stored evidence. Replacement acceptance
must wait until any active adjustment/incident is resolved or dismissed.

Adjustment records bind the incident/version at adjustment start (nullable for proactive rehearsal adjustments),
comparison target and server clock. Completion timestamp is server-owned;
the incident may subsequently advance its event_version without rewriting that
original adjustment binding. Commands always bind the current incident version.
`verification_not_before_monotonic_s = completed_monotonic_s + settling_policy_s`.
Completion and cutoff are both null while adjustment is in progress. A positive
verification uses fully post-cutoff windows, unchanged target/version and an observable
source. Recheck with no adjustment starts fresh rehearsal comparison and need not
invent an AnomalyEvent or VerificationResult. An incident-bound recheck retains the
same adjustment/target. Inactive/noisy/stale audio is inconclusive, not recovery.

Pause suppresses corrective recommendations, exposes SUSPENDED and a reason, and
resets persistence. Resume revalidates input/profile and requires fresh evidence.
Stop releases capture; STOPPED is terminal for this session. Dismissal does not accept
or rewrite a baseline. An unresolved incident never becomes recovered by pause,
timeout, disconnect or dismissal. Runtime owns these lifecycle operations; the
shared validation helpers only reject structural/binding violations.

## Validation and remaining implementation gates

Run from the repository root with a Python environment containing the test dependency:

```text
python -m pip install -r core/contracts/requirements-test.txt
python -m unittest discover -s core/contracts/tests -v
```

Contract tests enforce schema validity, typed/schema agreement, evidence exclusivity,
null masks, identity/version binding, clock/span order, command payloads and representative
snapshot/response/event shapes. Runtime's first checkpoint must additionally test
actual transactional retry behavior, command-state authorization, audio quality gates,
immutable storage, reconnect races and post-adjustment verification. No mock contract
test is evidence that those lane-owned behaviors already work.
