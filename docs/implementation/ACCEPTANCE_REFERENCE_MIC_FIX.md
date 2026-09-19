# Reference preparation and microphone selection acceptance correction

Base: `25a4dd40d8db48028242a5d66420d287f17d3bc5`.
Tested executable integration: `252d8221fc85b8ca0537ef456e6359158d5b7513`.

## Cause and bounded correction

The affected upload was persisted successfully: 44.1 kHz stereo PCM16 with
9,952,128 frames (about 226 seconds). Both reported reference jobs actually started
and eventually completed. Native capture had not yet started during preparation.
The Fake analyzer fully consumes shared frontend windows; resampling a long file
to the host's 48 kHz profile takes time. The job's progress was hard-coded to 0.1
throughout that work. The UI did poll the job and apply terminal completion; no
missing completion event was found. Its separate 400-poll total limit could also
terminate observation of a legitimately long job.

Runtime now updates transient progress from consumed PCM without rewriting the
large persisted audio state on every chunk. Successful completion remains 1.0.
An independently reproduced input-construction exception outside the job's failure
guard could strand a job; that construction now produces a durable failed state.
The UI allows advancing jobs to continue, with a 60-second inactivity watchdog and
a 30-second status-request deadline. No frontend numerical behavior was bypassed.

Native discovery already had friendly names and host APIs, but the HTTP response
discarded them. Additive optional name/host_api/is_default metadata now reaches the
selector and source strip. Stable IDs remain command values, never ordinary labels.
Output-only and recognized loopback filters remain. Cross-host names alone do not
establish physical identity, so alternatives remain with host disambiguation.

Accepted Runtime commits: `605e868fe2064a82909a476a00cb86c768a79b0c` and
`221c401cfdbf76e51d699490c6901c4681584a9b`.
Accepted UI commit: `d377b571c4dfc5646ec4d539358e673c3a475881`.
Lead approved the additive discovery semantics in `7f884e6`.

## Validation and manual retest

- Canonical `scripts/validate.py`: 239 Python tests, 43 UI tests, unchanged full
  Fake HTTP/WebSocket/SQLite correction-loop smoke and release audit/self-tests PASS.
- Focused regressions cover inflight progress, durable failure after restart,
  more than 400 advancing polls, stalls and hung status requests, friendly labels,
  stable IDs, default metadata, legacy entries, and input/loopback filtering.
- Lead reproduced the original 10% plateau using an actual browser upload of a
  generated 226-second 44.1 kHz stereo PCM16 WAV with Live Microphone selected.
  The old job eventually entered rehearsal, confirming the completion path existed.
- Corrected browser upload showed 25%, 58%, 90%, then completed. A concurrent HTTP
  trace observed completion at 76.36 seconds from monitoring start (not total upload
  time), followed by authoritative session creation and the rehearsal console.
- Friendly labels included the known Default input and
  `Microphone Array (Realtek(R) Audio) · Windows WASAPI`, with no raw device hash.
- The selected WASAPI device initially returned a Windows driver startup error.
  One explicit Resume recovered; session-1 reached REHEARSAL with fresh native
  frames (including frame:session-1:12), no suspension reason, and visible Active
  source state. Fake evidence remained honestly abstained.

Tests used an isolated port-8011 storage directory to preserve the user's running
port-8010 process and database. The in-app browser retained old JavaScript after
reload; a fresh localhost origin loaded the current UI. Restart the user's existing
Runtime and hard-refresh its page to consume these fixes. No user audio, session,
or private database was deleted; no restricted audio was added to Git.
