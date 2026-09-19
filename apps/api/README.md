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

Set `PA_RUNTIME_STORAGE_DIR` for durable state. Native discovery uses the optional
sounddevice/PortAudio backend; the launcher no longer trusts `PA_AUDIO_DEVICE_IDS`.
The proposed native dependency pins are sounddevice 0.5.6, cffi 2.1.1 and pycparser 3.0;
Lead integration into the root dependency set remains required. A missing backend
is reported as `native_backend_unavailable`; file execution remains available.

Creating a session starts managed acquisition. File replay is paced on the session
clock; native capture uses a bounded callback queue and a separate analysis worker.
Pause/Stop release capture. Resume creates a new analysis run on the same session
clock; uploaded-file Resume replays the selected asset from its beginning. EOF,
device loss and worker errors suspend with an explicit reason. After process restart,
create a new session/clock. State transitions and command retries retain CP1 semantics.

The common planner defaults to W=192000/hop=48000 samples (4/1 seconds at 48 kHz).
Native input is mono float32 without amplitude normalization. The callback copies
at most 1024 samples into an eight-packet queue; two planned windows may wait for
analysis. Oldest queued windows and results older than two seconds are dropped or
abstained, with discontinuity gates. Timing uses ADC-anchored sample counts and a
50 ms clock-jitter budget; gross drift, status errors and lost samples start a new
run. The same 50 ms budget permits clock-resolution jitter at the publication
boundary and is conservatively added to native verification freshness requirements.
Clipping gates include PCM16 positive full scale (32767/32768), not just amplitude
1.0. These are transport settings, not a validated ML operating envelope.

Recent retention is 128 frames with PCM hashes and 128 events per session. Baseline
selection must fit entirely within retained coverage. Overlap contributes unique
seconds and qualified nonoverlapping windows. The durable API retains a 128-record
audit tail in memory and archives every immutable audit record, bound evidence frame
and hash transactionally in SQLite. Baseline versions, command retry ledgers and
audit disk storage grow with human/workflow history and are not silently pruned.
Uploaded assets remain bounded by the upload limits; the asset catalogue is durable.

The production launcher uses ContinuousFakeInstrumentAnalyzer: unscripted windows
produce explicit example-only abstention. A non-fake injected analyzer is wrapped by
RealAnalyzerAdapter and its evidence remains uncalibrated, with null probabilities,
intervals and instrument advice. Production confidence requires a Lead-approved
empirical bundle; there is no bypass flag. Client-supplied physical provenance,
gain, enhancements and geometry remain unverified. Native opening alone cannot
qualify Live. Unverified native capture also marks frame quality incompatible.
No public schemas or UI routes were added.

`RuntimeAPI(available_audio_devices={...})` retains the in-process CP1 scripted Fake
harness, with managed capture disabled by default for that explicit test seam. It is
not used by the production launcher. `managed_audio=True` selects managed capture
for a supplied test backend. Worker diagnostics are available to Runtime through
`api.workers[session_id].metrics()`; snapshots/events expose suspension and quality
through existing fields. The UI does not consume a new metrics contract.

The same server serves only `apps/ui/` at `/apps/ui/`, never the repository root.
See `CP2_RUNTIME_CHECKPOINT.md` for measured validation and external gates.

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
