# Bounded delayed candidate analysis — 2026-09-20

User correction inspected at `d267da4dc7aab72e9e3c291fe7a8017bf3b3a641`.
Sessions are continuous; the failure is a two-second evidence-age budget consumed
by roughly six-second CPU inference, not a four-second session lifetime. This
amendment supersedes the earlier prohibition on widening candidate freshness.

## Separate scheduling, completion and display

Host-selected `candidate_delayed_v1` is the default for the explicit candidate-p1
launcher. It uses queue admission age **2 s**, completed-result age **20 s** measured
from the unchanged capture END, experimental hint display **up to 10 s** from the
ORIGINAL publication, and UI local receipt watchdog **12 s**. The hint deadline is
`min(original_publication + 10, capture_end + 20)`. A new result supersedes the old
one immediately. Equal-frame refresh, reconnect and repeated snapshots never renew
the deadline. Pause/stop/source/reference/session change, disconnection, physical
gap, incompatible capture, stale result and contradictory evidence suppress it.

`strict_v1` preserves Fake/production defaults: queue 2 s, result 2 s, hint hold up
to 10 s but clamped to capture-end + 2 s, receipt watchdog 5 s. The candidate profile
is a host policy, not a model's self-authorization or a production accuracy claim.
No geometry change: candidate remains 44.1 kHz, 176400 samples, 44100-sample hop.
The application should disclose delayed analysis rather than call old audio instant.

Worker queue capacity remains two. Drop obsolete queued work and prefer the newest
complete window before inference; repeat the 2 s admission check after acquiring
the model lock. Do not extend admission age to 20 s or build a latency backlog.
Only completion/publication uses the result budget. A result older than 20 s is
stale and cannot create/clear an incident, recommend or verify recovery.

## Analysis skips are not missing PCM

An intentionally skipped analysis window is scheduling loss, not necessarily a
hole in the samples of the next complete four-second window. Track these skips
separately from native dropped packets, overflow, sample/clock/run discontinuity.
The optional internal worker `on_analysis_gap(window)` callback resets pending
anomaly persistence under the current session/source-generation fence before the
next analysis. It does not clear an incident, complete verification or cancel a
human adjustment. A contiguous intact next window need not carry `dropout=true`
solely because earlier inference work was skipped. Actual capture faults continue
to mark dropout/reset; never concatenate across missing PCM or fabricate samples.

Fresh post-adjustment full-window timing and all calibration/action gates remain.
Unverified native capture remains incompatible for advice. This timing amendment
can make real perception results visible but does not authorize otherwise blocked
directional advice or calibrated recommendations.

## Additive wire timing

Optional `SessionSnapshot.analysis_timing` contains `profile_id`,
`queue_max_age_s`, `result_max_age_s`, `hint_hold_s`, `receipt_max_age_s`, and
`snapshot_monotonic_s` (server clock at serialization). Budgets follow the profiles
above. Optional `InstrumentPerception.adjustment_hint.expires_monotonic_s` is the
fixed server deadline. With analysis_timing present, every non-null hint carries
that deadline; it must be later than server-now and no later than either bound.
No numerical audio amount or confidence is added. Older snapshots without timing
retain the existing conservative UI behavior.

UI maps server remaining lifetime to its local elapsed timer; it must not subtract
server monotonic timestamps from browser epoch time. Display observation age and
processing latency separately from local receipt age. Server stale/null evidence
always overrides client display time; no local hint resurrection or historical
recommendation masquerading as current. Numerical confidence gates are unchanged.

## Explain reference position honestly

Current P1 matches identical relative sample spans in the reference cache. Show
the compared interval derived from authoritative sample_start/end/rate as an
ASSUMED synchronized-start reference interval, not detected song position. Source
start/restart/switch begins a new sample origin. Starting late, tempo drift, seeking,
section jumps and looping are not solved. Absent matching reference coverage means
comparison unavailable while inference can still run; do not label it aligned.
No DTW/beat tracking/music-position research or reference retarget action is added.

## Semantic audit follow-up

The user supplied the read-only semantic-gate audit of `d267da4` (MIC-004/005/007/008).
Its prohibition on widening freshness is superseded only by the explicit delayed
candidate policy above; this does not claim one-second CPU inference throughput.
MIC-007 is a comparison-cache migration defect: after existing cache hash, model,
configuration and target binding checks pass, a genuine older compatible cache may
prevent comparison but must not suppress otherwise compatible source separation.
Keep migration reasons and comparison values invalid/null; never invent v2 levels
or bypass corrupt/incompatible identity, clipping or geometry checks.

MIC-005 does not authorize weakening command binding or automatic stale command
replay. Per-packet ADC/fallback timestamp-mode alternation is diagnostic metadata,
not a session lifecycle transition. Keep raw diagnostics internally; sample that
metadata when publishing a genuine capture lifecycle/result update, instead of
creating standalone durable transitions for every fluctuation. Actual source,
generation, quality and error changes must still publish. State-version,
idempotency, reference and generation checks remain unchanged. Add flapping-clock
and concurrent lifecycle regression coverage. MIC-008 presentation should explain
active capture awaiting a completed result and measured processing delay without
claiming an in-flight model call unless authoritative evidence supports that claim.

## Ownership and acceptance

Lead freezes wire/documentation/tests. Existing Runtime owner implements timing,
skip/gap separation, authoritative expiry/age, metrics and tests; existing UI owner
renders longer bounded hints and delayed/synchronized-start explanations. ML/model
weights and existing measurement math stay untouched.

Tests must cover 6 s inference acceptance vs 2 s queue rejection, >20 s result
rejection, bounded sustained slow execution, intentional skips vs actual PCM loss,
persistence reset, fixed expiry under repeat/reconnect, and every lifecycle gate.
Run canonical validation and actual Windows microphone/P1 smoke for at least120 s
when accessible, recording inference/publication ages, fresh/stale counts, skips,
queue bound and stop/reopen. Do not claim positive hints when another quality gate
blocks them, or claim Linux/PN54 validation without executing there.
