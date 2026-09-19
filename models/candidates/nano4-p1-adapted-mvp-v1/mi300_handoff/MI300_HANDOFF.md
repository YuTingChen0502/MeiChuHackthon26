# MI300 Adaptation Handoff

Nano4 method selection is complete. MI300 must reproduce and meaningfully adapt the frozen P1_ADAPTED path, not restart architecture research.

1. **Selected method:** `P1_ADAPTED`, HTDemucs 6-source matched-reference gain response with final output-projection adaptation.
2. **Upstream checkpoint:** `model_bundle/torch_cache/hub/checkpoints/5c90dfd2-34c22ccb.th`, SHA-256 `34c22ccb381c6f9fdbf324f04e1e2fe21aaaf293f5ded163a162697ff9a02ddd`.
3. **Nano4 adapted checkpoint:** `model_bundle/checkpoint.pt`, SHA-256 `b8293c362802e863109c9bec82b50c8211b63ad3947a53a12bd5d81eab0a6229`. This is reference/initialization evidence and was not produced on MI300.
4. **Dataset:** MoisesDB v0.1, archive SHA-256 `4cde33ce416ac7c868cffcb60eb31f5c741ab7ae5601cbb9d99ed498b72c48c1`, CC BY-NC-SA 4.0 non-commercial research.
5. **Split:** `training_manifest.json` and `pair_plan.json`. Train has 48 parents, validation 12, calibration 8. The eight prior CP2-final parents are training-only. CP2B fresh-final is excluded.
6. **Family balancing:** Equal-count guitar/bass/drums/vocals one-source lists, independently shuffled with `seed + epoch`, round-robin interleaved; batch size 8 yields two examples per family.
7. **Trainable subset:** `decoder.3.conv_tr.{weight,bias}` and `tdecoder.3.conv_tr.{weight,bias}` only, 13,860 optimizer-visible parameters and 9,240 effective four-family coefficients.
8. **Optimizer:** AdamW.
9. **Learning rate:** `1e-4`; weight decay `0`; global gradient clip `1.0`.
10. **Schedule:** Constant learning rate, no scheduler.
11. **Batch size:** Train 8, validation 8.
12. **Epochs/selection:** Ten epochs; evaluate each epoch and retain minimum family-balanced validation paired-gain MAE. No early termination in the frozen recipe.
13. **Gain policy:** One-source `[-6,-4,-2,+2,+4,+6] dB`; shared scale `0.1`. Zero-change, common `[-4,+4] dB`, and deterministic multi-source controls remain evaluation evidence.
14. **Loss:** Smooth-L1 paired gain delta `1.0`; source absolute-level Smooth-L1 `0.1`; scale-sensitive waveform L1 `10.0`. Do not use independent normalization or a scale-invariant primary objective.
15. **Frontend:** 44.1 kHz, four-second windows, mono family mixtures duplicated to dual-mono HTDemucs input.
16. **Command/config:** Use `execution_config.json` with the existing external `train_adapted.py` harness:

```bash
export PYTHONPATH=/work/austinhpc25/MeiChuHackathon26
python /work/austinhpc25/nano4_cp2_fastest_first_pass/cp2b_broad_family/p1_adapted/train_adapted.py \
  --config /work/austinhpc25/nano4_cp2_mvp_candidate_v1/mi300_handoff/execution_config.json \
  --output-dir /path/to/mi300-recorded-output
```

17. **Must change for MI300:** Only the environment, scheduler wrapper, filesystem locations, and ROCm/runtime mechanics required to execute the same semantics. Record exact Git SHA, job ID, ROCm/PyTorch versions, resources, timing, and output hashes.
18. **Must not change:** Architecture, trainable subset, frontend, taxonomy, gain/label semantics, family balancing, loss, split roles, or final-test discipline unless a concrete MI300 blocker is documented and escalated.

## Untouched Evaluation

`exposure_ledger.json` is authoritative for historical exposure. CP2 and CP2B final parents and their artist groups are already opened. They cannot become a new untouched MI300 final test. A future set must be selected from unexposed artist groups using metadata only, frozen before audio preparation or model inference, and must not be tuned after opening.

## Claim Boundary

- MI300 meaningful adaptation: not yet executed.
- PN54 deployment: not executed.
- Real-room microphone validation: not executed.
- Production RealAnalyzer enablement: not authorized.
