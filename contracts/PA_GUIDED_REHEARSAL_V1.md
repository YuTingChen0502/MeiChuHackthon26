# Guided rehearsal companion V1

Lead-approved necessary interface addition for MVP_PRE_MODEL_READY, 2026-09-20.
The frozen public, analyzer, setup and session records are unchanged. The previous
internal guided_probe observation context had no UI request path; this companion
binds human rehearsal intent without adding inferred activity, gain or target policy.

`POST /v1/sessions/{session_id}/probes` accepts RehearsalProbeCommand and returns
RehearsalProbeResponse {command: existing CommandResponse, probe: RehearsalProbeState}.
`GET /v1/sessions/{session_id}/probes` returns RehearsalProbeState for reconnect.
The command binds session/idempotency/state version/reference/baseline/incident in
the same way as session commands. Validate URL/body and reject stale bindings (409),
invalid mode/instrument (422), unavailable input/model (503). Use the existing session
command ledger namespace; identical retries return the original whole response before
version checks, changed content/key reuse conflicts. Persist state and response
atomically and roll back on failure. Existing command routes reject this record.

Modes: instrument requires one configured instrument_id; full_band and idle require
null. Only rehearsal mode with workflow REHEARSAL and no active adjustment can change
a probe. Selection never asserts that the instrument is playing. A new probe gets
an opaque probe_id and server monotonic not_before cutoff. Only complete windows
starting after the cutoff (including native uncertainty margin) may use that request;
discard partial pre-request support. Use observation_purpose=guided_probe plus the
selected probe_instrument_id for instrument mode. Full-band uses ordinary rehearsal
purpose with null probe ID; all modes use the SAME frontend/analyzer/state path.

Every change increments session state_version and publishes an existing authoritative
SessionSnapshot event. Probe detail remains on the companion GET; UI refreshes it
after a session transition/reconnect and binds its state_version to the snapshot.
On pause, stop, restart, source gap/discontinuity, active adjustment or leaving
rehearsal, cancel probe intent and reset persistence. Idle has null probe_id/cutoff.
Runtime may expose current version in GET even when no probe is active. Baselines,
reference targets, normal envelopes and live comparison policy never change here.

Guided samples may be inactive, unsupported, unknown or numerically unobservable
(for example too few active anchors). Show that evidence honestly. Full-band coverage
and a human-selected valid interval still govern baseline acceptance. A UI progress
step/button or successful probe command is not calibration, activity or recovery.
