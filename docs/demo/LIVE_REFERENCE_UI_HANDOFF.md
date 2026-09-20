# Live-reference UI checkpoint

2026-09-20. This supersedes the public rehearsal/baseline flow in
`DEMO_WORKFLOW_UX_AUDIT.md` following the explicit Lead/user policy change.
Shared authority: `LIVE_REFERENCE_MIC_FREEZE.md` at `34474ea10e0658a3ae9743ca24d5714776ba754b`
(including perception amendment `1b1a489994a33d03f7841e9304cf0c43ad0e43fd`).

## Workflow and presentation decisions

| State | Primary question / information | Primary action / transition |
| --- | --- | --- |
| Home | Which song? Saved songs and clearly separate offline examples. | Add song or select a saved song. |
| Setup | What is the reference and known configuration? Friendly logical mic or uploaded-file input. | Prepare reference; dedicated job-progress/failure layout. |
| Legacy song | Can the existing reference be reused? Prior baseline/history remain untouched. | Listen with this reference; create new-policy session without upload/analysis. |
| Listening | What is actually being heard? Uploaded reference is fixed; Runtime perception and independent advice authorization. | No dominant CTA while waiting/monitoring; microphone selection stays available. |
| Anomaly / adjustment | What needs attention? Only authoritative current advice is foregrounded. | Start adjustment, then I've adjusted; never mixer control. |
| Verification | Did the change help? Only authoritative post-adjustment result. | Listen again when a new check is needed. |
| Recovered | Did verification close this incident? | Return to monitoring; acknowledgement changes presentation only. |
| Switching / unavailable / paused | Which input was requested, which actually opened, is audio current? | Persistent mic selection; explicit Resume when paused. |

Removed from the public path: rehearsal, guided probes, baseline review/acceptance,
Start Live. Retained internal legacy adapter helpers/tests do not create a second
public product flow. Setup disappears after successful session creation. Technical
IDs, masks, reasons, bundle/provider and exact errors remain in closed disclosures.
Neutral Harmonix styling is retained; no new visual features or inference logic.

## Binding and truth boundary

- Setup always calls `setupLiveReference`, retaining the existing upload/job transport,
  then `workflow_policy: live_reference_v1`. No client rate or capture fingerprint.
  Missing microphone does not prevent session creation; Runtime returns unavailable.
- Only `audio-devices.microphones` populates normal selectors. Raw endpoints are diagnostic.
- `switch_microphone` uses the existing bound command envelope with state version,
  reference/event, idempotency key and expected source generation. It neither recreates
  the session nor uploads/analyzes the reference again. Uncertain transport retries reuse
  the same command/key. HTTP 200 is operation acceptance, not successful acquisition.
- First PCM may produce `applied` + `listening` + `frame_fresh=false`. This does not
  authorize detection or numerical advice. Pending/rolled-back/failed are explicit.
- Recognition labels come only from Runtime `perception.state`. Raw masks never become
  client-inferred detection. `Detected · uncalibrated` remains visible even with downstream
  unknown/abstained InstrumentState. Advice is withheld unless Runtime explicitly permits
  it and current calibrated, non-abstained public evidence contains the numeric value.
- Source generation/run/clock/endpoint/reference and receipt freshness fence old display.
  Switch/reconnect/session transitions cannot restore prior-source advice or recovery.
  The mic select DOM survives frame refreshes so an open choice is not destroyed.
- Product errors explain lost input, expired observations, reference failure or connection
  failure; raw errors remain in details. Fake and offline labels remain explicit.

## Validation and evidence limits

- `node --test tests/ui/*.test.mjs`: **69 passed**. Includes detected/uncalibrated
  separation, no numerical permission from detection alone, pending PCM/model separation,
  logical inventory, unavailable setup, reuse, conflict refresh, reconnect cursor,
  late command/socket/source generations, stopping reconnect, recovery gating and isolation.
- `scripts/validate.py --runtime-only`: **130 Python tests passed**, UI tests passed
  (67 at that run), legacy Fake HTTP/WS + SQLite + worker-hook adapter smoke passed,
  release audit passed. This smoke retains legacy regression semantics; it is NOT
  new-policy or real-model microphone proof.
- Browser at localhost static production UI: inspected Home, setup, offline listening,
  anomaly focus, uncertain, unsupported, detected/uncalibrated with advice withheld,
  recovered and Return to monitoring. Mic controls remain visible and disabled in offline
  mode. No baseline/rehearsal buttons. Screenshots inspected for setup/anomaly/uncalibrated
  layouts. Offline examples are authored presentation data, never analysis evidence.
- **Pending Runtime endpoint checkpoint:** actual new-policy setup/job/Live, hot-switch
  pending/applied/rollback, legacy reuse and actual candidate UI/WS walkthrough. Do not
  declare full workflow/physical acceptance from this checkpoint. Runtime/ML owners must
  supply actual physical microphone -> frozen model execution and publication evidence.
  Two-mic switching, Windows long capture and Linux/PN54 remain separate hardware gates.

Only apps/ui, tests/ui and docs/demo are changed by this lane. Shared commits were
merged exactly as routed by Lead, not edited by UI. No change to model masks, confidence,
physical validation or numerical authorization.

## Focused review correction

Current unavailable/paused/stopped capture now outranks retained rollback/pending
outcomes in the status and page state. Stale or alignment-unavailable observations
show Uncertain; initial Runtime Listening without a model result stays Listening.
Input loss is separate, and Runtime Unsupported masks remain visible while waiting.
No positive recognition or advice is inferred. Added three targeted regressions:
**72 UI tests passed**. Actual new-policy/candidate integration still awaits Runtime.

## Runtime integration checkpoint (2026-09-20)

Merged the Lead-authorized Runtime commit
`6f86da3feb1ac015f6e45757509b92d42f277f8d` without editing Runtime files.
This resolves the new-policy **Fake** integration dependency above. Final same-session
Runtime restart correction and candidate/physical acceptance remain with Runtime/Lead;
this report does not claim those pending checks passed.

Reproduce the nonphysical integration test from the repository root:

```text
python tests/ui/live_reference_smoke.py
node --test tests/ui/*.test.mjs
python scripts/validate.py --runtime-only
```

The Python harness binds loopback, uses RuntimeAPI and the real HTTP/WS transport,
serves the existing production UI, and supplies only the existing injected test
backend plus explicitly scripted FakeAnalyzer. Its test-only scenario route is
never installed in production. No native hardware backend is constructed or opened.
`--serve --port 8101` supports browser QA and prints a generated WAV path. Temporary
storage and injected streams are released when the harness stops.

Results on Windows/Python 3.14/Node 25:

- New smoke **PASS**, 60 adapter snapshot notifications on final rerun: actual upload/job/file Live,
  reference-target anomaly, start/complete adjustment, recheck/fresh recovery,
  logical microphone switch, exact idempotent replay, failed-switch rollback,
  paused selection/resume, WS reconnect cursor, stop, and reuse of an actual legacy
  session's existing song/reference without reupload or reanalysis.
- **72 UI regressions PASS**.
- Merged full Runtime validator **PASS**: 33 contract + 39 Runtime + 76 integration
  Python tests, UI tests, legacy Fake HTTP/WS smoke, release audit. Negative launcher
  argument tests intentionally print usage errors while their tests pass.

Actual browser walkthrough (not offline UI fixtures): Home -> Add song -> generated
PCM16 WAV upload -> visible preparation progress -> direct Uploaded File Live ->
Runtime anomaly/recommendation -> Start adjustment -> I've adjusted -> Listen again ->
Re-listening -> Back in range -> Return to monitoring. Then selected logical USB
input backed exclusively by injected PCM: pending cleared advice, applied input
showed Detected with advice withheld, failed Desk selection restored USB binding,
stale Runtime evidence showed Uncertain/null advice, pause -> select Desk -> still
paused -> explicit resume showed initial Listening, browser reload -> saved song
reopened same session, Stop showed Stopped/Session ended rather than a device error.
Fake labeling persisted; no public rehearsal/baseline action appeared. Screenshots
and DOM/accessibility observations were inspected. The longer injected run produced
Runtime stale_evidence; UI suppressed it correctly, with no freshness widening.

### Mandatory synchronized-reference limitation

For candidate comparison, a capture restart or microphone switch begins a new
relative sample-zero timeline. The operator must restart playback/performance from
the **beginning of the uploaded reference** at the same time. The current demo does
not establish arbitrary-entry, tempo drift, section-jump, or unsynchronized musical
alignment. A missing defensible match remains alignment unavailable; never present
it as a comparable observation. The Fake test does not establish real alignment.

Hardware stayed reserved for Runtime/Lead throughout this UI integration. Lead will
inspect candidate visuals during its canonical native run. No physical microphone,
model accuracy, two-device switching or Linux/PN54 claim is made here.
