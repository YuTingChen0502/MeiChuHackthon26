# Harmonix demo workflow audit and implementation intent

Audited production code at `95fa5fed576d6e45f608f413bc84167161d34f13` before product edits. Browser walkthrough used the actual UI/Runtime API with FakeAnalyzer, synthetic test audio and an isolated deterministic microphone adapter. Also checked the ordinary Fake launcher with unavailable native capture and uploaded-file EOF. These are functional checks, not physical/model validation.

## Phase A: visible-element inventory

Repeated instances inherit their component classification. Nothing below authorizes a contract, evidence, or gate change.

| Surface / visible elements | Classification | Intended treatment |
| --- | --- | --- |
| Harmonix wordmark, song name, workflow label | KEEP | Quiet shared navigation; remove duplicate hero state badges. |
| Home headline, description, Add new song | SIMPLIFY | One primary Add song; concise workflow promise. |
| Recent-song buttons | KEEP | Song names, not session IDs. |
| Session ID field / Open existing song | DEBUG-ONLY | Secondary connection disclosure. |
| Fixture rehearsal / live shortcuts | MOVE TO SECONDARY | Explicit example disclosure; never silently interpret an upload as real analysis. |
| Song name / reference file / source / microphone selector | KEEP | Setup only; clear labels and file format requirement. |
| Project name | MOVE TO SECONDARY | Optional organization disclosure; preserve submitted value. |
| Instrument family labels, quantities, +/- | KEEP | Known song configuration; accessible individual button labels. |
| Custom family input / Add instrument | MOVE TO SECONDARY | Optional additional instruments. |
| Long configuration/source/device explanations | SIMPLIFY | Short product guidance; simulated input and unsupported limitations stay explicit. |
| Setup Back / Analyze and start | KEEP | One primary Prepare reference; Back secondary. |
| Preparation progress, progress bar, repeated bottom status | SIMPLIFY / REMOVE | Dedicated busy layout and one progress message; prevent duplicate submission. |
| Source state / frame age | KEEP | One compact current connection status; stale remains explicit. |
| Fake/Real/fixture truth notice | SIMPLIFY | Concise always-visible evidence boundary; exact bundle/provider in details. |
| Model/support disclosure | MOVE TO SECONDARY | Support restrictions also remain visible on relevant instrument rows. |
| Session/reference/baseline IDs, provider, model, clock/run/sample interval | DEBUG-ONLY | Diagnostics disclosure; exact values preserved. |
| Reference/baseline summary | KEEP | Quiet context, never dominant. |
| Instrument names, status, authorized relative dB | KEEP | Compact observations; unknown/unsupported never rendered normal or zero. |
| Initial-letter icons and repeated evidence-history bars | REMOVE | No needed decision information; not audio waveforms. |
| Confidence probabilities, intervals and reason codes | SIMPLIFY / DEBUG-ONLY | Uncalibrated/abstained explicit; detailed calibrated event meaning in disclosure. No invented percentages. |
| Start rehearsal (already in rehearsal) | SIMPLIFY | Full-band listening first; optional guided soundcheck secondary. |
| Guided prompts, progress, highlighted family | KEEP | Focused optional sampling step. |
| Skip / Continue without qualifying evidence / Next performer | SIMPLIFY | Skip sample secondary; Continue only after received evidence. |
| Calibration review title, human-approval explanation | SIMPLIFY | Dedicated baseline review layout. |
| Accepted by / intentional reference difference / Accept as Baseline | KEEP | Explicit human approval and exact selected interval unchanged. |
| Use latest observation | KEEP | Secondary refresh of reviewed evidence; no automatic baseline. |
| Start Live | KEEP | Primary only after accepted baseline; Runtime gates intact. |
| Live normal title and all repeated status blocks | SIMPLIFY | Quiet monitoring, compact family coverage, no unnecessary main CTA. |
| Anomaly instrument / deviation / suggested correction | KEEP | Dominant decision surface; no inferred mixer fault. |
| Start adjustment / Complete adjustment / Recheck | SIMPLIFY | Separate adjust, completion, and focused verification stages. |
| Pause / Stop | MOVE TO SECONDARY | Session options, except Resume when suspended. |
| Verification outcome / before-after values | KEEP | Focused fresh verification; numeric display only if observable. |
| Recovered result | SIMPLIFY | Clearly close loop; explicit Return to monitoring affects presentation only. |
| Fixture scenario selector | DEBUG-ONLY | Example controls; never send fixture truth to Runtime. |
| Raw failures / raw suspension reasons / stale success toast | REMOVE | Product explanation with exact technical details in secondary disclosure. |

Observed demo risks: setup stayed actionable during preparation and duplicated progress; file EOF displayed raw `audio_eof` twice beside an obsolete “ready” message; Live transition displayed a false probe-cancel warning; all adjustment stages retained the same anomaly layout; recovery remained a secondary box with no clear return action. Runtime clears resolved incidents, so recovery presentation must bind the supplied verification to the current baseline/session rather than require an incident that no longer exists.

## Canonical state flow

| State / primary user question | Visible / layout hierarchy | Hidden | Primary CTA / secondary | Transition |
| --- | --- | --- | --- | --- |
| HOME: Which song? | Editorial entry, Add song, recent songs | Setup, monitoring, diagnostics | Add song / recent song | SONG_SETUP or restored current state |
| SONG_SETUP: What are we listening to? | Reference + known instruments + input; preparation replaces editable form while busy | Baseline, live controls | Prepare reference / Back | Successful reference job and session → REHEARSAL; failure restores inputs |
| REHEARSAL: Does the band sound right? | Full-band listening prompt then current observations; optional guided sampling | Setup; Live controls | Review balance / guided soundcheck | BASELINE_CONFIRM; active incident uses correction flow first |
| BASELINE_CONFIRM: Is this the balance to keep? | Reviewed observation and explicit approval; accepted confirmation replaces form | Setup and unrelated session controls | Accept as Baseline, then Enter Live / latest observation | Runtime acceptance and explicit Live command |
| LIVE_NORMAL: Do I need to act? | Quiet monitoring or explicit unavailable/unsupported state, compact coverage | Setup, calibration, correction buttons | None; listening is the task / session options | Authoritative incident → LIVE_ANOMALY |
| LIVE_ANOMALY: What should I adjust? | Instrument → authorized deviation → recommendation | Normal-grid detail, setup, baseline | Start adjustment, then I've adjusted | Completed adjustment → VERIFYING |
| VERIFYING: Did the adjustment work? | Focused verification, fresh-evidence explanation | Old recommendation and unrelated controls | Listen again, then no CTA while request is armed / retry if inconclusive | Runtime verification → RECOVERED or continued correction |
| RECOVERED: Can we continue? | Calm conclusive result, authorized before/after if available | Old anomaly prompt | Return to monitoring | Presentation acknowledgement → LIVE_NORMAL; no server state mutation |

Safety interruptions (paused, stopped, disconnected, stale, unsupported) override positive presentation. Reconnect restores server state; a lost local recheck acknowledgement offers an explicit recheck rather than pretending analysis was armed. Recovery acknowledgement is bound to the exact verification/session/baseline and cannot hide a new incident.

## Phase B constraints

Reuse RuntimeAdapter, command versions/idempotency/conflict refresh, cursors, source discovery, upload/job chain, guided probe endpoint, and selected baseline interval. No new frontend app, inference, confidence calculation, automatic mixer action, baseline mutation, or candidate/physical claim. Use existing Harmonix tokens, neutral dividers, whitespace, functional typography and small radii. Green is reserved for server-verified recovery.

## Implementation and validation record

- Presentation state selection and product error translation are in `apps/ui/workflow.js`. RuntimeAdapter and all public contracts are unchanged.
- Preparation hides the editable form, prevents duplicate submission, and restores the same inputs on failure. Setup no longer creates an implicit fixture session from a failed real upload.
- Rehearsal offers full-band review first, with guided soundcheck as a secondary option. Baseline review shows the observation bound to its submitted interval, not an unrelated newer frame. Approval and Enter Live remain separate guarded commands.
- Completed adjustment and armed verification are distinct. The local acknowledgement is session/adjustment/result-bound, including retries after an inconclusive result. Acknowledging recovery changes presentation only.
- Session options, organization, custom families, exact model/quality/identity data and raw errors are disclosures. Connection state, evidence age, Fake/candidate/fixture identity and unsupported/uncalibrated restrictions stay visible where relevant.

Validation: `node --test tests/ui/*.test.mjs` — 50 passed. `python -B scripts/validate.py --runtime-only` — 28 contract + 32 Runtime + 65 integration tests, all 50 UI tests, real-adapter HTTP/WS/SQLite Fake E2E and release audit passed. One intermediate integration run encountered Windows localhost `ConnectionResetError` (10054); a complete rerun passed without Runtime changes.

Manual browser walkthrough, actual production UI at the default 1265 × 720 viewport:

| Check | Observed result |
| --- | --- |
| Home → Add song → upload → microphone → reference job | One primary action; busy preparation replaces setup; rehearsal appears only after successful job/session creation. |
| Rehearsal → review → Accept as Baseline → Enter Live | Distinct layouts; explicit approval; Enter Live disabled until fresh evidence arrives. |
| Live normal → anomaly → adjustment → verification → recovery | Quiet monitoring; dominant authorized deviation/correction; one Start adjustment / I've adjusted / Listen again action at a time; Re-listening has no competing CTA; Back in range closes the loop. |
| Return to monitoring | Presentation acknowledgement only; no baseline or mixer mutation. |
| Anomaly viewport | Primary Start adjustment bottom at 646px within the 720px viewport; no horizontal overflow. |
| Invalid reference upload | Product-language failure; original setup inputs restored; exact details collapsed. |
| Microphone unavailable / source switch / file EOF | Missing-device guidance; microphone selector disappears for Uploaded File; EOF is translated, not shown as `audio_eof`. |
| Pause/resume, reload/session reopening | Authoritative state restored; relevant controls only; no false probe-cancel warning. |
| Disconnect after recovery | Fresh-audio interruption replaces positive state; numeric balances withheld; no dominant correction action. |
| Offline examples / abstention | Explicit illustrative labels; no Runtime commands; insufficient evidence shows no numeric balance or healthy substitute. |

Successful Fake walkthrough produced no browser warnings/errors. This is functional/UI evidence only: no live physical microphone, PN54 acoustic path, RealAnalyzer accuracy, or calibrated candidate-confidence claim. Candidate limitations and Runtime physical gates remain dependencies, not bypasses.
