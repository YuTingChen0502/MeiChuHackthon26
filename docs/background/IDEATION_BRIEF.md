# 2026 MeiChu Hackathon — AMD Physical AI Ideation Brief

## Goal

我們現在不是要立刻選題，而是系統性找到少數真正值得深入的
AMD Physical AI hackathon directions。

成功不是產生很多 idea。
成功是最後只留下 3–5 個同時具有：

Specific human problem
× surprising-but-obvious solution
× Physical AI necessity
× AMD-native advantage
× strong live demo
× hackathon buildability

的候選。

如果沒有夠好的候選，寧可輸出 NO_SURVIVOR，不要硬選。

---

## Core thesis — but NOT an assumed answer

目前最值得探索的 technical opportunity 包括：

- continuous / always-on perception
- multimodal perception
- persistent physical-world state / memory
- temporal reasoning
- proactive intervention
- efficient local multimodal inference
- heterogeneous CPU / GPU / NPU execution
- privacy / low-latency / offline interaction

但這些只是 hypotheses。

不要預設最後一定是：
- SOP / workflow assistant
- persistent-memory application
- camera monitoring

必須主動尋找其他 2026 才開始 practical 的 capability。

---

## What "novelty" means

Novelty ≠ 使用最新模型。
Novelty ≠ 世界上沒有人做過。
Novelty ≠ implementation 很難。

我們要找的是：

「某種以前不 practical 的 human–AI interaction，
因為 2026 AI capability 成熟而突然可以成立。」

尤其重視 product / interaction mechanism novelty。

Question:

> 如果回到 2023，這個產品會明顯比較難成立嗎？

如果不會，"Why now?" 很可能不夠強。

---

## Physical AI bar

不要把：

image → VLM → text answer

當成夠強的 Physical AI。

比較值得探索的是：

physical event
→ perception
→ state / context
→ meaningful interpretation
→ decision
→ timely intervention
→ physical/human outcome

Robot 不是必要條件。

Human-in-the-loop 也可以形成完整 closed loop。

可使用：
camera / phone / microphone / wearable /
BLE / IMU / inexpensive sensors 等 commodity hardware。

不要預設有 robot arm、LiDAR、depth camera 等額外設備。

---

## AMD bar

AMD 不能只是 deployment target。

必須能回答：

> 如果拿掉 local AMD compute，產品是否真的變差？

可能成立的理由：
- continuous sensing
- privacy
- latency
- offline operation
- power efficiency
- NPU/iGPU heterogeneous execution
- local multimodal inference

如果 Gemini / cloud API 就能完成 90% 的核心價值，
AMD fit 通常不足。

以 workshop slides 為 AMD hardware/resource 的 authoritative source。
不要自行假設未提供的規格或設備。

Nano4 / NVIDIA H200 可以視為 offline R&D / training resource，
但除非有非常強理由，不應成為 AMD-track live product 的核心 runtime。

---

## Technical difficulty

不要追求最大技術難度。

理想區間：

看起來：
「這怎麼做到的？」

實際：
3–4 個成熟 components
+ 聰明的 system design
+ 穩定的 integration

技術需要有 substance，
但 complexity 超過 Demo 所需之後就是 liability。

優先考慮 pretrained models。
Fine-tuning 僅在它真正解決 bottleneck 時加入。

---

## Historical winner lesson

不要複製過去得獎題目。

只吸收 pattern：

Specific human moment
×
Unexpected but immediately understandable mechanism
×
Sponsor technology is essential
×
Complete live interaction

過去成功作品說明：
technical complexity 本身並不保證成功。

---

## HARD GATES

一個 candidate 只要明顯 fail 任一核心 gate，就淘汰，
不要用其他優點平均補回來。

### G1 — Concrete human moment
能不能用一句話指出：

「誰，在什麼具體時刻，發生什麼 failure/friction？」

不是「智慧醫療」、「工業安全」、「教育」。

### G2 — Non-generic mechanism
solution 是否有一個：
「原來可以這樣」
但看到後又立刻合理的 core twist？

### G3 — Physical necessity
如果 AI 不感知真實世界，
核心 idea 是否就不存在？

### G4 — AMD necessity
如果改成 cloud/API，
核心 UX / feasibility 是否明顯退化？

### G5 — Live-demo compression
10 秒能否看到：

physical event
→ AI understands
→ intervention
→ visible outcome

### G6 — Hackathon feasibility
能否用現有 / commodity hardware +
成熟 open-source models，
約一天完成最核心 loop？

---

## Anti-patterns

優先淘汰：

- AI smart-X platform
- generic coach / assistant / monitor
- camera → detection → notification
- VLM image captioning with UI
- chatbot / RAG with a physical-world wrapper
- 「因為有 NPU，所以跑一個 model」
- 需要三分鐘解釋問題才覺得重要
- invented / weak pain point
- overly broad multi-feature product
- technical research project with weak product insight
- cloud solution disguised as edge AI
- old CV application merely rebuilt with a newer model

---

## Exploration strategy

使用兩條獨立搜尋線，避免 framing bias。

### Lane A — Main path (~80%)
2026 technical capability
→ new interaction mechanism
→ AMD-native advantage
→ search for concrete human moments

### Lane B — Control path (~20%)
independently identify overlooked, concrete human frictions
→ ask whether a newly practical AI capability uniquely unlocks a new solution

不要讓 Lane B 被 Lane A 的 vocabulary 污染。

最後合併候選，再跑同一組 HARD GATES。

---

## Output discipline

不要輸出完整 brainstorm history。

可以在內部探索廣，但只報告 decision-relevant 結果。

最終最多留下 4 個 candidates。

每個只提供：

1. Problem — 一句
2. Core twist — 一句
3. Why now — 一句
4. Why AMD — 一句
5. 10-sec demo — 一句
6. Minimal stack — 一行
7. Biggest reason to kill it — 一句

最後再給：

- strongest unresolved question
- 哪些方向已被淘汰，以及最主要的 2–3 個 failure patterns

不要硬選 winner。

總輸出保持精簡。