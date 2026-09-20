# Dataset-family attempts and listening hints — acceptance

2026-09-20. Tested integrated source:
`24c72baf27c5cb954bdfe0c563212152ee33fb8d`.

Accepted checkpoints:
- ML: `6b8152a64dac73e29043a8f33dc3b459329c4e75`.
- Runtime: `9645c7d0bd1a6d719fd507e4bb17708640f89f87`
  (implementation `e833adc08d44f1a7c1136170dd4e290a6f867797`).
- UI: `69b23d7760e49eae049008330f102dd6605a76b7`
  (initial presentation `a032a1ecc06ccaeaa7902c8d78cd4234d137dfd5`).

`python -B scripts/validate.py` passed on clean integrated source:
35 shared, 46 Runtime, 102 integration, 29 training, 55 analyzer and 38 benchmark
tests (305 Python total); 95 UI tests; three actual HTTP/WebSocket smokes; release
audit and self-tests with zero findings. The Live-reference smoke observed 68
notifications; the new uncalibrated-hint/reprepare smoke observed 34.

The actual frozen-weight P1 regression exercises six model outputs and file/mic
PCM parity. The transport/browser hint checks use explicitly simulated evidence;
they are not empirical musical, physical-room or confidence-calibration results.
See `docs/demo/DATASET_HINT_UI.md` for browser receipt and migration workflow.

Current behavior:
- All five normalized dataset families are attempted: bass, drums, guitar, keys,
  vocals. No hard-coded non-bass unsupported publication mask.
- Exact mapped source estimates remain separate from reliable identification.
  Unvalidated attribution is uncertain; keys has only a partial piano proxy and
  does not receive invented whole-family numerical values. Unknown labels remain
  insufficient evidence, not fabricated recognition.
- Optional experimental increase/reduce hints use current comparable evidence,
  at least three eligible anchors and existing median centering/threshold. They
  never supply public dB amounts, calibrated probabilities, incidents or recovery.
- Quality, freshness, source identity, calibration-only bypass and restart fences
  pass. Global gain does not create individual-instrument trial directions.
- Reference cache migration creates an explicit new reference/session on the same
  song; it cannot silently retarget old history. Verified retained WAVs are reused.
  Historical stores missing original stereo/custom-RIFF bytes may require the
  original file again; no lost bytes are invented.
- Session deletion remains integrated and tested. The cancelled/unadopted creation
  path stops only its newly created session, preserving the user's current session.

Frozen weights, original candidate manifests and historical empirical support are
unchanged. Historical bass-only matched-digital validation is not expanded by this
engineering change. CPU freshness limitations, calibration, MI300 lineage and
PN54/physical validation remain independent gates.
