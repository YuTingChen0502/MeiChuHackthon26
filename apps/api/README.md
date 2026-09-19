# Runtime API checkpoint

`RuntimeAPI` is the reviewed in-process transport boundary for the first fake-driven
checkpoint. It does not start a network listener and does not add a root dependency.
A later loopback HTTP/WebSocket adapter should delegate directly to these methods;
the UI must not import a `PASession` or mutate snapshots.

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

The current supported launch is an in-process Python application:

```python
from apps.api import RuntimeAPI

api = RuntimeAPI(storage_dir="runtime-data", window_size_samples=48000 * 4)
status, health = api.health()
```

There is deliberately no claimed HTTP/WebSocket launcher in this commit. Binding a
network stack requires the Lead to select/integrate the root deployment dependency.
The method boundary and all returned session records already use the frozen schemas.

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
handler. It returns `202` and a `job_id`; poll the job until `status=completed` and
use `POST /v1/sessions` with a source binding and complete capture fingerprint.

## Commands and reconnect

Acceptance and adjustment bodies are the frozen `SessionCommand` objects. For
acceptance, `action` is `accept_baseline` and `payload` contains the selected
run/clock/sample interval, `accepted_by`, `reference_difference_accepted`, and note.
For adjustment, send `start_adjustment`, retain the returned authoritative
`adjustment_id`, then send `complete_adjustment` and `recheck` with that exact ID.

Reconnect atomically from an authoritative snapshot cursor:

1. `connect_events(session_id)` returns `snapshot` and cursor `N`.
2. Connect the event transport with `after_sequence=N`.
3. `connect_events(session_id, after_sequence=N)` returns every retained event after
   `N`, or one fresh `SessionSnapshot` event if retention cannot cover the gap.
4. Discard duplicate sequences and refresh from a snapshot on an unexplained gap.
