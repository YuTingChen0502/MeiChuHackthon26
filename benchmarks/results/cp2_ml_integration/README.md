# CP2-ML integration checkpoint

ML_INTEGRATION_READY = YES

Implemented and tested only. This milestone supplies no trained winner, real-data feasibility,
supported-instrument assertion, calibrated confidence, measured operating envelope, deployment
or physical demonstration. No remote training campaign was duplicated locally.

## Exact implementation and validation

- Generic integration: 096238a0ce5068d4e9a14971a3f66f7152d0bd11.
- Lead foundation synced: 98979e33125dfa286489e9cca2b4af49d661053a through merge
  7bdc143cd06c88af9c5ef1392a4f9d1ba772c125.
- Final reference coverage seam: 1477275744f40faff95386986185d9e87d259622.
- Release-safe intentional test URL construction: a3a4695316d0bb5c33559df716b94b053434c6f1.
- Full run from clean1477275: training29, analyzers30, benchmarks38, shared28 = **125 PASS**.
  Exact commands, source SHA, environment and outputs are in validation.json.
- The a3a4695 one-line test-only correction separately passed its disclosure regression and
  scripts/release_audit.py --self-test with zero source findings. Audit rules were unchanged.
- Runtime owner additionally reported four actual-loader integration tests passing, including
  factory/registry construction, durable references, exact identity, null/abstained unaccepted
  evidence, invalid bundle rejection and state-only availability transitions. Those tests remain
  Runtime-owned; the local125 count does not include them.

The existing direct CPU optimizer/export smoke tests remain regression tests on synthetic fixtures,
not a new local training campaign or musical evidence. Torch3.14 tracing deprecation warnings from
existing export tests did not fail the suite. Winner-specific export must choose a supported framework path.

## Completed generic infrastructure

Exact bundle layout, all required fields and CLI/API examples:
[CP2_ARTIFACT_BUNDLE_V1.md](../../../models/CP2_ARTIFACT_BUNDLE_V1.md).

Intake binds checkpoint/runtime SHA-256; Nano4/MI300 source run/Git/config/environment identity;
frontend/taxonomy/level-scale/profile/sample/channel/window compatibility; candidate family metadata;
dataset provenance/grouped splits/seed; benchmark/calibration/parity records; and adaptation lineage.
Missing, malformed, modified, unsupported or incompatible content fails explicitly.

Metadata-only evidence import copies no binary checkpoint, raw audio, dataset, optimizer state or cache.
Full artifact import is explicit, bounded and content-addressed. No source changes or manifest-driven
executable imports occur. Repository metadata rejects recognized credentials/signed URLs without
printing secrets or changing hashed source bytes. Remote provenance assertions still require review.

BackendRegistry and load_bundle use the frozen InstrumentAnalyzer / AnalyzerEvidence boundary.
RealAnalyzer owns generic identity/lifecycle/context bookkeeping, contract validation, accepted family
masking and safe invalid/null evidence. BackendUnavailable yields abstention. The host owns acceptance;
remote bundles cannot self-approve. Reference reuse works across instances with a shared host context
store and backend feature cache. Optional measured coverage is forwarded only under acceptance and
bounded by the reference PCM; nothing is fabricated.

Generic held-out evaluation, explicit event-label conversion, calibration fit/test evaluation,
matched artifact comparison, export callback and strict parity tools are available. The default
registry is empty. Numerical evaluation/calibration uses NumPy; generic loader/hash/intake succeeds
with NumPy/Torch/Torchaudio/Demucs imports deliberately blocked.

## Exact remote delivery expected

Deliver manifest.json plus referenced JSON: frontend, taxonomy, source-level scale semantics,
actual training config/environment/training report, dataset provenance and four grouped split lists,
hash-bound adaptation lineage proof, and any measured BenchmarkResult, CalibrationCandidate and
ExportParityReport records. Supply originating full Git SHA, run ID, execution site, seed, config
and environment hashes, five model identities, input profile, candidate families, raw uncertainty
feature identities and checkpoint/runtime file paths and SHA-256.

Binary checkpoint/runtime artifacts can remain external during metadata intake; loading requires
their verified local bytes. Unavailable calibration/parity references remain null and benchmark
references may be empty until measured. Such intake never authorizes numerical production.

## Exactly what remains

1. Winner-specific model loading/inference/frontend/reference-feature persistence and framework export
   behind the existing host adapter callbacks.
2. Measured evaluation/export parity using authorized real held-out inputs and intended hardware.
3. Fitted and independently tested calibration with actual accepted envelope/families/coverage.
4. Model/evidence bundle freeze and host-reviewed engineering or competition acceptance.

No public/shared contract change is required. Competition acceptance additionally requires auditable
meaningful MI300 adaptation ancestry. Local Gate A remains BLOCKED_EXTERNAL_ASSETS until authoritative
rights-cleared assets and review are supplied; independent remote campaigns are not asserted complete here.
