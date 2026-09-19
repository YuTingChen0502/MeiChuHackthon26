# Runtime API checkpoint

`RuntimeAPI` is the application boundary for the fake-driven checkpoint. The
Starlette adapter in `apps.api.transport` exposes the frozen loopback HTTP/WebSocket
surface and delegates workflow changes to this service. The UI must not import a
`PASession` or mutate snapshots.

Projects, songs, uploaded PCM, reference jobs/profiles, immutable baselines, command
responses, event history and session counters are persisted under `storage_dir`.
After an application restart, prior sessions are restored as `SUSPENDED` because the
monotonic clock changed; completed idempotent retries remain available, while sensing
must continue in a newly created session/clock.

## Route mapping

| Planned loopback route | Runtime handler |
|---|---|
| `GET /v1/health` | `health()` |
| `GET /v1/audio-devices` | `audio_devices()` |
| `POST /v1/projects` | `create_project(request)` |
| `POST /v1/songs` | `create_song(request)` |
| `POST /v1/audio-assets` | `upload_audio(wav_bytes, filename=...)` |
| `POST /v1/songs/{id}/reference` | `start_reference_job(id, request)` |
| `GET /v1/jobs/{id}` | `get_job(id)`; the worker calls `run_reference_job(id)` |
| `POST /v1/sessions` | `create_session(request)` |
| `GET /v1/sessions/{id}` | `get_session(id)` |
| `POST /v1/sessions/{id}/actions` | `post_action(id, SessionCommand)` |
| `POST /v1/sessions/{id}/baseline` | `accept_baseline(id, SessionCommand)` |
| `WS /v1/sessions/{id}/events?after_sequence=N` | `connect_events(id, after_sequence=N)` |

The supported loopback launch is:

```text
python -m pip install -r requirements-runtime.txt
python -m uvicorn apps.api.transport:app --host 127.0.0.1 --port 8000 --workers 1 --loop asyncio --http h11 --ws websockets-sansio
```

Set `PA_RUNTIME_STORAGE_DIR` for durable state and optionally
`PA_AUDIO_DEVICE_IDS=mic-1,mic-2` for runtime-verified device IDs. An empty device
list is reported honestly as unavailable. Host and browser Origin checks are
loopback-only by default.

When `apps/ui/` is present in the integrated checkout, the same process serves only
that directory at `/apps/ui/`; it never mounts the repository root. This Runtime
checkpoint still uses `FakeInstrumentAnalyzer`, and `PA_AUDIO_DEVICE_IDS` is only a
runtime availability/Live gate. Native microphone capture and its sustained audio
worker remain a separate integration gate; no fake evidence is presented as physical
capture or model accuracy.

## Setup request/response example

```json
{"name":"Demo project"}
```

returns `201` with `{"project_id":"project-1","name":"Demo project"}`. A song
request is:

```json
{"project_id":"project-1","name":"Demo song","instruments":[{"instrument_id":"guitar","family":"guitar"},{"instrument_id":"bass","family":"bass"},{"instrument_id":"drums","family":"drums"}]}
```

Upload 16-bit PCM WAV bytes, then submit `{"asset_id":"asset-1"}` to the reference
handler. It returns `202`; the application runs the reference job asynchronously.
Poll until `status=completed`, then create a session with the explicit completed
`reference_id`, source `input_kind` plus `input_asset_or_device_id`, and a complete
capture fingerprint. The server allocates `clock_id`.

## Commands and reconnect

Acceptance and adjustment bodies are the frozen `SessionCommand` objects. For
acceptance, `action` is `accept_baseline` and `payload` contains the selected
run/clock/sample interval, `accepted_by`, `reference_difference_accepted`, and note.
For adjustment, send `start_adjustment`, retain the returned authoritative
`adjustment_id`, then send `complete_adjustment` and `recheck` with that exact ID.

Reconnect atomically from an authoritative snapshot cursor:

1. GET the session snapshot and retain its `event_sequence` cursor `N`.
2. Connect `WS /v1/sessions/{id}/events?after_sequence=N`.
3. The socket sends individual retained and ongoing `SessionEvent` records. A
   retention gap produces one authoritative snapshot event before live delivery.
4. Discard duplicate sequences and refresh from a snapshot on an unexplained gap.

Runtime identities, setup records, sessions, command results, and immutable baseline
versions are stored in one SQLite database. Each command response, resulting session
state, and baseline promotion commit atomically; failed commits restore the in-memory
pre-command state. Restored sessions are suspended because process restart changes
the monotonic clock and require a newly created session for sensing.
