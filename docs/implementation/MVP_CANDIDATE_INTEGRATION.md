# MVP candidate product integration — 2026-09-20

Status: **engineering candidate integration complete**. Executable integration:
`a84d026f931463efa5485e36c98f2f136b4db2b7`. This does not authorize production
numerical perception or claim a physically validated real-model correction loop.
The earlier complete module inventory in `MVP_PRE_MODEL_READY.md` remains the
model-independent acceptance record; this document updates its model-waiting rows.

## Accepted checkpoints

| Lane | Accepted checkpoint | Integrated behavior |
|---|---|---|
| Nano4 publication | `01eaf5ddcc439efe799be61e54589d331c8556c6` | Frozen candidate, exact checkpoints and provenance retained without squashing |
| ML | `795f179bde8bbae9b3e25b8a591e2d25735ddfde` | Offline HTDemucs reconstruction, prepared references, frozen raw AnalyzerEvidence, support and failure gates |
| Runtime | `f9098018d0bfd2f501058ce6190d1403a48be12c` | Candidate factory injection, full identity binding, native framing/quality and API orchestration |
| UI | `6cef9d5006f2a72847227297ba6766f19bfb464f` | Runtime parity, candidate/source states, reference progress and corrected baseline review |

All checkpoint changes stayed within lane ownership. Main and the UI checkpoint
were clean before the final merge. Public contracts and their meanings are unchanged.
Existing worktrees remain authoritative; no replacement lane was created.

## Product and evidence boundaries

The complete deterministic Fake-backed product remains available: song/setup,
reference analysis, guided rehearsal, explicit baseline acceptance, explicit Live,
anomaly/recommendation, human adjustment and fresh-evidence verification. Native
microphone capture and bounded sustained acquisition are separately exercised.
Candidate mode uses the same analyzer, Runtime, API and UI boundaries.

The candidate supports raw bass evidence only within matched-digital comparisons.
Other named families remain unsupported and unknown families lack evidence.
Confidence is uncalibrated; probability remains null. Core's existing minimum-valid-
source identifiability and calibration gates remain intact, so the bass-only
candidate cannot authorize centered numerical balance advice. Physical microphone
candidate evidence abstains. This is intentional safe behavior, not a real acoustic
capability demonstration.

The UI correction removes invented no-frame baseline intervals, automatically
rebinds review after run/clock changes, and allows explicit selection of the latest
Runtime interval without losing operator inputs. The submitted clock belongs to the
reviewed interval. The UI owner exercised actual form submission to a Fake-backed
baseline; subsequent Live rejection of unverified capture remained enforced.

## Validation and reproducibility

Final integrated command:

```text
python -B scripts/validate.py
```

The Lead validation environment uses Python 3.14.3 with the existing CPU ML packages
and Node 25. Results: 234 Python tests (shared 28, Runtime 32, integration 60,
training 29, analyzer 47, benchmark 38), 39 UI tests, unchanged complete Fake
HTTP/WebSocket/SQLite correction-loop smoke, and release audit/self-tests PASS.
Existing dependency deprecation warnings do not change those results.

Actual CPU candidate Runtime execution was independently tested by the Lead at
clean `42695c4f122fff0297989ec787ff8187fbe6a6c6`, before the UI-only merge:
`evidence/p1_runtime_42695c4.json`. It covered reference/cache, uploaded generated
audio, synthetic microphone framing, safe abstention, HTTP and WebSocket replay
in 20.052 seconds. It is not a physical microphone or accuracy measurement.

The Runtime checkpoint retains actual local native capture and a 300.063-second
Fake-backed soak: 296 windows, zero drops/stale/gaps, histories capped at 128,
queue peak 1 of 2, post-warmup RSS 62.97–68.67 MiB. Native lifecycle probing
covered two runs, pause/resume and device release. These are local host results,
not PN54 results and not sustained P1 inference results.

ML's recorded CPU observation took 7.929 seconds for four seconds of audio.
This host is not established as a realtime candidate deployment. The remote H200
measurement must not be relabeled CPU or PN54 latency.

## Remaining execution gates

1. Accept meaningful MI300 adaptation and its exact artifact/evidence lineage.
2. Measure the supported operating envelope on held-out data, fit and validate
   confidence calibration, then freeze the approved production bundle.
3. Validate export/provider parity and sustained model performance on PN54.
4. Perform rights-cleared speaker-room-microphone correction/verification trials;
   record final measured evidence and video.

An integration adapter may be reused for a compatible MI300 bundle; compatibility
must be validated, never inferred merely from a similar filename. Current frozen
fresh-final exposures cannot become untouched evaluation data again.

No remaining generic product implementation is assigned to the three workers.
They should sync the final pushed main and stay on standby for concrete evidence-
driven integration corrections. Fake regression mode must remain available.

Private Git history and restricted research WAVs are not approved public release
material. Use the existing scanned, history-free source export route described in
`docs/release/RELEASE_READINESS.md`; model/data redistribution requires separate
rights review. No repository visibility change or public history publication is
authorized by this acceptance.
