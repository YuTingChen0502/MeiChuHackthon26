# CP2B Broad-Family Method Comparison

Decision: **NARROW_ENVELOPE**

Selected MI300 adaptation direction: **P1_ADAPTED**, specifically the escalated HTDemucs 6s output-projection artifact with SHA-256 `b8293c362802e863109c9bec82b50c8211b63ad3947a53a12bd5d81eab0a6229`.

This is a packaging report over completed Nano4/H200 evidence. No model was run for this packaging task. No MI300 run occurred in CP2B, and this report does not claim MI300, PN54, real-room, microphone, production, or competition-runtime validation.

## 1. Executive Decision

CP2B is `NARROW_ENVELOPE`, not a broad `GO`. The selected adaptation direction is P1_ADAPTED because it is a genuine task-specific adaptation, materially expanded guitar coverage versus the historical baseline, and was evaluated without changing weights, thresholds, family support, or evaluator after the fresh-final freeze. This selection is not a claim that it wins every metric. At its frozen family-specific operating points, fresh-final support survives only for bass. Drums and vocals fail the `0.90` precision floor, guitar remains unsupported despite material improvement, and keys remains unsupported.

P1_BASELINE remains the historical off-the-shelf HTDemucs baseline. It is a comparator, not the automatic winner and not the selected MI300 adaptation direction.

## 2. Required Method Comparison

Abbreviations in the required table are `M` balance MAE dB, `C` coverage, `P` precision, and `R` recall including abstentions. P1 family cells use the untouched fresh-final result: frozen action metrics where an operating point exists, otherwise the predeclared common 3 dB diagnostic. P2 family cells use canonical validation at 3 dB because P2 was eliminated before fresh-final.

| method | guitar | bass | drums | vocals | keys | clean | simulated-acoustic | noise | runtime | implementation complexity | final support envelope |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `P1_BASELINE` | Diagnostic only: `M 1.076, C .659, P .571, R .538` | Diagnostic only: `M .126, C .997, P .981, R 1.000` | Diagnostic only: `M .151, C .996, P .977, R .992` | Diagnostic only: `M .247, C .996, P .976, R .969` | Unsupported diagnostic: `M 2.801, C .073, P .263, R .066` | Fresh 3 dB overall: `M .355, C .796, P .867, R .770`; historical off-the-shelf comparator | `SIMULATED_ACOUSTIC_ONLY`; bass/drums/vocals pass on 4-parent sensitivity, guitar `P .857/R .375/C .489`, keys `C 0` | Historical selective validation: drums/vocals pass all 20 dB cells; common 10 dB envelope fails | Historical H200 per-pair `p50 .0881769 s`, `p95 .0924909 s` | Low: fixed separator and paired-reference delta; no task training | Historical preliminary drums/vocals matched-digital envelope at true anomaly `>=4 dB`, alert `2 dB`, tested 20 dB SNR; comparator only, not selected or task-adapted |
| `P1_ADAPTED` | Unsupported after calibration despite fresh 3 dB improvement: `M .841, C 1.000, P .710, R .683` | **Supported** at frozen `2.0/1.5 dB`: `M .198, C 1.000, P .963, R 1.000` | Unsupported after final: frozen `M .203, C 1.000, P .877, R 1.000`; precision fails `.90` | Unsupported after final: frozen `M .306, C .998, P .862, R .974`; precision fails `.90` | Unsupported: fresh 3 dB `M 2.788, C .073, P .263, R .066` | Fresh common 3 dB overall: `M .403, C .864, P .894, R .793`; common diagnostic passes bass/drums/vocals but is non-actionable | `SIMULATED_ACOUSTIC_ONLY`; bass `P/R/C 1/1/1`, drums `1/.938/1`, vocals `1/1/1`, guitar `.900/.563/.989`, keys `C 0` | Selective validation: bass/drums/vocals pass all 20 dB cells; common 10 dB envelope fails | Escalated H200 per-pair `p50 .0853773 s`, `p95 .0894654 s` | Medium: two output projections, 13,860 optimizer-visible parameters, 9,240 effective four-family coefficients | **Bass only**, matched digital excerpts, true anomaly `>=2 dB`, alert `1.5 dB`; selected MI300 adaptation direction |
| `P2_ADAPTED` | Calibration unsupported; validation `M .633, C 1.000, P .957, R .239` | Calibration unsupported; validation `M .730, C 1.000, P 1.000, R .031` | Calibration supported at `2.0/1.5 dB`: `M .392, C 1.000, P .963, R .802`; no fresh run | Calibration supported at `2.0/1.5 dB`: `M .461, C 1.000, P .950, R .792`; no fresh run | Calibration unsupported; validation `M .865, C .999, P n/a, R 0` | Validation overall: `M .632, C 1.000, P .994, R .358`; eliminated at calibration | **Not run after elimination** | **Not run after elimination** | Batched H200 canonical eval: preprocessing+prefix `25.4918 s` plus adapted inference `0.8909 s` over 816 pairs | High: AST preprocessing/prefix cache, two adapted encoder blocks, direct head, uncertainty and learned gates | None; eliminated after calibration supported only drums/vocals |

The runtime column is not an apples-to-apples latency benchmark. P1 numbers are per-pair separator prediction distributions. P2 preprocesses and caches the full canonical set, then performs highly batched head/encoder inference; its `0.8909 s / 816 pairs` must not be compared directly to a P1 per-pair percentile or used as a PN54 claim. Likewise, the rows are not a single same-split leaderboard: P1 methods have untouched fresh-final results, while P2 was eliminated at calibration.

## 3. Status Vocabulary

| Status | Meaning in this report |
|---|---|
| `IMPLEMENTED` | Code/configuration and an identifiable artifact or execution path exist. |
| `TESTED` | The path executed on the stated benchmark data. |
| `EMPIRICALLY_VALIDATED` | It met the predeclared targets on the stated independent split and operating point; this never implies room or production validity. |
| `SIMULATED_ACOUSTIC_ONLY` | A deterministic synthetic RIR/mic-color transform was applied; this is not physical acoustic evidence. |

P1_BASELINE is `IMPLEMENTED` and `TESTED` as a historical digital comparator. P1_ADAPTED is `IMPLEMENTED`, `TESTED`, and `EMPIRICALLY_VALIDATED` only for bass in the untouched fresh-final digital benchmark at its frozen operating point. P2_ADAPTED is `IMPLEMENTED` and `TESTED`, with genuine adaptation verified, but is not fresh-final validated. The acoustic sensitivity result is `SIMULATED_ACOUSTIC_ONLY`.

## 4. P1 Adaptation Provenance

- Architecture: HTDemucs 6s with task-adapted final frequency and waveform output projections.
- Base checkpoint: `/work/austinhpc25/nano4_cp2_readiness_3d161dd/torch-cache/hub/checkpoints/5c90dfd2-34c22ccb.th`, SHA-256 `34c22ccb381c6f9fdbf324f04e1e2fe21aaaf293f5ded163a162697ff9a02ddd`.
- Selected adapted checkpoint: `/work/austinhpc25/nano4_cp2_fastest_first_pass/cp2b_broad_family/p1_adapted/escalated/results/htdemucs6s-output-projections-adapted.pt`, SHA-256 `b8293c362802e863109c9bec82b50c8211b63ad3947a53a12bd5d81eab0a6229`.
- Exact training config: `/work/austinhpc25/nano4_cp2_fastest_first_pass/cp2b_broad_family/p1_adapted/escalated/config.json`, SHA-256 `75b8a60ba232830346d088827f11f63bf8dd10ddd93a37c40eb3fca832814ea5`.
- Repository commit: `3d161dd86c941e4a72ac4053ac795b0c3f7e5cb0`; seed `260920`; ten epochs; batch size `8`; learning rate `0.0001`; bfloat16 autocast with float32 losses.
- Trainable parameters were only `decoder.3.conv_tr.{weight,bias}` and `tdecoder.3.conv_tr.{weight,bias}`; backbone trainable parameters were `0`.
- First-gradient L2 norms were `0.0484636571` and `0.1500478537`; both module hashes changed.
- Training used 1,920 one-source-gain pairs from 40 train parents and 576 pairs from 12 validation parents. No calibration, test, or fresh-final pairs were used.
- Initial to selected family-balanced validation gain MAE changed from `0.4529062659` to `0.3661391530`. Guitar changed from `1.1319502592` to `0.8881468177` dB.

The selected configuration is fully pinned in `selected-mi300-adaptation-config-v1.json`:

- Frontend: 44.1 kHz, 4.0-second/176,400-sample paired reference and observation waveform segments. Mono and stereo PCM are accepted; stereo assets are mean-downmixed to mono, stems are summed into mono mixtures, then each mixture is duplicated to dual-mono two-channel HTDemucs input. HTDemucs retains its hybrid waveform/frequency frontend. No resampling, per-example normalization, or peak scaling is performed.
- Taxonomy: canonical guitar/bass/drums/vocals/keys map to HTDemucs guitar/bass/drums/vocals/piano; model source order is drums/bass/other/vocals/guitar/piano; generic `other` is excluded. The selected adaptation loss supervises guitar, bass, drums, and vocals only.
- Pair generation: one-source gains `[-6,-4,-2,+2,+4,+6] dB`; common-gain controls `[-4,+4] dB`; zero-change control; deterministic multi-source cycle `[-2,+4,0,+2] dB`; shared scale `0.1`; clean/no-noise profile. The training filter uses one-source-gain pairs only; controls remain evaluation/calibration evidence.
- Family balancing: equal support is required across the four trained families, each family list is shuffled deterministically with `seed + epoch`, and examples are interleaved round-robin in config family order. With batch size 8 this yields two examples per trained family per full batch.
- Optimizer: AdamW, one parameter group containing all optimizer-visible parameters of `decoder.3.conv_tr` and `tdecoder.3.conv_tr`, learning rate `1e-4`, no scheduler/constant rate, weight decay `0`, global gradient clip `1.0`.
- Parameter accounting: 13,860 optimizer-visible coefficients cover all six output rows of both projection modules; 9,240 are effective core output coefficients for the four supervised source rows. The remaining backbone has zero trainable parameters.
- Loss: Smooth L1 paired gain-delta loss weight `1.0`; mean reference/observation source-amplitude Smooth L1 weight `0.1`; mean reference/observation waveform L1 reconstruction weight `10.0`.
- Training: batch size `8`, validation batch size `8`, ten fixed epochs, bfloat16 autocast with float32 losses, and best-checkpoint selection by minimum validation family-balanced paired-gain MAE. "Early stop" means retain the best of all ten epochs; there was no early termination.
- Augmentation: only deterministic controlled gain intervention and fixed shared scale. No stochastic noise, RIR, EQ, pitch, time-stretch, or peak-normalization augmentation was used in the completed run.
- Checkpoint contract: a PyTorch `.pt` dictionary containing record/schema type, base-checkpoint hash, trained family list, full model source order, exact trainable parameter names, nested CPU state dictionaries for the two projection modules, and the complete config.
- Frozen evaluation: activity floor `-70 dBFS`, missing-output penalty `12 dB`, target floors `P .90/R .75/sign .95/C .60`, MAE ceiling `2 dB`, and frozen family action points/statuses exactly as reported in Sections 6 and 8. The common 3 dB threshold remains diagnostic only.

The completed Nano4 run used **40** train parents, 80 recordings, and 1,920 four-family one-source training pairs. The authoritative later CP2B split declares **48** train parents by adding eight prior-exposed former-final parents to training. The recommended MI300 direction uses all 48 declared train parents, which would produce 2,304 four-family one-source pairs under the same grid; that 48-parent extension is **NOT_TESTED**. Those eight prior-exposed parents are training-only and may never become calibration or fresh holdout data. Exact parent IDs, split IDs, counts, and the authoritative split artifact/hash are pinned in the selected config.

## 5. P2 Genuine C2 And EfficientAT Fallback

P2_ADAPTED genuinely adapted AST encoder blocks 10 and 11. The encoder SHA changed from `722cc1ac0e8dcef5577fae8f908076e75b5243a8e7dd9054ed5c437ea8ba9cc2` to `65cbc2c038abdcedcc2f23b76bf8f46b49a6418112061b0695ba1daa53988e87`, and the first encoder-gradient L2 norm was `2.7668410773`.

EfficientAT was explicitly bypassed because the required torchvision source checkpoint was missing (`explicitly_bypassed_missing_torchvision_source_checkpoint`). AST was therefore the implemented broad-family C2 path. This fallback fact does not upgrade AST's evidence.

P2 calibration selected only:

| Family | Min anomaly dB | Alert dB | MAE dB | Coverage | Sign accuracy | Precision | Recall incl. abstention |
|---|---:|---:|---:|---:|---:|---:|---:|
| drums | 2.0 | 1.5 | 0.3917806365 | 1.0000000000 | 1.0000000000 | 0.9625000000 | 0.8020833333 |
| vocals | 2.0 | 1.5 | 0.4609914332 | 1.0000000000 | 0.9687500000 | 0.9500000000 | 0.7916666667 |

Bass, guitar, and keys had no candidate meeting all targets. P2 was eliminated at this stage; no P2 fresh-final, acoustic, or noise run occurred.

## 6. Calibration Contract

Targets were frozen before fresh-final access: precision at least `0.90`, recall including abstentions at least `0.75`, sign accuracy at least `0.95`, balance MAE at most `2.0 dB`, and balance coverage at least `0.60`. Missing predictions carry a `12.0 dB` penalty. Selection preferred the smallest minimum true anomaly and then the smallest alert threshold. Multi-source-gain cases were excluded from operating-point selection; zero-change and common-gain cases were retained as negative controls.

P1_ADAPTED calibration selected:

| Family | Status | Min anomaly dB | Alert dB | MAE dB | Coverage | Sign accuracy | Precision | Recall incl. abstention |
|---|---|---:|---:|---:|---:|---:|---:|
| bass | supported candidate | 2.0 | 1.5 | 0.1911582571 | 1.0000000000 | 1.0000000000 | 0.9696969697 | 1.0000000000 |
| drums | supported candidate | 2.0 | 1.0 | 0.1359596866 | 1.0000000000 | 1.0000000000 | 0.9056603774 | 1.0000000000 |
| guitar | unsupported | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| keys | unsupported | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| vocals | supported candidate | 2.0 | 1.0 | 0.2030710283 | 0.9375000000 | 1.0000000000 | 0.9677419355 | 0.9375000000 |

## 7. Fresh-Split Discipline

The method, artifact, evaluator hashes, operating points, and supported-family candidates were frozen at `2026-09-20T02:56:10+08:00`, before fresh-final audio access. Fresh-final inference used 16 parents, 10 normalized artists, 32 excerpts, and 944 deterministic pairs. Splits are parent-disjoint and normalized-artist-disjoint. The evaluator reports `prior_calibration_or_test_assets_accessed: false`, `optimizer_or_training_steps: 0`, and `no_retuning: true`.

The 944 pairs comprise 816 one-source-gain, 64 common-gain, 32 multi-source-gain, and 32 zero-change cases. Gain interventions were `-6, -4, -2, 0, +2, +4, +6 dB`. The source is real recorded MoisesDB material, but the observations are digitally constructed matched excerpts, not room-microphone recordings.

## 8. Frozen Fresh-Final Decision

P1_ADAPTED frozen family-specific operating points produced:

| Family | Frozen status | MAE dB | Penalized MAE dB | Coverage | Sign accuracy | Precision | Recall incl. abstention | Target result |
|---|---|---:|---:|---:|---:|---:|---:|---|
| bass | supported | 0.1984481680 | 0.1984481680 | 1.0000000000 | 1.0000000000 | 0.9629629630 | 1.0000000000 | pass |
| drums | unsupported after final | 0.2025127110 | 0.2025127110 | 1.0000000000 | 1.0000000000 | 0.8767123288 | 1.0000000000 | precision fail |
| guitar | unsupported before final | n/a | n/a | n/a | n/a | n/a | n/a | no frozen action point |
| keys | unsupported before final | n/a | n/a | n/a | n/a | n/a | n/a | no frozen action point |
| vocals | unsupported after final | 0.3055904281 | 0.3312360631 | 0.9978070175 | 0.9895287958 | 0.8617511521 | 0.9739583333 | precision fail |

No threshold or support set was changed after observing these results. Thus the defensible action envelope is bass only, on this digital protocol, at `|true anomaly| >= 2.0 dB` and a `1.5 dB` predicted alert threshold.

## 9. Common 3 dB Diagnostic

The common `3.0 dB` alert threshold was predeclared for method diagnostics, not selected after final. It passes all targets for P1_ADAPTED bass, drums, and vocals on fresh-final, but it cannot be used to rescue drums/vocals or retune the frozen action policy.

| Method | Family | MAE dB | Penalized MAE dB | Coverage | Sign accuracy | Precision | Recall incl. abstention |
|---|---|---:|---:|---:|---:|---:|---:|
| P1_BASELINE | bass | 0.1259585065 | 0.1571239697 | 0.9973753281 | 1.0000000000 | 0.9811320755 | 1.0000000000 |
| P1_ADAPTED | bass | 0.1984481680 | 0.1984481680 | 1.0000000000 | 1.0000000000 | 0.9809523810 | 0.9903846154 |
| P1_BASELINE | drums | 0.1508635595 | 0.2028334562 | 0.9956140351 | 1.0000000000 | 0.9769230769 | 0.9921875000 |
| P1_ADAPTED | drums | 0.2025127110 | 0.2025127110 | 1.0000000000 | 1.0000000000 | 0.9769230769 | 0.9921875000 |
| P1_BASELINE | vocals | 0.2469462261 | 0.2984947075 | 0.9956140351 | 0.9921259843 | 0.9763779528 | 0.9687500000 |
| P1_ADAPTED | vocals | 0.3055904281 | 0.3312360631 | 0.9978070175 | 0.9921259843 | 0.9760000000 | 0.9531250000 |

P1_BASELINE is stronger on several of these particular metrics. That does not make an off-the-shelf baseline the selected adaptation artifact or an automatic winner; P1_ADAPTED is selected as the MI300 adaptation direction because the required direction must be task-adapted, and its support is bounded by the frozen decision above.

## 10. Guitar And Keys

Guitar improved materially versus baseline on the untouched fresh split at the common 3 dB diagnostic: coverage `0.6586666667 -> 1.0`, penalized MAE `4.8046931042 -> 0.8409677075 dB`, precision `0.5714285714 -> 0.71`, and recall `0.5384615385 -> 0.6826923077`. It nevertheless failed calibration and has no frozen action operating point, so it remains unsupported.

Keys remains unsupported. At the common 3 dB diagnostic, adapted coverage is `0.0732984293`, precision `0.2631578947`, recall `0.0657894737`, and penalized MAE `11.3247396272 dB`.

## 11. Selective Noise Evidence

Post-selection P1_ADAPTED noise testing was validation-only on four preselected validation parents, 60 base pairs, and 360 family/noise/SNR tasks. It used observation-only MUSAN ambient, babble, and speech at 20 and 10 dB SNR with a 2 dB alert threshold. This was selective sensitivity evidence, not fresh-final evidence.

At 20 dB SNR, all bass/drums/vocals cells had precision, recall, sign accuracy, and coverage equal to `1.0`; MAE ranged from `0.3618456749` to `0.5779518030 dB`. At 10 dB SNR, no common passing envelope remained. Examples include drums precision `0.8823529412` ambient, `0.8` babble, and `0.8125` speech; vocals babble precision/recall/sign accuracy were `0.5/0.625/0.875`, and vocals speech were `0.4347826087/0.625/0.875`. Five dB SNR was explicitly excluded. Noise was digitally injected and is not physical-room evidence.

## 12. Simulated Acoustic Sensitivity

The acoustic test is labeled exactly `SIMULATED_ACOUSTIC_SENSITIVITY`. It used 92 validation pairs and a fixed sparse causal RIR/mic-color FIR with transform SHA-256 `47cab63d9a79cebcc9aa087cec14e7c941a6ff3a84ca22793342bcb20f274871`. It was applied after the gain intervention with no normalization.

This result is `SIMULATED_ACOUSTIC_ONLY`. It is not a microphone capture, room measurement, PA rehearsal, venue test, feedback test, or physical evidence. It cannot establish real-room support.

| Method | Family | MAE dB | Penalized MAE dB | Coverage | Sign accuracy | Precision | Recall incl. abstention |
|---|---|---:|---:|---:|---:|---:|---:|
| P1_BASELINE | bass | 0.1629531786 | 0.1629531786 | 1.0000000000 | 1.0000000000 | 1.0000000000 | 1.0000000000 |
| P1_BASELINE | drums | 0.0912865947 | 0.0912865947 | 1.0000000000 | 1.0000000000 | 1.0000000000 | 1.0000000000 |
| P1_BASELINE | guitar | 0.4889835162 | 6.3696115025 | 0.4891304348 | 1.0000000000 | 0.8571428571 | 0.3750000000 |
| P1_BASELINE | vocals | 0.3322414540 | 0.3322414540 | 1.0000000000 | 1.0000000000 | 1.0000000000 | 1.0000000000 |
| P1_BASELINE | keys | n/a | 12.0000000000 | 0.0000000000 | n/a | n/a | 0.0000000000 |
| P1_ADAPTED | bass | 0.3227731190 | 0.3227731190 | 1.0000000000 | 1.0000000000 | 1.0000000000 | 1.0000000000 |
| P1_ADAPTED | drums | 0.2656217393 | 0.2656217393 | 1.0000000000 | 1.0000000000 | 1.0000000000 | 0.9375000000 |
| P1_ADAPTED | guitar | 0.9242997909 | 1.0446878366 | 0.9891304348 | 1.0000000000 | 0.9000000000 | 0.5625000000 |
| P1_ADAPTED | vocals | 0.4877976328 | 0.4877976328 | 1.0000000000 | 1.0000000000 | 1.0000000000 | 1.0000000000 |
| P1_ADAPTED | keys | n/a | 12.0000000000 | 0.0000000000 | n/a | n/a | 0.0000000000 |
| P2_ADAPTED | all | not run after elimination | not run | not run | not run | not run | not run |

## 13. Family Diversity Metadata

| Split | Parents | Normalized artists | Core-family parent counts: bass/drums/guitar/keys/vocals |
|---|---:|---:|---|
| train | 48 | 17 | 48 / 48 / 48 / 48 / 48 |
| validation | 12 | 4 | 12 / 12 / 12 / 12 / 12 |
| calibration | 8 | 3 | 8 / 8 / 8 / 8 / 8 |
| fresh final | 16 | 10 | 13 / 16 / 13 / 10 / 16 |

Fresh-final genres are electronic `3`, pop `3`, rap `2`, rock `7`, and singer-songwriter `1`. Metadata subtype proxies include bass guitar/synth bass; acoustic, clean-electric, and distorted-electric guitar; drum machine and component/acoustic drum labels; grand piano, organ, other keys, synth lead, and synth pad; and background, female lead, and male lead vocals. These are exact native metadata labels, not inferred timbre classes. Parent and normalized-artist overlap checks pass.

## 14. Reproducibility

- Fresh-final manifest SHA-256: `9f6eed2993966cb671f19874e4dab97f3b766360f737a5bbeb2832935a5efcf3`.
- Fresh-final pair-plan SHA-256: `52bb0d08d525b28d652ce29182eb86e816d65df152a78d5bc7cb0484a666e97f`.
- Frozen split SHA-256: `b6d0699727372431759b991a8fd7922c6d8fea6e6f3a86755fec7a5701e9059a`.
- Method freeze SHA-256: `54a0c55b0b44ba74881c3df3e3fae441e978600f8b429bc4aa7ee5f71fe7180a`.
- Fresh comparison SHA-256: `6ff9aac0c28543fd4eb9a5b8ebd0fa4747e4400d310f02342cb99f05616cd6ec`.
- Sensitivity report SHA-256: `23aafdc4992f4132c79087304ed10da7f851ba1b85cef8e2e3e514e6e8e2f535`.
- Segment length `4.0 s`; activity floor `-70 dBFS`; inference split enabled, overlap `0.25`, shifts `0`; P1 adaptation/final seed `260920` (historical baseline execution seed `260919`).

Runtime provenance is explicit: historical P1 baseline `p50 0.0881769164 s`, `p95 0.0924908512 s`; escalated P1 adapted `p50 0.0853772634 s`, `p95 0.0894653935 s`; P2 canonical validation preprocessing+prefix `25.4917719364 s` and adapted inference `0.8909344673 s` over 816 pairs. These H200 harness measurements differ in batching and preprocessing boundaries and are not PN54 or production latency evidence.

The selected config also pins the exact Nano4 adaptation, validation, calibration, method-freeze, fresh-final, sensitivity, split, manifest, pair-plan, script, wrapper, report, and checkpoint paths and SHA-256 values. A post-MI300 evaluation must use a new, never-opened parent- and normalized-artist-isolated holdout; the already opened CP2B fresh-final set cannot serve as untouched post-MI300 final evidence.

## 15. Slurm Resource Ledger

The exact sacct ledger is `cp2b-slurm-job-ledger-v1.json`. All successful jobs requested one H200 GPU, 8 CPUs, 64 GiB memory, one node, account `gov115094`, partition `dev`. Across the 13 requested job IDs, allocated GPU time is `1,509` GPU-seconds (`0.4191666667` GPU-hours), including the 4-second failed validation job; successful allocated GPU time is `1,505` GPU-seconds (`0.4180555556` GPU-hours). The submission-to-final-end span is `2,684` seconds, from `2026-09-20T02:27:04+08:00` through `2026-09-20T03:11:48+08:00`.

Failures were retained: `404705` had no node/GPU allocation and failed because the typed `--gres=gpu:h200:1` request was unavailable; it was resolved with the advertised H200 feature and untyped GPU request. `404718` ran for 4 seconds and failed because `BagOfModels` had no `decoder` submodule; the corrected evaluator completed as `404722`.

## 16. MI300 Selection And No-Run Claim

`selected-mi300-adaptation-config-v1.json` pins the exact reproducible P1_ADAPTED source path. It selects a direction for a future MI300 adaptation run; it is not evidence that such a run occurred. CP2B jobs ran on NVIDIA H200 nodes. No artifact in this package is claimed to have been trained, evaluated, benchmarked, or exported on MI300.

## 17. Claims Boundary

- No MI300 execution or MI300 performance claim.
- No PN54 execution, latency, power, deployment, or compatibility claim.
- No real-room, mixed-room microphone, live-PA, venue, audience, feedback, or physical acoustic validation.
- No production readiness, production-calibrated confidence, broad-family support, or automatic mixer-control claim.
- No absolute per-instrument SPL claim.
- No P2 fresh-final, acoustic, or noise claim.
- No support claim for drums, vocals, guitar, or keys at the frozen P1_ADAPTED action policy.
- Simulated acoustic and digitally injected selective noise are not physical evidence.

## 18. Final Recommendation And Evidence Index

Proceed only with the exact P1_ADAPTED output-projection path as the selected **MI300 adaptation direction**, while preserving a fresh, artist-isolated post-MI300 final split and the same abstention-aware targets. Do not deploy or present the current Nano4 artifact as MI300-derived. Do not retune the current frozen final. Treat bass-only digital support as the maximum empirically validated CP2B action envelope, and require new evidence for every broader claim.

Primary package files:

- `selected-mi300-adaptation-config-v1.json`: exact selected direction and explicit no-MI300-run claim.
- `cp2b-final-evidence-v1.json`: machine-readable decision and metrics.
- `cp2b-slurm-job-ledger-v1.json`: sacct-derived resource/failure ledger.
- `cp2b-external-sha256-manifest.txt`: recursive hashes and explicit exclusions.

Primary source evidence:

- `../cp2b-method-freeze-v1.json`
- `../p1_adapted/escalated/results/adaptation-report.json`
- `../p1_adapted/escalated/calibration/canonical-calibration-operating-points.json`
- `../p1_adapted/fresh_final/results/canonical-frozen-method-comparison-v1.json`
- `../p1_adapted/sensitivity/results/post-selection-sensitivity-v1.json`
- `../p2_adapted/results/adaptation-report.json`
- `../p2_adapted/results/calibration-operating-points/calibration-operating-points-report.json`
- `../split_audit/cp2b-family-diversity-audit-v1.json`
