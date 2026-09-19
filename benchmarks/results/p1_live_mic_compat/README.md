# Live microphone P1 compatibility checkpoint

Source:8e6922cd3070be001b50841d5023b687621796c1.
Lead amendment/base:1b1a489994a33d03f7841e9304cf0c43ad0e43fd.
Existing branch:codex/cp2-ml-real-audio.

## Change

P1CandidateAnalyzer now executes its actual frozen runner on compatible complete
44100Hz/176400-sample file AND live_microphone windows with an exact reference span.
Execution precedes configured-family masks, bass instance counts, missing target
bass activity and candidate-mode publication gating. No independent normalization,
new model, training, threshold tuning or frozen-artifact change occurred.

The runner produces drums/bass/other/vocals/guitar/piano in memory. Public
AnalyzerEvidence remains source_levels/dBFS_rms, bass-only; unsupported/unknown
configured families remain invalid/null. Microphone bass may be active/observable/
valid while uncalibrated_candidate and real_room_not_validated remain action-limit
reasons. Probability/calibration/production advice are NOT authorized.

Reference spans match relative canonical intervals exactly, including the1-second
hop and explicit restart at0. Gaps preserve song position or Runtime marks alignment
unavailable. No matching span means matched_reference_span_unavailable; no DTW,
tempo tracking or fabricated alignment.

## Instrumentation

analyzer.execution_diagnostics() returns started/completed actual apply_model call
counts and the latest call index, inference duration, source order/shape, per-source
waveform SHA-256 and source levels. Reference inference also counts. No PCM/stems
are retained by diagnostics. A separate tiny lock prevents status readers from
blocking on the global multi-second model execution lock; this has a regression test.
Runtime remains responsible for capture freshness, queue depth, dropping and timing
aggregation. The existing loader/factory and five-ID model/profile interface is unchanged.

## Validation

All ML/shared suites passed:
training29 + analyzers51 + benchmarks38 + shared33 = **151 tests**.
Commands:python -m unittest discover -s DIRECTORY -q for
training/tests, analyzers/tests, benchmarks/tests and core/contracts/tests.
Source audit/self-tests passed with zero findings.

The21 focused P1 tests distinguish injected contract checks from the actual frozen
CPU model. Injected tests cover no configured bass, null reference bass, support masks,
relative hop/restart matching, explicit missing alignment, and nonblocking diagnostics.
Actual-weight regression verifies identical file/mic PCM produces identical six-source
waveform hashes and levels with actual model calls, alongside the frozen base/adapted
identity and published smoke parity.

actual_weight_file_mic_parity.json records the standalone command run from clean
source8e6922c:

    python -B -m benchmarks.p1_candidate_smoke --candidate models/candidates/nano4-p1-adapted-mvp-v1 --cache-dir HOST_TEMP_CACHE --device cpu --output benchmarks/results/p1_live_mic_compat/actual_weight_file_mic_parity.json

- Actual model calls:reference1, file2, repeated file3, microphone-identity replay4.
- All six source waveform hashes and levels match exactly across file/mic execution.
- Raw microphone bass is valid; uncalibrated/real-room limitation reasons remain.
- File inference6.384s; microphone-identity replay7.340s on this local CPU.
- Upstream SHA-256:34c22ccb381c6f9fdbf324f04e1e2fe21aaaf293f5ded163a162697ff9a02ddd.
- Adapted SHA-256:b8293c362802e863109c9bec82b50c8211b63ad3947a53a12bd5d81eab0a6229.

This replay uses actual weights and the existing restricted MoisesDB-derived
validation fixture, changing only acquisition identities. It is NOT actual physical
microphone capture, new model-quality evaluation, public redistribution approval,
or real-time/PN54 validation. Exact original provenance/split/gain, inference profile,
seed and input/model hashes remain in the JSON. No raw audio is copied here.

The physical microphone/worker/UI acceptance belongs to Runtime. Slow CPU inference
must not be relabeled fresh; publication age and dropped frames remain explicit.
Production calibration/action authorization stays NO_GO.
