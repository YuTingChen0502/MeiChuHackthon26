# AI Performance Controller — PA Module
## Technical Implementation Design V1

**Date:** 2026-09-19  
**Basis:** INFO(1).md; AMD 題目(5).pdf; AMD 工作坊簡報(6).pdf; 大松手冊(4).pdf  
**Status:** Design and experiment specification. No training, PN54 profiling, or acoustic benchmark was executed in this design session. All proposed acceptance thresholds are engineering targets, not measured results.

## Executive decision

先做「有可比較性檢查的、單麥克風、音量偏差閉環」。以 **HTDemucs 6-source** 建立可解釋基準；在 **MI300 微調 EfficientAT MobileNet 的部分預訓練權重與任務 heads**；以相同資料、相同輸出語意比較 direct 與 hybrid。最終選擇必須同時通過 task metrics、calibration、PN54 sustained throughput 與 physical replay。

不先選 LLM，不先承諾 NPU，也不把 separator 的 source quality 當成 ΔdB 的量測準確度。

### Decision register

| Decision | Status | Interpretation |
|---|---|---|
| PA / volume first; one mic; uploaded reference; uploaded and live analysis | LOCKED | Product authority: INFO |
| Human adjustment, Accept as Baseline, local critical inference | LOCKED | No mixer automation; no cloud roundtrip in the live loop |
| Confidence and abstention | LOCKED | Unknown is not Normal |
| MI300 and PN54; fine-tune or RAG | LOCKED | Official requirements [F1] |
| Task-specific audio fine-tuning on MI300 | RECOMMENDED | Chosen compliance and product path; official rules do not uniquely mandate this exact training architecture |
| Demucs 6-source diagnostic baseline; EfficientAT direct/hybrid race | RECOMMENDED | All PA-task capabilities remain unmeasured |
| Exact supported instruments, window size, anomaly thresholds, minimum usable SNR | OPEN EXPERIMENT | Promote only after benchmark |
| CPU baseline; optional NPU/iGPU acceleration | RECOMMENDED / OPEN EXPERIMENT | Inventory actual PN54 before provider choice |
| Tone interface, optional local language explanation | STRETCH | Disabled in first release |
| Conductor, section-wise targets, automatic mixer control, absolute instrument SPL | OUT OF SCOPE | A protocol may exist; implementation does not |

### Source audit and operational deadlines

[F1] explicitly requires both AMD devices, real-world interaction, and at least one of fine-tune/RAG. Its report-completeness criteria include public GitHub, an English reproducible README, and a public operation video. These are submission deliverables, not optional polish.

[F2] p.6 describes CPU/GPU/NPU execution according to workload. Its p.19 installation example is not proof of the loaned machine's actual SKU, OS, or driver. Product-family specifications elsewhere in the slides must not be copied into the PN54 inventory.

[F3] printed p.7 requires the PDF presentation and public-during-demo GitHub link by **2026-09-20 11:00, Taiwan time**. Preliminary presentation is 7 minutes plus 6 minutes QA. Each team has a two-minute equipment-test slot in the 11:20–12:30 preparation period. Plan a precompiled, locally cached, offline-capable demonstration; do not leave model installation to that slot.

## Technical boundaries that must be explicit

1. **Mixture balance does not uniquely reveal mixer controls.** A guitarist playing harder, an upstream gain change, and an acoustic path change can produce similar microphone observations. Report an observed acoustic balance deviation, not a proven fader fault.
2. **An ideal studio reference and an accepted room-mic baseline are different domains.** Exact paired ΔdB claims are strongest for comparable content and an unchanged acoustic path. Cross-performance/cross-room reference comparison is advisory unless separately validated.
3. **No section-aware target implies a coverage limitation.** A single fixed normal envelope cannot also perfectly classify all intentional solos, dropouts, and dynamics. V1 keeps a fixed accepted target and abstains on unsupported musical contexts; it does not secretly implement section-dependent remixing.
4. **Instrument families are not individual mixer channels.** Two guitars are a guitar group unless an independently validated backend can disambiguate them. Known configuration is a prior, not proof that a source is currently audible.

---

# A. Recommended System Architecture

**RECOMMENDED:** one local application with a bounded audio worker, not a microservice platform.

```text
OFFLINE / DEVELOPMENT
Licensed isolated stems + provenance
        -> paired mixture generator + noise / acoustic augmentation
        -> MI300: fine-tune / validate / calibrate
        -> model bundle + preprocessing + taxonomy + evidence manifest
        -> PN54: compatibility test / export-parity test / profile

PN54 / PERFORMANCE CORE
UploadedFileInput ----+
                      +-> AudioFrontend -> WindowPlanner -> QualityGate
LiveMicrophoneInput --+         |                            |
                                +-> raw level / clip meter    +-> NoiseProcessor
                                                               (default identity)
                                                                    |
ReferenceManager -> model-specific ReferenceContext -----------------+
BaselineManager  -> accepted, immutable BaselineContext -------------+
                                                                    v
                                                    InstrumentAnalyzer
                                               A: separator + features
                                               B: paired learned estimator
                                               C: masks / separator + encoder
                                                                    |
                                                       AnalyzerEvidence
                                                                    v
                                                   ComparabilityGate
                                                                    v
                                                     DeviationEngine
                                                                    v
                                                     ConfidenceEngine
                                                                    v
                                             StateTracker / EventManager
                                                                    v
PA ROLE                                        PA anomaly + action policy
                                                                    v
                                                   Recommendation -> UI
                                                                    |
                                                               Human PA
                                                                    |
                                                         Action acknowledged
                                                                    v
                                         Fresh audio -> VerificationEngine

OptionalLanguageModel: explanation consumer only, never numerical authority.
InferenceBackend: model execution underneath each analyzer; not the PA policy.
```

Runtime concurrency: capture callback only buffers PCM and timestamps; a worker runs inference; the local API serves UI and commands. Audio capture cannot wait for HTTP, disk writes, model inference, or language generation. A bounded queue drops stale analysis work, records gaps, and resets event-persistence evidence after discontinuity.

---

# B. Module Specifications

All rows below are **RECOMMENDED** interfaces. A module may initially be a small class or pure function.

| Module | Responsibility / Input | Output | Dependency and replaceability |
|---|---|---|---|
| AudioInput | File decoder or native microphone capture | AudioChunk: float PCM, sample rate, sample index, clock and source IDs | File and mic implement the same iterator; no semantic labels in PCM interface |
| AudioFrontend | Validate, consistently downmix, resample, track DC/clipping/dropout | Canonical audio and quality metadata | DSP only; versioned, backend-independent |
| WindowPlanner | Assemble deterministic trailing windows | AudioWindow with exact sample span | Same windows for offline replay and streaming; no future audio |
| NoiseProcessor | Optional noise handling | Analysis audio plus transform/quality metadata | Identity implementation first; never silently changes gain |
| FeatureExtractor | Raw mix energy, bands, activity descriptors | Typed level features and diagnostics | Amplitude-preserving branch retained independently of normalized embeddings |
| AudioEncoder | Extract frame/patch representations | Embeddings / feature maps | Replaceable checkpoint and frontend; cache keyed by exact version |
| InstrumentAnalyzer | Mixture + known configuration + compatible reference context | AnalyzerEvidence with supported taxonomy, raw source levels or source deltas, uncertainty features | A/B/C adapters; no PA action strings |
| InferenceBackend | Execute a model artifact | Tensors and timing/provider diagnostics | Torch CPU/ROCm or ORT CPU/NPU/iGPU; explicit capability report |
| ReferenceManager | Analyze the full uploaded reference | ReferenceProfile and model-specific views | File content hash + analyzer/frontend/taxonomy IDs; no stem requirement |
| BaselineManager | Collect accepted room audio and freeze a profile | Immutable versioned BaselineProfile | Human authorization, quality checks, capture fingerprint; never self-updates in Live |
| ComparabilityGate | Check context support, activity, clipping, path compatibility | comparable / weak / unsupported + reasons | Separate from loudness anomaly logic; cannot reject a gain anomaly merely because gain changed |
| DeviationEngine | Convert evidence to the canonical level definitions in H | Source, common-mode and balance deltas | Handles evidence mode once; direct predictions are not baseline-subtracted twice |
| ConfidenceEngine | Calibrate prediction reliability and interval | ConfidenceState / abstention | Separate per deployed model/precision/operating profile |
| StateTracker | Smoothing, persistence, stale-data handling, event deduplication | Stable states and AnomalyEvent | Stateless model predictions cannot directly trigger UI actions |
| VerificationEngine | Compare fresh post-adjustment evidence to unchanged baseline | recovered / partial / not_recovered / inconclusive | Requires observable source; silence is not recovery |
| PARoleModule | Interpret anomalies; generate bounded human action | Recommendation and workflow transitions | Role protocol only; future conductor must not leak into V1 |
| ToneAnalyzer | Reserved contract for optional tone evidence | Optional typed extension | STRETCH; disabled by default |
| OptionalLanguageModel | Explain an already finalized structured event | Optional prose | STRETCH; can be removed without losing any core behavior |
| SessionStore | Persist projects, accepted profiles, events and provenance | Versioned local records and audit log | SQLite + local files sufficient; no cloud database required |

**Important boundary:** do not compare an A-generated baseline directly to B-generated source levels. Changing model, normalization, precision or noise processing requires a compatible profile view and validated calibration, or re-analysis of retained baseline audio.

---

# C. ML Feasibility Plan

## C1. Experimental ladder

| Stage | Test | What it can establish | Stop / fallback |
|---|---|---|---|
| P0: oracle arithmetic | Known wet stems -> level definitions -> expected labels | Label generation, global-vs-balance math, silence masks | Fix math before any model experiment |
| P1: separation | Mixtures only -> htdemucs_6s -> original-scale source energy | Whether source attribution and gain response survive separation | Wrong taxonomy or non-monotonic gain response blocks that instrument |
| P2: direct | Same pairs -> pretrained EfficientAT features + regression/classification heads | Whether lightweight features contain the needed information | Frozen feature linear probe is a diagnostic, not the final fine-tuning story |
| P3: adaptation | Unfreeze final encoder blocks on MI300 | Task-specific improvement over frozen representation | Check gradients/weights; stop by budget rather than running an open-ended search |
| P4: hybrid | P1 energy/masks + fine-tuned encoder + pair fusion | Whether separation helps enough to justify runtime cost | Compare at matched coverage and latency; do not stack models automatically |
| P5: physical | Held-out assets -> speaker -> room -> microphone -> PN54 | Real acoustic feasibility and sustained local execution | Publish the tested operating envelope, not synthetic-only claims |

PN54 export/compatibility smoke tests start alongside P1. Do not wait for training to finish before discovering that the inference graph cannot run locally.

## C2. Required controls

Zero-change AA pairs; global-only ±gain; one-source ±gain; two-source changes; instrument inactive; unsupported extra instrument; speech over music; unchanged music with louder noise; microphone-gain change; clipping; normal dynamics and source dropouts. Filename, augmentation seed, playback controls, injected instrument ID, and true SNR must not enter the model input.

Evaluation layers must remain separate:

- **Tier 1:** same recording, aligned excerpt, digital remix: exact injected labels.
- **Tier 2:** same recording, speaker/mic replay: exact digital intervention, acoustic measurement affected by playback chain.
- **Tier 3:** a different performance/arrangement: no automatic exact ΔdB label just because a fader injection is known.

A Tier 1/2 success is not evidence of full Tier 3 capability.

## C3. Initial go/no-go targets

**OPEN EXPERIMENT: proposed thresholds, not empirical results.** For one-source anomalies |gain| ≥4 dB in supported, observable contexts:

| Measure | Initial target |
|---|---|
| Attributed alert precision | ≥0.90 |
| Event recall, counting missed/abstained events | ≥0.75 |
| Sign accuracy on accepted predictions | ≥0.95 |
| Balance MAE on accepted predictions | ≤2.0 dB |
| Eligible-frame coverage | ≥0.60; also report all-frame coverage |
| False alerts in normal continuous audio | ≤1 per 10 minutes as an initial test target |
| Event detection latency | p95 ≤8 seconds for the initial 4-second window profile |
| Human correction verification | ≥9/10 controlled independent trials, also report uncertainty |

Short hackathon recordings cannot establish a production false-alarm rate. Report numerator, denominator, minutes tested, and confidence intervals. Include unconditional errors so that abstention cannot conceal a broken estimator.

---

# D. Recommended Initial Models

## D1. First benchmark set

| Candidate | Role | Why it is selected | Limitations |
|---|---|---|---|
| HTDemucs `htdemucs_6s` | Backend A | Official checkpoint explicitly includes guitar, in addition to bass/drums/vocals/piano/other [S1] | No PA ΔdB guarantee; heavy sliding-window compute; source bleed; piano caveat in upstream docs |
| EfficientAT `mn10_as` | Backend B quality-first candidate | Static MobileNetV3; about 4.88M parameters; released pretrained weights and downstream/instrument-tagging examples [S2] | Audio tagging is not gain estimation; requires our scale-sensitive branch and fine-tuning |
| EfficientAT `mn05_as` | Backend B edge-first candidate | About 1.43M parameters; same family/interface [S2] | Less capacity may hurt attribution; CPU latency still needs measurement |
| A features + fine-tuned EfficientAT | Backend C | Direct test of whether separated-energy evidence improves the actual task | Two branches are only justified by measured improvement |

Do not map a standard four-stem model's `other` to `guitar`. Do not default to `htdemucs_ft`: the official README describes a significantly more expensive inference path, and it does not solve the missing-guitar-taxonomy problem [S1].

**Critical separator integration:** Demucs documents that its saving path may rescale individual outputs to avoid clipping, breaking relative stem levels [S1]. Read in-memory source tensors at the original input scale; restore any common input normalization; never independently peak-normalize output stems. Avoid clipping instead of using hard clipping as a measurement fix.

## D2. Secondary candidates

**STRETCH:** Meta `sam-audio-small` for targeted extraction/teacher comparison after core probes. Its official implementation supports text/visual/temporal prompts, requires checkpoint access, and documents inference-memory/latency tradeoffs [S3]. Its existence does not establish ROCm compatibility, PN54 speed, or amplitude fidelity for this task.

**OUT OF SCOPE for first benchmark:** a generic LLM on raw audio; a large separator ensemble; or architecture names without a reachable checkpoint, documented taxonomy, and reviewable license.

No source reviewed here supplies a validated, drop-in model for this exact PA task. The paired gain-estimation adaptation is the project's ML work, not a pretrained capability we may assume.

---

# E. MI300 Training Plan

## E1. Data sources and rights

**RECOMMENDED:** begin with available, rights-cleared self-recorded stems; supplement with small research subsets only after checking the actual dataset terms.

| Data | Intended use | Constraint |
|---|---|---|
| Self-produced multitracks | First smoke test; public demo; genuinely held-out recording test | Retain creation/permission records; separate songs/takes for fitting and testing |
| MoisesDB | Real-recorded instrument-separated material | Official dataset uses CC BY-NC-SA 4.0; do not infer unrestricted commercial or contest/public-redistribution rights [S4] |
| Slakh2100 / BabySlakh | Guitar/bass/drums synthetic development and wider timbre variation | Synthetic domain; not a real-vocal benchmark. Use deduplicated split logic; verify dataset license separately from utility-code license [S5] |
| MUSAN speech/noise subsets | Speech, noise, speech-babble augmentation | OpenSLR lists CC BY 4.0; keep attribution [S6] |
| Self-recorded room/crowd ambience | Actual demo-domain noise | Record consent/privacy expectations; avoid publishing identifiable incidental speech |

Slakh's full distribution is large; use the author's prototyping subset or already available extracts rather than letting a full download block the first experiment [S5]. `ASSET_MANIFEST` must record origin, license/permission, attribution, file hash, and allowed publication status. Unresolved rights block public inclusion of that asset, not necessarily the whole code repository.

## E2. Pair generation

For the exact-label live-monitoring task, use the same source excerpt and stable source-specific acoustic paths in a pair:

```text
s_i -> h_i * s_i -> reference/baseline mixture
                    -> apply controlled source gains -> observed mixture
both branches: known common gain; independently sampled background noise
```

Start with a shared speaker/room response for the one-speaker demo. Later test different fixed `h_i` per instrument for more realistic spatial-source simulation. Keep `h_i` unchanged within a live calibration/observation pair when the target label is the injected gain.

Gain training: mostly one-source changes, plus zero-change, common-gain and multi-source controls. Draw continuous gain in [-6,+6] dB; evaluate a fixed grid {-6,-4,-2,0,+2,+4,+6}. Add common-gain augmentation independently. Sample SNR and noise independently of the anomaly label.

Do not independently normalize every reference/observation clip and then expect to recover absolute/common gain. Either apply a shared, recorded scale, or keep the exact scale factors for the raw-level branch. Balance labels are invariant to a common offset, but raw-level labels are not.

Do not inject a gain into a silent source and label it an observable 6 dB change. Separate configured, active, audible and attributable states. Mask regression loss on unobservable examples while retaining them for abstention evaluation.

For dry reference -> room observation, path coloration is a nuisance with a separate task regime. Either compute post-path source-energy labels from available stems, or mark exact control-gain estimation unsupported. Do not silently assign the same scalar label across unrelated performances or independently changed rooms.

## E3. Architecture and objective

**RECOMMENDED starting architecture:**

```text
reference/baseline windows -> shared pretrained encoder -> cached ref features
observed window           -> shared pretrained encoder -> observation features
raw log-power / band-energy branch ----------------------+
known-instrument mask -----------------------------------+
                                                         v
concat(ref, obs, obs-ref, obs*ref, level features)
                                                         v
small fusion MLP / temporal head
  -> source-level deltas / balance deltas
  -> source activity and anomaly direction
  -> uncertainty features / error scale
```

Use the encoder's frame/patch features, not only a final semantic class probability. Preserve scale-sensitive evidence; semantic similarity and a unit-norm embedding alone are not a calibrated gain meter.

A starting loss:

`L = λlevel Huber(d_hat, d_true) + λactivity BCE(activity) + λevent BCE(changed_sources) + λcommon Huber(c_hat,c_true) + λconsistency L_common_gain_invariance`

The level term is masked by observability and valid pairing. Start simple, tune weights on validation, and only add heteroscedastic/quantile heads if they improve held-out error and calibration. Separator pseudo-labels may support distillation, but controlled stem-derived labels remain the quantitative evaluation authority.

Training sequence: frozen-encoder head warmup -> unfreeze final one or two encoder stages -> compare with frozen and non-reference ablations -> calibrate on held-out material. The final exported inference path must actually use the MI300-adapted weights. A random head attached to a wholly frozen encoder is not the preferred claim of meaningful fine-tuning.

**Separator adaptation is conditional, not the first training job.** If A wins the perception/PN54 race while B/C do not, a timeboxed alternative is to fine-tune a small final decoder/projection subset of A on licensed stems with source-reconstruction plus paired gain-consistency supervision, then re-evaluate amplitude fidelity and deployment. This is an OPEN EXPERIMENT, not a guaranteed rescue. The final demonstrated path must use the adapted artifact; an unused trained B checkpoint cannot supply the fine-tuning claim for an otherwise unchanged A-only runtime.

## E4. Validation and budget

Split by song/recording, artist when possible, and underlying MIDI identity. All augmented versions of a parent stay in the same split. Use independent validation, calibration and final test subsets; hold out noise recordings and acoustic conditions separately. Do not call public test songs unseen if a pretrained separator may have used them. Add newly self-recorded test material.

Resource ledger: actual MI300 model/partition, visible memory, provided framework/runtime, permitted GPU-hours, elapsed time and checkpoint provenance. The team must set a total budget and stop condition before submitting training. Use the provided working environment; do not upgrade the host ROCm/driver as part of the experiment. Check a forward/backward/optimizer smoke test first. Use plain supported PyTorch operators, avoiding CUDA-only extensions unless ported and verified.

## E5. Export bundle and acceptance

```text
model_bundle/
  manifest.json
  model.onnx                    # portable initial neural graph
  checkpoint.pt                 # training/eager reference, where redistribution is allowed
  frontend.json
  taxonomy.json
  thresholds.json
  calibration.json
  licenses/
  evidence/
    training_run.json
    adaptation_ablation.json
    export_parity.json
    pn54_profile.json
```

Export real-valued neural operations first; keep STFT/log-power preprocessing on CPU initially. Test FP32 CPU parity before quantization. Quantized variants need representative calibration inputs and a new PA-task evaluation; model quantization is not a guarantee of unchanged outputs [S9]. Cache the exact accepted artifact locally; build versioned profiles for each deployed variant.

---

# F. PN54 Deployment Plan

## F1. Inventory before choices

Collect CPU SKU, RAM/available memory, storage, OS/build, audio-device IDs/formats, GPU/NPU identifiers, drivers, Python/framework versions, supported ORT providers, and model-loading diagnostics. Record actual provider assignment, not just provider installation.

The current official documentation consulted lists ROCm 10.0 and Ryzen AI Software 1.8. Those document versions do **not** prove either is installed on the loaned PC. ROCm compatibility depends on the actual hardware/software configuration [S7].

## F2. Backend order

| Backend | Use | Condition |
|---|---|---|
| PyTorch CPU | Correctness anchor and emergency eager path | Benchmark memory and sustained throughput |
| ORT CPU FP32 | First portable student deployment | Export-parity pass |
| ORT + Ryzen AI VitisAI EP | NPU experiment | Actual supported device/OS/drivers; inspect CPU/NPU partition and compile cache |
| Windows ML / supported iGPU route | Windows acceleration experiment | Installed stack and per-op execution verified |
| PyTorch ROCm / supported GPU runtime | Linux or other explicitly supported configuration | Exact GPU/OS/runtime matrix passes |

AMD documents automated partitioning between supported NPU operators and CPU operators, and reports/caches for that process [S8]. A successful model load is not evidence of a fully NPU-executed graph. ORT now describes DirectML as sustained engineering with new Windows features moving to WinML; keep it an optional adapter rather than a permanent architectural dependency [S10].

## F3. Audio/frontend policy

Native capture on PN54, float PCM, fixed input gain where available. Disable or verify AGC, speech enhancement, AEC and noise suppression. If gain transformations cannot be controlled, mark the capture profile limited and validate that exact profile. The UI must never capture system loopback as if it were the physical microphone.

Do not force every model to one sample rate. Store a canonical captured stream and deterministic adapters: Demucs-compatible rate for A; the checkpoint's declared frontend for EfficientAT. Downmix the full reference consistently with the mono observation path; check anti-phase/cancellation rather than assuming stereo reference energy equals room-mic energy.

## F4. Profiling

**OPEN EXPERIMENT starting profile:** W=4 s, hop=1 s; probe W=6 s if attribution requires it. Measure full preprocessing+inference+postprocessing p50/p95, warm/cold load, memory, dropped windows and 20-minute sustained execution.

For reprocessing overlapping windows, the necessary steady-state condition is **processing time per update < hop**, not merely real-time factor <1. A 4-second window taking 2 seconds has RTF=0.5 but cannot sustain a 1-second update rate.

Measure capture-to-published-result age separately from change-to-confirmed-alert latency. With trailing windows and persistence, a seconds-scale alert is expected by design; do not advertise sub-100-ms PA diagnosis from a sub-100-ms kernel time.

Fallback to a prevalidated smaller/CPU profile, explicitly exposing `degraded`, its new update rate, and any narrower coverage. Switching an execution profile requires its matched calibration and baseline compatibility. If no local profile sustains the required loop, report the limitation; a remote inference call is not an equivalent fallback to this MVP.

---

# G. Reference and Baseline Algorithm

## G1. ReferenceProfile

Analyze the full user-uploaded file through the same canonical pipeline. Retain metadata, instrument support, active-window coverage, robust level/band statistics, compatible embeddings and an acoustic-content support bank. A full song is not collapsed into one unconditional average that every 4-second live window must match.

For offline paired testing, align corresponding excerpts using only audio or an explicitly declared test pairing. Runtime must not receive playback filenames or fader values. Different performances need the comparability gate; exact correspondence is not assumed.

Reference comparison is advisory in rehearsal. Report “guitar appears more prominent than the reference; verify this balance” if the studio-to-room conversion has not been quantitatively validated. Calibrated-baseline mode can provide stronger numeric statements within its tested envelope.

## G2. Accept as Baseline

On request, freeze a technically valid recent rehearsal interval; initial collection budget 30–60 seconds, adjustable after probe. Require instrument-specific active coverage, no clipping/dropouts, acceptable comparability, and a stable capture fingerprint. Use robust summaries and preserve representative valid windows. Show coverage rather than declaring an entire song calibrated from a few active seconds.

The human may intentionally accept a balance that differs from the ideal reference. Record this explicit choice. Human aesthetic authority can override a reference mismatch; it cannot make missing or corrupt audio a valid baseline.

Baseline fields include song/configuration, accepted-by/time, model/frontend/precision versions, capture settings, source audio hashes, instrument coverage, normal envelopes, and limitations. Acceptance is atomic, creates a new immutable version, and does not overwrite an active incident's evidence.

A baseline created from an uploaded room recording may be valid for that documented capture setup. A dry uploaded mix is **not automatically** a venue-calibrated microphone baseline. Mark unverified capture provenance accordingly and require physical validation before Live activation for that setup.

## G3. Comparability without section-wise remixing

V1 stores one fixed accepted balance policy, not Intro/Verse/Chorus targets. The support bank checks whether instrumentation/texture and the capture setup resemble supported calibration conditions; it is not a mechanism for continually changing target gain.

Design the context features to be insensitive to the specific gain perturbation being detected. Validate that a +6 dB guitar anomaly does not simply make the gate reject all anomalous audio. For explicit same-excerpt verification, audio-content correspondence can improve matching without score/section interpretation.

**Declare the comparison regime in the model bundle.** The first quantitative profile is `matched_excerpt`: prepare fixed-duration baseline windows; identify a candidate corresponding window from audio-only features; check top-match separation and temporal continuity; otherwise abstain. Matching-feature gain invariance and robustness are OPEN EXPERIMENTS, not established capabilities. Exact benchmark pairing may be provided to the offline harness, but live selection must not consume player filenames, injected gains or fixture IDs. The accepted target remains zero residual balance deviation; matching content is a nuisance-control step, not a section-specific gain schedule.

Train and deploy with the same conditioning representation. A head trained on aligned 4-second reference/observation pairs must not silently receive a full-song averaged reference embedding at runtime. `stable_texture` / pooled-context estimation is a separate experimental profile and must be trained and evaluated with that same aggregation. Until that profile passes, unsupported different-performance contexts remain abstentions. Persist the comparison regime and the model-specific baseline context asset in the profile.

Unsupported context -> `not_comparable`, no numeric correction. Do not quietly call a solo “guitar too loud”, or report Normal when analysis is abstaining. Intentional changes and faults are not always identifiable from one waveform; the PA remains the authority.

## G4. Invalidation

Manual microphone movement, device/gain changes, an incompatible model/profile change or known venue change -> require revalidation/recalibration. Heuristics may flag suspected path changes, but cannot guarantee automatic recognition of every moved microphone. Live data never silently becomes the new baseline.

---

# H. Level / ΔdB Definition

**RECOMMENDED canonical semantics.** Equations below define the product measurement, not a claim that a model already measures it accurately.

For source i over a valid active window:

`L_i = 20 log10(RMS(source_i) + ε)`

`δ_i = L_i(observation) - L_i(baseline)`

In a stable linear path and the same musical excerpt, if microphone/playback common gain changes by G and the source intervention is g_i:

`δ_i = G + g_i`

Choose a common-mode convention:

`c = median_{j in reliable active sources}(δ_j)`

`d_i = δ_i - c`

`d_i` is the **balance deviation** shown in the primary PA card. With at least three reliable active sources and a majority unchanged, one-source guitar +4 dB yields c≈0 and d_guitar≈+4 dB. A common +4 dB on all sources yields c≈+4 and every d_i≈0.

The majority-unchanged assumption is an operating assumption, not a theorem about every performance. With two sources, insufficient stable anchors, or ambiguous simultaneous changes, report pairwise balance differences or an unattributed mix change; do not force “which fader changed”.

Pairwise quantities `δ_i-δ_j` are identifiable without choosing a common-mode origin. They are useful diagnostics and a fallback for relative comparison, not evidence about which physical control moved.

### Three distinct fields

| Field | Meaning |
|---|---|
| `observed_mix_level_delta_db` | RMS-level difference of actual microphone mixtures; can include increased noise |
| `common_mode_gain_db` | Robust common displacement estimated from attributable active sources |
| `balance_deviation_db` | Source delta after removing the common displacement |

An optional source-to-mix energy ratio is a **different** quantity. Its change is `δ_i - Δmix`, which is not generally the injected source gain. Example under four equal-power mutually uncorrelated sources: guitar +4 dB increases total mixture energy by about 1.392 dB; guitar's source-to-mix ratio changes by only about 2.608 dB. These are derived values, not measurements.

Training labels must follow the same convention: `d_i_true = g_i - median(g_active)`. For multi-source examples the centered label need not equal each raw injection. Keep raw injected gains, common-mode labels, centered balance labels and valid-source masks separately.

A source's dB value is digital/acoustic-relative evidence, not an absolute SPL or guaranteed mixer-fader readout. Use numerical floors only to avoid log singularities; below observable energy, emit unavailable/unknown rather than a huge negative dB.

---

# I. Confidence and Abstention

## I1. Define the event before the percentage

For actionable numeric anomalies, calibrate the probability of:

`correct attribution AND correct direction AND |balance error| <= 2 dB`

The 2 dB tolerance is an initial engineering choice. Presence probability, separation reconstruction quality, text/audio similarity and a regression head's raw score are not interchangeable with this event's probability.

## I2. Calibration

Train the perception model on train, select it on validation, then calibrate on a separate calibration set. Candidate reliability features include margin, raw error-scale estimate, activity, mask/embedding agreement, context distance, clipping/noise evidence and temporal disagreement. Fit a simple reliability mapping and evaluate it on the untouched test set.

Temperature scaling is a candidate for classification logits [S11]; it does not automatically calibrate dB regression or the joint correctness event. For magnitude intervals, start with held-out residual quantiles by supported operating regime; split-conformal methods are an extension. Their coverage assumptions do not promise validity under arbitrary venue/domain shift [S12].

On too little calibration data, show `uncalibrated`/qualitative confidence; do not display “92%” because a sigmoid produces 0.92.

## I3. Gate and policy

Technical hard gate: no clipping, no stale/dropout window, compatible baseline, supported source and observable context. Statistical gate: calibrated confidence threshold chosen on validation/calibration, acceptable prediction-interval width, and persistence.

**OPEN EXPERIMENT seeds:** alert entry at |d|≥3 dB with 3 consecutive valid updates; recovery at |d|≤1.5 dB with 3 valid updates. Overlapping windows do not constitute independent observations. Tune thresholds against false alerts per minute and event recall.

Low confidence -> `abstained`, public numeric estimate `null`, reason displayed. Normal -> only valid, comparable evidence inside the normal envelope. Source inactive -> `inactive`/`not_observable`, not “too quiet” and not recovery.

## I4. Recommendation and verification

Start with one change at a time. A possible policy for a confidently excessive source is a human-facing bounded step:

`step_db = -sign(d) * min(2, max(|d|-1, 0))`

This is a conservative trial step, not a derived physical inverse. A known linear demo player may be corrected directly by the operator, but the inference system must not read that control state.

Record adjustment start/completion. Verification uses windows whose entire sample span is after completion plus the settling policy; it checks the same instrument, same baseline version and adequate audibility. Outcomes: recovered, partial, not recovered, or inconclusive. No success because the instrument stopped playing or the microphone disconnected.

---

# J. Noise Benchmark

For clean music m and noise n at the observation point:

`SNR = 10 log10(P_m / P_n)`

For desired SNR S:

`n_scaled = n * sqrt(P_m / (P_n * 10^(S/10)))`

Measure after the relevant room/noise-path transforms. Keep zero-noise “clean” as a separate condition. Overall mixture SNR can be high while a quiet guitar has low source-to-interference ratio; retain source observability metadata.

| Dimension | Initial scope | Expansion |
|---|---|---|
| SNR | clean, 20, 10, 5, 0 dB | 15 and -5 dB |
| Noise | speech, babble/crowd, room ambience | unseen recordings, transients |
| Gain | -6,-4,-2,0,+2,+4,+6 dB | continuous off-grid values |
| Source | guitar, bass, drums; vocals if validated | additional family taxonomy |
| Acoustic regime | digital; fixed one-speaker/mic geometry | unseen RIR and physical placements |
| Musical context | comparable active mixtures | normal dynamics, solos, dropouts, different take |

Avoid the full Cartesian explosion initially. Run a stratified fixed validation matrix, then expand weaknesses. Every condition reports source attribution, sign, magnitude, anomaly precision/recall/F1, calibration, coverage and latency. Continuous normal streams separately measure alerts/minute and false recovery.

For physical tests, independently record music-only and noise-only at unchanged playback/mic settings to estimate controlled SNR, where the chain is sufficiently stable/linear. If this cannot be done, label conditions as uncontrolled ambient noise and do not attach an invented exact SNR. A live one-mic SNR estimate is not ground truth.

Default noise handling is no destructive denoising. Compare raw and denoised branches only when the denoiser improves final balance errors and calibration; a perceptually cleaner sound can still be a worse level measurement.

---

# K. State Machine

Implement orthogonal `session_mode` and `incident_state` to avoid duplicating the same adjustment logic in rehearsal and live. The named workflow below remains visible in the API.

| State | System action | User action | Transition | Failure / required data |
|---|---|---|---|---|
| PROJECT_SETUP | Validate song and instrument configuration | Create setlist/song/config | Upload accepted -> REFERENCE_UPLOADED | Unsupported taxonomy shown; project/config version required |
| REFERENCE_UPLOADED | Decode, hash, enqueue analysis | Wait/cancel/replace | Job start -> REFERENCE_ANALYZING | Bad format/size -> error; file asset ID required |
| REFERENCE_ANALYZING | Common-pipeline offline analysis | Wait/cancel | Complete -> REFERENCE_ANALYZED | Failed model/decode -> retry; job/model IDs required |
| REFERENCE_ANALYZED | Expose support and reference quality | Choose mic or rehearsal file | Start -> REHEARSAL | Unsupported source warning; compatible ReferenceProfile required |
| REHEARSAL | Compare with ideal reference where valid | Listen, adjust or request accept | Qualified anomaly -> ANOMALY_DETECTED; accept -> ACCEPT_BASELINE | Low quality stays rehearsal with abstention, not fabricated target |
| ANOMALY_DETECTED | Freeze event evidence and generate candidate action | Acknowledge/dismiss/start adjustment | Start -> PA_ADJUSTING | Event, confidence, target version and reason required |
| PA_ADJUSTING | Continue sensing; suppress duplicate recommendations | Adjust controls; mark complete | Complete -> RECHECK or VERIFY_RECOVERY | Pause/timeout remains unresolved; adjustment ID/time required |
| RECHECK | Use fresh post-action rehearsal audio | Listen/repeat/accept | Valid result -> REHEARSAL; accept -> ACCEPT_BASELINE | Insufficient fresh audio -> inconclusive |
| ACCEPT_BASELINE | Validate technical quality; atomically save accepted version | Confirm interval and intentional deviations | Save -> REHEARSAL; explicit Live request -> LIVE_MONITORING | Missing coverage/capture provenance -> blocked; human can accept aesthetics, not corrupt data |
| LIVE_MONITORING | Compare only against frozen accepted baseline | Monitor or end session | Persistent trusted anomaly -> LIVE_ANOMALY | Input/profile problem -> SUSPENDED; baseline ID required |
| LIVE_ANOMALY | Show instrument, evidence and one suggested action | Adjust/dismiss/mark intentional | Adjust -> PA_ADJUSTING | Ambiguous event stays unassigned, no exact correction |
| VERIFY_RECOVERY | Check observable post-adjustment evidence against same baseline | Wait/retry | recovered -> LIVE_MONITORING; partial/not_recovered -> LIVE_ANOMALY | inactive/noisy/stale -> inconclusive, never auto-recovered |
| SUSPENDED | Stop corrective recommendations; show cause | Reconnect, restore profile, recalibrate | Fresh validated input -> previous safe state | Input gap, mismatch, capture drift; reset persistence |
| ERROR | Preserve diagnostics, release resources | Retry/reset | Explicit recovery -> safe prior state | Error code, job/run ID and retryability required |
| STOPPED | Stop capture and finalize log | Start another song/session | New session -> setup/ready | No hidden background capture |

Switching songs cancels current temporal context; events and baseline references cannot leak across songs. An intent dismissal does not automatically overwrite the baseline.

---

# L. Backend / API Contracts

## L1. Analyzer interface

```python
class InstrumentAnalyzer(Protocol):
    def capabilities(self) -> AnalyzerCapabilities: ...
    def prepare_reference(self, audio: AudioAsset,
                          config: InstrumentConfig) -> AnalyzerReferenceContext: ...
    def analyze(self, window: AudioWindow,
                context: AnalyzerContext) -> AnalyzerEvidence: ...
    def close(self) -> None: ...
```

`AnalyzerCapabilities`: supported instrument families, sample-rate/channel requirements, context/window limits, evidence mode, model/frontend/precision IDs, reference-conditioning support and backend options.

`AnalyzerEvidence.evidence_mode`: `source_levels` or `source_level_deltas`. For the first, DeviationEngine computes a compatible reference difference; for the second, it consumes the already conditioned difference. Exactly one representation is authoritative per response. All tensors have declared units and validity masks. Do not subtract baseline twice or mix energy ratio labels with source-gain labels.

## L2. Local API surface

| Endpoint | Contract |
|---|---|
| GET /v1/health | Runtime status, actual execution provider, model ID, queue/dropout state; no credentials |
| GET /v1/audio-devices | Native capture device descriptors and supported formats |
| POST /v1/projects | Project and setlist metadata |
| POST /v1/songs | Song + declared instrument families; returns supported/unsupported mapping |
| POST /v1/audio-assets | Upload bytes; decode/size/duration validation; opaque asset ID, no arbitrary server path |
| POST /v1/songs/{id}/reference | Associate asset and start async reference job -> 202 + job ID |
| GET /v1/jobs/{id} | Progress, failure reason, retryability and artifact IDs |
| POST /v1/sessions | Start rehearsal/file/live session with explicit source and profile IDs |
| POST /v1/sessions/{id}/actions | Start/end adjustment, recheck, dismiss, pause, resume, stop |
| POST /v1/sessions/{id}/baseline | Accept a selected valid interval; version precondition + idempotency key |
| GET /v1/sessions/{id} | Full authoritative state snapshot |
| WS /v1/sessions/{id}/events | Sequenced AnalysisFrame, state transitions, events and verification results |

HTTP 409 for stale expected-version or invalid state; 422 for invalid input; 503 for unavailable model/device. Commands must include the incident/baseline version they act upon. Resubmitting an acceptance command cannot create multiple baselines. UI reconnects via a full state snapshot plus event sequence, not by guessing from the last displayed card.

**RECOMMENDED stack:** Python application/worker; typed models; a small local HTTP/WebSocket API; lightweight web UI; SQLite + files. Pin tested dependency sets separately for MI300 training, CPU deployment, and optional acceleration. Bind to loopback by default; recording/retention is explicit and local.

---

# M. UI Data Contracts

The companion `PA_CONTRACTS_V1.schema.json` defines the externally visible records, with illustrative valid/abstained frames. The schema validates structure; cross-record/version/time invariants still require application tests.

| Object | Essential fields |
|---|---|
| SongState | id/name/config version; instrument family list; reference/baseline IDs; workflow state |
| ReferenceProfile | id/song; source asset hash; model/frontend IDs; coverage; context policy |
| BaselineProfile | id/version/song/reference; accepted time; capture fingerprint; model/frontend; supported instruments; coverage/normal envelope; validity |
| AnalysisFrame | run/session/sequence; source; exact sample span; model/baseline versions; quality; global-level fields; InstrumentState[] |
| InstrumentState | family/group ID; activity; source delta; balance deviation; normal/too_loud/too_quiet/unknown; confidence; extension fields |
| AnomalyEvent | id/instrument(s); onset/confirmed time; direction; evidence-frame IDs; baseline; active/acknowledged/resolved state |
| Recommendation | event/source; human control hint; bounded step or qualitative action; evidence and expiry |
| ConfidenceState | calibration status/ID; defined probability event; probability or null; interval or null; abstention and reasons |
| VerificationResult | adjustment/event/baseline; post-action evidence; outcome; before/after; inconclusive reason |

Replace the ambiguous `level`/`relative_balance_db` with explicit `source_level_delta_db`, `balance_deviation_db`, and optional source-to-mix diagnostic names. A UI-compatible `deviation_db` may be an alias, but the API documentation must define it as the centered balance deviation.

UI displays session mode, current capture source, model/backend, profile status, card state and data age. Show supported/unknown explicitly. Under low confidence, omit numeric correction instead of merely greying a false-precision number. Display exact decimal resolution only when justified; “about +4 dB” or an interval is the preferred operator wording.

The fixture examples are labeled illustrative. Their values are not benchmark outputs and must never be used to imply model accuracy.

---

# N. Physical Demo Plan

## N1. Assets and isolation

Use rights-cleared multitracks to prepare a full mixed reference and held-out normal/+gain/-gain/corrected mixtures. Runtime receives only the mixed reference and the microphone signal. Stems may exist in a separate demo player because it represents the source environment, not a sensor available to the AI.

```text
Separate playback device / independent demo player
  -> rendered mixture or human-operated multitrack mix
  -> wired speaker
  -> actual acoustic room + separate noise source / real ambience
  -> one physical microphone
  -> PN54 inference
```

A speaker and suitable cables/stand are **team-provided needs**, not confirmed items in the supplied hardware kit. Use a fixed, documented speaker/mic geometry. The player must have no control/label data channel into the analyzer. Keep inference blinded to filenames and injected gains; randomize trial order. The model can access the legitimate uploaded mixed reference, not hidden reference stems.

## N2. Main sequence: approximately 2–3 minutes within the presentation

1. Show uploaded mixed reference and known instrument configuration.
2. Play a rehearsal condition through the speaker. Show a supported reference-relative warning, with uncertainty appropriate to studio-to-room comparison.
3. Human corrects the physical playback mix; system rechecks. Human selects an adequate rehearsal interval and presses Accept as Baseline.
4. Enter Live. Play normal audio long enough to demonstrate no alert.
5. Introduce a held-out guitar +4/+5/+6 dB condition plus manageable ambient noise. Wait for the validated persistence/latency budget.
6. Human reduces the source or plays the corrected mixture. System verifies recovery using fresh audible evidence.
7. Briefly increase interference enough to show honest abstention, then restore normal conditions.

Do not rely on the exact same excerpt being used to fit the model; reference conditioning is allowed, training contamination is not. If the reference-to-room estimate is weaker, show an advisory warning there and make the quantitatively benchmarked baseline-to-live comparison the technical centerpiece. This does not waive the product's rehearsal feature.

## N3. Evidence and fallbacks

Keep separate proof of MI300 adaptation, exported weight hash, PN54 execution provider/profile, and the physical input path. Prepare a rights-cleared public video of the genuine acoustic loop as backup, clearly labeled as recording if played. A WAV-only fallback is an offline product feature, not a replacement for the required physical demonstration.

A one-speaker demonstration proves behavior through one acoustic path; it does not prove a full multi-amplifier band in an arbitrary venue. State the tested setting on the evaluation slide.

---

# O. Risk Register

| Risk | Detection / consequence | Fallback and limit |
|---|---|---|
| Guitar attribution fails | Wrong source family or cross-instrument response | Use six-source taxonomy; add hybrid evidence; constrain to validated guitar/bass/etc. If only bass works, label guitar unsupported rather than relabel other |
| ΔdB inaccurate/non-monotonic | Gain sweep fails even in clean data | Check normalization, label semantics, silence and bleed; retain direction-only as explicit degraded/partial capability, not completed numeric MVP |
| Direct embedding loses gain information | Correct instrument but poor continuous response | Add raw log-power/band branch; fine-tune final blocks; compare hybrid |
| Noise weak / speech mistaken for vocal | Errors rise and calibration breaks with SNR/type | Train hard negatives; narrow published operating envelope; improve geometry; abstain. No invented live SNR |
| Normal dynamics cause alerts | High false-alert rate in unchanged full-song audio | Context gate, activity masks, persistence; publish coverage limit; no secret section-target controller |
| Not enough stable sources | Common-mode attribution ambiguous | Pairwise balance only / unassigned change / abstention; no fader diagnosis |
| Mic AGC / playback limiter | True intervention not preserved at sensor | Fix/verify capture/playback settings, leave headroom, flag clipping; revalidate actual chain |
| Mic/venue moves after calibration | Source-dependent spectrum/level shift | Known changes force recalibration; suspicious changes suspend; do not promise perfect automatic detection |
| PN54 incompatibility | Import/compile/provider failure | Early CPU/export smoke; use tested CPU bundle; optionally supported iGPU/NPU path |
| Too much latency | Queue grows, stale result age | Smaller student, validated longer hop, fewer unnecessary branches; show degraded mode. No remote critical inference |
| Unnecessary heavy LLM | Extra latency/memory with no task gain | Templates. Optional explanations outside critical path |
| MI300 not accessible / adaptation fails | No trained artifact in runtime | Resolve access early; smaller real fine-tune within quota. Pure DSP/pretrained-only runtime does not satisfy the chosen fine-tune route |
| Rights/pretraining contamination | Unclear assets or inflated “unseen” test | Self-produced public demo; provenance; grouped split; label pretrained-overlap uncertainty |
| False verification success | Silence/noise shift appears like correction | Require active source, compatible context, fresh post-action windows and unchanged baseline |
| Changed model invalidates profile | Baseline/model scale mismatch | Recompute compatible profile and calibration before resuming |
| Physical demo path leaks truth | Runtime reads fixture label or mixer control | Separate player; opaque asset IDs; audio-only analyzer input; randomized blinded trials |

---

# P. Implementation Order and Done Criteria

Time allocations are **planning timeboxes**, not benchmark predictions. Parallelize a model/data lane and a runtime/contracts lane; add a UI/demo lane only after the contract exists. Do not assume any specific team size.

| Order | Deliverable | Done criterion |
|---|---|---|
| 0 — immediately | PN54/MI300 inventory, resource budget, rights-cleared stems, physical speaker path | One captured WAV; known environment; readable model weights; no deadline-blocking download |
| 1 — first 1–2 hours | Pair generator, oracle math and common contracts | Zero/common/source gain tests pass; mixed-audio-only boundary verified |
| 2 — next 1–2 hours | A baseline + B import/export smoke | Gain-response/error table exists; lightweight model can execute on PN54 CPU |
| 3 — timeboxed parallel block | MI300 partial-backbone fine-tune; worker/file/mic integration | Actual encoder weights changed; adapted checkpoint saved; same PCM produces consistent downstream results |
| 4 — before backend freeze | A/B/C comparison, calibration, physical capture test | Select by matched coverage/error/latency; record explicit failures and operating limits |
| 5 — integration | Baseline acceptance, incident state, bounded recommendation, fresh-audio verification | Complete correction loop without labels or cloud; silence and disconnection do not claim recovery |
| 6 — release | Minimal UI, sustained PN54 run, offline launch, public evidence | Restart-to-demo works; model cached; documentation reproduces the actual selected path |
| 7 — submission buffer | English README, source/asset manifest, public recording, PDF and GitHub submission | Meet 2026-09-20 11:00 Taiwan deadline from handbook [F3] |

Reserve the final two hours before the submission deadline for integration/recording/documentation; no new backbone, LLM, driver or major schema change then. Stop training at the earliest of the authorized resource budget, chosen model-freeze deadline, or a failed continuation gate.

### Repository shape

```text
apps/api/                 local commands + snapshots + events
apps/ui/                  operator interface
core/audio/               input, frontend, windowing, quality
core/contracts/           schemas, typed objects, invariant tests
core/profiles/            references, baselines, compatibility
core/runtime/             queue, executor, state, confidence, verification
analyzers/separation/     A adapter
analyzers/direct/         B encoder, fusion, feature branch
analyzers/hybrid/         C adapter
roles/pa/                 anomaly and action policy
training/                 pair generator, losses, fine-tune, calibration
benchmarks/               digital/acoustic tests and raw result manifests
demo_player/              independent environment simulation, not imported by analyzer
models/                   manifests; only distributable artifacts
assets/                   provenance and download/generation instructions
README.md                 English reproducible setup and actual limitations
```

### Mandatory invariant tests

Identical source audio and matched timestamps give equivalent file/live downstream inputs. Common gain does not create per-source imbalance. `other` is not guitar. Silent sources do not create large negative dB. A stale frame cannot initiate or clear an incident. Abstained frames are not Normal. Baseline is immutable during Live. Verification frames begin after the adjustment cutoff. Model/profile mismatch blocks comparison. Demo labels never enter inference. CPU/export/quantized variants are evaluated against the same fixtures. No public artifact includes workshop credentials or private incidental recordings.

## Final engineering decision

The first irreversible commitment should be the **measurement definition and contract**, not a model brand. The first experiment should determine whether a real gain change produces a stable, correctly attributed response. The first release must preserve the whole human correction loop, including a truthful “cannot currently determine” state.

---

# Source Register

Sources establish competition facts or upstream capabilities only. They do not establish performance of this proposed PA system.

## User-provided authority

- **[F1]** `AMD 題目(5).pdf`, pp.1–3: Physical AI, MI300/PN54, fine-tune/RAG, scoring and public deliverables.
- **[F2]** `2026 梅竹黑客松 AMD 工作坊簡報(6).pdf`, slides 6, 11, 18–20: heterogeneous compute, repositories, ROCm and Lemonade framing. Credentials are deliberately not copied.
- **[F3]** `大松手冊(4).pdf`, printed pp.7–8: submission, setup and presentation timing.
- **[F4]** `INFO(1).md`: authoritative frozen product scope.

## Primary web sources consulted 2026-09-19

- **[S1]** Meta Demucs official repository: `https://github.com/facebookresearch/demucs` — checkpoint taxonomy and per-stem output rescaling warning.
- **[S2]** EfficientAT authors' repository: `https://github.com/fschmid56/EfficientAT`; associated paper `https://arxiv.org/abs/2211.04772` — static MobileNet checkpoints and downstream examples.
- **[S3]** Meta SAM-Audio official implementation and model card: `https://github.com/facebookresearch/sam-audio`; `https://huggingface.co/facebook/sam-audio-small`.
- **[S4]** MoisesDB publisher/repository: `https://github.com/moises-ai/moises-db`; `https://music.ai/blog/press/introducing-moisesdb-the-ultimate-multitrack-dataset-for-source-separation-beyond-4-stems/`.
- **[S5]** Slakh author release and split utilities: `https://zenodo.org/records/4599666`; `https://github.com/ethman/slakh-utils`. Dataset-site access was unreliable during review; dataset-license clearance remains an implementation check.
- **[S6]** MUSAN/OpenSLR: `https://www.openslr.org/17/`.
- **[S7]** AMD ROCm compatibility matrix: `https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html`.
- **[S8]** AMD Ryzen AI 1.8 deployment and operators: `https://ryzenai.docs.amd.com/en/latest/modelrun.html`; `https://ryzenai.docs.amd.com/en/latest/ops_support.html`.
- **[S9]** ONNX Runtime quantization: `https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html`.
- **[S10]** ONNX Runtime DirectML status: `https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html`.
- **[S11]** Guo et al., calibration: `https://arxiv.org/abs/1706.04599`.
- **[S12]** Angelopoulos and Bates, conformal uncertainty: `https://arxiv.org/abs/2107.07511`.
- **[S13]** AMD Lemonade server and current OGA flow: `https://ryzenai.docs.amd.com/en/latest/llm/server_interface.html`; `https://ryzenai.docs.amd.com/en/latest/hybrid_oga.html`.

## Optional language layer note

`Qwen3-4B-Hybrid` remains an inherited **STRETCH candidate**, not an installed/validated component. Current AMD documentation confirms Lemonade's OpenAI-compatible local endpoints and OGA's hardware/version-specific hybrid paths; it also warns that older optimized artifacts are incompatible with the 1.8 release [S13]. Query the actual installed model catalog and validate its exact artifact/runtime pair before using it. Do not let an unavailable inherited model alias block the PA release.
