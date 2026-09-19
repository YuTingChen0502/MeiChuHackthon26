# Checkpoint 1 integration record

Date: 2026-09-19. Owner: engineering Lead. Scope frozen at Checkpoint 1.
Decision: all three corrected checkpoints accepted and integrated. No Checkpoint 2
work is authorized by this record.

## Shared / Gate-0

Gate-0 base: `f22f1e161bb69964765ba58305f7f169950f945c`.
Setup/transport freeze: `3580069588bd37865ac9e78a733acf088a255481`.
Main before this integration pass: `8f8247fbea02a49a1c64018d1e782e94674ee853`.
All three accepted tips descend from Gate-0. Frozen Analyzer, session and setup
contracts retain their semantics. The original public schema is unchanged:
SHA-256 `3b4b198eafbdbd846b366b6c338456230b043b7bf73a21387d025ea3f3993ae0`.

The Lead obtained WORKTREE_STATUS directly from all three workers before review.
All reported clean trees and no outstanding CROSS_LANE_REQUESTS. Cleanliness and
ancestry were independently checked before merging. Three pre-existing main deletions
under `.codex/agents/` were preserved separately in the named stash
`checkpoint1-preserve-preexisting-agent-config-deletions`; they are not part of this
checkpoint. Main was clean before the first merge.

## ML / Evidence

Accepted branch: `codex/ml-evidence-foundation`.
Tip: `19c23fd18e8f01381b71eb032e9317af997926eb`.

Implemented: deterministic controlled pairs and oracle labels; silence/validity masks;
noise controls; configured-source separation measurements; synthetic and HTDemucs
probe runners; checkpoint hashes; manifested WAV ingestion with hashes/provenance;
grouped splits and deterministic pair planning; unfitted direct-estimator evidence
scaffold and portable pair-fusion training-mechanics smoke.

Repeated 54/54 lane tests, then 57/57 ML/shared tests after merging against main's
expanded shared suite. The recorded CPU optimizer audit updates all 12 parameter
tensors and decreases loss from 2.1651 to 1.2778 in eight steps. This is training
mechanics, not encoder/audio feasibility or meaningful MI300 adaptation.

The corrected HTDemucs synthetic smoke has 25% raw-delta numerical coverage and 0%
identifiable centered-balance coverage. Earlier centered metrics are superseded.
Backend selection remains open; these synthetic results neither select nor reject
HTDemucs on music. Rights-cleared grouped multitracks, fitted direct comparison,
held-out calibration, MI300 adaptation and PN54 measurements remain external or
experimental dependencies. They do not block this Fake-driven merge.

## Runtime / PA Core

Accepted tip: `e143474cd6d3ad1b4f95acbabcc98d848ba6f381`.
Frozen reference branch: `codex/checkpoint1-runtime` (worker checkout was detached).
Already integrated in `8f8247f`; the prescribed Runtime merge step was a verified no-op.

Implemented: common file/mic framing; injected FakeAnalyzer evidence; downstream
state/confidence/deviation; rehearsal and Live workflow; anomaly/recommendation;
human adjustment/recheck; explicit immutable baseline; fresh-evidence verification;
SQLite atomic session/baseline/idempotency durability; cold-restart suspension;
HTTP setup/upload/reference jobs/session commands and individual WS events/reconnect.

Repeated 51/51 shared/Runtime/integration tests, including actual loopback Uvicorn.
The focused read-only review found no remaining Fake-slice merge blocker. Prior
suspension bypasses, uncommitted snapshot visibility and opposing lock order are fixed.
Native capture and the API-triggered rehearsal acquisition worker are not implemented;
the smoke supplies windows through the worker-only hook, never a public fake endpoint.

## UI / Demo

Original status tip: `3c826b508147c5f560c00abb0d6c583076436339`.
Accepted corrected tip: `e9b9d110a852e1d613f487b3d62254af7514d4ab`.
Frozen reference branch: `codex/checkpoint1-ui` (worker checkout was detached).

All requested Checkpoint 1 corrections are resolved: approved-listener startup,
fixture no-send behavior, text-safe rendering, probability/tolerance/interval meanings,
distinct inactive/unsupported/unknown states, explicit interval/human acceptance,
Resume, bounded example recommendations, frame-only event refresh, delayed-snapshot
rejection, reconnect recovery, receipt-age gating, and per-session cursor isolation.
Baseline acceptance clearing latest_frame no longer prevents Enter Live.

Repeated 12/12 UI tests. The worker verified browser startup under the approved
listener. The Lead independently tested generated WAV and selected-file media.play()
calls, media-event status and stop. Player code has no UI/runtime/analyzer imports or
network calls. Audible speaker/microphone behavior was not tested.

UI reports local frame receipt age, not estimated audio-capture age. Its five-second
receipt gate is a checkpoint guard, not a calibrated real-time operating threshold.
UI renders authoritative state and never estimates audio state.

## Integrated functionality proven

The saved `checkpoint1_smoke.py` uses the actual JS RuntimeAdapter and commandFor
helper over real HTTP/WS to the SQLite-backed application. Only its test harness feeds
scripted Fake evidence through the private worker hook. It exercises:

uploaded reference -> asynchronous reference job -> rehearsal anomaly/recommendation
-> human adjustment -> recheck -> explicit Accept as Baseline -> Live anomaly/
recommendation -> adjustment -> fresh-evidence recovery -> LIVE_MONITORING.

| Required invariant | Checkpoint evidence |
|---|---|
| File/mic converge | Common SharedAudioPipeline and adapter-convergence tests |
| Rehearsal reference; Live baseline | Context target assertions, full-loop tests and smoke |
| Human-only baseline; immutable in Live | Explicit command, durable retry and Live-rejection tests |
| Abstention is not Normal | Downstream gates with numeric withholding |
| Inactive/unsupported/unknown distinct | Analyzer/state branches and UI rendering checks |
| Stale cannot create or clear incident | Persistence/quality gates; stale/dropout and verification tests |
| Silence/disconnect cannot recover | Unobservable verification becomes inconclusive |
| Verification uses post-adjustment audio | Settling cutoff and evidence-window assertions |
| UI does not infer state | Authoritative snapshots/refresh; display-only helpers |
| Player does not leak truth | Isolated local media code; no imports/API path to inference |
| Analyzer remains replaceable | Frozen evidence boundary and constructor injection |
| No critical LLM | No LLM perception or workflow dependency in the slice |

## Finding classification and remaining dependencies

- MERGE_BLOCKER: none remaining. UI startup, fixture mutation, event ordering and
  cross-session cursor defects found in this pass were corrected before merge.
- POST_MERGE_FIX: overlapping-window acceptance/coverage and sustained buffering/
  history growth need correction or bounded policies before sustained acquisition.
  The tested checkpoint uses finite, nonoverlapping windows. The fake confidence
  implementation must be replaced/gated before non-fake evidence is enabled.
- EXPECTED_NOT_IMPLEMENTED_YET: native microphone acquisition, continuous session
  worker, empirical ML accuracy, fitted calibration, physical acoustic demonstration,
  MI300-adapted model integration and PN54 validation.

There are no outstanding cross-lane requests or incompatible lane assumptions at
this freeze. ML's older 21-test shared base was reconciled by testing against main's
24-test shared suite. All lanes recognize Fake evidence and training-mechanics
results as non-empirical. No feature work was added during this review.

## Merge order and validation

No source conflicts were expected or encountered.

1. ML tip `19c23fd...` -> merge `3c6a49eacd8386d5c1d20528cb63269990e192f2`;
   57/57 ML/shared tests passed before proceeding.
2. Runtime tip `e143474...` -> already integrated; 51/51 tests passed before proceeding.
3. UI tip `e9b9d11...` -> merge `7273eace4b5d483f098079c6a8bbd13eb8757209`;
   12/12 UI tests passed.

Final available suite: 84/84 Python tests including CPU Torch, plus 12/12 UI tests.
Shared contracts repeated separately in the pinned transport environment: 24/24.
Integrated smoke: PASS, ending in LIVE_MONITORING with an unchanged accepted baseline.
Whitespace checks pass and original-schema hash is unchanged. The commit containing
this record and the smoke harness is the final Checkpoint 1 integration record; its
first parent is the UI merge above.

Run from the repository root with Runtime dependencies and Node available:
`python docs/implementation/checkpoint1_smoke.py`.
Full Python validation used existing Python 3.14 with CPU Torch. Transport and shared
checks also used the approved Python 3.12 temporary dependency set. No dependency
changes were made in this integration pass.

Next critical path, not started here: authorize the next checkpoint; obtain verified
musical assets for empirical ML comparison and plan native acquisition/real-model
calibration before the PN54 physical loop.
