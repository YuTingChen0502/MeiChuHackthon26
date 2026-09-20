# Session deletion UI acceptance

## Scope and integration

UI-only implementation: `480138508251ed27e0a8f73fa0ff23436951fd74`.
Approved Runtime implementation: `39df3a5e24a5ea3b66a7d257a004fc01996296c5`.
Integration base for the accessible confirmation correction:
`c83d1ff123e56a382bc73d24eb48e8f1778c4e59`.

Each Recent songs entry has a secondary Delete session action. The in-page
modal identifies the song and session, explains permanent history deletion and
stopping active listening, and states that the song/reference remain. Cancel
receives initial focus; Cancel and Escape leave the entry untouched. Focus is
restored on dismissal. This replaces native confirmation, which blocked the
embedded-browser QA interaction.

The adapter sends bodyless `DELETE /v1/sessions/{id}`. Only a matching successful
`{session_id, deleted: true}` response removes the catalog entry. Failure leaves
it available for explicit retry. Pending requests are deduplicated. Deleting
the current session clears its bindings and subscription; another session is
not disturbed. Generation/deletion guards reject late snapshots and loads.
WebSocket close 4404 terminates reconnect without pretending to acknowledge
deletion or automatically removing a catalog entry. Offline examples cannot
delete Runtime data.

## Validation

- 84 UI tests pass, including ten deletion-focused tests (cancel, failure,
  duplicate pending requests, exact acknowledgement, current/other session,
  late responses, terminal 4404 and presentation wiring).
- Actual HTTP/WebSocket Fake integration smoke passes with 68 notifications:
  existing reference upload, source switching, anomaly/adjustment/verification,
  reconnect and retained legacy-reference coverage; plus active/other deletion,
  repeated deletion, terminal 4404, late-snapshot rejection and reference reuse.
- Browser QA used production UI files on isolated `127.0.0.1:8101`, generated
  PCM and FakeAnalyzer only. Cancel and Escape retained Temporary deletion QA
  (`session-2`). After explicit confirmation, the success message appeared and
  the entry disappeared. Reload did not restore it; GET returned 404. Creating
  `session-3` from the same `song-1` / `reference-1` proved retention.

All deleted records were worker-generated temporary QA records. No real user
session was deleted. These results validate deletion/transport behavior, not
physical microphone performance, model accuracy or PN54 readiness. No
perception, confidence, numerical authorization or physical gate was changed.
