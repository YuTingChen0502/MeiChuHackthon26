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

## Validation before Runtime checkpoint

94 UI tests pass, including authoritative direction inversion, absent/null hint,
opposing numeric values that do not override the hint, source/quality gates,
malformed hint suppression, all five family uncertainty states and partial keys.
Existing real HTTP/WebSocket Fake regression passes (68 notifications).
These are presentation/transport checks, not model or physical-validation claims.

The additional reference recovery uses the approved mutually exclusive
`{reference_id}` request, never a microphone ID as an asset ID. First the operator
chooses Prepare stored reference; job completion does not change the session.
A separate Stop this session and start anew action stops listening, then creates
a new session with the same song and newly prepared immutable reference. Previous
history remains. Late creation responses cannot override deliberate session
switching. An unavailable original recording offers the existing Add song upload
form: historical stereo/custom WAV data may need the original WAV selected again.

Actual new-hint transport/browser acceptance requires the separately routed
Runtime implementation.
