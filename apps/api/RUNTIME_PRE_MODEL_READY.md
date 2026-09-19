# Runtime pre-model deployment and validation

This lane supplies capture, shared preprocessing/framing, bounded continuous
workers, PA workflow, persistence, transport and a host-approved model boundary.
Model accuracy, empirical calibration and hardware-provider parity are separate
evidence gates. Fake results remain explicitly example-only.

## Launch

Use the pinned root `requirements-runtime.txt` in an isolated Python environment.
The default transport launcher requires a production bundle; missing/failed loads
produce existing HTTP 503 SetupError `model_unavailable`, never a Fake fallback.

```powershell
python -m apps.api.launch --storage C:/PA/runtime --mode fake
python -m apps.api.launch --storage C:/PA/runtime --mode bundle --bundle C:/PA/models/approved-bundle --host-review C:/PA/reviews/approved.json --adapter approved-id=approved_host_module:create_backend
python -m apps.api.inventory
```

The launcher defaults allowed browser origins to `http://127.0.0.1:<port>` and
`http://localhost:<port>` for its selected `--port` (8000 by default). An explicit
`PA_ALLOWED_ORIGINS` configuration is preserved; it must include the UI origin
if that origin should submit requests. Other origins remain rejected.

Adapter imports above are explicit trusted host CLI choices. Bundle manifests
cannot import executable modules. Applications may instead inject
`create_app(bundle_registry=BackendRegistry(...))`, or a RuntimeAPI analyzer
factory implementing the frozen capabilities/prepare_reference/analyze/close
interface. Direct RuntimeAPI defaults retain the CP1 deterministic Fake seam;
production launcher defaults never do. Use one process on loopback.

Suggested local layout: `models/<immutable-manifest-hash>/` for validated bundle
files, `reviews/` for separately reviewed host settings, `runtime/` for SQLite,
and `runtime/context-cache/` for durable model reference contexts. Set
`PA_MODEL_CONTEXT_CACHE` to relocate the latter. No download, accelerator choice,
CPU fallback or model replacement is inferred. A CPU adapter is selectable only
with its compatible reviewed execution profile. Replacement requires restart,
a new session, and compatible/reanalyzed reference and baseline profiles.

## Host review and calibration

The ML loader uses BackendRegistry, BundleAcceptance, and ReferenceContextStore.
Runtime constructs these concrete types from host choices; it does not treat a
manifest as approval. The reviewed host JSON contains:

- `acceptance`: exactly the Lead/ML BundleAcceptance fields (manifest/evidence
  hashes, reviewer, engineering/competition use, accepted families/regimes,
  operating envelope, calibration ID and support/probability/interval limits).
- `model`: all five frozen model identity fields; `runtime_artifact_sha256`;
  `calibration_sha256`: SHA256 of candidate JSON serialized with sorted keys,
  compact separators, Python JSON default ASCII encoding and no NaN.
- `providers`: exact allowed capability providers; `supported_scores`: explicit
  `[name, unit]` pairs supported by the fitted mappings.
- `quality_envelope`: `sample_rates_hz`, `minimum_window_samples`,
  `maximum_window_samples`; hard clipping/dropout/stale/comparability/capture gates
  remain mandatory regardless of these settings. Optional `minimum_snr_db` requires
  an available estimate (unknown abstains); `uncertainty_feature_bounds` contains
  `{name, unit, minimum, maximum}` limits on model-produced uncertainty features.
- `normal_envelopes_by_family`: reviewed `center_db`, `lower_db`, `upper_db` values.
- `capture_profiles`: records with `model`, `source_kind`, `reviewed_by`,
  `operating_envelope_id`, and a complete existing CaptureFingerprint. The Runtime
  matches the observed device/rate/channels to exactly one reviewed profile;
  physical gain/geometry/provenance come from host review, never browser claims.

These are descriptions, not an accepted calibration template. Supply empirical
values only after review. Synthetic/unknown candidates cannot pass production
approval. Missing normal mapping abstains on normal observations; missing anomaly
mapping abstains on anomalous observations. Both fitted events are supported.
The endpoint policy is `left_closed_right_open_last_closed`; intervals describe
true balance minus predicted balance. No candidate-derived ConfidenceState is
published directly by an analyzer.

Reference coverage stays insufficient unless a reviewed analyzer supplies
validated per-source coverage. A real human-accepted baseline prepares its opaque
context from retained exact interval PCM using existing prepare_reference. Context
IDs must be durable across instances in the bundle cache. Missing/expired PCM or
context fails closed; there are no fabricated real baseline IDs/envelopes.
Rehearsal PCM retention is limited to 1,000,000 samples, never persisted, and is
cleared at close. Choose a recent complete interval; restart requires a new session.

## Native and shared stream behavior

Device identity uses an unambiguous PortAudio host/name pair, independent of
enumeration index. Identical ambiguous pairs are withheld. This is not a hardware
serial number or proof of microphone geometry/AGC state. Native selection is
resolved again on open. Format negotiation tries requested/default rate and mono
then stereo; callback only copies a bounded float32 packet and enqueues it.
Downmix and shared 32-tap deterministic sinc rate conversion happen off callback.
There is no gain normalization or instrument analysis in input adapters.

File and microphone inputs use the same frontend, overlapping window planner,
quality, analyzer, deviation/confidence, PA policy and verification. Canonical rate
and native capture rate are recorded separately internally. FIR lookahead is 16
input samples; incomplete resampling tails are discarded, never invented after
EOF/disconnect. Input clipping is conservatively retained through conversion.
Default acquisition packet queue is 8; inference queue is 2, dropping oldest work;
maximum evidence age is 2 seconds. Drops/gaps reset support. History retains 128
frames/hashes/events, timing statistics 2048 samples. SQLite preserves durable audit
and idempotency records; bounded memory does not imply deleting durable history.

Expected input or inference failure suspends the session. Operator resume joins
the old worker, creates a new acquisition run, and replaces a failed analyzer only
with identical capabilities. Restarted application sessions remain read-only or
stoppable and require a new session clock. Stale, silent, disconnected or inactive
observations cannot count as recovery. Baseline promotion and Start Live remain
explicit human commands; live baseline records are immutable.

Guided rehearsal uses the Lead-frozen GET/POST `/v1/sessions/{id}/probes` companion.
It shares the command ledger and analysis path, discards windows overlapping the
request cutoff, and cancels intent on transitions/gaps. Instrument selection is
never activity truth. Full-band windows and explicit human selection govern
baseline acceptance; instrument-probe windows cannot become a full-band baseline.
Reopening uses saved UI IDs/setup metadata plus existing session/reference checks;
there is no catalog API or fixture endpoint.

## Validation and PN54 procedure

```powershell
python -m unittest discover -s core/contracts/tests -q
python -m unittest discover -s tests/runtime -q
python -m unittest discover -s tests/integration -q
python docs/implementation/checkpoint1_smoke.py
python -m tests.runtime.sustained_probe --seconds 300 --output C:/PA/reports/soak/report.json
python -m tests.runtime.native_session_probe --device-id <inventory-id> --seconds-per-run 6 --output C:/PA/reports/native-session.json
```

The sustained probe generates constant synthetic PCM and abstaining Fake evidence;
its labels/config/source hashes are recorded. The native session probe opens the
selected microphone twice, exercises pause/resume/stop, and writes timing/quality
metadata only, never microphone PCM. Run each probe from the exact committed tree.
`core.runtime.parity.compare_window` accepts two host factories and a context
factory, compares identical PCM/backend evidence, and closes both analyzers.
Invalid/null evidence yields unavailable, not a parity pass. It is an injection
hook for a real provider bundle; it makes no accuracy/calibration claim.

For PN54: copy the exact source revision using the Lead release tooling, install
pinned dependencies, run read-only inventory, select its actual native microphone,
run the suites and both probes, then select the reviewed provider/profile and run
paired parity with held-out PCM. Retain exact commit, bundle/config hashes, OS,
provider and report. Local ASUS/Intel/Realtek results do not establish PN54 hardware
support. No remote access, accelerator availability or model lineage is invented.
MI300-derived task adaptation remains the competition gate even if a Nano4
engineering artifact is used for development first.

Final current-source validation results are recorded in the milestone checkpoint
and owned reports; prior 20-minute reports remain historical evidence at their
original commits.
