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
runtime. Its prepared scenario truth is deliberately private to that process.

## Runtime integration request

The UI respects the L2 setup order and frozen session-wire commands. Concrete
setup/upload/reference-job response models and command endpoint availability are
Runtime-lane work. Until those handlers exist, this checkpoint remains a fixture
adapter and does not send mutations.
