# Frozen P1 RealAnalyzer candidate integration

Status: candidate implementation only; production authorization and confidence calibration remain absent.
Consumed publication: 01eaf5ddcc439efe799be61e54589d331c8556c6, directory
`models/candidates/nano4-p1-adapted-mvp-v1/`. Remote experiment origin remains
`3d161dd86c941e4a72ac4053ac795b0c3f7e5cb0`; it is not replaced by the integration commit.

## Host invocation

```python
from analyzers.separation.p1_candidate import make_p1_candidate_loader
from apps.api.config import runtime_options

loader = make_p1_candidate_loader(
    cache_dir=host_owned_context_directory,
    candidate_mode=True,  # explicit uncalibrated engineering diagnostics only
    device="cpu",
)
options = runtime_options(
    environment={
        "PA_ANALYZER_MODE": "bundle",
        "PA_MODEL_BUNDLE": "models/candidates/nano4-p1-adapted-mvp-v1",
    },
    loader=loader,
)
# The Runtime host binds these, never ordinary UI model tuning:
options.update(analysis_sample_rate_hz=44100, window_size_samples=176400, hop_size_samples=44100)
# Supply options to the Runtime service constructor.
```

Alternatively call `load_p1_candidate(bundle_path, cache_dir=..., candidate_mode=True, device="cpu")`
and use capabilities/prepare_reference/analyze/close directly. The candidate root, its exact
results/model_bundle.tar.gz, or an extracted model_bundle directory are accepted.
The explicit host loader closes over the fixed adapter; registry imports are never selected by
the manifest. Provider/adapter ID is `htdemucs6s-p1-output-projections-v1`.
No PA_HOST_REVIEW/production acceptance should be supplied; this candidate rejects acceptance.
Default candidate_mode=False returns null numerical evidence and does not replace Fake defaults.

capabilities.model carries five frozen-bound identities. Frontend and taxonomy IDs come from the
publication; level_scale_id is the integration identity
`htdemucs6s-source-rms-dbfs-before-centering-v1`. execution_profile_id hashes actual Torch, Demucs,
NumPy, device/backend, deterministic settings and checkpoint segment behavior. CPU/CUDA/ROCm or
framework changes therefore require a new profile/reference cache. expected_model compares all
five IDs. The profile reports the actual software environment, never the old H200 environment.
The source-level scale is before common-mode centering.

## Exact offline reconstruction

Host pins are in models/p1_frozen_spec.json. They were copied from verified archived bytes and
identify the publication commit; they are not regenerated from incoming untrusted bundles.
The complete archive SHA-256 is
5963e80929e2fa987f223056dacf70659066ef07154b169447e1864dd5e933ad.
Every required archived file is pinned, including frontend/taxonomy/threshold/limitations/evidence.
No extractall or remote fetch occurs. Missing, modified or mismatched artifacts fail closed.

Upstream HTDemucs6s:
34c22ccb381c6f9fdbf324f04e1e2fe21aaaf293f5ded163a162697ff9a02ddd.

Adapted subset:
b8293c362802e863109c9bec82b50c8211b63ad3947a53a12bd5d81eab0a6229.

The 60,361-byte subset is not a complete model. Both files must verify before deserialization.
The upstream checkpoint uses weights_only=True with explicit HTDemucs/Fraction safe globals.
Its exact class/state reconstructs the single-network bag offline. The subset uses weights_only=True
and strictly replaces only decoder.3.conv_tr and tdecoder.3.conv_tr weight/bias tensors.
Before/after module hashes must match the publication, and both modules must differ.
No optimizer, training step or checkpoint substitution occurs.
The committed smoke WAVs are restricted validation research fixtures, not synthetic audio or public demo assets.
Their dataset/split/intervention provenance is retained; this integration grants no redistribution rights.

The input is exactly mono44100Hz/176400 samples, duplicated to dual mono without independent
normalization, clipping rescaling or saved-stem processing. The frontend rejects other shapes;
shared Runtime owns acquisition/downmix/resampling. split=True, overlap=.25, shifts=0 and seed260920
match the frozen harness. The original bag.segment=4 assignment does not override the underlying
checkpoint's 39/5-second training segment in Demucs4.0.1; this adapter preserves that exact behavior.
Deterministic mode and intraop threads are scoped and restored; actual interop threads are recorded.

## Reference and evidence boundary

prepare_reference accepts legitimate AudioWindows and InstrumentConfig only. Its private cache
stores five-ID identity, host pin hash, configuration, sample spans, window IDs, PCM hashes and
bass source levels. It stores no ground-truth gain labels and does not publish reference coverage.
Cache content is hash-bound and persists across analyzer instances with the same supplied directory.
A target binds on first analysis and cannot be silently rebound. Missing/corrupt/incompatible context
fails closed. Cache preparation is bounded to1024 windows.

The supported comparison is deliberately narrow: matched digital excerpts with equal absolute sample
spans in the supplied reference. A missing/ambiguous span does not trigger guessed alignment.
No learned room/context matcher exists. An uploaded-file flag alone cannot establish acoustic provenance:
the host must supply genuinely comparable matched-digital content. This adapter does not certify that claim. Microphone observations, stable_texture, clipping, wrong
sample rate/window, changed five-ID profile or missing context cannot produce candidate numeric evidence.
Accepted digital baselines can reuse the same preparation/context lifecycle; actual live-room or
re-timed baseline matching remains outside this candidate's evidence envelope.

Evidence mode is source_levels with units dBFS_rms: observation source_level_db and matched
target_source_level_db. Bass is the only candidate-supported family. Each configured instrument gets
exactly one row. Guitar/drums/vocals/keys are invalid/null with unsupported_family and activity=unsupported.
Unknown families are invalid/null with INSUFFICIENT_EVIDENCE and activity=unknown. Multiple configured
bass instances are ambiguous and invalid. Below-floor source estimates are invalid, never Normal.

Bass above the frozen-70dBFS floor gets raw source levels in explicit candidate mode only.
No calibrated probability or invented uncertainty feature is emitted. calibration_metadata() and
acceptance_metadata() return None; valid raw bass rows retain uncalibrated_candidate.
No InstrumentState, recommendations, common-mode centering, threshold decisions or workflow state
is constructed. Unsupported stems never become hidden valid anchors. Core's existing>=3-valid-source
rule therefore withholds centered balance and numerical advice for this bass-only evidence.

## Dependencies and verification

No root dependencies changed. The optional model environment needs NumPy, Demucs4.0.1 and compatible
Torch/Torchaudio; Torch must support weights_only and safe_globals (2.6+ API). Locally tested:
Python3.14.3, Torch2.11.0+cpu, Torchaudio2.11.0, NumPy2.4.3, Demucs4.0.1.
CUDA is not required. Torch CUDA devices also cover ROCm builds; that execution path is not validated
by this CPU smoke. Missing/incompatible optional dependencies fail explicitly, without Fake substitution.

```text
python -m unittest analyzers.tests.test_p1_candidate -v
python -m benchmarks.p1_candidate_smoke --candidate models/candidates/nano4-p1-adapted-mvp-v1 --cache-dir HOST_CACHE --device cpu --output benchmarks/results/p1_candidate_integration/cpu_smoke.json
```

The smoke command requires committed source, records exact integration/origin SHA and byte identities,
uses only the published MoisesDB-derived restricted validation PCM, repeats identical inference, and compares raw bass source
levels/delta to the published smoke using0.01dB cross-platform integration tolerance. This is not
an action threshold, retuning or a real-audio accuracy claim.

A later MI300 P1 candidate can supply a separately reviewed host trust spec and compatible new
manifest/base/subset identities through the same loader/interface. No remote manifest can register
itself. Actual MI300 lineage/calibration/freeze acceptance remains separate from engineering diagnostics.

Remaining limitations: uncalibrated, bass-only matched-digital, no MI300-final artifact, no PN54
performance qualification, no real-room envelope, no production authorization. CPU smoke latency
is measured in its report; it must not be represented as live real-time readiness.
