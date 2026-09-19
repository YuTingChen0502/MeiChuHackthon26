# Nano4 MVP Model Candidate v1

Status: `FROZEN_EXPERIMENTAL_MVP_CANDIDATE`

Repository: `3d161dd86c941e4a72ac4053ac795b0c3f7e5cb0`

## Frozen Method

- Method: `P1_ADAPTED`.
- Architecture: HTDemucs 6-source matched-reference gain response.
- Task adaptation: final frequency and waveform output projections only.
- Upstream checkpoint SHA-256: `34c22ccb381c6f9fdbf324f04e1e2fe21aaaf293f5ded163a162697ff9a02ddd`.
- Adapted projection checkpoint: `model_bundle/checkpoint.pt`.
- Adapted checkpoint SHA-256: `b8293c362802e863109c9bec82b50c8211b63ad3947a53a12bd5d81eab0a6229`.
- Trainable subset: `decoder.3.conv_tr.{weight,bias}` and `tdecoder.3.conv_tr.{weight,bias}`.
- Parameter accounting: 13,860 optimizer-visible parameters; 9,240 effective guitar/bass/drums/vocals output coefficients.

The bundle contains both the adapted projection delta and the exact upstream checkpoint needed to load it. The adapted module hashes differ from upstream and were reverified during smoke.

## Runtime Contract

Canonical inference is:

`matched reference + current observation -> adapted HTDemucs -> source levels -> source deltas -> common mode -> centered balance -> support and threshold gate`

- Sample rate: 44.1 kHz.
- Window: 4 seconds, 176,400 samples.
- Asset channels: mono or mean-downmixed stereo.
- Model channels: dual-mono two-channel input.
- Amplitude: preserve reference/observation scale; no independent peak or RMS normalization.
- Separator execution: split inference, overlap 0.25, shifts 0, seed 260920.
- Confidence: `UNCALIBRATED_QUALITATIVE_ONLY`.

## Support Mask

| Family | Status | Logical numeric output | Reason |
|---|---|---|---|
| bass | `SUPPORTED` | Available when activity and common-mode eligibility pass | Passed frozen CP2B calibration and fresh-final targets. |
| drums | `UNSUPPORTED` | `null` / abstain | Frozen fresh-final precision `0.8767 < 0.90`. |
| guitar | `UNSUPPORTED` | `null` / abstain | Improved diagnostically but failed calibration. |
| keys | `UNSUPPORTED` | `null` / abstain | Failed calibration; generic `other` is not mapped to keys. |
| vocals | `UNSUPPORTED` | `null` / abstain | Frozen fresh-final precision `0.8618 < 0.90`. |
| unknown family | `INSUFFICIENT_EVIDENCE` | `null` / abstain | Outside frozen taxonomy. |

Unsupported evidence is never converted to Normal and configured families are never silently omitted.

## Frozen Thresholds

- Bass minimum evaluated anomaly magnitude: 2.0 dB.
- Bass alert threshold: 1.5 dB centered balance magnitude.
- Activity floor: -70 dBFS for reference and observation source estimates.
- Centered balance requires at least three configured numeric model-source deltas.
- Coverage target: at least 0.60; precision 0.90; recall including abstentions 0.75; sign accuracy 0.95; MAE at most 2.0 dB.
- Common 3 dB threshold is diagnostic only and cannot expand action support.

## Tested Envelope

The action claim is bass-only relative-level evidence for comparable matched digital excerpts under the frozen CP2B regime. Selective validation-only digital noise evidence tested MUSAN ambient, babble, and speech at 20 and 10 dB observation SNR. Bass/drums/vocals passed the tested 20 dB cells, but there was no common 10 dB envelope and the bundle action mask remains bass only. The deterministic acoustic sensitivity check was simulated, not physical evidence.

## Deterministic Smoke

- Final smoke job: `405013`, one H200, 8 CPUs, 64 GiB, 10 seconds.
- Non-final fixture: existing validation parent `25789239-1075-43b9-bfc9-51dff4a29590`; no CP2B fresh-final data was reopened.
- Fixture intervention: bass `+4 dB`; expected gain was not passed to inference.
- Result: `PASS`, all 12 checks true.
- Repeated logical-output SHA-256: `57c9fab2521471fd91d4c719e974a7e09382df4d1b18f6bd63e21d3df71c68c0` for both independent runs.
- Bass raw delta: `+3.956268 dB`; centered balance: `+4.011835 dB`; alert state: `ANOMALY_CANDIDATE`.
- Drums, guitar, keys, and vocals each returned explicit null numeric evidence and `ABSTAIN` with reasons.
- Hidden benchmark labels accepted by inference harness: false.
- Adapted projection identity differed from upstream for both selected modules.

The initial smoke job `405008` also passed. It was superseded by `405013` after correcting only the recorded NumPy dependency version in bundle metadata; no model, threshold, inference, or support logic changed.

## Runtime And Size

- Adapted delta checkpoint: 60,361 bytes.
- Upstream checkpoint: 54,996,327 bytes.
- Model bundle directory: 55,114,516 bytes.
- Deterministic compressed model bundle: 50,803,256 bytes.
- Bundle archive SHA-256: `5963e80929e2fa987f223056dacf70659066ef07154b169447e1864dd5e933ad`.
- Smoke peak CUDA allocation: 668,539,392 bytes, approximately 637.6 MiB.
- Smoke process maximum RSS: 1,382,988 KiB, approximately 1.32 GiB.
- Final repeated cold-process totals: 1.192 and 1.205 seconds.
- Observation separation after model/reference setup: 82.5 and 82.0 ms.

These are H200 experimental harness measurements, not PN54 or production latency/memory guarantees.

## Inference Harness

Path: `runtime_smoke/inference_harness.py`

SHA-256: `352a99713b621e72ee2efe23885e4a168f2d8b80d603eb636036a2850e844535`

Conceptual command:

```bash
python runtime_smoke/inference_harness.py \
  --reference reference.wav \
  --observation observation.wav \
  --instrument-config instrument_config.json \
  --model-bundle model_bundle \
  --output evidence.json \
  --device cuda
```

The harness is external experimental integration evidence. It does not enable or replace production `RealAnalyzer`.

## MI300 Handoff

- Handoff: `mi300_handoff/MI300_HANDOFF.md`.
- Frozen policy configuration: `mi300_handoff/adaptation_config.json`.
- Executable-shaped configuration: `mi300_handoff/execution_config.json`.
- Training manifest: 48 train, 12 validation, 8 calibration parents.
- Pair plan: 3,264 train, 816 validation, 544 calibration pairs; optimizer uses 2,304 family-balanced four-core one-source train pairs.
- Architecture, frontend, trainable subset, gain semantics, family balancing, optimizer, constant `1e-4` learning rate, batch size 8, ten-epoch selection, and losses are frozen.
- MI300 may change only scheduler/filesystem/ROCm runtime mechanics unless a concrete blocker is documented and escalated.

The MI300 configuration has not been executed. CP2B fresh-final is already opened and cannot serve as untouched post-MI300 evidence.

## Exposure Ledger

`mi300_handoff/exposure_ledger.json` records all 240 MoisesDB parents with normalized artist identity, CP2 role, CP2B role, and prediction/training exposure. It records 84 exposed parents across 34 artists. Thirty-five parents from wholly unexposed artist groups remain metadata-only candidates, not a selected final set. Any future final must be selected using metadata only and frozen before audio/model inspection.

## Evidence And Limitations

The compact bundle copies the CP2B comparison report, final machine evidence, and method freeze. `model_bundle/evidence/index.json` references hashes for training, fresh-final, noise, simulated-acoustic, diversity, and external harness evidence without copying datasets.

Major limitations:

- Bass is the only action-supported family.
- Confidence is uncalibrated.
- Matched digital evidence does not establish mixed-room microphone behavior.
- Simulated acoustic sensitivity and digitally injected noise are not physical evidence.
- No absolute per-instrument SPL, autonomous mixing, or physical mixer-fault inference is supported.
- No MI300 adaptation, PN54 deployment, production RealAnalyzer enablement, or real-room validation occurred.

## Final State

- `NANO4 MODEL RESEARCH: COMPLETE`
- `NANO4 MVP CANDIDATE: FROZEN`
- `MI300 MEANINGFUL ADAPTATION: NOT YET EXECUTED`
- `REALANALYZER PRODUCTION ENABLEMENT: NOT YET AUTHORIZED`
- `PN54 DEPLOYMENT: NOT YET EXECUTED`
