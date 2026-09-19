# Current engineering status — 2026-09-20

**MVP_PRE_MODEL_READY is READY for model-independent software.** The complete
executable integration is `af342d89b0504d51af3319061dd8ce7b18527899`; subsequent
release/documentation commits retain that implementation. ML `fa706815`, Runtime
`25f8808b` plus launcher correction `eaf5b73d`, and UI `947dae26` are accepted.
See `docs/implementation/MVP_PRE_MODEL_READY.md` for the complete module matrix and
`docs/implementation/MVP_PRE_MODEL_VALIDATION.md` for exact test/browser/native
report evidence. Latest pushed main remains the authoritative source revision.

Canonical writers remain Lead, CP2-ML, **Continue CP2 native audio runtime**, and
CP2-UI in the existing `C:/Coding/MeiChuHackathon26-wt-cp2-*` worktrees. The duplicate
Runtime audit task has stopped. Nano4 and MI300 are independent execution/training
environments, not source worktrees. Either may supply the first engineering bundle;
the final competition artifact still requires meaningful official MI300 lineage.

Completed work covers the Fake/native/API/UI product, generic bundle intake,
empirical-policy consumers, deployment tooling and English release materials.
It does not assert measured real-music accuracy, fitted calibration or PN54 readiness.
No remote campaign result is accepted merely because it produces numerical outputs.

Release note: an organizer workshop PDF contained access details. Its authority copy
is retained locally but excluded from tracked/public source. Private Git history must
remain private. `scripts/release_audit.py` produces a scanned history-free source
export; see `docs/release/RELEASE_READINESS.md`. Do not paste private credentials,
signed dataset URLs or restricted data into evidence, docs or task messages.

The remaining critical path is remote artifact/evidence acceptance, winner-specific
backend completion if required, held-out evaluation/calibration, bundle freeze,
PN54 model parity/profile, physical speaker-room-mic validation and final measured
metrics/video. Stop unrelated non-ML feature development; do not invent a supported
family envelope or enable numerical production confidence before empirical approval.

Everything below is the historical CP1 handoff for context. Its pending cleanup,
branch, dispatch and compute-access status does not override actual current Git,
the convergence record, or newer user authorization.

---

# MeiChuHackathon2026 — AI Performance Controller
## Current Project Handoff

**Date:** 2026-09-19  
**Current stage:** Checkpoint 1 complete → preparing Checkpoint 2  
**Repository:** `YuTingChen0502/MeiChuHackthon26`  
**Remote visibility:** private during development  
**Authoritative branch:** `origin/main`

---

# 1. Product

產品暫稱：

# AI Performance Controller

目前唯一需要真正完成的 role：

# PA Module

產品不是：

- automatic mixer
- generic audio chatbot
- VU meter
- LLM listening to music

核心 interaction：

```text
Observe
→ Recognize
→ Compare
→ Diagnose
→ Recommend
→ Human Adjusts
→ Verify

Human PA 保留 mixer / equipment 的實際控制權。

2. Problem

PA 在彩排與正式演出時必須同時：

操作設備
監聽多個樂器
記住每首歌的 sound
找出異常來源
處理突發變化

產品定位是：

一雙不會分心、能記住每首歌 accepted state、
並持續監控偏差的第二雙耳朵。

不宣稱 AI 比專業 PA 更懂 mixing。

3. Runtime Constraint

現場核心 sensor：

One Microphone

Runtime observation：

mixed music
+
room acoustics
+
environmental noise

不可假設：

isolated live stems
digital mixer multichannel feeds
per-instrument microphones
4. Song Knowledge

演出前：

Song
├── instrument configuration
└── uploaded ideal reference audio

目前已知歌曲 / 樂器配置。

不要求任意未知歌曲理解。

5. Rehearsal
Ideal Reference
      ↓
Rehearsal Observation
      ↓
Instrument-aware Analysis
      ↓
Compare
      ↓
Deviation
      ↓
Recommendation
      ↓
Human PA adjusts
      ↓
Recheck

PA 認為 sound acceptable 後：

[ Accept as Baseline ]

形成：

Calibrated Baseline
6. Live

正式演出主要比較：

current observation
vs
accepted calibrated baseline

而不是不斷逼近 studio reference。

正常：

No action

異常：

instrument attribution
→ balance deviation
→ confidence
→ recommendation
→ human adjustment
→ fresh evidence
→ verification
7. Not Section-aware Mixing

目前不做：

Intro target
Verse target
Chorus target
Solo target
→ automatic remixing

Audio-content matching 可以用於判斷：

current observation 跟哪個 reference context 可比較。

這不等於 section-dependent mixing。

Conductor / musical-intent reasoning 為 future direction。

8. Guided Probe

架構允許 rehearsal 時做：

Please play Guitar
Please play Bass
...

取得 session-specific calibration evidence。

但完整 expert soundcheck protocol 不是目前 critical path。

9. MVP Audio Quantity

Volume first。

不宣稱：

Guitar = 73 dB SPL

主要 quantity：

Relative Balance Deviation

例如：

Guitar
about +4 dB from accepted baseline

需要區分：

global mix change
vs
instrument-specific balance change
10. Ground Truth

有 isolated stems 的 development/evaluation data 時：

reference =
vocals + guitar + bass + drums

人工：

guitar += +4 dB

即可得到 known intervention label。

模型 runtime 仍只看到：

mixed audio
11. Noise

環境 robustness 使用：

SNR

而不是「噪音百分比」。

主要測：

attribution
sign
ΔdB MAE
anomaly precision/recall
confidence/abstention
coverage
performance vs SNR
12. Confidence

Abstention 是 MVP requirement。

不能永遠輸出：

Guitar +3.72 dB

若不可辨識：

Possible guitar deviation
Confidence low
Unable to reliably attribute

Fake confidence 只允許 Checkpoint-1 integration。

Real analyzer 啟用前必須有 empirical calibration / gating。

13. Core Architecture
Uploaded File ──┐
                ├── Audio Frontend
Live Mic ───────┘
                     ↓
              Shared Pipeline
                     ↓
             InstrumentAnalyzer
             [PLUGGABLE]
          ┌──────┼───────┐
          │      │       │
   Separation  Direct  Hybrid
          └──────┼───────┘
                 ↓
          AnalyzerEvidence
                 ↓
          Comparability
                 ↓
          Deviation Engine
                 ↓
          Confidence Engine
                 ↓
          InstrumentState
                 ↓
            PA Role
                 ↓
        Recommendation
                 ↓
          Human Action
                 ↓
            Verification
14. Module Boundary
Performance Core

Owns：

audio frontend
windows
quality
state
reference
baseline
deviation
confidence
verification
InstrumentAnalyzer

Owns：

audio perception only.

Returns：

AnalyzerEvidence

It does NOT own:

PA policy
final confidence semantics
workflow
UI
action recommendation
PA Role

Owns：

rehearsal/live workflow
anomaly policy
recommendation policy
guided calibration workflow
UI

Presentation and explicit human actions only.

Does not infer audio state.

15. Input Modes

Both supported:

UploadedFileInput
LiveMicrophoneInput

Both MUST converge on the same downstream pipeline.

16. ML Strategy

Core ML is NOT an LLM.

Primary task:

Reference-conditioned, instrument-aware level-deviation estimation
from a single mixture under noise.

Pluggable candidates:

A. Separation baseline

Initial candidate:

HTDemucs 6-source

Used as interpretability / feasibility baseline.

Not final by assumption.

B. Direct estimator

Conceptually:

Reference
      +
Observation
      ↓
shared/pretrained audio representation
      ↓
fusion
      ↓
instrument activity
ΔdB
uncertainty evidence

Initial lightweight candidate family explored in design:

EfficientAT
C. Hybrid

Separator evidence + learned features.

Only justified by empirical gain.

17. LLM

LLM is optional.

It may consume:

{
  "instrument": "guitar",
  "deviation_db": 4.1,
  "confidence": 0.92
}

and generate explanations.

It must NOT perform:

instrument attribution
ΔdB estimation
anomaly detection
confidence
verification

Volume MVP must work without an LLM.

18. Compute Strategy
Local Windows machine

Source of code changes and integration.

Nano4 / H200

Role:

Fast ML research accelerator

Use for:

separator feasibility
direct-model probes
sweeps
benchmark iteration
quick training experiments

Nano4 does NOT replace official MI300 adaptation.

MI300

Role:

Official meaningful task-specific adaptation

Use for:

environment validation
task-specific fine-tuning
checkpoint/evaluation/export evidence

Final demonstrated model lineage should descend from MI300 adaptation.

PN54

Role:

Final local Physical AI runtime

Use for:

microphone capture
local model inference
CPU/iGPU/NPU profiling
physical demo

Critical live inference should not depend on remote cloud.

19. Remote Compute Rule

Nano4 / MI300 / PN54 are execution environments.

They are NOT independent sources of code.

Correct flow:

Codex / local Git
     ↓
commit SHA
     ↓
origin
     ↓
Nano4 / MI300 / PN54 checkout exact SHA

Avoid ad-hoc code edits directly on compute machines.

Every experiment should record:

Git SHA
config
environment
asset manifest
model/checkpoint
metrics
20. Codex Development Architecture

Engineering Lead:

PA Lead — MeiChuHackathon26
Model: Astra
Effort: High
Mode: Local

Role:

shared-contract authority
architecture decisions
merge/integration
cross-lane routing
checkpoint acceptance

Implementation happens in independent Worktree chats.

Checkpoint 1 used:

ML / Evidence
Runtime / PA Core
UI / Demo

Workers communicate new events directly to Lead.

No Coordinator is required anymore.

Events use conceptual IDs:

lane / event / commit

Routine lane-local issues are fixed locally.

Lead only receives:

checkpoint commit
correction complete
cross-lane request
blocker
assumption invalidated
ML go/no-go
21. Checkpoint 1
COMPLETE

Integrated commit:

f543fb7318c77e10c8337e16ae395f04e9e4a8c3

Commit message:

Record and validate Checkpoint 1 integration

Remote:

origin/main

was verified at this commit before later local cleanup work.

22. Checkpoint-1 ML

Accepted:

19c23fd18e8f01381b71eb032e9317af997926eb

Implemented:

deterministic pair generator
oracle labels
validity masks
noise controls
separation probe infrastructure
asset manifests
grouped splits
pair planning
direct-estimator training mechanics
CPU optimizer smoke

Training mechanics demonstrated actual gradient/weight change.

This DOES NOT establish musical feasibility.

Current major external dependency:

rights-cleared real multitrack audio

No real backend has been selected.

23. Checkpoint-1 Runtime

Accepted:

e143474cd6d3ad1b4f95acbabcc98d848ba6f381

Implemented:

shared file/mic framing
FakeAnalyzer flow
rehearsal/live workflow
state/confidence/deviation
recommendations
adjustment/recheck
Accept as Baseline
immutable baseline
fresh evidence verification
SQLite persistence
cold restart / suspension
HTTP API
reference jobs
session commands
WebSocket events

Native physical microphone acquisition is NOT yet implemented.

Continuous sustained session worker is NOT yet complete.

24. Checkpoint-1 UI

Accepted:

e9b9d110a852e1d613f487b3d62254af7514d4ab

Implemented:

operator console
rehearsal/live state
reference/baseline
instrument cards
anomaly states
inactive / unsupported / unknown
confidence
staleness handling
recommendations
explicit human actions
verification display
real browser media playback
isolated demo player
reconnect/session switching

Demo player has no truth side-channel into inference.

Physical audible speaker→mic path has not been validated.

25. Checkpoint-1 Integrated Flow

Proven:

Uploaded reference
→ asynchronous reference setup
→ rehearsal anomaly
→ recommendation
→ human adjustment
→ recheck
→ explicit Accept as Baseline
→ Live
→ anomaly
→ recommendation
→ human adjustment
→ fresh evidence
→ recovered

Important:

FakeInstrumentAnalyzer powers perception in this proof.

The product workflow is real.
The audio intelligence is not yet proven.

26. Checkpoint-1 Validation

Final reported integration:

84 Python tests passed
12 UI tests passed
24 shared contract tests independently revalidated
Integrated smoke PASS

Overall:

96 normal suite tests
+
separate contract revalidation

Integration smoke command:

python docs/implementation/checkpoint1_smoke.py
27. Current Visible Product

UI can be served from repo root:

python -m http.server 8000

Then:

http://localhost:8000/apps/ui/
http://localhost:8000/demo_player/

These show current operator/demo surfaces.

They do NOT prove real ML or physical inference.

28. Current Git / Remote State

Remote repository:

https://github.com/YuTingChen0502/MeiChuHackthon26

Note spelling:

Hackthon

not local folder's:

Hackathon

Remote is currently private.

origin/main was verified at:

f543fb7318c77e10c8337e16ae395f04e9e4a8c3

after the first Checkpoint-1 push.

A later local cleanup is currently pending.

29. IMPORTANT Current Local Dirty State

At handoff time, local main tracks origin/main but has uncommitted:

deleted:
.codex/agents/contract-reviewer.toml
.codex/agents/implementation-reviewer.toml
.codex/agents/ml-reviewer.toml

modified:
.gitignore

The remote currently contains duplicate reviewer files:

contract-reviewer.toml
contract_reviewer.toml

implementation-reviewer.toml
implementation_reviewer.toml

ml-reviewer.toml
ml_reviewer.toml

The hyphen and underscore copies have matching content.

Recommended cleanup:

preserve underscore canonical files;
commit deletion of duplicate hyphen versions;
commit appropriate .gitignore;
push normally;
do not use force push again unless specifically necessary.

Remote .gitignore was empty before this cleanup.

30. Recommended .gitignore

Should cover at least:

__pycache__/
*.py[cod]
.pytest_cache/
.venv/
venv/

.env
.env.*
!.env.example

*.db
*.sqlite
*.sqlite3

data/
datasets/
runs/
checkpoints/

*.pt
*.pth
*.ckpt
*.safetensors
*.onnx

.DS_Store
Thumbs.db
.vscode/

Review actual current diff before committing.

31. Recommended Git Tag

After cleanup, recommended but not yet confirmed executed:

checkpoint-1

pointing at:

f543fb7318c77e10c8337e16ae395f04e9e4a8c3

This preserves the known-good CP1 integration.

32. Checkpoint 2

NOT YET STARTED.

Main objective:

REAL AUDIO PERCEPTION

Expected critical path:

rights-cleared real multitracks
        ↓
empirical pair generation
        ↓
separation gain-response
        ↓
direct estimator
        ↓
GO / NO-GO / narrow envelope
        ↓
MI300 meaningful adaptation
        ↓
calibration
        ↓
RealAnalyzer integration
        ↓
PN54
        ↓
physical acoustic demo
33. Checkpoint-2 ML Expected Work
real rights-cleared stems
oracle/pair pipeline on real audio
separation P1
clean gain response first
noise/SNR sweep second
direct estimator on identical splits
compare:
attribution
sign
ΔdB MAE
coverage
abstention
runtime evidence
explicit GO / NO-GO / NARROW_ENVELOPE

Nano4 should be used aggressively for fast probes.

MI300 environment validation should start in parallel.

34. Checkpoint-2 Runtime Expected Work
native microphone discovery
native capture
stable PCM timing/sample identity
continuous window planner
overlapping windows
bounded queues
stale work dropping
dropout/discontinuity handling
sustained buffering/history policy
quality/clipping
long-running acquisition worker
real analyzer adapter integration point

Runtime should NOT wait for final ML.

FakeAnalyzer remains usable until RealAnalyzer is ready.

35. Checkpoint-2 UI Expected Work

UI is mostly feature-frozen.

Only:

actual Runtime API parity
native/live source states
physical-demo integration
rights-cleared demo scenarios
reconnect regressions
fallback fixture mode

No cosmetic feature expansion.

36. Real Analyzer Enablement Requirement

Do not replace Fake with real evidence just because a model can output numbers.

Before numerical real-analyzer UI/action:

empirical model evidence
appropriate calibration/gating
confidence semantics
operating envelope

must exist.

Fake confidence must not silently survive into real perception.

37. Biggest Current Technical Risk

Still:

Can one mixed microphone signal under realistic music/noise conditions
support useful instrument-specific relative balance deviation?

Checkpoint 1 did not answer this.

Checkpoint 2 must.

38. Biggest Current External Dependency
Rights-cleared multitrack audio

Need ideally:

guitar
bass
drums
vocal
stems
usable provenance/license
allowed for evaluation
preferably usable for public demo or replaceable with self-recorded demo assets

Without this, empirical ML is blocked.

39. Competition Compute Narrative

Desired final story:

rights-cleared data
      ↓
MI300
task-specific audio fine-tuning
      ↓
exported adapted artifact
      ↓
PN54
local microphone inference
      ↓
PA UI

Nano4 is development acceleration, not the official competition adaptation story.

40. Physical Demo Target

Final:

Prepared / human-controlled audio source
        ↓
Speaker
        ↓
Real room
+ environmental noise
        ↓
One microphone
        ↓
PN54
        ↓
RealAnalyzer
        ↓
PA UI
        ↓
Human correction
        ↓
Fresh microphone evidence
        ↓
Verified recovery

Demo player must never leak truth/labels/control values into analyzer.

41. Claims Discipline

Currently allowed to claim:

complete PA workflow implemented
contracts frozen
Fake-backed E2E application works
API / WS / SQLite work
deterministic ML evidence infrastructure exists
CPU training mechanics work

Currently NOT allowed to claim:

real guitar +4 dB estimation works
robust noisy instrument attribution
calibrated confidence
MI300-trained model works
PN54 inference works
physical mic demo works
arbitrary live band generalization
42. Development Strategy

Preserve parallelism:

ML
→ real feasibility

Runtime
→ native streaming

UI
→ physical integration support

Nano4
→ fast ML execution

MI300
→ official adaptation readiness

Lead coordinates shared decisions.

Do not wait for ML to finish before Runtime progresses.

Do not let UI consume critical-path engineering time.

43. Next Immediate Actions

Before Checkpoint 2:

Resolve current local Git cleanup.
Push clean main.
Optionally tag checkpoint-1.
Ask existing Astra High Lead to create:
docs/implementation/CHECKPOINT_2_PLAN.md
Start Nano4 environment inventory.
Start MI300 environment / forward-backward smoke.
After Lead approves CP2:
create NEW CP2 Worktrees from latest origin/main.

Recommended new worktrees:

CP2 — ML Real Audio
CP2 — Runtime Native Audio
CP2 — UI Physical Demo
44. Current Leadership / Agent Model

Main project-management / integration thread:

PA Lead — MeiChuHackathon26
Astra / High / Local

Keep this Lead.

Do not reopen a new Lead merely for Checkpoint 2.

Read-only specialist subagents may be spawned as needed.

Implementation work belongs in Worktrees.

45. Operational Principle

When new information arrives from:

Lead
ML Worktree
Runtime Worktree
UI Worktree
Nano4
MI300
PN54

update the project state immediately.

Always distinguish:

implemented
tested
empirically validated
deployed
physically demonstrated

These are not interchangeable.

46. Current Project Summary

The project has successfully passed:

architecture risk

and largely passed:

product-integration risk

The remaining dominant risks are:

ML feasibility
real acoustic robustness
edge deployment

Checkpoint 2 should therefore optimize for evidence generation, not feature count.


---
