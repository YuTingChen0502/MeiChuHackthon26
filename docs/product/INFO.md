# `INFO.md`

## Dataset-family perception amendment — 2026-09-20

Attempt analysis of all instrument families represented in dataset provenance;
absence of empirical validation must not become a hard-coded unsupported gate.
Unreliable identification remains uncertain. Where actual current comparative
evidence supports a direction, a clearly experimental human listening trial may
suggest raising/lowering without a numeric amount or invented confidence.
See [the shared amendment](../implementation/DATASET_PERCEPTION_HINT_FREEZE.md).
This supersedes conflicting historical bass-only product masks, not measured results.

## User-approved workflow correction — 2026-09-20

The current product is song/instrument configuration + uploaded ideal reference
-> Live against that reference -> human level adjustment -> fresh analysis.
Microphones are logical user-facing inputs and can be switched within the same
session without re-upload/re-analysis. No public rehearsal, Accept as Baseline,
Start Live transition or guided rehearsal flow. Legacy records/code may remain
unreachable for compatibility. Authoritative perception and uncertainty gates,
no automatic mixer, and no absolute instrument SPL claims remain in force.
See [the exact shared freeze](../implementation/LIVE_REFERENCE_MIC_FREEZE.md).
This explicit user decision supersedes conflicting historical scope text below.

```md
# AI Performance Controller
## PA Module — Product & Technical Handoff

**Project:** 2026 MeiChu Hackathon — AMD Physical AI  
**Stage:** Product definition complete → Technical implementation design  
**Status:** PA MVP scope substantially frozen

---

# 1. Executive Summary

我們要做的是：

# AI Performance Controller

目前第一個、也是唯一需要完成的 role：

# PA Module

它不是 automatic mixer，也不是單純 audio dashboard。

核心 interaction：

```text
physical audio
→ recognize current state
→ compare against expected state
→ diagnose deviation
→ recommend minimum correction
→ human PA adjusts
→ listen again
→ verify

核心產品價值：

在 PA 同時操作設備、監聽聲音與處理現場狀況時，
提供一雙可以持續監聽、記得每首歌已校準狀態、
並在發生偏差時指出問題來源的第二雙耳朵。

2. Authoritative Resources

實作前必讀：

AMD 題目.pdf
2026 梅竹黑客松 AMD 工作坊簡報.pdf
大松手冊.pdf
本 INFO.md

Background only：

PHASE_A_FINAL_HANDOFF_V3.md
PHASE_B_PROBLEM_DISCOVERY_BRIEF_V1.md

Authority：

Competition facts:
AMD 題目
> AMD workshop
> handbook
> latest official AMD docs

Product scope:
INFO.md
> older exploration documents

舊 Phase A/B 不得重新覆寫目前已定義的產品 scope。

3. Official Competition Constraints

目前官方資訊確認：

HARD

作品必須使用：

AMD Instinct MI300
PN54 AI PC

使用的模型至少必須：

fine-tune
或 RAG

其中一項成立。

作品需要：

真實世界輸入
Physical AI interaction
可說明的 cloud-to-edge workflow

即：

data / adaptation
→ MI300
→ training / fine-tuning
→ model deployment
→ PN54
→ local physical sensing
→ inference
→ feedback / interaction
4. Confirmed Provided Hardware

目前確認每隊可取得：

AMD Instinct MI300      x1 remote
PN54 AI PC              x1
Microphone
Camera
Keyboard
Mouse

其他硬體可以另外準備。

5. Hardware Unknowns

以下不得自行假設：

PN54 exact CPU
PN54 RAM
PN54 SSD
PN54 exact NPU
PN54 exact iGPU
PN54 OS
driver versions
ROCm compatibility
Ryzen AI runtime
MI300 quota
MI300 environment
network reliability

拿到硬體後第一步：

inventory
→ runtime check
→ model compatibility
→ benchmark
6. Deployment Principle

最終 critical runtime：

PN54

不是 MI300 cloud inference。

理想 deployment：

                     MI300
                       │
        dataset generation / training
          task-specific fine-tuning
                       │
                  model export
                       ↓
─────────────────── PN54 ───────────────────
                       │
                 microphone input
                       ↓
                 local inference
                       ↓
                    PA feedback

Critical live demo 不應依賴：

external LLM API
remote MI300 roundtrip
uncontrolled cloud service
7. Product Definition

PA Module 在彩排時：

讀取該首歌的 uploaded ideal reference；
從 microphone 或 uploaded rehearsal audio 分析現場狀態；
辨識各 instrument；
比較 volume / later tone；
找出 deviation；
給 PA 調整建議；
PA 人工調 mixer；
系統重新確認；
PA 按 Accept as Baseline。

正式演出時：

載入該歌曲 accepted baseline；
持續監聽；
正常時不動作；
發現異常時辨識來源；
給出 deviation + confidence；
建議 PA 處理；
調整後再次確認。
8. Important Boundary

目前不是：

Intro target
→ Verse target
→ Chorus target
→ Solo target
→ continuously remix

PA MVP 不根據歌曲 section 持續變更 target。

這類 musical temporal understanding：

section
bar
beat
phrase
dynamics
entrance

未來更適合：

advanced PA
Conductor Module

目前不進 critical path。

9. Song Setup

每一首歌至少輸入：

Song
├── metadata
├── instrument configuration
└── ideal reference audio

例如：

Song A

Vocal
Guitar
Bass
Drums

Reference:
song_a_reference.wav

Reference 由使用者事先上傳。

目前不要求使用者上傳 stems。

10. Two Audio Input Modes

必須支援：

Uploaded Audio

用途：

reference
prerecorded rehearsal
offline test
demo
evaluation
Live Microphone

用途：

rehearsal
live monitoring

Architecture：

Uploaded File ──┐
                ├── AudioInput
Microphone ─────┘
                     ↓
               Common Pipeline

Offline / live 不得變成兩個完全不同的系統。

11. Runtime Sensor

現場核心 sensor：

One Microphone

Input：

mixed music
+
room response
+
environmental noise

目前不假設：

live stems
multi-channel mixer output
isolated instrument microphones
12. Product Core Loop
Observe
   ↓
Recognize
   ↓
Compare
   ↓
Diagnose
   ↓
Recommend
   ↓
Human Adjusts
   ↓
Verify
   ↺
13. Core ML Is NOT an LLM

本專案最重要的 ML task：

Audio Perception

具體是：

reference-conditioned,
single-mixture,
instrument-aware deviation estimation.

輸入：

known instrument configuration
+
reference / baseline
+
observed mixed audio

輸出：

InstrumentState[]

例如：

Guitar
present = true
deviation_db = +4.1
confidence = 0.92

因此：

不使用 LLM 直接從音訊猜 instrument gain。

這種數值判斷需要可 benchmark 的 audio model / DSP pipeline。

14. Instrument Analyzer

核心抽象：

InstrumentAnalyzer

概念：

audio
+
instrument configuration
+
optional reference features

→ InstrumentState[]

它必須可以更換 backend。

15. Candidate Analyzer Strategies

目前未鎖定最終 algorithm。

A. Separation-based
mixture
→ source separation
→ source features
→ relative level

優點：

最容易快速建立 baseline
可解釋
可直接檢查 separation quality

缺點：

computation heavy
source bleed
instrument taxonomy 受模型限制
separator quality 不等於 gain-estimation quality

Status:

OPEN EXPERIMENT

B. Direct Reference-conditioned Estimator
reference ────┐
              ├── encoder
observation ──┘
                   ↓
              comparison
                   ↓
        instrument-specific heads
             ├─ presence
             ├─ Δlevel
             └─ confidence

不要求重建完整 isolated stems。

直接預測 PA 真正需要的 quantity。

Status:

RECOMMENDED RESEARCH DIRECTION

C. Hybrid
separator information
+
shared embeddings
+
reference comparison

→ InstrumentState

Status:

OPEN EXPERIMENT

16. Architecture Must Remain Pluggable

以下必須 replaceable：

AudioInput
NoiseProcessor
InstrumentAnalyzer
AudioEncoder
ToneAnalyzer
InferenceBackend
LanguageModel

產品邏輯不能依賴某一個特定 model class。

17. Ideal Reference

使用者上傳的歌曲音檔。

它代表：

該歌曲理想上希望呈現的 sound / mix。

系統做：

Reference Audio
      ↓
Offline Analysis
      ↓
ReferenceProfile

可能包含：

instrument presence
relative instrument characteristics
overall mix statistics
audio embeddings
level features
tone features

具體 feature 尚待實作實驗決定。

18. Calibrated Baseline

Ideal reference 與 live baseline 是不同概念。

流程：

Ideal Reference
      ↓
Rehearsal
      ↓
AI comparison
      ↓
PA manually adjusts
      ↓
Re-check
      ↓
Accept as Baseline
      ↓
Calibrated Baseline

Baseline 表示：

今天這個場地、設備、樂手與 sound system 下，
人類 PA 已確認 acceptable 的實際狀態。

正式演出主要監控：

deviation from calibrated baseline
19. Why Human Accepts the Baseline

MVP 不假裝 AI 能自行知道：

「現在已經完美。」

最終 calibration decision 由：

Human PA

完成。

UI：

[ Accept as Baseline ]

這是 intentional human-in-the-loop design。

20. Level Definition

不要將核心 target 定義為：

Instrument SPL = X dB

Single microphone 下 absolute instrument SPL 高度受到：

mic position
mic gain
speaker distance
room acoustics

影響。

因此主要 quantity：

Relative Level Deviation

例如：

Guitar
+4.1 dB from accepted baseline
21. Global vs Instrument Level

需要區分：

Global Mix Change
Guitar +4
Bass   +4
Vocal  +4
Drum   +4

可能只是整體 playback / master level 改變。

Instrument Balance Change
Guitar +4
Bass    0
Vocal   0
Drum    0

才代表 guitar 在 mix 中突出。

因此 state 至少應包含：

global_mix_level
relative_instrument_balance

PA 最重要：

relative instrument balance
22. Formal Ground Truth

Training / evaluation 時若具有 stems：

x_ref(t)
=
s_vocal(t)
+ s_guitar(t)
+ s_bass(t)
+ s_drums(t)

故意改變 guitar：

x_test(t)
=
10^(g/20) * s_guitar(t)
+
sum(other stems)
+
noise(t)

若：

g = +4 dB

則：

Ground Truth Guitar Deviation = +4 dB

模型 runtime 仍只看到：

mixed audio
23. Primary Metrics
Instrument Attribution
accuracy
precision
recall
F1
Level Direction
too loud
too quiet
normal

Metric：

sign / class accuracy
Level Magnitude
MAE in dB

例如：

GT = +4.0 dB
Pred = +3.6 dB

error = 0.4 dB
Anomaly Detection
precision
recall
F1
24. Noise Robustness

Environment noise 是核心 requirement。

包含：

crowd
speech
room ambience

不要用：

noise = 40%

描述。

使用：

Signal-to-Noise Ratio (SNR)

Controlled benchmark 可以包括：

clean
20 dB
15 dB
10 dB
5 dB
0 dB
-5 dB

範圍可依實驗調整。

25. Noise Evaluation

每個 SNR 都測：

instrument attribution
direction accuracy
level MAE
anomaly F1
confidence

最後得到：

model performance
vs
SNR

並定義：

Reliable Operating Envelope
26. Confidence / Abstention

系統必須能知道：

自己什麼時候不可信。

可靠：

Guitar
+4.1 dB
Confidence: 92%

不可靠：

Possible guitar deviation

Confidence: Low

Unable to reliably attribute
under current noise / overlap.

不可：

永遠輸出一個看似精確的錯誤數值

Status：

LOCKED MVP REQUIREMENT

27. MI300 Role

目前最自然、最有意義的 MI300 用法：

Audio Model Fine-tuning

Training data 可從 isolated stems 建立。

例如：

stems
 ↓
random instrument gain perturbation
 ↓
random noise
 ↓
random SNR
 ↓
optional room-response augmentation
 ↓
mixed observation

label 天然知道：

instrument
ΔdB
SNR

MI300：

dataset processing
→ fine-tune
→ evaluation
→ model export / optimization

這比在產品旁邊硬塞 unrelated RAG 更自然。

Status：

RECOMMENDED

28. Audio Model Strategy

不需要從 scratch 訓練大型 model。

較合理：

pretrained audio representation
        ↓
task-specific fine-tuning
        ↓
instrument / level / confidence heads

或：

pretrained source separator
        ↓
task-specific downstream estimator

具體 backbone：

OPEN EXPERIMENT

應先 benchmark 再選。

29. PN54 Role

PN54：

Final Local Runtime

負責：

audio capture
preprocessing
audio inference
state estimation
baseline comparison
confidence
recommendation
UI/backend

Critical inference 應 local。

實際：

CPU / iGPU / NPU

哪個最好：

OPEN EXPERIMENT

直到 PN54 實機 profile。

30. LLM Role

LLM 不是 audio perception。

正確位置：

Audio ML
    ↓
structured result
    ↓
PA policy
    ↓
optional LLM
    ↓
natural-language explanation

可以用於：

PA explanation
equipment troubleshooting
knowledge retrieval
conversational control
future role interaction

不可作為：

primary instrument detector
primary ΔdB estimator
critical anomaly detector
31. Candidate Local LLM

若真的需要 LLM：

目前優先 candidate：

Qwen3-4B-Hybrid
+
AMD Lemonade

原因：

Lemonade 是 AMD local AI runtime。
提供 OpenAI-compatible API。
AMD 官方文件目前明確展示
Qwen3-4B-Hybrid 的 Hybrid NPU+iGPU execution。

但：

NOT LOCKED

實際 PN54 尚未驗證。

因此 interface 應：

LanguageModelProvider

而不是把 Qwen 寫死。

若 PN54 不適合：

smaller model
CPU/GPU model
deterministic template

都必須可替換。

Volume MVP 即使完全沒有 LLM也應成立。

32. Tone

最終產品希望理解：

EQ
brightness
mud
distortion
effects
reverb
compression
...

但 tone source attribution 比 volume 困難。

所以：

Volume = MVP
Tone   = Stretch / experimental

Architecture 要留：

ToneAnalyzer

但不能讓它阻塞 MVP。

33. Performance Core

建議概念切割：

PerformanceCore
│
├── Input
│   ├── FileAudioInput
│   └── MicAudioInput
│
├── AudioFrontend
├── NoiseProcessor
├── InstrumentAnalyzer
├── FeatureExtractor
├── StateTracker
├── ReferenceManager
├── BaselineManager
├── DeviationEngine
├── ConfidenceEngine
└── VerificationEngine
34. Role Module

角色特有邏輯不要寫入 Core。

Concept：

RoleModule
├── state_schema
├── reference_schema
├── anomaly_policy
├── action_policy
└── workflow
35. PA Module

目前實作：

PA Module

關心：

instrument
volume
balance
tone

Reference：

ideal song reference
+
accepted rehearsal baseline

Actions：

raise/lower level
check instrument/channel
later: EQ / effects
36. Future Conductor Module

只是 scalability direction。

不實作。

可能 state：

tempo
timing
entry
dynamics
musical section

可能 reference：

score
reference performance
musical intent

重要的是：

未來換 role 應該換 Role Module，
而不是重寫 microphone / audio state / confidence /
reference / verification infrastructure。

37. State Machine
PROJECT_SETUP
      ↓
REFERENCE_UPLOAD
      ↓
REFERENCE_ANALYSIS
      ↓
REHEARSAL
      ↓
COMPARE_REFERENCE
      ↓
RECOMMEND_ADJUSTMENT
      ↓
PA_ADJUSTS
      ↓
RECHECK
      ↓
ACCEPT_BASELINE
      ↓
LIVE_MONITORING
      ↓
      ├─ NORMAL → continue
      │
      └─ ANOMALY
             ↓
        CONFIDENCE_GATE
             ↓
        RECOMMEND
             ↓
        PA_ADJUSTS
             ↓
        VERIFY
38. Core Data Model

概念：

InstrumentState {
    instrument
    present
    level
    relative_balance_db
    deviation_db
    tone_features?
    confidence
}

UI example：

Guitar

+4.1 dB
from accepted baseline

⚠ Too Loud

Confidence: 92%
39. UI Structure

至少三個區域：

A. Session State
Song A
REHEARSAL / LIVE
B. Instrument Blocks
Guitar   ⚠ +4.1 dB
Bass     ✓ Normal
Vocal    ✓ Normal
Drums    ✓ Normal
C. Action
Action Required

Guitar exceeds accepted baseline.

Suggested:
Reduce guitar level.

若不確定：

Low Confidence

Current mixture is too noisy
for reliable attribution.
40. Demo Constraint

不會有真正樂團現場演奏。

Demo 使用：

prepared audio
→ speaker
→ physical room
+ environmental noise
→ one microphone
→ PN54

因此仍真正經過：

physical acoustic environment

而非單純 offline WAV classification。

41. Offline Analysis Is Also a Product Feature

Uploaded-file analysis 不是只有測試用途。

正式產品需要支援：

upload audio
→ analysis

以及：

microphone stream
→ analysis

兩者共用 core analyzer。

42. Demo Assets

預先準備：

reference.wav
normal.wav

guitar_plus_2.wav
guitar_plus_4.wav
guitar_plus_6.wav

guitar_minus_4.wav
bass_plus_4.wav

noise_low.wav
noise_medium.wav
noise_high.wav

corrected.wav

也可以 runtime 疊 noise。

需要使用：

自有內容
可授權內容
可公開 dataset

避免作品最後被歌曲版權卡住。

43. Ideal Demo
Upload Reference
      ↓
Analyze
      ↓
Play Rehearsal
      ↓
"Guitar too loud"
      ↓
Correct
      ↓
Accept as Baseline
      ↓
Live Mode
      ↓
Normal
      ↓
inject guitar anomaly + crowd noise
      ↓
"Guitar +4.x dB"
      ↓
Correct
      ↓
"Recovered"

完整表現：

reference
→ physical sensing
→ diagnosis
→ human intervention
→ physical verification
44. MVP
Must Have
uploaded reference
uploaded-audio analysis
live microphone analysis
known instrument configuration
single microphone
volume analysis
instrument attribution
relative ΔdB
rehearsal workflow
Accept as Baseline
live monitoring
noise robustness
confidence / abstention
PA recommendation
verification
PN54 local inference
meaningful MI300 fine-tuning
45. Stretch
tone / EQ
effects
better separation
section-aware PA
mixer API
automatic mixer control
Conductor Module
LLM PA assistant
RAG PA knowledge base
46. Explicitly Out of Scope
fully autonomous mixer
section-by-section auto remixing
absolute instrument SPL from one mic
arbitrary unknown-song understanding
full conductor implementation
real band requirement
cloud-dependent critical inference
LLM-based numerical audio judgement
47. Biggest Technical Risk

目前最大的 unknown：

在 single mixed microphone signal

room effects
environmental noise 下，
instrument-specific relative-level deviation
究竟能估到多準？

因此第一個 engineering milestone 不是 UI。

而是：

Technical Feasibility Benchmark
48. First Experiment

建立 controlled benchmark：

multiple songs
× multiple instruments
× multiple gain deviations
× multiple noise types
× multiple SNR

例如：

instrument:
guitar / bass / vocal / drums

gain:
-6 -4 -2 0 +2 +4 +6 dB

SNR:
clean / 20 / 10 / 5 / 0 dB

比較：

separation baseline
vs
direct estimator
vs
hybrid

先知道什麼 realmente works，
再決定 final ML pipeline。

49. Development Principle

不要：

frontend first
LLM first
everything-at-once

應：

1. controlled data
2. offline feasibility
3. reliable ΔdB estimate
4. noise test
5. confidence
6. baseline workflow
7. streaming
8. PN54 deployment
9. UI
10. stretch features
50. One-Sentence Functional Definition

The PA Module uses a pre-uploaded song reference and a single microphone to analyze instrument balance during rehearsal, lets the human PA accept an adjusted performance as the per-song live baseline, and then locally monitors the live performance under environmental noise to identify abnormal instrument-level deviations, recommend corrective action, and verify recovery.

51. Architecture Summary
                       INPUT
             ┌──────────┴──────────┐
             │                     │
       Uploaded File         Live Microphone
             │                     │
             └──────────┬──────────┘
                        ↓
                  Audio Frontend
                        ↓
                  Noise Handling
                        ↓
             Pluggable Instrument
                   Analyzer
              ┌────────┼────────┐
              │        │        │
          Separation Direct   Hybrid
              └────────┼────────┘
                        ↓
                InstrumentState
                        ↓
        Reference / Baseline Manager
                        ↓
                Deviation Engine
                        ↓
                Confidence Gate
                        ↓
                    PA Module
                        ↓
             Recommendation Logic
                        ↓
              optional Local LLM
                        ↓
                       UI
                        ↓
                 Human Adjustment
                        ↓
                  Re-observation
                        ↓
                   Verification
52. Current Decision Status
LOCKED
PA first
one microphone
uploaded song reference
uploaded + live input modes
known instrument configuration
Accept as Baseline
live anomaly monitoring
volume-first
relative deviation, not absolute SPL
noise robustness
confidence / abstention
human control
modular roles
MI300 + PN54
local critical inference
RECOMMENDED
meaningful audio fine-tuning on MI300
PN54 as live runtime
pluggable instrument analyzer
separation baseline + direct estimator feasibility race
controlled synthetic gain/noise training data
OPEN EXPERIMENT
exact audio backbone
source separator
direct estimator architecture
exact anomaly threshold
reliable minimum SNR
rolling-window length
PN54 execution backend
exact local LLM
achievable tone analysis
STRETCH
tone / EQ
effects
LLM PA reasoning
RAG
mixer API
automatic control
section-aware behavior
Conductor Module

AMD 目前官方的 Lemonade 文件確實提供 OpenAI-compatible local API，並明確列出 `Qwen3-4B-Hybrid` 的 NPU-prefill + iGPU-decode Hybrid 路徑；因此它適合作為 **optional LLM candidate**，但由於你們實際 PN54 規格仍未知，不應鎖死。:contentReference[oaicite:1]{index=1}

而 MI300 → meaningful fine-tune → PN54 local inference 不是我們自己額外發明的限制；它正好符合先前從 AMD 正式題目整理出的 mandatory resource / pipeline requirements。:contentReference[oaicite:2]{index=2}
