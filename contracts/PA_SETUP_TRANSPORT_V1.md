# PA setup and local transport V1

**2026-09-20 amendment:** new product setup uses `workflow_policy=live_reference_v1`
and enters Live against the uploaded reference, with optional source/fingerprint
resolved by Runtime. Logical microphones and same-session switching follow
[the Lead freeze](../docs/implementation/LIVE_REFERENCE_MIC_FREEZE.md).
The rehearsal setup described below applies only to the retained legacy policy.

Lead decision: approved for implementation on 2026-09-19. This supplements L2 and
`PA_SHARED_INTERFACES_V1.md`; it does not change existing public/session/analyzer
record meanings. Runtime commit reviewed: `78a362ea184ec3f5302c0cef271c16a06299d316`.
Its in-process facade is a starting point, not a claim that a listener already exists.

## Transport selection and ownership

Use Starlette 1.6.0 ASGI with Uvicorn 0.53.0 and websockets 17.1. The Lead-owned
`requirements-runtime.txt` pins the tested dependency set. Transport requires Python
3.11+; Python 3.12 was tested. Shared payload types retain their existing compatibility.
MI300 training environments do not inherit this deployment requirement automatically.

Select stdlib asyncio + h11 + Uvicorn `websockets-sansio`; one process/worker,
loopback `127.0.0.1`, no auto-reload for the demonstration. No uvloop, CUDA dependency,
cloud inference, or second workflow implementation is required. Runtime owns the
adapter under `apps/api/` and must delegate to its application/session methods.

The planned launch, to become supported only when Runtime provides this module, is:

```text
python -m pip install -r requirements-runtime.txt
python -m uvicorn apps.api.transport:app --host 127.0.0.1 --port 8000 --workers 1 --loop asyncio --http h11 --ws websockets-sansio
```

The adapter may serve `apps/ui/` at `/apps/ui/` for same-origin UI/API integration.
Do not mount the whole repository or serve demo-player scenario data from this API.
Demo playback remains a separate process/device. Before browser mutations, validate
the expected Host/Origin for the loopback UI and WS; do not enable wildcard origins.
Background reference processing and audio inference must not block the ASGI event
loop or the capture callback. Preserve per-session command/event serialization.

## Frozen setup payloads

Validate the named definitions in `PA_SETUP_WIRE_V1.schema.json`. JSON objects are
closed and nonfinite numbers are rejected. Keep session commands/responses exactly
as defined in `PA_SESSION_WIRE_V1.schema.json`.

| Route | Input definition/body | Success |
|---|---|---|
| POST /v1/projects | CreateProjectRequest | 201 ProjectResponse |
| POST /v1/songs | CreateSongRequest | 201 SongSetupResponse |
| POST /v1/audio-assets | Raw PCM16 WAV bytes, Content-Type audio/wav | 201 AudioAssetResponse |
| POST /v1/songs/{id}/reference | StartReferenceRequest | 202 ReferenceJob |
| GET /v1/jobs/{id} | No body | 200 ReferenceJob |
| POST /v1/sessions | CreateSessionRequest | 201 SessionSnapshot |
| GET /v1/sessions/{id} | No body | 200 SessionSnapshot |

CreateProjectRequest is `{"name":"Demo project"}`. CreateSongRequest contains
`project_id`, `name` and `instruments`, each with `instrument_id` and `family`.
Instrument IDs and family/group entries must be unique in this V1 configuration.
Return actual supported/unsupported mappings from analyzer capabilities; never treat
declared configuration as evidence of observed activity.

Audio uploads use bytes, not a server path or fixture-label channel. An optional
`X-Audio-Filename` header is display-only metadata and never enters inference. No
multipart dependency is needed. Validate format, complete sample bytes and bounded
size/duration before storing. Set finite configurable limits (initial launcher
defaults: 128 MiB and 900 seconds); return 413 when an upload exceeds them. PCM16 WAV
is the initial supported format; unsupported media/encoding receives 415 or 422 with
a clear reason. Decode/downmix through the common frontend. Asset IDs are opaque.
`content_hash` identifies original uploaded bytes; ReferenceProfile.source_asset_hash
must identify that same source asset. Store derived PCM hashes separately if needed.

A reference request is `{"asset_id":"asset-1"}`. Its queued job is run by the
application worker without requiring a client-only "run job" endpoint. Pollable
states are queued, running, completed or failed; a completed job provides its
reference_id. If a newer reference request supersedes an earlier one, old job
completion must not silently replace the newer selection.

CreateSessionRequest contains `song_id`, explicit `reference_id`, `source` with
`input_kind` and `input_asset_or_device_id`, and `capture_fingerprint` using the
existing public CaptureFingerprint shape. The chosen completed reference must belong
to that song and remain its selected revision; otherwise return 409. Validate the
asset/device ID and capture metadata before constructing a session.

**Clock allocation is server-owned.** The request does not accept `clock_id`.
The application allocates session/clock identities and returns the full SourceBinding
in SessionSnapshot. Start in rehearsal; enter Live through the frozen explicit
`start_live` command after acceptance. No implicit baseline or Live promotion.
Client-supplied capture provenance is a declaration, not proof of physical validation;
the runtime must enforce the design's capture compatibility/Live gate.

Setup errors use `SetupError`: `{"error":{"code":"...","message":"...","retryable":false}}`.
Use 404 for unknown resources, 409 for incompatible/current-state bindings, 422 for
invalid structured values, and 503 for unavailable runtime/device. Session commands
continue to use their frozen CommandResponse and HTTP statuses. Enforce body and URL
session equality and route/action matching before mutation.

## Session events and availability

Expose `WS /v1/sessions/{id}/events?after_sequence=N`. Send individual SessionEvent
objects, not the in-process facade's `{snapshot,cursor,events}` polling wrapper.
Obtain a snapshot through GET first, then subscribe after its cursor. Replay retained
events; for a retention gap send one authoritative snapshot event and continue.
Reject invalid/future cursors rather than silently declaring unavailable history read.
Deliver ongoing events after subscription, not just the initial retained batch.

Malformed requests, command conflicts, stale cursors and worker failures need transport
tests. The native microphone and sustained worker are separate Runtime work; an empty
device list must remain an honest unavailable state. Do not expose private fake-analyzer
scenario controls as public setup/session request fields.

## Checkpoint migration required before browser integration

1. Runtime's create_session currently chooses the song's latest reference implicitly
   and expects a client clock_id. Adopt explicit reference_id + server-owned clock.
2. Add setup-schema validation instead of allowing malformed dictionaries to reach
   set/hash/attribute operations and return unexpected 500 responses.
3. Preserve original asset hash through reference preparation.
4. Fix the workflow/persistence findings in the Lead checkpoint review before claiming
   end-to-end UI integration. Merely wrapping the existing facade in HTTP is insufficient.

## Validation and sources

The exact dependency versions installed successfully in a temporary Windows Python
3.12 environment. A temporary standalone ASGI app returned HTTP 200 over loopback and
sent/received WebSocket JSON with the selected Uvicorn settings; the server was stopped
afterward. This validates the transport combination, not the unimplemented product
listener or PN54 deployment.

Version/capability sources checked 2026-09-19: [Starlette](https://pypi.org/project/starlette/),
[Uvicorn](https://pypi.org/project/uvicorn/) and [websockets](https://pypi.org/project/websockets/).

## Explicit session deletion (user-approved 2026-09-20)

`DELETE /v1/sessions/{id}` has no body and uses the existing mutation Origin/Host
protections. Success is HTTP 200 `DeleteSessionResponse`:
`{"session_id":"session-1","deleted":true}`. Repeating deletion of an absent ID
returns the same success; IDs are never reused. Existing GET/actions for a deleted
ID return 404. An already-connected event socket closes with 4404/unknown_session.
This is an additive setup/application endpoint, not an analyzer/session-command change.

The UI must obtain explicit confirmation naming the session and explaining that
active listening stops and session history is deleted, while song/reference assets
are retained. Runtime fences the session, stops/cancels acquisition and pending
source opens, and safely retires in-flight inference before it can publish or
persist new state. It must not close a model while inference is using it. In one
durable operation remove the session snapshot, its command ledger and session audit
records. Do not delete songs, projects, references, uploaded audio, shared baseline
profiles or model bundles. Session deletion is the explicit exception to retaining
that session's audit history; other audit immutability remains unchanged.

Deletion must survive process restart and late inference/callback/command races;
late writes must not resurrect the session. Preserve monotonic identity counters.
Failure uses existing SetupError; do not acknowledge success before durable deletion.
Other sessions must remain unaffected. UI removes its recent-session entry only on
confirmed HTTP success, disconnects a deleted current subscription and clears its
current snapshot. Canceled confirmation and failed requests leave the entry intact;
delayed snapshots/reconnect cannot re-add it. Offline examples never issue deletion.
No automatic retention purge, bulk delete, reference deletion or model change.
