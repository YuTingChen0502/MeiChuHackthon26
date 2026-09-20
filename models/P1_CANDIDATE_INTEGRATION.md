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
all six actual source levels (including null below-floor estimates). It stores no ground-truth gain labels and does not publish reference coverage.
Cache content is hash-bound and persists across analyzer instances with the same supplied directory.
A target binds on first analysis and cannot be silently rebound. Missing/corrupt/incompatible context
fails closed. Cache preparation is bounded to1024 windows.

Cache payload version 2 includes `reference_policy` with policy ID
`p1-dataset-family-attempt-v1`, the exact five-family source mapping below, and
`partial_families: ["keys"]`. Per-window values are `source_levels_dbfs` keyed by
all six model sources. The existing `p1-reference:<sha256>` asset hashes the entire
payload; five public model identities and the frozen archive remain unchanged.
Version 1 or a mismatched policy returns `reference_context_reprepare_required`,
invalid/null measurements and no matched window. A structurally valid, hash/model/config/target-bound
version 1 cache still permits observation-side six-source separation diagnostics;
it never supplies comparison spans or target levels. Unsupported regimes, clipping,
bad PCM geometry, corruption, identity mismatches and target-binding mismatches still
prevent execution. A mismatched unknown policy is not treated as a compatible v1 cache.
Missing cache still returns
`reference_context_unavailable`; corrupt bytes, model/profile or configuration
mismatches fail closed. No values are inferred from the old `bass_dbfs` field.
Recovery: use existing POST song/reference with the retained original audio asset,
prepare a new immutable reference, and explicitly create a new session for the
same song. Never retarget an existing session silently. Valid v2 reference context
remains reusable through same-session microphone changes.

The synchronized-demo comparison is deliberately narrow: complete file or physical-microphone
observations with equal relative sample spans in the supplied uploaded reference. New capture/source
generations start at canonical zero; the host must restart reference playback/performance accordingly. A missing/ambiguous span does not trigger guessed alignment.
No learned room/context matcher exists. An uploaded-file flag alone cannot establish acoustic provenance:
the host must supply comparably timed content. This adapter does not certify that claim.
Stable_texture, clipping, wrong sample rate/window, changed five-ID profile or missing context fail
explicitly. A gap preserves relative song position or must be marked unaligned by Runtime; it must
not silently reset the song clock. No DTW, tempo tracking or section-jump alignment is implemented.

For compatible PCM and an exact span, real HTDemucs executes for both file and microphone inputs.
Configured families, missing target bass activity and missing physical calibration do not skip
execution. All six model sources are generated before supported-family publication masks.
real_room_not_validated and uncalibrated_candidate are raw-evidence/action limitation reasons;
they do not invalidate otherwise available bass perception. Numerical PA advice still requires
the unchanged downstream calibration/identifiability gates.

Evidence mode is source_levels with units dBFS_rms: observation source_level_db and matched
target_source_level_db. Dataset-family attempts follow the Lead-approved
DATASET_PERCEPTION_HINT_FREEZE.md, separately from historical empirical support:

| Canonical dataset family | Model source | Published matched measurement |
|---|---|---|
| bass | bass | Usable raw levels when both estimates exist |
| drums | drums | Usable raw levels; family_attribution_unvalidated |
| guitar | guitar | Usable raw levels; family_attribution_unvalidated |
| vocals | vocals | Usable raw levels; family_attribution_unvalidated |
| keys | piano | Partial proxy; invalid/null with partial_source_representation |

`attempted_families` and `candidate_families` list all five canonical families;
`validated_families` is bass only. Historical `supported_families` remains bass
only in candidate mode and empty otherwise. Production authorization remains false.
The MoisesDB handoff training_manifest.json has SHA-256
5e3c4e479603c995daf16c8497fb631fbfed40cab4463864abfaffe98046b976:
136 recordings from 68 parents with all five canonical families. This later
48-train-parent handoff does not change the actual Nano4 40-parent/four-supervised-family
training history. Keys was not a supervised adaptation family. These canonical
families are not claimed to exhaust all raw-corpus instrument labels.

Each configured instrument gets exactly one row. No piano alias is introduced;
unknown labels, including piano and other, remain unknown/invalid/null with
INSUFFICIENT_EVIDENCE. Generic other is never assigned a specific identity.
All configured rows sharing a mapped model source are invalid/null with
ambiguous_same_family_sources, so they cannot count as independent anchors.
Missing source or target activity is invalid/null with source_below_activity_floor,
never Normal. Missing alignment remains invalid/null while real inference continues.

For the four exact mappings, finite matched estimates above the existing frozen
-70dBFS floor can be valid/active/observable numerical source evidence in explicit
candidate mode. This is not verified physical instrument identity. Non-bass rows
retain family_attribution_unvalidated for uncertain Runtime presentation; all usable
rows retain uncalibrated_candidate, plus real_room_not_validated on microphone input.
No probability, directional suggestion, InstrumentState or PA action is constructed
here. Core/Runtime owns independent-anchor, relative-balance, freshness, capture and
quality gates, including the optional experimental non-numeric hint.

execution_diagnostics() returns bounded real-runner started/completed call counters and the latest
inference duration, six-source order/shape/RMS and waveform SHA-256 values. It stores no stem audio
and is separate from AnalyzerEvidence, calibrated confidence and frontend/model identity. Reference
preparation counts as real inference too. Runtime owns queue age, freshness and latency aggregation.

No calibrated probability or invented uncertainty feature is emitted. calibration_metadata() and
acceptance_metadata() return None; valid raw bass rows retain uncalibrated_candidate.
No InstrumentState, recommendations, common-mode centering, threshold decisions or workflow state
is constructed. Partial and ambiguous estimates never become valid anchors. Numerical
PA advice remains subject to unchanged downstream confidence/calibration gates.

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
uses only the published MoisesDB-derived restricted validation PCM, repeats identical inference,
compares raw bass source levels/delta to the published smoke using0.01dB cross-platform integration
tolerance, and replays identical PCM as a microphone acquisition identity. File/mic regression
requires actual model calls and exact waveform hashes for all six sources. Identity replay is
not physical microphone validation. This is not
an action threshold, retuning or a real-audio accuracy claim.

A later MI300 P1 candidate can supply a separately reviewed host trust spec and compatible new
manifest/base/subset identities through the same loader/interface. No remote manifest can register
itself. Actual MI300 lineage/calibration/freeze acceptance remains separate from engineering diagnostics.

Remaining limitations: uncalibrated, bass-only empirically supported matched-digital envelope,
no MI300-final artifact, no PN54 performance qualification, no validated real-room envelope,
no production numerical/action authorization. Microphone inference nevertheless executes now under
the Lead-approved synchronized-demo policy; this does not establish new acoustic model quality. CPU smoke latency
is measured in its report; it must not be represented as live real-time readiness.
