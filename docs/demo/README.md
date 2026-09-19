# PA physical demo and UI checkpoint

## Launch

From the repository root, run `python -m http.server 8000`. Open
`http://localhost:8000/apps/ui/` for the operator console and
`http://localhost:8000/demo_player/` on the separate playback device/window.

The console fetches the frozen illustrative fixture at
`contracts/examples/pa_shared_v1.json`. It never presents fixture values as model
accuracy or physical-demo evidence. It renders explicit unknown/inactive states,
withholds a numeric balance when confidence abstains, and produces SessionCommand
objects that bind the snapshot version, reference, baseline and incident currently
visible to the operator. Fixture commands are logged only; integration needs the
Runtime lane's handlers.

## Physical isolation checklist

1. Prepare rights-cleared audio externally and assign opaque asset IDs.
2. Randomize playback order in the demo player. Do not use answer-bearing filenames.
3. Route only audio from the player to a speaker, then through the room to the
   microphone. The analyzer receives the microphone PCM plus legitimate mixed
   reference/profile context—not player scenario metadata.
4. Keep demo-player controls, injected gains, hidden scenario truth, and instrument
   labels out of the runtime/analyzer process and all API payloads.
5. Record the speaker/microphone geometry and clearly label any prerecorded backup
   as a recording.

`demo_player/player.js` has no imports and does not call the UI, API, analyzer, or
runtime. It plays a real generated audible-output check and may play a locally
selected rights-cleared audio file. Its status is driven by HTML media events, not by
button intent. File names and prepared scenario truth are intentionally not rendered
or transmitted outside that browser process.

## Runtime launch and UI integration

The approved local Runtime listener serves the UI at `/apps/ui/` and exposes the
frozen setup/session routes. Launch it from the repository root with the Lead-pinned
environment:

```text
python -m pip install -r requirements-runtime.txt
python -m uvicorn apps.api.transport:app --host 127.0.0.1 --port 8000 --workers 1 --loop asyncio --http h11 --ws websockets-sansio
```

The UI probes `/v1/health` before attempting setup. With Runtime available, it
creates the project/song, uploads PCM16 WAV reference bytes, waits for the reference
job, creates a rehearsal session, then consumes authoritative snapshots/events. On a
409 command conflict it refreshes the server snapshot. If Runtime is absent, local
development may fall back to the shared illustrative fixture only when a development
server exposes it; the Runtime listener intentionally serves only `apps/ui/` and does
not mount the repository or demo-player data.
