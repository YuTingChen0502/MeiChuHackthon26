# MVP native Runtime milestone

Runtime implementation is ready for the frozen candidate through analyzer injection.
This is engineering readiness, not production model, confidence, room-acoustics,
MI300 compliance or PN54 performance acceptance.

## Implementation

- Actual PortAudio device enumeration, unambiguous host/name-derived stable IDs,
  format negotiation and float32 microphone capture. Native callback copies at
  most 1024 frames per packet into an eight-packet queue; it never waits for model,
  HTTP, WebSocket or persistence work. Ambiguous duplicate descriptors are withheld.
- Native stereo downmix outside the callback and shared amplitude-preserving,
  deterministic sinc conversion. File and microphone converge on the same frontend,
  window planner, quality, analyzer, Core and PA workflow. Raw-channel clipping now
  survives WAV downmix as it already did for native input. Exact clock/run/rate,
  sample spans and capture timestamps propagate throughout.
- Independent acquisition and inference, two queued windows, oldest-work dropping,
  two-second evidence age gate, stale/drop counters, bounded timing samples, bounded
  histories and clean lifecycle. Discontinuity, sample gaps, clock changes, callback
  overflow, timeout and restart reset evidence/persistence. Silence and unobservable
  sources cannot become recovery. Pause/resume creates a fresh acquisition run.
- Existing full Fake workflow preserved: uploaded reference, rehearsal anomaly,
  human adjustment, recheck, explicit baseline acceptance and Start Live, live
  anomaly, recommendation, fresh post-adjustment verification/recovery. Live
  baselines remain immutable. Guided probes use the same downstream infrastructure.
- Five-ID compatibility is now persisted privately for every reference and checked
  on reuse: model bundle, frontend, taxonomy, execution profile and level scale.
  Missing legacy bindings require reanalysis. Observation, human baseline acceptance
  and Start Live reject identity drift. No public schema was changed.
- ML candidate commits through `185d864e4d291227c23bbf57ad002f330cd73c67`
  integrated after exact Lead base `e8d1aeced5112d5dcd3e145a2ed32f3e043c8fb8`.
  Runtime contains no HTDemucs implementation. Host `--mode candidate-p1` injects
  ML's loader on CPU with durable reference cache, fixes 44100 Hz / 176400 samples /
  44100 hop, and rejects production acceptance and incompatible geometry. Native
  sample rate is negotiated separately; model rate is not a UI tuning control.
- Candidate supported-family metadata remains bass-only; unsupported rows retain
  null corrections, uncalibrated probability remains null, and invalid evidence
  never becomes Normal. The candidate abstains for microphone/unmatched evidence.
  The unchanged Core anchor/calibration gates also withhold public bass corrections.
- Model load/runtime failures, close/replacement and identity changes are handled
  without Fake fallback. Setup/upload/reference/session/actions/baseline/native
  discovery/health/HTTP/WebSocket/reconnect/sequence/idempotency/SQLite behavior
  remains covered. Restart restores historical sessions suspended and fails
  interrupted reference jobs durably; a new session obtains a new clock.

## Validation

- Shared contracts: 28 passed.
- Runtime: 32 passed, including exact 48k-to-44.1k file/mic PCM and overlapping spans.
- Integration: 60 passed, including all-five-ID reuse, lifecycle failures/reconnect,
  native abstraction, queue pressure/staleness, baseline/verification gates,
  HTTP/WS and SQLite command conflicts/retries.
- Full analyzer regression: 47 passed on the corrected ML pin; 167 tests total.
- CP1 real JavaScript adapter + HTTP/WS + SQLite + Fake closed loop: PASS,
  final LIVE_MONITORING. Source audit/self-tests: PASS before report commit.
- Actual CPU candidate Runtime probe: PASS in 22.876 seconds on clean source
  `8b722ae6135a5ca213b94c672c7ac96617e63796`. Uses a generated four-second 110 Hz
  tone, amplitude .15, PCM16, no labels or external data. Actual selected analyzer
  prepares reference; separate session instances reuse its durable context.
  File/mic frames are non-example, abstained, non-Normal and numerically null.
  HTTP health/session return 200; WS reconnect replays the same event. This is
  integration evidence only, not musical accuracy or actual native candidate inference.

## Sustained and actual native results

Committed reports are under `tests/runtime/reports/mvp-*`. Both capture probes
started from clean `9ec15f0825abcd592f53df2468f0c3c9de878907`. All recorded executable
source hashes still match except the subsequently added candidate launcher and
frontend regression test; capture/frontend/planner/worker/Core/service/probe code
is unchanged. The model-independent soak uses abstaining Fake, not P1 throughput.

Paced sustained run: 300.063 seconds, 48 kHz input to 44.1 kHz canonical PCM,
four-second windows/one-second hop. Processed 296 windows; zero drops, stale windows,
discontinuities or errors. The final incomplete sinc tail is deliberately withheld,
so no post-EOF samples are invented. Inference queue peak 1 of 2. Frames, audio
hashes and events ended at 128 each. Processing p50/p95 94/203 ms; publication-age
p95 .360 seconds. Sampled RSS first/last/peak 57.39/67.18/68.67 MiB; after history
filled, sampled range 62.97–68.67 MiB. This finite run demonstrates observed bounded
behavior, not indefinite stability. Earlier 20-minute reports retain their own SHA.

Actual local Realtek WASAPI native lifecycle: 16.344 seconds, two eight-second
runs at 48 kHz captured/44.1 kHz analyzed, four-second windows/one-second hop.
Eight windows, zero callback/window/stale/discontinuity faults. Callback queue
peak 1 of 8; inference queue peak 1 of 2. Maximum ADC residual 3.913 ms. All Fake
outputs abstained. Pause/resume generated distinct run IDs and Stop released the
stream. No microphone PCM was saved. This local Intel/Windows result is not PN54
or room-perception validation.

## Reproduction

Use the pinned Runtime dependencies and ML's documented CPU dependencies.

```text
python -m unittest discover -s core/contracts/tests -q
python -m unittest discover -s tests/runtime -q
python -m unittest discover -s tests/integration -q
python -m unittest discover -s analyzers/tests -q
python docs/implementation/checkpoint1_smoke.py
python -m tests.runtime.sustained_probe --seconds 300 --analysis-rate 44100 --output <external-report-path>
python -m tests.runtime.native_session_probe --device-id <actual-device-id> --seconds-per-run 8 --analysis-rate 44100 --window-seconds 4 --hop-seconds 1 --output <external-report-path>
python -m tests.integration.p1_runtime_probe --candidate models/candidates/nano4-p1-adapted-mvp-v1 --output <external-report-path>
```

## Remaining external gates

No model-independent Runtime implementation blocker remains. ML still owns broader
source support, held-out confidence/calibration, real-room comparability and
meaningful MI300 adaptation lineage. PN54 still requires exact-provider installation,
physical microphone validation and sustained actual-model latency/parity measurements.
The current candidate cannot demonstrate a calibrated real-room PA correction loop;
the complete product loop is demonstrated only with explicitly Fake evidence.
