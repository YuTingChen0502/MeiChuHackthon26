# Candidate delayed native acceptance — `be58f3e`

This is Windows execution and lifecycle evidence, not model accuracy, calibration,
production authorization, or Linux/PN54 acceptance. The scalar JSON receipt is
`candidate-delayed-native-be58f3e.json`; no microphone PCM or separated stems were
saved.

- Source: `be58f3e196d6e333d6fc0d57acf3716878239b07`, clean at probe start.
- Profile: host-selected `candidate_delayed_v1`; 2 s queue admission, 20 s
  completed-result age, 10 s fixed hint hold, 12 s UI receipt watchdog.
- Capture: 120.361 s over six approximately 20 s segments: initial input,
  pause/resume, two applied source selections, failed selection with rollback,
  stop, and new-session reopen.
- Model: 22 completed actual P1 backend calls, including retired/fenced work. Worker
  metrics recorded 15 published windows; sampled snapshots contained 12 unique
  fresh frames.
- Timing: model processing p50 5.060 s / p95 5.573 s; completed-result age p50
  5.615 s / p95 6.190 s.
- Bounds: inference queue maximum 2; 70 obsolete analysis windows dropped/skipped;
  7 stale/fenced windows; zero native callback drops. Two capture runs reported one
  discontinuity each and were handled through the physical-gap gate.
- Controls: pause and resume succeeded; two switches applied; an unavailable input
  rolled back; both stop operations succeeded; reopen completed three model calls.
- Browser receipt: a fresh frame rendered 5.6 s after capture and 0.1 s after local
  receipt. The UI disclosed delayed analysis and an assumed synchronized-start
  5.0–9.0 s reference interval. It did not claim detected song position.
- Evidence: bass rendered Detected / uncalibrated while guitar, drums, vocals and
  keys remained uncertain. Advice, numeric confidence and adjustment hints stayed
  withheld. Native capture remained unverified for advice; timing did not bypass
  that gate.

Only one physical Realtek array was available. Host API aliases do not establish a
second microphone. Linux/PN54, a distinct second physical microphone, labeled room
accuracy, calibrated confidence, and production support remain unverified.
