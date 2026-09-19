# Reference job progress correction

Base: `25a4dd40d8db48028242a5d66420d287f17d3bc5`.

A valid long 44.1 kHz WAV is resampled by the shared frontend to the Fake host's
48 kHz analysis profile. Previously, the job reported progress 0.1 for the entire
preparation. A 30-second generated input reproduced this unchanged progress until
completion around 8.3 seconds. Lead independently observed the user's long job
complete eventually; the UI polling timeout is a separately owned correction.

Runtime now advances transient progress from 0.1 to 0.9 as the shared pipeline
consumes input PCM. Progress 1.0 remains terminal. Progress updates do not rewrite
the uploaded PCM or SQLite state per chunk; terminal state remains persisted.
No frontend numerical behavior, analyzer interface or public contract changed.

A second proven defect was input construction outside the failed-job handler.
Invalid stored clipping metadata raised an uncaught ValueError and left the job
running at 0.1. Construction now occurs inside the existing failure guard so this
becomes a durable failed job with its error available to polling clients.

Validation:

- Integration: 62 passed, including two focused regressions for progress while
  preparation is blocked and durable adapter-construction failure after restart.
- Runtime: 32 passed.
- Realistic isolated reproduction: generated PCM16 stereo, 44100 Hz, 9,952,128
  frames (225.672 seconds), both channels constant integer amplitude 3300.
  Uploaded through RuntimeAPI using the default Fake analysis geometry of
  48000 Hz / 192000-sample window / 48000-sample hop. Upload took 13.563 seconds;
  reference job completed in 58.375 seconds. Polled progress at approximately
  10/20/30/40/50 seconds: .184/.337/.489/.656/.818, then completed at 1.0.
  Creating the subsequent actual local WASAPI microphone session reached
  REHEARSAL; shutdown released capture. No microphone PCM was saved.
- Probe used temporary isolated storage and the bundled Python 3.12 environment.
  It did not alter or stop the user's existing listener or manual-demo database.

The timing is a local generated-audio reproduction, not an inference benchmark
or a guarantee that every long upload finishes before a fixed UI timeout.
