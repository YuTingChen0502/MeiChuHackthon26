# P1 RealAnalyzer candidate checkpoint

ML / REAL_ANALYZER_CANDIDATE_READY

Implementation tested at exact source185d864e4d291227c23bbf57ad002f330cd73c67.
Lead basee8d1aeced5112d5dcd3e145a2ed32f3e043c8fb8 is an ancestor; existing ML branch preserved.
Publication01eaf5ddcc439efe799be61e54589d331c8556c6 and original remote experiment
3d161dd86c941e4a72ac4053ac795b0c3f7e5cb0 retain their separate identities.
The evidence-only checkpoint containing this report is reported separately in the handoff.

## Consumed artifacts and code

Frozen directory: models/candidates/nano4-p1-adapted-mvp-v1/.
The loader prefers its verified complete archive; it never substitutes a download/cache checkpoint.

- Upstream base SHA-256:34c22ccb381c6f9fdbf324f04e1e2fe21aaaf293f5ded163a162697ff9a02ddd.
- Adapted subset SHA-256:b8293c362802e863109c9bec82b50c8211b63ad3947a53a12bd5d81eab0a6229.
- Archive SHA-256:5963e80929e2fa987f223056dacf70659066ef07154b169447e1864dd5e933ad.
- Base/projection module before/after hashes match the frozen publication, and adapted modules differ.
- Winner manifests, thresholds, taxonomy, evidence and weights remain unchanged.

ML-owned additions:
analyzers/separation/p1_bundle.py, p1_runner.py, p1_candidate.py;
analyzers/tests/test_p1_candidate.py;
models/p1_frozen_spec.json and P1_CANDIDATE_INTEGRATION.md;
benchmarks/p1_candidate_smoke.py and this evidence directory.

[Exact host invocation and limitations](../../../models/P1_CANDIDATE_INTEGRATION.md)
documents the closure passed as Runtime's injected loader, candidate mode, profile, cache and44100/176400/44100
rate/window/hop. No root dependency or shared/public contract was changed by the implementation.

## Verified behavior

Offline hash validation precedes safe weight deserialization. Exact HTDemucs6s base is reconstructed,
then only the two frozen final projection modules are replaced. No training or model race occurred.

Input processing preserves scale, duplicates mono to dual mono and consumes estimates in memory.
Reference preparation stores only legitimate reference measurements/PCM hashes/identities, never labels.
The cache can be reopened across instances with the same five-ID profile and host cache directory;
changed model/profile/configuration/target, missing/corrupt cache, or mixed reference timelines fail closed.

AnalyzerEvidence mode is source_levels, units dBFS_rms. Explicit candidate mode exposes raw bass
observation and target source levels only. Every configured family gets a row. Unsupported families
are invalid/null with unsupported activity; unknown families are invalid/null with INSUFFICIENT_EVIDENCE.
Repeated bass instances are ambiguous. Below-floor or unavailable evidence never becomes Normal.

No calibrated probability, derived state, advice, common-mode centering or workflow transition is
constructed. calibration_metadata and acceptance_metadata are None; production acceptance is rejected.
Default candidate mode is disabled. Core's existing three-valid-source rule remains unchanged, so
this bass-only candidate cannot authorize centered balance/numeric correction.

## Validation and CPU smoke

validation.json retains exact source SHA, commands, environment and complete output.
Full scripts/validate.py:226 Python tests (shared28/runtime30/integration54/training29/analyzers47/benchmarks38),
34 UI tests, unchanged complete Fake HTTP/WS/SQLite smoke and release audit/self-tests passed.
The candidate-specific17 tests cover weights, hashes, identities, deterministic real-model inference,
input amplitude, null support masks, label isolation, profile/window/reference rejection and cache reuse.

The initial full-test command exited zero but Windows CP950 failed to capture UTF-8 stdout.
The same unchanged source was revalidated with explicit UTF-8 to retain the complete log.
Existing TorchScript/Python3.14 deprecation warnings are unrelated and non-failing.

cpu_smoke.json uses the existing restricted MoisesDB-derived validation pair with its original
manifest/pair-plan/parent/split/gain provenance. It is NOT synthetic audio, fresh-final evidence,
public/demo media, or new musical feasibility research. No raw audio is copied into this evidence directory.

Actual local CPU smoke:

- Repeated AnalyzerEvidence identical.
- Published-vs-local raw bass delta difference:0.0000517824dB.
- Reference source-level difference:0.0001217662dB.
- Observation source-level difference:0.0001735486dB.
- Engineering cross-platform tolerance:0.01dB; no action threshold was changed.
- Model load3.964s; reference preparation7.641s; observation inference7.929s.
- Python3.14.3/Torch2.11.0+cpu/Torchaudio2.11.0/Demucs4.0.1/NumPy2.4.3.

This CPU observation time exceeds the four-second audio window and one-second hop.
It is a portable correctness smoke, not real-time or PN54 qualification.

## Remaining Runtime/product gates

Runtime can consume the committed explicit loader now; there is no missing model byte dependency.
Optional Torch/Demucs/NumPy environment is required; CUDA is not required. ROCm is an available
adapter path through Torch device selection but has not been validated by this local CPU run.

The host must supply comparable matched-digital content; uploaded-file metadata alone does not prove
acoustic provenance. Stable-texture matching, live microphone/room evidence and unmatched timeline
spans remain unavailable. Missing reference coverage remains insufficient rather than fabricated.
Only bass is candidate supported; final confidence remains UNCALIBRATED.

MI300-final lineage, held-out calibration, PN54 performance and physical room validation remain separate
gates. A later reviewed compatible MI300 P1 bundle can replace host pins/model bytes through the same
InstrumentAnalyzer interface. No production RealAnalyzer authorization is claimed.
