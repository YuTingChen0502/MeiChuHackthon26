# CP2 Runtime / Native Audio checkpoint

Lane: CP2-RUNTIME. Authorized base: `8c8226d18c0b2def5098368cebe6699be6498c15`.
All implementation changes stay within Runtime-owned directories. Public schemas,
ML code, UI code and root dependency configuration are unchanged.

## Implemented

Native PortAudio discovery and mono float32 capture; bounded acquisition and analysis
workers; shared incremental overlapping-window planning; stable sample/run/clock
identity; stale-window dropping and post-inference freshness gates; discontinuity
reset; clipping and silence quality; managed file/native lifecycle; bounded recent
frames/events/hashes; transactional immutable audit archival; unique baseline coverage;
nonoverlapping anomaly support; guarded RealAnalyzer boundary with mandatory
uncalibrated abstention. Default continuous Fake output is explicit simulated
abstention until scripted evidence is supplied by an in-process test harness.

## Validation

- Shared contract suite: 24 passed.
- Runtime suite: 20 passed.
- Integration suite: 35 passed, including actual loopback transport. Total: 79 tests.
- Unchanged CP1 JS RuntimeAdapter + HTTP/WebSocket + SQLite correction-loop smoke: PASS.
- Native local WASAPI smoke: six seconds, 48 kHz mono, 288768 captured samples,
  zero drops/discontinuities, exact captured-PCM/file-window replay parity. Gain,
  enhancements and physical geometry remain unverified. This is not PN54 evidence.
- `b95ce4f` sustained Runtime/API probe: 1200.156 seconds, 1197 windows, zero
  dropped/stale windows or discontinuities. Queue depth maximum 1 of capacity 2;
  processing p50/p95 63/94 ms; capture-to-publication age p95 125 ms. Frame/hash/event
  history each capped at 128. The one-second hop processing budget passed on this
  local Fake/abstaining run.
- Native timing/teardown corrections at `22c9ea3`: 120.188 seconds, 117/117 planned
  windows, zero callback/worker drops, stale windows or discontinuities. Maximum ADC
  residual 3.874 ms; callback queue maximum 1. No PCM saved for this continuity run.
- Final digital-rail correction at `e619c7d`: 150.156-second Runtime/API probe,
  147 windows, zero drops/stale/discontinuities, processing p50/p95 47/63 ms,
  publication-age p95 94 ms; frame/hash/event buffers each capped at 128.

Working-set memory in the 20-minute run went from 50.02 MiB to 58.59 MiB,
with a measured peak of 59.69 MiB. The complete sampled trend is retained;
this finite observation is not a proof of indefinite memory stability.

Reports under `tests/runtime/reports/` identify their exact tested source commits.
The long run tests `b95ce4f`; later corrections are covered by focused regressions
and the separately recorded native and 150-second runs. These revisions must not
be represented as one identical tested binary. The final CP1 compatibility fix is
covered by the unchanged JS/HTTP/WebSocket smoke and a regression: the private
in-process Fake harness may inject 10 Hz fixtures under a nominal 48 kHz UI device
profile. Managed capture and non-fake analyzers retain strict profile enforcement.
This exception is not exposed in public requests or launcher configuration.

The earlier two-second native diagnostic over-detected callback timestamp jitter.
The corrected adapter anchors time to sample counts with a declared 50 ms ADC
residual budget; the committed six-second `b95ce4f` probe measured a 19.5846 ms
maximum residual (`native_capture_b95ce4f.json`). Overflow
status and missing sample spans still break continuity. The earlier diagnostic is
superseded, not positive evidence. A subsequent 120-second diagnostic exposed
Windows clock-resolution jitter at the consumer boundary: 94 windows were wrongly
rejected as slightly future-dated. `22c9ea3` applies the declared 50 ms budget there,
while conservatively requiring the same extra margin for native post-adjustment
verification. The repeated native probe passed all 117 windows. Teardown exceptions
now preserve terminal notification and joining. `e619c7d` includes PCM16 positive
full scale in the shared clipping gate. No correction changed a public schema.

## Reproduction

Use Python 3.12.14 with the Lead-pinned runtime dependencies. The local native probe
used sounddevice 0.5.6, cffi 2.1.1 and pycparser 3.0 from a temporary environment.
The portable native backend follows the official raw-input/discovery API:
[raw input streams](https://python-sounddevice.readthedocs.io/en/latest/api/raw-streams.html) and
[device discovery](https://python-sounddevice.readthedocs.io/en/latest/api/checking-hardware.html).

```text
python -m unittest discover -s core/contracts/tests -v
python -m unittest discover -s tests/runtime -v
python -m unittest discover -s tests/integration -v
python docs/implementation/checkpoint1_smoke.py
python -m tests.runtime.sustained_probe --seconds 1200 --output <local-output>/sustained.json
python -m tests.runtime.native_probe --device-id <discovered-id> --seconds 6 --output <local-output>
python -m tests.runtime.native_continuity_probe --device-id <discovered-id> --seconds 120 --output <local-output>/continuity.json
```

Probe manifests record commit/config/source hashes, runtime, generated PCM procedure
or capture provenance, queue metrics and timing. Native WAV/raw float PCM stays in
local temporary output and is not committed or uploaded. The local final capture
artifact is `%TEMP%/cp2-native-final-capture/capture.wav`; the exact float source is
`capture.float32le` in the same directory. Its committed manifest records hashes. No probe claims instrument
accuracy, calibration, meaningful MI300 adaptation or physical PA verification.

## Limits and external gates

- Native dependency routing is resolved: Lead commit `42ba9035b06ca00fab60e8fdd8d07badbcf8b1f3`
  pins sounddevice 0.5.6, cffi 2.1.1 and pycparser 3.0 in `requirements-runtime.txt`
  and has been merged into this lane. This does not establish PN54 compatibility.
- Native input candidates can include virtual drivers; selection does not establish
  physical provenance. Runtime does not promote browser-declared AGC/gain/geometry
  assertions to verified capture. Actionable native Live remains gated.
- Real model enabling awaits approved MI300-adapted artifact, empirical calibration,
  operating envelope, compatible reference/baseline context and PN54 validation.
- Native clock tolerance and W=4 s/hop=1 s are transport profiles, not calibrated
  perception settings. Device index changes invalidate selection; reconnect is explicit.
- Worker stop requests cancellation and bounds thread joins to five seconds. Native
  driver calls and analyzers must cooperate; Python cannot preempt a hung native call
  or kill a blocked analyzer thread safely. Join timeout is surfaced.
- Recent baseline selection is limited to 128 retained frames. Immutable baseline,
  audit and idempotency history intentionally grows on disk with human/workflow actions.
  Standalone sessions without a durable sink retain their audit in memory.
- EOF suspends with `audio_eof`; explicit Resume replays an uploaded asset from its
  start on a fresh analysis run. Process restart requires a new session/clock.
- Worker metrics remain an internal Runtime diagnostic; no UI metrics contract was added.
- Processing and publication-age measurements are separate from confirmed-alert
  latency. Two independent four-second windows require eight seconds of support in
  the simulated anomaly policy. Empirical change-to-confirmed-alert latency awaits
  calibrated ML and the physical PN54 loop; none of these probes establishes it.

## Accepted checkpoint hold

Lead accepted `8ebaf632e9c19482f199a2e883fb43c7e803b509` as local RT-2A readiness.
The shared dependency sync and report correction do not authorize new features,
physical/ML enablement, Gate F acceptance or a merge of the lane implementation.
No capture or soak was rerun for this maintenance update.

Post-sync checks: all merged dependency pins matched the validation environment;
PortAudio imported and loaded; 79 shared/Runtime/integration tests and the unchanged
CP1 JS/HTTP/WebSocket/SQLite smoke passed. No new feature or enablement work began.
