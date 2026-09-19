# UI / Demo checkpoint review V1

Reviewed commit: `33a68e154e2d458c6808b79757837dcff753feee`.
Starting freeze: `f22f1e161bb69964765ba58305f7f169950f945c`.
Date: 2026-09-19. Reviewer: engineering Lead.

## Correction update

Correction commit `6187c69080da91f20633ce17be9c174e62a0a7a7` was source-reviewed;
the Lead repeated the UI suite with 7/7 passing. It resolves the remaining fixture
interval/probability-event mismatch, bounds the example step to -2 dB, adds Resume,
uses text-safe DOM construction and requires explicit human declarations before
preparing acceptance. The UI lane reports browser QA of these states and gates.
This supersedes the earlier fixture-polish findings below. The Lead has not
independently verified audible playback or physical capture.

The corrected UI is accepted as a fixture checkpoint. Live integration remains
pending the Runtime listener: select a genuinely qualified multi-frame interval,
use authoritative command outcomes/reconnects and establish advancing data age.
A checkbox declaration over the current fixture frame does not establish Runtime
baseline eligibility. No UI merge was performed during this review.

Correction commit `acd61d31f5ff722669b4d27359d01ac37fac6701` was source-reviewed and
its UI suite passed 7/7. It now calls HTML media playback with event-derived status,
separately labels confidence tolerance and interval, preserves inactive/unsupported
labels, discloses static fixture age, and matches rehearsal frame families to the
declared configuration. These supersede the corresponding original-code findings
below. Actual audible/browser validation was not performed by the Lead.

Historical findings at `acd61d3`: the generated anomaly still carries interval [-1.1,1.2]
beside +4.1 dB, and normal cards still use joint_anomaly_numeric_correct. Correct those
fixtures before the integrated demo; the formatter itself now preserves the fields.
The later correction above resolves Resume, text-safe rendering, explicit human choice
and the fixture policy step. Runtime interval selection and actual integration remain.

Setup payloads and transport selection are now available in
`contracts/PA_SETUP_TRANSPORT_V1.md`; this is not a listener-availability announcement.

## Disposition

The original `33a68e1` commit was a fixture-rendering checkpoint with useful session command binding
helpers. It is not yet accepted as a runnable playback demo or a completed UI
integration checkpoint. No cherry-pick/merge was performed in this review.

The existing Gate-0 shared freeze remains valid. The findings below are UI/Demo
implementation issues, not reasons to redesign the architecture or contracts.
Live upload/mutation integration separately depends on Runtime's published handlers.

## Validation performed

- Verified the reviewed commit descends from the declared freeze.
- Verified it does not change `contracts/` or `core/contracts/`.
- Ran `node --test tests/ui/app.test.mjs`: 5/5 passed.
- Ran `python -m unittest discover -s core/contracts/tests -v` with the existing
  temporary jsonschema 4.23.0 environment: 21/21 passed. The missing local package
  is no longer an unverified contract gate for this reviewed commit; no shared
  dependency/config edit was needed.
- Evaluated the commit's actual `fixtureScenario` and `showcaseFrame` functions
  without starting browser code, and validated both resulting snapshots through
  `validate_snapshot`: structural/binding checks passed.
- Read the isolated player source: no imports or calls to UI/runtime/analyzer were
  found. This establishes code separation, not acoustic playback or runtime isolation
  under a future deployment configuration.
- No browser visual QA, audible playback, or physical microphone test was performed.

The five UI tests exercise selected pure helpers, not the player, rendered confidence
meaning, time progression or complete card-state coverage. Passing the shared schema
does not establish all cross-record/product invariants; the checks below found gaps.

## Required UI / Demo corrections

### 1. Player claims playback without playing audio

At `demo_player/player.js:10`, clicking Play only changes text to "Playing ...".
There is no audio element, Audio instance, source URL/file selection or playback call.
Consequently this checkpoint cannot produce the advertised speaker -> microphone path.

Keep isolation, but implement local playback of operator-selected rights-cleared
mixed clips. Explicitly handle no clip, playback failure, pause/stop and completion.
Only show Playing after playback actually starts. No stems, gain labels or playback
controls may enter the analyzer. Test a real media-call boundary; physical playback
validation remains a separate later gate. Assets need not be bundled to make local
file playback possible.

### 2. Confidence tolerance is mislabeled as uncertainty

At `apps/ui/app.js:45`, `magnitude_tolerance_db` is rendered as `+/- tolerance dB`.
The frozen field defines the error tolerance in the calibrated correctness event;
it is not the prediction interval. The current guitar fixture displays
"92% confidence · ±1.5 dB" while carrying an unrelated interval `[-1.1, 1.2]`
for an estimate of +4.1 dB.

Render the actual probability-event meaning and label the tolerance explicitly, or
display the supplied `prediction_interval_db` as an interval. Do not synthesize one
from the tolerance. Make the illustrative interval and probability-event fixtures
consistent with the displayed anomaly/normal states. Add a formatter test that
distinguishes tolerance from interval.

### 3. Known inactive/unsupported states are lost

At `apps/ui/app.js:12-17`, abstention takes precedence over inactivity, and unsupported
is collapsed into Not Observable. The actual live fixture renders inactive drums as
"Abstained / Unknown". The test at `tests/ui/app.test.mjs:14` endorses that collapse.

Preserve Inactive and Unsupported as explicit primary statuses and show abstention
reasons alongside them. Keep all numeric balance values withheld when abstained.
Supply fixture coverage for too-quiet, inactive, unsupported and unknown as well as
normal/too-loud, so the UI checkpoint actually demonstrates its claimed conditions.

### 4. Reported age is a fixed fixture value

At `apps/ui/app.js:77`, `freshness` is always called with publication time + 0.6.
Nothing advances that value as the tab sits without observations. A pure helper test
using caller-supplied time does not verify the rendered view.

In fixture mode, explicitly label age as simulated or provide an advancing fixture
clock with stale scenarios. Before live integration, establish a server/session clock
mapping or truthful local receipt-age display; do not subtract browser timestamps from
server monotonic timestamps without a mapping. Stale/expired recommendations must not
appear actionable. Test the rendered time progression or clearly labeled fixture mode.

### 5. Rehearsal fixture disagrees with the declared instruments

`showcaseFrame` always adds vocal, but `start` builds its rehearsal snapshot from the
unchanged three-family reference fixture. Evaluating this code yields configured
families `[guitar, bass, drums]` and rendered IDs `[guitar, bass, drums, vocal]`.

Build each fixture coherently from its configuration, or define a separate four-family
fixture with matching versioned identities/coverage. Do not append a card absent from
the declared configuration. Add a cross-record fixture assertion; existing structural
schema validation intentionally does not prove this invariant.

## Before connecting real session data

- Add the missing Resume control for paused sessions and preserve current bindings.
- Replace unescaped snapshot strings interpolated into `innerHTML` with text-safe DOM
  rendering. Song names, family names and reason/hint strings are contract data, not HTML.
- Acceptance needs a selected technically qualified interval and an explicit human
  reference-difference choice; do not submit the current fixed `true` choice or assume
  one four-second frame satisfies baseline coverage.
- Keep bounded recommendation fixtures consistent with the selected Runtime policy;
  the current -3 dB fixture differs from the design's initial maximum 2 dB trial step.
  Final action policy remains PA/Runtime-owned; UI never computes its own correction.
- Actual command retries/reconnects must reuse keys only for identical retries and
  consume authoritative snapshots. Console logging alone is correctly fixture-only.

## Ownership and Runtime handoff

The Lead assigns `docs/demo/` and `tests/ui/` exclusively to UI / Demo in the
implementation plan. Existing UI tests/docs can remain there. No other root tests or
documentation ownership is implied. Corrections above belong to the UI lane; this
review makes no edits to its implementation files.

The user's CROSS_LANE_REQUEST was relayed to the existing Runtime task
"Implement PA Core vertical slice": publish implemented L2 setup/upload/reference-job
payloads/handlers, session commands, snapshot/events/reconnect details, launch
instructions and exact commit for Lead review. Runtime remains the owner of that API.
UI must not invent competing setup payloads or simulate accepted mutations meanwhile.

Re-review the corrected UI commit and actual Runtime API checkpoint before integration.
Do not label this fixture checkpoint as audio ML, calibrated accuracy or PN54 evidence.
