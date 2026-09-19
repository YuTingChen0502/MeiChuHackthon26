# MVP model-independent acceptance checks

This is the Lead's integration checklist, not a readiness claim. Run against the
final integrated commit. Test fixtures and synthetic calibration records prove
software invariants only; they do not authorize a production model or confidence.

## Required checks

| # | Requirement | Existing regression coverage / final evidence required |
|---|---|---|
| 1 | File and microphone converge downstream | `test_audio_and_state.py::test_file_and_microphone_converge_on_identical_pcm_windows`; `test_streaming.py::test_live_and_file_pcm_produce_same_downstream_simulated_state` |
| 2 | Actual native sessions run | Actual-device report with exact commit, device/rate/channel and elapsed time; injected device tests alone are insufficient |
| 3 | Sustained bounded worker/history | `test_continuous_runtime.py::test_frame_hash_and_event_history_are_bounded`; current-revision sustained report beyond history warmup, with queue/history bounds and process observations |
| 4 | Overlapping sample identity | `test_streaming.py::test_overlap_identity_and_amplitude`; `test_continuous_runtime.py::test_overlap_baseline_counts_unique_seconds_and_nonoverlap_windows` |
| 5 | Backpressure and stale work | `test_streaming.py::test_callback_backpressure_preserves_sample_holes`, `test_worker_stale_windows_never_reach_analyzer`; `test_continuous_runtime.py::test_slow_inference_is_stale_at_publication` |
| 6 | Gaps reset persistence | `test_streaming.py::test_capture_gap_produces_new_run_and_no_straddling_window`; `test_pa_vertical_slice.py::test_capture_gap_resets_pending_incident_persistence` |
| 7 | Stale/dropout cannot create or clear incidents | `test_pa_vertical_slice.py::test_stale_evidence_cannot_create_incident`, `test_silence_or_disconnection_is_inconclusive_not_recovered`; silent-PCM regression |
| 8 | Full Fake application | Unchanged `checkpoint1_smoke.py` plus current UI product flow, native source and guided rehearsal integration checks |
| 9 | Production unavailable/failure is safe | Model lifecycle tests including missing files, failing constructor, resource closure and no silent Fake fallback |
| 10 | Human-only baseline | Shared command validation and vertical-slice baseline acceptance; guided probes must never promote automatically |
| 11 | Live baseline immutable | Vertical-slice commands and current guided endpoint rejection in Live |
| 12 | Fresh observable verification | `test_continuous_runtime.py::test_verification_cutoff_includes_native_clock_uncertainty`; complete-window post-adjustment and silence/disconnection regressions |
| 13 | Session switch isolation | UI adapter delayed-response/cursor tests; test UI local catalog against authoritative server session identity |
| 14 | Restart/reconnect | SQLite rollback/restart tests, WS replay/gap snapshots, UI reconnect regression; guided state resets safely |
| 15 | UI no inference | UI tests and source review: numeric values, confidence, status and verification originate in Runtime; design artwork supplies no measured values |
| 16 | Demo no truth leakage | Player isolation review/tests; acoustic output only; no runtime imports, gain-label channel or fixture commands |
| 17 | Analyzer replaceable | Actual ML generic loader + Runtime factory integration, frozen evidence validation, durable reference and accepted-baseline context lifecycle |
| 18 | Shared contracts green | All `core/contracts/tests`; original four schemas retain their frozen meaning; guided companion tested separately |
| 19 | Public source hygiene | Redacted source scan and scanned history-free archive; no authority PDFs, raw restricted data, model caches, credentials or signed download URLs |

The conventional `file.py::method` notation above identifies unittest methods; run
the suites through `python scripts/validate.py`, not a pytest-specific command.

## Model intake acceptance

Exercise both Nano4 and MI300 metadata without attributing real empirical success
to test fixtures. Verify missing files, checkpoint hash mismatch, malformed manifest,
unsupported adapter, frontend/taxonomy/scale/profile mismatch, incomplete evidence,
safe unavailable behavior and source-preserving evidence import. A backend registry
must be controlled by the host, never by executable module names from a bundle.

Use the actual `analyzers.bundles` objects through `apps.api.config`; a stubbed loader
cannot establish cross-lane compatibility. Before real numerical state is allowed,
host review must bind model/artifact/evidence/calibration identities, operating
envelope, capture profile and confidence mappings. Test both anomaly and normal
calibration paths so abstention cannot accidentally become recovery.

## Product-flow acceptance

Exercise new and existing song selection, reference upload/job failure and success,
configured IDs, session reopening, guided instrument samples, full-band probes,
calibration review, explicit Accept as Baseline, explicit Start Live, human adjustment,
recheck and verification. Include stale command rejection, reconnect during probing,
unavailable source/model and session switching. Fixture mode remains explicitly
simulated and must not issue mutations to a real session.

## Evidence record

For every final run record exact Git SHA, command, Python/Node and dependency versions,
outcome, and limitations. Hardware reports additionally record actual device/provider,
rate/channel settings, duration and continuity/queue/history measures. Local native
capture is not PN54 evidence. Archive integrity and passing tests are not musical
feasibility. Retain a separate record for final model calibration and physical trials.
