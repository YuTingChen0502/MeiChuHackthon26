# Dataset-family uncertainty and listening trials

Presentation follows `docs/implementation/DATASET_PERCEPTION_HINT_FREEZE.md`.
The UI does not compute source levels, select anchor instruments, calculate
relative balance, or choose a direction.

- Setup says that instrument-family configuration does not validate recognition.
- Runtime `uncertain` remains uncertain for each dataset family. The
  `family_attribution_unvalidated` reason is explained as identification not yet
  validated; `partial_source_representation` explains incomplete family coverage.
  An explicit Runtime `unsupported` remains unsupported.
- Only a non-null current `adjustment_hint` can show a raising/lowering listening
  trial. It is labelled experimental and uncalibrated, with the majority-unchanged
  assumption visible. There is no numeric amount, probability, action button,
  incident, recovery claim or baseline mutation attached to it.
- Current source/frame identity, receipt freshness, connection and switch fences
  apply. Paused/stopped/missing/stale/dropout/clipped/incompatible/non-comparable
  audio cannot display a hint. The source must remain active, observable and
  valid. The bound instrument/family and identifiability assumption must match.
- Public numeric advice keeps its existing independent calibrated gates.
- Fixture/example labels and session deletion behavior remain unchanged.

## Validation

95 UI tests pass, including authoritative direction inversion, absent/null hint,
opposing numeric values that do not override the hint, source/quality gates,
malformed hint suppression, all five family uncertainty states and partial keys.
Existing real HTTP/WebSocket Fake regression passes (71 notifications on the final run).
These are presentation/transport checks, not model or physical-validation claims.

The additional reference recovery uses the approved mutually exclusive
`{reference_id}` request, never a microphone ID as an asset ID. First the operator
chooses Prepare stored reference; job completion does not change the session.
A separate Stop this session and start anew action stops listening, then creates
a new session with the same song and newly prepared immutable reference. Previous
history remains. Late creation responses cannot override deliberate session
switching. An unavailable original recording offers the existing Add song upload
form: historical stereo/custom WAV data may need the original WAV selected again.

Runtime integration used `0a0ffc59c3dba8e500107342a03fff7f6033e546`, followed by
the Runtime test-only correction `9645c7d0bd1a6d719fd507e4bb17708640f89f87`.
The isolated `live_reference_smoke.py --hint-smoke` passed with 34 notifications:
Runtime-generated lower/raise directions, no direction for global gain alone,
null public numeric/probability evidence, reconnect, pause/resume, reprepare reason,
actual retained-audio reanalysis, explicit new session and retained old history.
Its test-only confidence fixture remains `example_only: true`; production Fake
confidence is unchanged and no direction/hint is injected into Runtime.

Browser acceptance used the production UI at isolated localhost port 8101:
lowering and raising text remained experimental/uncalibrated with the simulation
notice; pause hid hints; reprepare displayed queued/ready states without retarget;
the separate new-session action moved from session-1/reference-1 to
session-2/reference-2, same song. GET confirmed the old session stopped and retained
its original reference. Reload retained both recent entries. The test tab and
temporary server were closed. No physical microphone was opened.

The review correction covers delayed creation after navigation: stop only the
exact newly created unadopted session through bound commands (up to four bounded
conflict attempts), without activating it or changing the selected session. A
failed cleanup exposes its exact session ID and recovery instructions. Unit tests
cover conflict/failure; actual HTTP/WS smoke confirms successful orphan prevention.
