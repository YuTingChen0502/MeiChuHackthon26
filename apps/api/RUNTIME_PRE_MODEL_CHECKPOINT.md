# Runtime pre-model milestone

RUNTIME_PRE_MODEL_READY = YES

Runtime implementation is complete for injection/configuration of the later trained
perception backend and its reviewed evidence. This is not a trained-model or
calibrated acoustic performance claim.

## Implementation completed

- Native device discovery with reorder-stable, unambiguous host/name identity;
  format negotiation, float32 capture, deterministic downmix, canonical shared
  resampling and exact sample/rate/run/clock/timestamp identity. Callback only
  copies bounded packets; analysis, HTTP, WebSocket and SQLite never run there.
- One file/microphone frontend/window/quality/analyzer/deviation/PA/verification
  path; configurable overlap, acquisition worker, bounded queues, backpressure,
  stale dropping, clipping preservation, silence/dropout/discontinuity handling.
- Explicit pause/resume/reconnect/stop, orderly shutdown, failed-analyzer close and
  exact-identity replacement. A consumer-failure/producer-finish resume race found
  during this milestone was fixed and regression tested.
- Actual ML BackendRegistry/BundleAcceptance/load_bundle integration, host-owned
  adapter registration, durable reference-context store, unavailable/failed/corrupt
  bundle handling, no Fake fallback, and strict identity/provider gates. Only the
  non-identity availability-state capability may change during an instance.
- Host-reviewed held-out calibration mappings for anomaly AND normal events,
  identity/artifact/support/probability/interval/quality/regime/capture gates,
  and real baseline context/envelope consumption. Synthetic candidates cannot be
  production approved. Bounded exact accepted-interval PCM uses prepare_reference;
  expired PCM fails closed rather than fabricating a baseline context.
- Full reference/rehearsal/anomaly/adjustment/recheck/human baseline/Start Live/
  live anomaly/fresh verification loop; immutable live baseline and independent
  volume/common-mode treatment. Inactive/silent/stale/noisy/unavailable evidence
  cannot become recovery.
- Existing setup/session/HTTP/WebSocket/SQLite/idempotency/reconnect behavior;
  interrupted reference jobs become durable failed jobs; historical sessions
  restore without loading retired models and require a new sensing session.
- Lead-frozen guided rehearsal GET/POST companion: durable atomic intent, same
  pipeline, complete post-request windows, no inferred activity truth, cancellation
  on gaps/transitions, full-band baseline interval requirement. Saved UI IDs use
  existing authoritative session/reference compatibility checks for reopening.
- Explicit local launcher, reviewed host/cache layout, read-only inventory,
  provider parity injection hook, sustained/native scripts and PN54 runbook.

No Runtime-owned edits changed frozen public schemas. The guided companion and
model integration code arrived through exact Lead/ML-authorized commits.

## Tests

- Shared contracts: 28 passed.
- Runtime: 30 passed.
- Integration: 52 passed, including four actual-loader tests (no stub loader),
  transactional guided intent, managed inference replacement, mid-stream native
  packet timeout/operator reconnect, and bounded real-path rehearsal PCM retention.
- Analyzer suite: 30 passed. Total: 140 tests.
- Unchanged CP1 real JavaScript RuntimeAdapter + HTTP/WebSocket + SQLite + Fake
  full PA correction loop: PASS; final state LIVE_MONITORING.
- Source-release audit and its self-tests: PASS with no findings before evidence
  commit; repeated at final checkpoint.

## Sustained and native evidence

Both final probes started from clean committed source
`7809b168e3531d5c09c207d6903929206718bcd7`. Subsequent changes are an ML test-fixture
source-audit correction, extra integration regression assertions, and these docs/
reports. Every executable Runtime/probe source hash in the soak report was checked
against the final workspace and remains identical.

The 300.344-second paced synthetic run processed 297 windows with
zero drops, stale windows or discontinuities; no worker error. Configuration:
48 kHz mono, W=192000/hop=48000 (4/1 seconds), queue capacity 2, max age 2 seconds,
4800-sample chunks, deterministic constant amplitude .05, no noise and no instrument
labels. Processing p50/p95 = 78/125 ms, publication-age p95 = 156 ms.
Queue depth peaked at 1/2. Frames, PCM hashes and events each ended at their 128 cap.
Sampled RSS: 50.82 MiB first, 54.18 MiB final, 58.48 MiB peak;
after history filled, sampled range 53.82–58.48 MiB.
This finite measurement is evidence of bounded observed behavior, not a proof of
indefinite stability. Earlier 20-minute evidence remains historical at its own SHA.

Actual local native session smoke: 12.313 seconds, two 6-second
capture runs and 20 total windows through RuntimeAPI, with pause/resume/new run/stop.
Realtek Microphone Array via Windows WASAPI, 48 kHz mono; zero callback/inference
drops, stale windows or discontinuities. Both queues peaked at 1. Maximum ADC
residual 3.213 ms under the declared
50 ms budget. Final workflow STOPPED. All Fake observations abstained; physical
gain/AGC/geometry remain unverified. No microphone PCM was written. The machine was
a local ASUS Intel Windows host, not PN54; no target-hardware performance claimed.

Reports: `tests/runtime/reports/runtime_300s_7809b16.json` and
`tests/runtime/reports/native_session_7809b16.json`. The first includes exact source
hashes/config/environment and sampled retention/RSS; the second records both native
runs and capture/lifecycle results. Deployment/reproduction is documented in
`apps/api/RUNTIME_PRE_MODEL_READY.md`.

## Remaining model-specific dependencies only

1. The selected trained backend's numerical perception, matching/reference feature
   persistence and runtime artifact/provider adapter, registered through the
   implemented allowlist/frozen analyzer interface.
2. Real held-out evaluation/calibration, measured source coverage, compatible
   execution/capture/quality/normal-envelope settings and reviewed host acceptance.
3. Exact artifact freeze, provider parity evidence and MI300 adaptation lineage
   for competition use (Nano4 engineering-first remains permitted).

No capture, streaming, queue, PA state-machine, persistence, API or lifecycle
redesign is required when those model-specific inputs arrive.
