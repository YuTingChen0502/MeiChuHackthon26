# Native microphone correction: staged evidence

Synced origin/main: `95fa5fed576d6e45f608f413bc84167161d34f13`.
ADC implementation and clean physical-test source:
`5cea661afdbf2760ecfc590fa339c25e4b7f25ca`.

## Proven cause and correction

Some Windows PortAudio host APIs deliver zero/unusable ADC timestamps with valid
PCM. Treating this metadata absence as fatal stopped real MME capture with
`native_adc_clock_unavailable`. The callback now anchors a sample-count timeline
using monotonic time when ADC timing is unavailable. Valid ADC timing still seeds
the initial clock and performs drift checks. Later ADC availability initializes
diagnostics without shifting the already established fallback timeline.

Overflow/status, excessive ADC drift and late fallback packets insert a sample-span
discontinuity marker and reanchor a new segment. Queue overflow still leaves actual
sample holes. No missing audio is synthesized. Invalid monotonic time or malformed
PCM still fails closed. Capture callbacks remain bounded and do no model, HTTP,
WebSocket or persistence work.

## Windows physical evidence

Windows 11 build26200, Python3.12.14, sounddevice0.5.6; Realtek Microphone Array,
actual default MME endpoint `portaudio:7e9e9dff606f9c65ff87`, negotiated48000Hz mono.
No microphone PCM was saved.

- Sustained60.484s:2812 fallback packets,0ADC packets,56fresh four-second windows
  with one-second hop. Zero callback/worker drops, stale windows or discontinuities.
  Callback queue peak2/8; inference queue peak1/2; publication agep95 .02133s.
- RuntimeAPI lifecycle16.578s:two eight-second runs,8fresh windows,distinct runIDs,
  explicit pause/close/reopen/stop,748fallback packets,zero faults. Final STOPPED.
  Fake outputs abstained. This is capture/lifecycle evidence, not perception.
- WASAPI comparison60.453s:Realtek endpoint `portaudio:b0f45d7b7c5f04d95e39`,
  negotiated48000Hz mono,2812ADC packets,0fallback packets,56fresh windows,
  zero drops/stale/discontinuities. Maximum ADC residual2.416ms,callbackqueue1/8,
  inferencequeue1/2,publicationagep95 .010s. Clock mode remained ADC-backed.
- Reports: `tests/runtime/reports/native-default-*-5cea661.json` and
  `tests/runtime/reports/native-wasapi-adc-5cea661.json`.

## Validation and incomplete gates

Canonical `scripts/validate.py` passed:243Python tests(shared28,Runtime36,
integration65,training29,analyzer47,benchmark38),44UI tests,fullFakeHTTP/WS/SQLite
workflow and release audit/self-tests. Focused tests cover absent/zero/nonfinite
ADC metadata followed by valid packets, valid clocks, status/drift/late fallback,
queue pressure, source close/reopen and frontend continuity.

This is an intermediate correction record, not overall READY. Logical microphone,
source-switch and live-reference shared contracts are being frozen by Lead; no
public shape was invented. Linux/PN54: NOT YET PHYSICALLY VERIFIED; authorized host
access is unavailable. Actual source-switch acceptance follows its integration.
