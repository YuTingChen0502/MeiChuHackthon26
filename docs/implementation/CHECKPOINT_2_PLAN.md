# Checkpoint 2 — real audio, MI300 adaptation, PN54 integration

Status: approved execution plan; ready to start independent work. External data and
hardware gates below remain real dependencies, not evidence already obtained.
Owner: engineering Lead. Date: 2026-09-19.

## Starting point and completion definition

Authoritative repository: https://github.com/YuTingChen0502/MeiChuHackthon26.
`origin/main` is the cross-machine source of truth. A fresh fetch for this review
confirmed main and origin/main at `594e61c090a3fdd0bdad2f65269b407677c5f7e3`, containing
Checkpoint 1 integration `f543fb7318c77e10c8337e16ae395f04e9e4a8c3` and subsequent
agent-config/ignore cleanup. Checkpoint 1 proved the Fake-driven correction loop;
it did not prove musical perception, physical capture, calibration or adaptation.

Checkpoint 2 is complete only when a measured real-audio analyzer, whose demonstrated
weights descend from meaningful task-specific adaptation on the official MI300
environment, runs locally on PN54 through the existing human correction workflow.
It must have a declared supported operating envelope, empirical calibration and
physical evidence. An intermediate negative feasibility result can be a valid lane
checkpoint; it is not completion of this overall objective.

Follow AGENTS.md, INFO.md, the public schema and technical design. This plan schedules
the design's P1–P5 path; it does not replace its architecture or reopen product scope.
Use all existing contracts under contracts/ and core/contracts/. No shared amendment
is required to begin. No implementation, compute job or new worktree is started by
writing this plan.

## New worktrees and exact-source discipline

Prefer three NEW Checkpoint 2 worktrees, all from one recorded latest origin/main SHA.
Suggested branch names are `codex/cp2-ml-real-audio`, `codex/cp2-runtime-native-audio`
and `codex/cp2-ui-physical-demo`. Do not reuse the old Gate-0 branches or detached
Checkpoint 1 worktrees as development bases. Preserve them as history; do not delete
or reset them as part of setup.

Before dispatch, publish this approved plan through main, fetch origin, verify that
origin/main contains it and Checkpoint 1, and record the single launch SHA for all
three worktrees. If main advances, review the delta and choose one new common SHA;
do not let each worker silently select a different starting point.

All code changes originate in these repository worktrees. Remote runs must fetch an
explicit pushed origin ref, check out its full immutable SHA, verify a clean source
tree and execute a hashed configuration from that revision. A pushed experiment
branch is allowed; it must be identified explicitly and must not be called approved
main. Unpushed commits, remote hotfixes and independent compute-machine source edits
are not allowed. Fix locally, validate, commit/push, then rerun the new SHA.

Record commit, config hash, dataset/asset hashes, split/seed, frontend/model hashes,
environment/provider, thresholds, label procedure, metrics and failures for every run.
Keep checkpoints/audio outside Git where appropriate; commit permitted manifests and
reproducible result summaries, not credentials or restricted recordings. Remote results
return to the owning lane for review and integration; machines are not write lanes.

## Exactly three implementation lanes and ownership

Paths are repository-relative and exclusive, including tests and supporting configs.

| Lane | Exclusive writable paths |
|---|---|
| ML / Real Audio Evidence | analyzers/, training/, benchmarks/, models/, assets/ |
| Runtime / Native Continuous Audio | core/audio/, core/profiles/, core/runtime/, roles/pa/, apps/api/, tests/runtime/, tests/integration/ |
| UI / Physical Demo Integration | apps/ui/, demo_player/, docs/demo/, tests/ui/ |

Lead-owned: contracts/, core/contracts/, docs/implementation/, authority/design files,
root dependency/build configuration and integration decisions. Requests for shared
dependency pins or interface changes go to Lead; workers do not edit them themselves.
ML owns model-specific frontend/execution adapters, fitting and model artifacts;
Runtime owns common capture/preprocessing orchestration and application execution.
UI owns presentation and isolated playback. No fourth implementation lane is created.

## 1. ML / Real Audio Evidence

### Exact objective

Establish falsifiable real-music gain/attribution evidence for the existing separation
and direct candidates, perform meaningful MI300 adaptation, and deliver a versioned
analyzer bundle plus calibration evidence suitable for local Runtime integration.
HTDemucs 6-source and the design's EfficientAT candidates are experiments, not winners
selected by reputation. Hybrid is conditional on measured value from both paths.

### Immediate tasks

1. Resolve the external multitrack input with the team/data provider. Populate and
   validate the existing asset manifest: provenance, permission, attribution, hashes,
   publication status, family mapping and parent-group split. Begin with rights-cleared
   self-recorded material if available. Dataset accessibility is not permission.
2. Reuse the oracle and manifested pair planner. Audit raw source gain, common mode,
   centered balance, active/observable masks and loss targets before actual training.
   All variants of a parent recording stay in one split; training, validation,
   calibration and untouched test material are separate. Hold out noise recordings
   and acoustic conditions. Do not relabel unrelated performances as exact gain pairs.
3. On Nano4, inventory the actual environment and run P1 separation on mixed audio
   only. Preserve scale; center only configured valid sources. Report per-instrument
   raw numerical coverage separately from identifiable balance coverage. A nominal
   family mapping or a separated waveform is not proof of attribution.
4. In parallel, implement P2 with actual pretrained audio features, a scale-sensitive
   branch and the existing paired objective. Compare a frozen-feature/head probe on
   the same pairs with P1. The current synthetic-feature head smoke is only an
   optimizer check, not this probe and not competition adaptation evidence.
5. Begin MI300 access/inventory/framework/forward-backward-optimizer validation now,
   while Nano4 probes proceed. Record allocated quota and a finite run/time/memory cap
   before GPU jobs. Use the provided working stack; do not upgrade host drivers.
6. When data/labels, checkpoint and MI300 smoke are ready, run the design's head warmup
   followed by partial pretrained-encoder unfreezing on MI300. Keep the training
   budget fixed and compare to the frozen and non-reference ablations. Do not wait
   for separation to succeed before preparing or testing the direct training path.
7. Fit reliability and residual/interval calibration on a separate calibration set.
   Export a CPU correctness anchor and the proposed portable inference artifact,
   frontend/taxonomy/scale/threshold/calibration metadata and provenance as the
   design E5 bundle. Verify eager/export parity before optional precision changes.

### Hard dependencies

- Real-music P1/P2 evidence requires rights-cleared multitracks and valid grouped
  manifests. The repository currently records empirical assets as not supplied.
- MI300 adaptation requires official environment access, actual checkpoint access,
  audited labels, a functioning optimizer path and a recorded resource budget.
- Calibrated numerical/actionable output requires enough independent calibration
  material and untouched evaluation. Backend deployment additionally requires actual
  PN54 execution measurements; Nano4 speed is not a substitute.
- Hardware access, permissions and dataset contents are not assumed available.

### First checkpoint deliverable (ML-2A)

A reproducible real-audio P1/P2 comparison packet: exact commit/config/asset identities,
raw rows, per-condition metrics and failure examples on the same fixed paired excerpt
set; a schema-valid pluggable analyzer path; and a separate MI300 environment/optimizer
validation report. Show unavailable steps as blocked by their named dependency. If
assets are unavailable, deliver ingestion/probe readiness and environment evidence,
but do not label that packet a passed real-audio feasibility checkpoint.

### Acceptance criteria

- Existing shared tests plus oracle/asset/split/adapter tests pass. Analyzer results
  validate against AnalyzerContext/AnalyzerEvidence and preserve identities/units.
- Mixtures and legitimate reference/context alone enter inference. Stem labels,
  injected gains, true SNR, seeds, filenames and player controls never enter the model.
- P1/P2 report zero-change, global-only, one-source, multiple-source, inactive,
  unsupported, noise/speech and clipping/path-mismatch controls. Start with clean,
  20/10 dB and selected 5/0 dB stress cases; expand the design's matrix by observed
  weakness, not an uncontrolled Cartesian sweep. Record actual noise conditions.
- Report precision/recall including abstentions, sign, magnitude, all/eligible-frame
  coverage, unconditional or explicitly penalized errors, latency and denominators.
  Do not conceal failure by accepting only a few easy predictions.
- For adaptation acceptance (ML-2B), preserve official MI300 run identity, starting
  checkpoint hash, changed pretrained-layer weights/gradient evidence, saved adapted
  hash, held-out comparison and exported descendant hash. A changing random head,
  decreasing synthetic loss or an unused trained model does not satisfy this gate.
- For deployment acceptance (ML-2C), meet the measured operating-envelope gates below,
  deliver calibration/export-parity results and link the exact deployed artifact to
  the adapted weights. Uncertainty features remain evidence, not public confidence.

### GO / NO-GO / fallback

- GO to bounded adaptation when real pairs/labels and the MI300 training path are
  valid; record a negative frozen probe rather than hiding it. GO to numerical PA
  deployment only after calibration and task/PN54 gates pass.
- NO-GO for a family/regime with wrong attribution, non-monotonic response, inadequate
  coverage or unsafe calibrated errors. Mark it unsupported/unobservable and abstain;
  narrowing the published envelope must be supported by evidence and Lead-reviewed.
- If direct gain information is weak, test the already designed raw-level branch or
  a timeboxed hybrid only if P1 evidence supports it. If separation alone wins, the
  design permits a bounded task-specific separator adaptation experiment on MI300;
  revalidate amplitude fidelity and local cost. This is not an automatic rescue.
- If neither path passes, report NO-GO for real numerical recommendations. Keep
  acquisition and abstaining diagnostics available. Do not substitute a pretrained-only
  or Fake demo for the chosen MI300 path, or switch to RAG without a Lead decision.

### Lane interactions and exclusions

Give Runtime artifact IDs, capabilities, valid sample/window requirements, evidence
mode, raw uncertainty semantics, parity tests and calibration provenance. Use
capabilities(), prepare_reference(), analyze(window, context), close() behind the
existing interface; do not expose the current training scaffold as a drop-in Runtime
analyzer until it implements that boundary. ML fits calibration; Core applies it.
Give UI only tested support/operating-limit information through Runtime and the demo
runbook. Do not implement UI, canonical InstrumentState, PA actions, native capture,
automatic mixing, tone/EQ or a new model architecture race outside the frozen design.

## 2. Runtime / Native Continuous Audio

### Exact objective

Replace finite injected acquisition with native continuous microphone capture and
uploaded-audio session execution through the same downstream path, then host the
approved real analyzer locally with bounded latency, honest abstention and durable
human workflow. Begin with Fake/abstaining adapters; do not wait for final ML.

### Immediate tasks

1. Inventory native devices/formats on the available local host and PN54 when granted.
   Select and verify a portable capture path; request any minimal root dependency pin
   from Lead. A configured device ID is not proof that a microphone was opened.
2. Replace list(chunks) and whole-stream buffering with incremental framing and bounded
   queues. Preserve sample indices, half-open windows, source/run/clock identity and
   original amplitude. Capture callbacks must not run inference or blocking storage.
3. Wire the existing session setup/lifecycle to a managed file/native worker. Handle
   EOF, cancel, pause/resume/stop, device loss, overload and process restart. Stop must
   release capture. Never process an infinite input as a finite list.
4. Implement the immediate real-model safety gate: Fake calibration remains limited
   to explicit example_only evidence. Non-fake evidence without compatible empirical
   calibration yields uncalibrated/null probability and interval, abstention, null
   public numeric instrument deltas and no corrective recommendation, per schema.
   Keep raw evidence available to controlled benchmarks, not disguised as PA advice.
5. Correct overlapping-window coverage and persistence. Use unique sample coverage
   and qualified nonoverlapping support; overlapping windows are not independent
   trials. Bound recent frame/audio history and persistence costs while retaining
   immutable baseline/audit evidence and declared retention behavior.
6. Validate actual capture fingerprint/gain/enhancement settings and matching. Device,
   gain, geometry or model/profile changes require suspension/revalidation. Keep dry
   upload provenance unverified until the physical setup is validated. Do not trust
   client-provided enhancements/provenance as measured truth.
7. Integrate an accepted ML bundle only through the frozen analyzer boundary. Load
   matched calibration/profile context; reanalyze references/baselines or require
   explicit reacceptance when incompatible. Start with CPU correctness/parity; profile
   actual PN54 providers before optional acceleration.

### Hard dependencies

- Real capture requires a usable microphone, OS permission, working capture backend
  and device access. File streaming, bounded framing and lifecycle tests do not.
- Bundle integration depends on ML's contract-valid artifact and declared frontend/
  taxonomy/scale/execution IDs. Actionable confidence depends on empirical calibration.
- Final local-performance/physical acceptance requires PN54, its real environment,
  a stable speaker/mic path and an approved adapted model. Local results cannot stand
  in for these. Dependency/ABI or shared metadata changes are Lead-owned requests.

### First checkpoint deliverable (RT-2A)

An API-managed native microphone and uploaded-file worker using the common incremental
pipeline, demonstrated with explicit Fake/abstaining evidence. Supply a captured-WAV
artifact/manifest when recording is permitted, device/profile inventory, bounded queue
metrics and tests for lifecycle, discontinuities and overlapping-window coverage.
This deliverable must not depend on model-selection completion.

### Acceptance criteria

- Existing shared/command/durability tests and Checkpoint 1 smoke stay green. Replay
  identical captured PCM through file and live adapters and compare frontend/windows
  and downstream results within declared tolerances and clock differences.
- A 20-minute sustained run has bounded buffers/history, recorded memory trend,
  queue depth, dropped windows and processing p50/p95. Drop policy preserves sample
  discontinuity evidence; no silent catch-up using stale audio and no false recovery.
- For the initial W=4 s/hop=1 s profile, processing p95 must fit within the hop and
  queue age must remain bounded. Measure capture-to-publication age separately from
  change-to-confirmed-alert latency. Explicitly evaluate a slower supported profile
  if this fails; revalidate its persistence/calibration and report the changed cadence.
- Paused/stopped/restarted sessions retain the established authorization and atomicity
  guarantees. Silence, disconnection, stale or incomparable windows cannot open a
  corrective incident or resolve one as recovered. Verification uses complete windows
  after adjustment completion plus settling, with sufficient valid support.
- Baseline acceptance remains human-only, with adequate per-source unique active
  coverage; Live cannot mutate it. Compatible model/frontend/taxonomy/precision and
  capture identities are checked, not inferred from UI declarations.
- Non-fake uncalibrated evidence cannot inherit the simulated 0.95 confidence. A
  calibrated result is enabled only for the exact validated bundle/profile/regime.
- RT-2B/PN54 acceptance records actual provider assignment, CPU/export parity, sustained
  performance and the exact adapted artifact used in the physical loop.

### GO / NO-GO / fallback

- GO for native-worker integration after bounded-stream/lifecycle tests, independent
  of real-model quality. Keep outputs simulated or abstained until ML gates pass.
- NO-GO for actionable Live on unverified capture, incompatible profiles, absent
  calibration, stale queues or failing PN54 throughput. Suspend and expose the reason.
- Use only a prevalidated smaller/CPU or slower profile with matching calibration and
  baseline compatibility as fallback. File replay remains a supported diagnostic
  input; it is not a substitute claim for physical microphone validation. No remote
  cloud inference fallback for critical PN54 perception.

### Lane interactions and exclusions

Publish actual device/setup availability and worker status through existing APIs;
coordinate any genuinely missing closed-record field with Lead before UI depends on
it. Provide ML captured examples with legitimate provenance for evaluation, never
demo truth as inference input. Feed UI authoritative snapshots/events, quality reasons,
calibration state and verification. Do not fit models, edit model artifacts, implement
UI, invent new confidence meanings or introduce automatic baseline/mixer actions.

## 3. UI / Physical Demo Integration

### Exact objective

Keep the operator console substantially feature-frozen. Make the existing controls,
status and isolated player reliable against native sessions and the eventual PN54
deployment, and document/rehearse the genuine physical correction demonstration.

### Immediate tasks

1. Retain the existing layout and workflow. Add only necessary wiring/corrections for
   Runtime's real device availability, session lifecycle and existing quality/error
   states. Do not invent native capture status, confidence or new setup payloads.
2. Verify authoritative session selection, fresh-event receipt, stale/disconnected
   gating, retries/version conflicts and no cross-session state leakage. Keep local
   receipt age honestly labeled; it is not measured capture latency.
3. Exercise explicit qualified-interval selection, reference-difference choice,
   Accept as Baseline, adjustment/recheck and verification against the native worker
   when RT-2A is ready. Retain visible uncalibrated/inactive/unsupported/unknown states.
4. Prepare the existing isolated playback/runbook with rights-cleared clips, opaque
   ordering, stable geometry and external ground-truth records. Validate the player
   on its playback device. Only acoustic output reaches the runtime microphone.
5. Prepare physical trial/checklist and permitted evidence capture. Use the real PN54
   session/provider/model identity; clearly label any prerecorded backup. Report
   unsupported conditions instead of cosmetic success states.

### Hard dependencies

- Native device/worker interaction waits for RT-2A, not for final calibrated ML.
- Real recommendations/verification demonstration waits for accepted calibrated
  analyzer, official MI300 artifact lineage, PN54 availability and verified capture.
- Public playback/video assets require explicit publication rights. Physical validation
  requires a speaker, microphone, stable geometry and the actual PN54 runtime.

### First checkpoint deliverable (UI-2A)

A narrow integration/test/runbook update with the existing UI: device unavailable,
native rehearsal, uncalibrated abstention, pause/resume/stop, disconnected/reconnected
and session-switch cases; isolated real playback verified on the available hardware.
Until Runtime is available, test existing transport fixtures and record that dependency;
do not build a second analyzer/worker or expand the interface to fill the gap.

### Acceptance criteria

- Existing UI and adapter tests stay green. Authoritative controls never mutate fixture
  sessions, infer audio state, silently accept a baseline or conceal Runtime rejection.
- Numerical instrument balance/probability/interval display follows existing validity
  and calibrated-confidence records; no synthetic confidence in a real session.
- Evidence age and disconnection gate corrective presentation. Recovery is displayed
  only from Runtime's fresh-evidence VerificationResult, not a button press or silence.
- The isolated player has no imports/API/metadata path into the analyzer/runtime.
  Trial labels and gain controls stay with the external evaluation log.
- UI-2B completion rehearses the complete physical human loop on PN54 with recorded
  bundle/profile identities and successes/failures. Media playback alone is not proof.

### GO / NO-GO / fallback

- GO for the small native-session integration after RT-2A; GO for the physical claim
  only after real model/calibration, capture and PN54 gates pass.
- NO-GO when source identity, freshness, calibration or isolation is unclear. Preserve
  unavailable/abstained states and report the blocked dependency.
- A clearly labeled fixture/offline replay or permitted prerecorded physical video
  can explain the system while a device is unavailable. It does not satisfy a live
  physical-validation gate and must never masquerade as current inference.

### Lane interactions and exclusions

Runtime owns native acquisition and session truth; ML supplies tested limits via
Runtime/approved documentation. UI reports reproducible integration defects directly
to the owning lane through Lead. Do not redesign screens, add dashboards, capture
audio in the browser as a parallel sensing path, add inference, LLM explanations,
tone/EQ, section targets or mixer control. Full guided-soundcheck UX remains deferred;
existing guided-probe context must remain usable by the common infrastructure.

## Compute responsibilities and concurrency

| Environment | Responsibility | Immediate parallel work | Required evidence / restriction |
|---|---|---|---|
| LOCAL | Development, tests, integration and portable correctness anchor | All three worktrees; stream tests; asset/label checks; CPU/export smoke | Only repository-origin code; Checkpoint 1 regressions remain available |
| NANO4 | Fast P1/P2 feasibility and bounded sweeps | Inventory/import/load; separator/direct probes as soon as assets exist | Exact origin commit/config, actual device/runtime, same split/matrix; no PN54 speed claim |
| MI300 | Official meaningful task-specific adaptation | Access/quota/environment and finite gradient/optimizer validation immediately, alongside Nano4 | Record official allocation and actual provider; launch adaptation once data/path are ready, without waiting for every Nano4 sweep |
| PN54 | Final local runtime, profiling and physical validation | Inventory/native audio/CPU compatibility as soon as access exists, while ML trains | Actual hardware/provider, model lineage, calibration, sustained and acoustic evidence; never assume NPU support |

Nano4 may continue validation/noise sweeps while MI300 trains an audited candidate on
the fixed train split. MI300 does not need to idle until P1 succeeds; it must wait for
valid data/labels and its own working path. Runtime streams with Fake/abstaining
adapters concurrently. PN54 compatibility and audio capture start before final model
selection. UI prepares isolation and regression checks during both ML and Runtime work.
Lack of a remote credential or dataset blocks only dependent tasks and is reported
explicitly; it does not stop local streaming or interface-preserving preparation.

## Dependency and integration sequence

1. Lead publishes this plan, freezes one current origin/main launch SHA and creates
   the three new worktrees when execution is dispatched. All lanes can begin their
   independent tasks; MI300 environment validation and Nano4 inventory run in parallel.
2. Rights-cleared data -> manifest/splits/oracle -> comparable P1/P2 real-audio evidence.
   Runtime native/file worker and UI runbook progress independently of those results.
3. Valid real training pairs + checkpoint + MI300 smoke/budget -> official partial-
   backbone adaptation. Nano4 can continue fixed validation experiments concurrently.
4. ML-2A and RT-2A are reviewed independently. Integrate bounded native Runtime and
   the uncalibrated safety gate first; then contract-valid real analyzer diagnostics;
   then the minimal UI connection. Diagnostics remain abstaining until calibration.
5. Adapted model + validation selection -> separate calibration -> held-out metrics/
   export parity -> accepted bundle. Lead reviews model metadata/calibration handoff
   before Runtime enables numerical recommendations. A valid schema alone is not
   calibration or a deployment GO.
6. Accepted bundle + RT-2A + PN54 access -> sustained local profiling and acoustic
   trials -> final human correction demonstration. Integrate only green checkpoints,
   testing relevant lanes after each merge and the full loop after integration.

## Evidence gates for real numerical/physical GO

Use technical design C3 as initial engineering targets, not observed performance or
new contract guarantees. Freeze the evaluation config and eligible population before
looking at final test results. For supported, observable one-source anomalies of
absolute gain at least 4 dB, report:

| Metric | Initial design target |
|---|---|
| Attributed alert precision | >=0.90 |
| Event recall including misses/abstentions | >=0.75 |
| Sign accuracy on accepted predictions | >=0.95 |
| Accepted balance MAE | <=2.0 dB |
| Eligible-frame coverage | >=0.60; report all-frame coverage too |
| False alerts during normal continuous audio | <=1 per 10 minutes as a test target |
| Confirmed event latency, initial 4-second profile | p95 <=8 seconds |
| Controlled independent correction trials | >=9/10; report uncertainty and denominators |

Report calibration/reliability curves, actual interval coverage/width, abstention
coverage, unconditional errors, normal-stream minutes and confidence intervals.
Insufficient sample counts mean insufficient evidence, not a production guarantee.
Thresholds may be revised using validation and Lead review, never tuned on final test
results and retroactively described as predeclared. Do not select a backend from its
name, nominal architecture size or separation reputation.

Digital aligned same-recording evidence, acoustic replay and unrelated performance
are different regimes. A successful aligned comparison does not prove arbitrary
reference-to-performance matching. Keep comparison matching audio-based; it may choose
comparable evidence but may not become a section-dependent target schedule. For real
room noise, report controlled SNR only when independently measured; otherwise label
the ambient condition rather than inventing ground truth.

## Handoffs, escalation and completion packet

Workers communicate directly with Lead. Use Event-ID=<lane>/<event>/<commit-or-stable-id>;
deduplicate events. STATUS_UPDATE records progress without starting work. Checkpoint
review requests receive CHECKPOINT_ACCEPTED or concrete CORRECTIONS_REQUIRED for the
agreed scope; acceptance does not automatically start another checkpoint.

Cross-lane requests identify the actual owner, exact field/file, failing evidence,
smallest proposed change and affected tasks. Lead forwards worker-owned corrections;
Lead-owned shared changes are validated/committed on main and published before
affected workers synchronize. Routine lane-local fixes stay in their lane. Evidence
corruption, incompatible shared state or a proven-invalid assumption stops affected
work at a safe atomic point; other independent work continues.

Every checkpoint supplies exact commit, clean-tree status, tests, raw evidence links,
limits and outstanding dependencies. Final acceptance requires all of:
real-audio comparison/calibration report; official MI300 adaptation lineage; validated
export/bundle; native continuous worker; actual PN54 sustained profile; physical
human correction trials; current contracts/tests and a reproducible launch/runbook.
No stretch feature, new public shape or product behavior is authorized implicitly.

Planning verdict: READY_TO_START_CHECKPOINT_2. This permits the parallel work plan;
it does not certify the external assets, hardware access or final physical outcome.
