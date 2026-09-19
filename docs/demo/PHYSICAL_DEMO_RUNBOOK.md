# Physical demo runbook

## Required hookup

```text
independent playback device / isolated demo player
  -> wired audio output
  -> powered speaker
  -> documented room and ambient condition
  -> one physical microphone
  -> PN54 native Runtime
  -> authoritative operator console
  -> human adjustment
  -> fresh post-adjustment microphone evidence
  -> Runtime verification
```

No USB, network, or control path may connect the player to Runtime. Disable or
disconnect unneeded casting, remote control, MIDI, mixer automation, and shared
metadata paths.

## Hardware checklist

- PN54, power supply, tested local Runtime environment, and offline model bundle;
- one selected physical microphone, stand, cable/interface, and OS permission;
- playback device, powered speaker, audio/power cables, and spare adapters;
- fixed tape marks for speaker, microphone, and orientation;
- power/headroom check with no clipping or limiter surprise;
- screen/video capture device that does not become the Runtime microphone;
- rights-approved local audio and an independently stored trial sheet;
- permitted prerecorded physical-loop backup, clearly labeled as a recording.

Record actual device IDs, sample rate, provider, model/frontend/execution profile,
capture settings, geometry, and hashes in `EVIDENCE_PACKET.md`; do not fill from
nominal specifications.

## Preflight

1. Confirm the CP2 commit and clean working tree on PN54.
2. Start Runtime on loopback and open the operator console.
3. Confirm health identity and device discovery. Reject injected/example-only devices
   for a physical claim.
4. Select the intended microphone in the Runtime-discovered list. The browser's
   requested profile is not proof of gain, enhancements, geometry, or provenance.
5. Play the player's audible path check. Confirm sound reaches the room microphone;
   stop it before evidence collection.
6. Fix and mark geometry. Check clipping, dropout, staleness, capture compatibility,
   comparability, and suspension reasons in Runtime state.
7. Verify the frame is not `example_only` and confidence is calibrated for the exact
   bundle/profile/envelope. If not, demonstrate abstention only.
8. Start video capture and show the physical path without exposing answer metadata.

## Main sequence

1. Upload the rights-approved mixed ideal reference and declare known families.
2. Create a native-microphone rehearsal session from a discovered device.
3. Play the prepared rehearsal condition through the speaker. Wait for authoritative
   fresh evidence; do not narrate a predetermined answer before Runtime reports it.
4. If Runtime abstains or suspends, show that truth and follow the recovery rule below.
5. The human adjusts the independent playback environment. Mark adjustment start and
   completion only through operator controls.
6. Wait for fresh evidence, recheck, select a qualified interval, explicitly choose
   whether a reference difference is accepted, and press **Accept as Baseline**.
7. Enter Live. Play normal material and record the no-alert interval.
8. Play a randomized anomaly condition plus only the approved ambient condition.
9. If Runtime emits a calibrated recommendation, the human applies one bounded
   correction. The player never sends that control or target to Runtime.
10. Complete the adjustment and wait for Runtime's post-settling verification. Only
    a fresh `VerificationResult` with observable evidence may be called recovered.
11. Run an interference/inactivity condition and record honest abstention or
    inconclusive verification.

## Recovery rules

- Missing or invalid model: retain the Runtime HTTP 503 `model_unavailable` state;
  do not substitute Fake confidence. Reference-loader failures remain failed jobs.
- Device unavailable/backend failure: remain in setup, show discovery status, inspect
  OS permission/cable, rediscover, then create a new session if required.
- Disconnect/dropout/stale/capture mismatch: Runtime must suspend or degrade; never
  call the last card current. Restore the path and require fresh evidence.
- Historical session after restart: display `SUSPENDED` and
  `runtime_restart_requires_new_session`; create a new sensing session/clock.
- Reconnect/session switch: load the authoritative session ID, obtain a fresh snapshot,
  then reconnect from its cursor. Controls stay gated until the event stream opens.
- Uncalibrated/out-of-envelope/unsupported/inactive/unknown: show abstention; do not
  supply a numeric value or substitute fixture confidence.
- Physical gate unavailable: use the labeled fixture/offline or prerecorded fallback.
  State explicitly that it does not pass the live physical-demo gate.

## Teardown

Stop the session, confirm capture release, stop playback, preserve allowed logs/video,
hash evidence files, and remove restricted audio from recording/export locations.
