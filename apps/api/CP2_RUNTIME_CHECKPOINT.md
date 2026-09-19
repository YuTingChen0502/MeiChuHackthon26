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
- Runtime suite: 17 passed.
- Integration suite: 33 passed, including actual loopback transport.
- Unchanged CP1 JS RuntimeAdapter + HTTP/WebSocket + SQLite correction-loop smoke: PASS.
- Native local WASAPI smoke: six seconds, 48 kHz mono, 288768 captured samples,
  zero drops/discontinuities, exact captured-PCM/file-window replay parity. Gain,
  enhancements and physical geometry remain unverified. This is not PN54 evidence.
- The finalized implementation will be measured in a separate committed-code
  1200-second paced Runtime/API probe before final checkpoint reporting.

The earlier two-second native diagnostic over-detected callback timestamp jitter.
The corrected adapter anchors time to sample counts with a declared 50 ms ADC
residual budget; the six-second probe measured a 4.354 ms maximum residual. Overflow
status and missing sample spans still break continuity. The earlier diagnostic is
superseded, not positive evidence.

## Reproduction

Use Python 3.12.14 with the Lead-pinned runtime dependencies. The local native probe
used sounddevice 0.5.6, cffi 2.1.1 and pycparser 3.0 from a temporary environment.
The portable native backend follows the official raw-input/discovery API:
https://python-sounddevice.readthedocs.io/en/latest/api/raw-streams.html
https://python-sounddevice.readthedocs.io/en/latest/api/checking-hardware.html

```text
python -m unittest discover -s core/contracts/tests -v
python -m unittest discover -s tests/runtime -v
python -m unittest discover -s tests/integration -v
python docs/implementation/checkpoint1_smoke.py
python -m tests.runtime.sustained_probe --seconds 1200 --output <local-output>/sustained.json
python -m tests.runtime.native_probe --device-id <discovered-id> --seconds 6 --output <local-output>
```

Probe manifests record commit/config/source hashes, runtime, generated PCM procedure
or capture provenance, queue metrics and timing. Native WAV/raw float PCM stays in
local temporary output and is not committed or uploaded. No probe claims instrument
accuracy, calibration, meaningful MI300 adaptation or physical PA verification.

## Limits and external gates

- Lead must integrate the proposed native dependency pins in `requirements-runtime.txt`.
- Native input candidates can include virtual drivers; selection does not establish
  physical provenance. Runtime does not promote browser-declared AGC/gain/geometry
  assertions to verified capture. Actionable native Live remains gated.
- Real model enabling awaits approved MI300-adapted artifact, empirical calibration,
  operating envelope, compatible reference/baseline context and PN54 validation.
- Native clock tolerance and W=4 s/hop=1 s are transport profiles, not calibrated
  perception settings. Device index changes invalidate selection; reconnect is explicit.
- Worker stop requests cancellation and waits up to five seconds. A non-cooperative
  hung analyzer cannot be killed safely in a Python thread; timeout is surfaced.
- Recent baseline selection is limited to 128 retained frames. Immutable baseline,
  audit and idempotency history intentionally grows on disk with human/workflow actions.
  Standalone sessions without a durable sink retain their audit in memory.
- EOF suspends with `audio_eof`; explicit Resume replays an uploaded asset from its
  start on a fresh analysis run. Process restart requires a new session/clock.
- Worker metrics remain an internal Runtime diagnostic; no UI metrics contract was added.
