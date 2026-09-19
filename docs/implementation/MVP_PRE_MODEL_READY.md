# MVP_PRE_MODEL_READY — convergence inventory and acceptance record

Owner: existing Engineering Lead. Started 2026-09-20. Replaces the incremental
PRE_MODEL_FREEZE target. Status: IN_PROGRESS; this record does not yet assert READY.
The user reports independent Nano4 and MI300 campaigns; no remote result has been
imported or accepted by this local milestone. Do not duplicate their training.

## Definition and source discipline

Complete the functioning PA MVP with explicit Fake/test perception and actual
Runtime/API/UI/native capture. A trained backend later replaces the analyzer through
the frozen InstrumentAnalyzer/AnalyzerEvidence seam. No product/workflow/UI redesign
or unrelated engineering is allowed to remain disguised as waiting for ML.

Use the existing ML, canonical Runtime and UI worktrees. The duplicate Runtime audit
task is stopped. Main originally reviewed at 42ba903; accepted ML 3d161dd merged at
8d5c5c3332466ed899e909dfcb20b450f737ff9c, accepted Runtime 434b637 merged at
ff1806c3655e6fbcc208d808a5aba5109e8a789c. ML integration-ready fa7068155461e42ece413235347a6bd5f43667ee is accepted on main. Runtime readiness25f8808b751e25abb287c1b3126b898509640637 is accepted at main3b12c787f7bb69bef75114088e0d57d6dc05d163. UI remains under concrete functional correction review. DONE plumbing rows below are backed by the ML artifact-bundle runbook and Runtime milestone report; winner-specific numerical adapters and measured evidence remain separate waiting rows. Each subsequent integration must record an
exact commit and passing checks. Existing Gate-0/public contracts retain meaning.

## Complete module matrix

IN_PROGRESS below is an honest working status, never final acceptance. Final rows
must be DONE, WAIT_MODEL or WAIT_HARDWARE with evidence. Tooling and actual measured
artifacts are separate rows so templates cannot masquerade as empirical completion.

| Module | Owner | Status | Evidence / dependency and next action |
|---|---|---|---|
| Product authority / scope | Lead | DONE | AGENTS, INFO, technical design; no ideation reopened |
| Frozen public records | Lead | DONE | contracts/; original schema unchanged; shared suite |
| Analyzer boundary | Lead/ML | DONE | PA_ANALYZER_V1 + TypedDict/validation; exactly one evidence mode |
| Session/setup wire boundary | Lead | DONE | PA_SESSION_WIRE_V1, PA_SETUP_WIRE_V1; atomic command tests |
| Root dependencies | Lead | DONE | requirements-runtime.txt; native pins validated at 42ba903 |
| Common integration entrypoint | Lead | IN_PROGRESS | scripts/validate.py; run after all lane merges |
| Internal bundle/approval handoff | Lead | IN_PROGRESS | MODEL_HANDOFF_INTERNAL_V1; bind ML and Runtime tests |
| English README / architecture | Lead | IN_PROGRESS | root README with diagram, install, roles, limits |
| Source release audit/export | Lead | IN_PROGRESS | scripts/release_audit.py; clean source-only export, private history excluded |
| Current handoff / reproducibility | Lead | IN_PROGRESS | update authority status and exact integration record |
| License and asset policy | Lead | IN_PROGRESS | docs/release/RELEASE_READINESS.md; no rights fabricated |
| Multitrack manifests | ML | DONE | existing validated manifest + per-use review template |
| Provenance / integrity audits | ML | DONE | CP2 audit detects hash/truncation/split duplicate errors |
| Grouped splits | ML | DONE | train/validation/calibration/test groups and leakage tests |
| Controlled pairs / oracle | ML | DONE | preserved CP1 math, independent gain audit, masks |
| P1 separation probe infrastructure | ML | DONE | fixed-pair runner; actual music results separate |
| P2 direct probe infrastructure | ML | DONE | matched offline adapter; no selected fitted winner |
| Remote bundle manifest/layout | ML | DONE | generic environment/run/config/model/sample/evidence identities |
| Checkpoint/hash/provenance validation | ML | DONE | reject malformed/missing/mismatched artifacts |
| Model/frontend/taxonomy/scale/profile binding | ML | DONE | exact five IDs and expected sample/window checks |
| Trained artifact intake | ML | DONE | safe local cache/import, no implicit executable imports |
| Nano4 result/evidence import | ML | DONE | source SHA/config/split/seed, sanitized references, no raw data |
| MI300 result/evidence import | ML | DONE | same interface plus meaningful adaptation lineage for competition |
| Analyzer registry / production shell | ML | DONE | host allowlist and frozen output validation; safe unavailable |
| Reference context lifecycle | ML/Runtime | DONE | compatible opaque durable/cache context; no fake production context |
| Held-out benchmark / comparison tooling | ML | DONE | runnable generic entrypoints with test-only fixtures |
| Calibration fitting tooling | ML | DONE | separate anomaly/normal event candidates; no automatic acceptance |
| Export/parity harness | ML | DONE | CPU anchor, exact input/profile hashes, adapter plug-in |
| Real trained winner / family envelope | ML | WAIT_MODEL | incoming remote artifact and empirical evidence |
| Fitted confidence / held-out performance | ML | WAIT_MODEL | independent empirical calibration/test records |
| Winner-specific inference/export adapter | ML | WAIT_MODEL | only actual backend tensor/loading implementation may remain |
| Uploaded file input | Runtime | DONE | bounded PCM16 upload and common incremental pipeline |
| Native microphone discovery | Runtime | DONE | PortAudio device inventory; actual local discovery checked |
| Native microphone capture | Runtime | DONE | committed local capture/continuity reports; not PN54 |
| Canonical PCM / sample-clock identity | Runtime | DONE | stable source/run/clock/sample spans and parity tests |
| Deterministic overlapping planner | Runtime | DONE | incremental window/overlap identity tests |
| Continuous acquisition | Runtime | DONE | separate capture/framing and analysis workers |
| Bounded queues / backpressure | Runtime | DONE | queue cap/drop policy tests and recorded soak |
| Stale work / post-inference freshness | Runtime | DONE | pre/post inference checks; no stale action/recovery |
| Dropout/discontinuity / persistence reset | Runtime | DONE | new run/gap gates and tests |
| Clipping/silence/quality | Runtime | DONE | PCM16 positive rail, invalid data and weak/silent gates |
| Bounded frames/events/audit history | Runtime | DONE | 128-entry tails; immutable durable audit archive |
| Analyzer injection / ownership/close | Runtime | DONE | finish factory lifecycle/error paths with replaceable analyzer |
| Production model unavailable/failure | Runtime | DONE | explicit unavailable; no automatic Fake fallback |
| Reference analysis jobs | Runtime | DONE | close/error handling and authoritative completion |
| Baseline context and review policy | Runtime | DONE | accepted retained PCM, reviewed envelope; human-only |
| Baseline immutable in Live | Runtime | DONE | existing command/invariant tests |
| Deviation / common-mode / balance | Runtime | DONE | frozen source delta semantics; downstream centering |
| Empirical confidence gate consumer | Runtime | DONE | consume approved mappings and envelope; no fake values |
| PA state tracking / recommendations | Runtime | DONE | existing Fake full loop and abstention gates |
| Fresh observable verification | Runtime | DONE | post-adjustment complete-window + clock margin tests |
| Pause/resume/stop | Runtime | DONE | lifecycle/retry/reopen tests; bounded teardown |
| Persistence/restart | Runtime | DONE | SQLite atomicity, audit, new-clock restart suspension |
| API and WS/reconnect | Runtime | DONE | loopback transport tests and CP1 smoke |
| Long-running current Runtime | Runtime | DONE | clean7809b1 source:300.344s,297 windows,zero drops/stale/gaps,history128; Runtime checkpoint report |
| Song creation/setup | UI/Runtime | IN_PROGRESS | real UI/API product-flow acceptance |
| Existing song reopen/fallback persistence | UI | IN_PROGRESS | durable saved IDs, server validation, stale/restart handling |
| Reference upload/analysis UX | UI | IN_PROGRESS | asynchronous job flow, failure/retry and selected reference |
| Configured instrument identity UX | UI | IN_PROGRESS | server family support distinct from measured activity |
| Session/PA console switching | UI | IN_PROGRESS | no cross-session events/cursors/state leakage |
| Reference versus baseline display | UI | IN_PROGRESS | authoritative bindings and accepted version |
| Instrument cards / status | UI | IN_PROGRESS | valid-only numbers; no state inference |
| Abstain/inactive/unsupported/unknown | UI | IN_PROGRESS | all distinct, no false Normal |
| Native/live source availability | UI | IN_PROGRESS | actual discovery/errors/source identity |
| Model/provider/execution display | UI | IN_PROGRESS | existing execution truth, no invented provider |
| Unavailable/loading/degraded/suspended | UI | IN_PROGRESS | authoritative errors/quality/state |
| Guided instrument rehearsal | UI/Runtime | IN_PROGRESS | human sample prompts; shared measured evidence, no truth injection |
| Full-band calibration probes | UI/Runtime | IN_PROGRESS | common analysis, explicit interval and qualified coverage |
| Calibration review | UI/Runtime | IN_PROGRESS | per-source evidence/limits, no automatic promotion |
| Explicit Accept as Baseline / Start Live | UI | IN_PROGRESS | human actions, rejection/error handling and current bindings |
| Adjustment/recheck/verification UX | UI | IN_PROGRESS | real commands, fresh-evidence result display |
| UI reconnect/restart behavior | UI | IN_PROGRESS | actual Runtime plus regression tests |
| Fixture fallback / deterministic full app | UI/Runtime | IN_PROGRESS | explicit simulation; no commands from fixture into Runtime |
| Isolated real-audio demo player | UI | DONE | CP1 media execution/isolation tests; no truth data channel |
| Physical-demo hookup instructions | UI | IN_PROGRESS | speaker-room-one-mic routing; no browser inference |
| PN54 inventory script | Runtime | DONE | hardware/provider/device inventory; do not assume hardware |
| Deployment/cache/log/storage layout | Runtime | DONE | explicit local paths/config and offline startup |
| One-command launch/config templates | Runtime | DONE | supported Fake/missing/bundle modes with exact commands |
| Microphone selection/settings | Runtime/UI | IN_PROGRESS | actual discovery, verification profile separately reviewed |
| CPU/test-analyzer fallback | Runtime | DONE | explicit mode and compatible profile; no silent real-to-Fake |
| Runtime parity/sustained harness | Runtime/ML | DONE | portable correctness and sample/clock/profile checks |
| Offline/cache behavior | Runtime/ML | DONE | no runtime downloads/cloud perception; unavailable fail closed |
| PN54 model parity/profile | Runtime | WAIT_HARDWARE | actual PN54 plus selected artifact; local run is not proof |
| Rights-cleared fixture/demo asset ledger | ML/UI | IN_PROGRESS | generated audio permitted; actual music requires remote provenance |
| Model/evidence manifest templates | ML | DONE | exact missing fields remain pending, not guessed |
| Reproducible run commands | Lead/Runtime/UI | IN_PROGRESS | test the final documented commands |
| Demo sequence/hardware checklist | UI | IN_PROGRESS | full guided PA path and acoustic wiring |
| Presentation skeleton/evidence slots | UI | IN_PROGRESS | only measured values/results stay blank |
| Video shot list/fallback | UI | IN_PROGRESS | actual trial capture, labeled fixture/prerecorded fallback |
| Physical acoustic closed loop | Runtime/UI/ML | WAIT_HARDWARE | approved model, capture geometry, actual PN54 trials |
| Final measured evidence/video | Lead/UI/ML | WAIT_MODEL | accepted artifact/calibration and physical deployment evidence |

## Acceptance and evidence discipline

Run all shared, ML, Runtime, integration and UI suites; actual JS/API/WS/SQLite Fake
loop; native session smoke and sustained Runtime beyond history warmup. Verify
file/mic convergence, overlap IDs, stale/dropout incident exclusion, restart/reconnect,
replaceable/unavailable analyzers, human immutable baseline and fresh observable
verification, UI no-inference and player no-truth leakage. A passing final snapshot
release scan excludes private history and authority PDFs; never publish the old Git
history. Document each exact source revision and measured limitations.

The final remaining path must be only remote training result -> artifact/evidence
acceptance -> winner-specific adapter if needed -> held-out evaluation/calibration
-> bundle freeze -> PN54 model parity/profile -> physical speaker-room-mic validation
-> final measured evidence/video. Any other pending software row prevents READY.
