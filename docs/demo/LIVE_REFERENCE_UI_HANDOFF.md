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
