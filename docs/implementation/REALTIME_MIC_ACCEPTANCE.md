# Real microphone execution acceptance — 2026-09-20

## Verdict

**Windows native candidate execution: PASS. CPU real-time freshness: NOT PASS.**
This proves continuous physical microphone processing by the frozen P1 candidate;
it does not establish room accuracy, calibrated PA advice, or one-second inference.
Linux/PN54 and a second distinct physical microphone were unavailable and remain
unaccepted. Do not describe this as completion of every physical acceptance gate.

## Integrated correction

- Shared decision: `34474ea10e0658a3ae9743ca24d5714776ba754b` and
  [Live reference freeze](LIVE_REFERENCE_MIC_FREEZE.md).
- ML: `302926fadb62833338a0914b954d163f59f389b4`. Physical microphone input
  executes actual P1 inference. Missing comparison coverage also permits separation,
  while comparison remains invalid/null. No fabricated alignment or probabilities.
- Runtime: `11ee347b0ecc82934b314620ae969ad28387c200`. Logical inputs, zero-ADC
  fallback, bounded acquisition, source fencing, rollback and same-session restart.
- UI: `ecae296cd69a83e33e8b153dd0effb7484f38551`. Live-only reference workflow,
  independent perception/actionability, honest configured-family labels and visible
  rollback acknowledgement even while waiting for fresh model evidence.
- All-lane executable integration before final UI wording: `5ac8a81bd4291da6b71accc889d6ab0f815c0674`.
  UI follow-up merge: `eae1da72c67cc4dc6729f81a456086337589de76`.

The user explicitly authorized Lead to finish the narrow ML/Runtime changes in
their existing worktrees after those tasks stopped on an account usage limit.
No replacement lanes, model training, architecture change or freshness widening.

## Actual Windows evidence

[Full execution report](evidence/candidate_native_5ac8a81.json),
[metrics](evidence/candidate_native_5ac8a81_summary.json),
[speaker playback record](evidence/candidate_native_5ac8a81_playback.json),
[same-session restart](evidence/candidate_restart_5ac8a81.json).

| Check | Actual result |
|---|---|
| Native capture duration | 600.476 seconds across five 120-second source runs; 619.013 seconds wall time |
| Real model execution | 97 completed HTDemucs calls, including late completions fenced from publication; 18/20/18/18/18 completed current-source calls at segment checkpoints |
| Model output | Actual drums, bass, other, vocals, guitar, piano outputs with hashes/levels in diagnostics |
| Frontend/windows | Native input negotiated separately; canonical 44,100 Hz, 176,400 samples, 44,100-sample offered hop |
| Continued execution | Model calls continue beyond 32-second reference coverage and after discontinuities; comparison stays unavailable |
| Model latency | 6.012 s p50 / 6.435 s p95, measured actual model calls only |
| Publication age | Per-run p95 up to 8.474 s; exceeds unchanged 2 s freshness gate |
| Backpressure | Queue maximum 2; 440 old-window drops; 17 stale/cancelled windows |
| Native integrity | Zero callback-queue drops; 8 reported discontinuities, not fabricated missing audio |
| ADC fallback | Actual `sample_count` capture remained running; missing ADC timestamp alone was not fatal |
| Switching | Same session/reference retained; fresh clock/generation for each switch and failed-selection rollback; old-source frames never current in sampled snapshots |
| Stop/reopen | Actual stream released and new session captured/inferred again |
| Restart | Same session-6 reconstructed candidate and completed two model calls before and after application restart; same reference, new clock/generation |
| Bounds | Sampled analysis queue <=2, frames/hashes <=128, events <=128; RSS 677 MB cold to 1,962 MB peak with model allocations; this is not a proof of unlimited-duration constant RSS |
| Physical sound | A generated four-second low-level tone played through Realtek speakers during native capture; no acoustic attribution/accuracy ground truth claimed |

Only one physical Realtek array was available. Backend aliases are not two distinct
microphones. Raw native endpoints remain internal diagnostics; ordinary selectors
use logical names. A generated 32-second reference was reused with exact compatible
model/profile identity. No microphone PCM or separated stems were saved.

## UI and action evidence

The UI owner observed the actual production UI at port 57181 against the above
candidate session, not a Fake browser harness. Session-4 remained on reference-1
while generations 2, 4, 7 and 9 arrived through Runtime. Reload/reopen retained the
same session. Stop reached generation 10; new session-5 used a fresh identity.
The source selector showed friendly logical names. Bass was Uncertain and the four
other configured families Unsupported. Advice and probabilities remained withheld.
No positive detection was claimed from these stale CPU results.

Two narrow presentation errors discovered during physical observation were fixed:
configured families had been described as supported, and a listening/rolled-back
source lacked an ordinary recovery acknowledgement. Current error/stopped/paused
states continue to outrank historical rollback. Duplicate disconnected-service
notices remain a non-critical presentation follow-up; no state or evidence is
promoted by them.

Final browser retest on `eae1da72c67cc4dc6729f81a456086337589de76` at port 8014
verified both corrections with real candidate session-6/reference-1. One rollback
attempt failed with a PortAudio host error: generation 9 correctly displayed
Microphone unavailable. Explicit logical selection recovered at generation 12.
One bounded failed-selection retry successfully restored capture at generation 14;
the ordinary banner read **Restored · Listening — waiting for fresh audio**, with
uncertainty and advice-withheld text. This was inspected with Technical details
closed. Bass remained Uncertain and the other families Unsupported, with no numbers.
[Final authoritative snapshot](evidence/candidate_browser_eae1da7.json) records the
successful retry without erasing the earlier failed rollback. The test session was
then explicitly stopped and its microphone released.

## Reproduce

Use the documented candidate dependencies and a Python environment containing
PyTorch, Demucs, NumPy, the Runtime dependencies and sounddevice. The actual run
used Python 3.14.3/Torch CPU with isolated sounddevice dependencies; it does not
certify another host's providers or speed. From repository root:

```text
python scripts/validate.py
python -m tests.runtime.real_candidate_native_probe --storage .pa-runtime/canonical-live-p1-5ac8a81 --output .pa-runtime/candidate-native-report.json --segment-seconds 120
python -m docs.implementation.evidence.candidate_restart_5ac8a81
```

The native probe creates its generated reference/cache if absent. First preparation
performs real inference and takes additional time. It starts its own temporary
HTTP/WS server and prints the port. The archived restart script uses the exact
storage path above and must run only after the native probe releases the microphone.
The restart script's SHA-256 is recorded in its evidence JSON.

For the product UI, run one candidate server (no separate frontend process):

```text
python -m apps.api.launch --mode candidate-p1 --bundle models/candidates/nano4-p1-adapted-mvp-v1 --storage .pa-runtime/manual-candidate --port 8014
```

Open `http://127.0.0.1:8014/apps/ui/`. Add song/configuration, upload a rights-cleared
PCM16 WAV ideal reference, prepare it, enter Live and select a logical microphone.
Each new source generation starts relative sample zero: start the performance or
playback from the beginning of the reference. Missing spans do not wrap or guess.
Control-C stops the server and releases capture. Do not run competing capture probes.

## Remaining acceptance boundary

The execution blocker is removed. A faster tested execution environment is still
needed for fresh one-second-hop perception on this model. Do not loosen freshness
or label old outputs Detected to conceal CPU latency. Linux/PN54 capture, distinct
physical-device switching, MI300 competition lineage, physical-room accuracy and
fitted calibration each require their own actual evidence.
