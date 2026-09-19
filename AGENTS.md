# Repository Guardrails

These rules apply to the entire repository. If requirements conflict, stop and ask the project Lead; do not silently reinterpret scope or contracts.

## Authority

Use the following authority order:

1. For competition facts: `docs/official/AMD題目.pdf`, then `docs/official/AMD工作坊簡報.pdf`, then `docs/official/大松手冊.pdf`, then other official organizer/AMD material.
2. For product scope and locked decisions: `docs/product/INFO.md`.
3. For public data and API shapes: `contracts/PA_CONTRACTS_V1.schema.json`.
4. For implementation architecture: `docs/design/PA_TECHNICAL_DESIGN_V1.md`.
5. Tests, code, READMEs, and older discovery/handoff notes are subordinate. Older Phase A/B material is background only and must not reopen locked scope.

## Locked Product Scope

Build the PA Module MVP: a known per-song instrument configuration, an uploaded ideal reference, one mixed-room microphone, volume-first instrument attribution and relative level deviation, rehearsal calibration, human-approved baseline, live anomaly monitoring, corrective recommendations, and verification.

Uploaded-audio analysis and live microphone monitoring are both product inputs.

Critical live inference runs locally on PN54.

The current competition-compliance path is meaningful task-specific audio fine-tuning on MI300. The model artifact used by the demonstrated runtime must descend from that adapted path unless the Lead explicitly approves a switch to another compliant strategy such as RAG.

Tone/EQ, effects, mixer control, autonomous mixing, arbitrary unknown-song understanding, a Conductor Module, and section/beat/bar/phrase-aware control are stretch or out of scope.

Never implement section-aware automatic remixing.

Audio-context matching for comparability is allowed and may be required. It may determine which reference or baseline content is comparable to the current observation. It must not become a section-dependent target schedule or automatic remix policy.

## Rehearsal and Guided Calibration

The architecture must support optional guided calibration probes during rehearsal.

The PA workflow may request short instrument-specific samples, for example asking guitar or bass to play briefly, to obtain session-specific evidence before or alongside full-mix rehearsal.

These probes are calibration observations. They are not section-aware live remixing and must use the same shared analysis infrastructure.

The volume MVP does not require a complete expert soundcheck protocol before the core closed loop works, but the architecture must not make guided probing difficult to add.

## Ownership Boundaries

- **Input adapters** (`FileAudioInput`, `MicAudioInput`) acquire and frame audio only. Both must feed the same downstream frontend, analyzer, state, baseline, deviation, confidence, and verification pipeline; do not build separate offline and live analyzers.

- **Performance Core** owns shared audio preprocessing, noise handling, state tracking, reference/baseline management, deviation, confidence/abstention, and verification. It must not contain PA-specific workflow or UI logic.

- **InstrumentAnalyzer** owns audio perception and returns backend-neutral `AnalyzerEvidence`, such as source activity, source-level evidence, reference-conditioned deltas, and uncertainty features.

  Canonical `InstrumentState` is constructed downstream by the shared deviation/confidence pipeline.

  The analyzer must remain pluggable: separation-based, direct reference-conditioned, hybrid, and future backends must be replaceable without changing product workflow or public contracts.

- **PA Role Module** owns PA anomaly/action policies, recommendations, guided rehearsal workflow, and rehearsal/live state transitions. Future roles must plug in without rewriting shared sensing infrastructure.

- **UI/application layer** owns presentation, session control, and explicit human actions. It must not estimate audio state or silently mutate baselines.

- **Runtime/model adapters** own PN54/MI300, CPU/iGPU/NPU, inference-engine, and optional language-model specifics. Keep core and domain code backend-neutral.

- **Public contracts** live under `contracts/`. Do not change a public schema, field meaning, enum, or compatibility guarantee without explicit Lead approval.

## Non-Negotiable Behavior

- No LLM may perform or gate critical audio perception. Instrument detection, relative dB estimation, anomaly detection, confidence, and abstention must come from benchmarkable audio ML/DSP.

- An optional LLM may only explain or assist with an already-structured result.

- Baselines are never accepted automatically. Only the human PA's explicit **Accept as Baseline** action may promote a rehearsal state to the calibrated per-song baseline.

- Confidence and abstention are mandatory outputs and gates. When attribution is unreliable, report uncertainty and abstain instead of emitting false precision.

- Treat relative instrument balance and global mix level separately.

- Do not claim absolute per-instrument SPL from one microphone.

- Do not infer a specific physical mixer/fader fault merely from an observed acoustic balance deviation.

## Parallel Development Discipline

Before parallel write-heavy work begins:

1. Public contracts and shared internal interfaces must be frozen enough for the current milestone.
2. Each worktree must have exclusive file/module ownership.
3. Agents must not opportunistically edit another worktree's owned files.
4. If a required change crosses a frozen interface or ownership boundary, stop and report it to the Lead instead of silently redesigning the interface.
5. Public contract changes are integrated through the Lead before dependent work continues.

Read-only exploration, review, testing analysis, and research may run in parallel freely.

## Experiments and Portability

- Every experiment must record a reproducible configuration and ground truth: code/config version, dataset provenance and split, random seeds, instrument/gain perturbations, noise type and SNR, augmentation, model/checkpoint, runtime environment, thresholds, metrics, and the procedure that generated labels.

- Results without reproducible config and ground truth are not decision evidence.

- Prefer portable, backend-neutral dependencies.

- Do not add CUDA-specific packages, kernels, or assumptions unless they are isolated behind a runtime adapter with a non-CUDA path for AMD/ROCm or CPU execution.

- Nano4, MI300, and PN54 are execution environments, not independent sources of code changes.

- Code changes must originate from the Git repository / Codex worktrees.

- Every remote experiment must record the exact Git commit and experiment config.

- Avoid ad-hoc divergent edits directly on Nano4, MI300, or PN54.

## Execution Policy

When encountering a local, reversible implementation problem within your
owned files and the frozen architecture/contracts:

1. diagnose it,
2. apply the smallest correct fix,
3. run the relevant validation,
4. continue the assigned task,
5. report the issue and fix at the end.

Do not stop merely to ask permission for routine implementation fixes.

Stop and escalate to the Lead only if the required change would:
- alter locked product scope,
- change a public contract or shared interface,
- modify another lane's owned files,
- require a destructive or irreversible action,
- require unavailable credentials / permissions / paid resources,
- invalidate benchmark ground truth or experimental evidence,
- or require choosing between materially different product behaviors.