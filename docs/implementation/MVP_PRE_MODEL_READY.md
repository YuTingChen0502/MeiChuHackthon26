# MVP_PRE_MODEL_READY — convergence inventory and acceptance record

Owner: existing Engineering Lead. Started 2026-09-20. Replaces the incremental
PRE_MODEL_FREEZE target. Status: READY for model-independent software. This is not an empirical model, PN54 or physical-demo acceptance.
The user reports independent Nano4 and MI300 campaigns; no remote result has been
imported or accepted by this local milestone. Do not duplicate their training.

## Definition and source discipline

Complete the functioning PA MVP with explicit Fake/test perception and actual
Runtime/API/UI/native capture. A trained backend later replaces the analyzer through
the frozen InstrumentAnalyzer/AnalyzerEvidence seam. No product/workflow/UI redesign
or unrelated engineering is allowed to remain disguised as waiting for ML.

The existing ML, canonical Runtime and UI lanes are accepted and integrated. No new
writer or compute worktree was created. Accepted checkpoints:

- ML: `fa7068155461e42ece413235347a6bd5f43667ee`.
- Runtime: `25f8808b751e25abb287c1b3126b898509640637`, followed by the tested
  launcher-port correction `eaf5b73dd6bc398498771ebd38b26b8e8f7e501b`.
- UI: `947dae26f2410023d71f0b4a024e14f5e7e75592`.
- Complete executable integration: `af342d89b0504d51af3319061dd8ce7b18527899`.

Final documentation/release commits descend from that tested integration. See
[MVP_PRE_MODEL_VALIDATION.md](MVP_PRE_MODEL_VALIDATION.md) for commands, counts,
actual browser checks, hardware report lineage and limits. The coordination ledger
records decisions and event deduplication. Gate-0/public meanings are unchanged.

## Complete module matrix

DONE means implemented and tested model-independent infrastructure, not empirical
musical validation. WAIT_MODEL and WAIT_HARDWARE rows explicitly separate actual
weights, calibration and physical evidence from completed tooling.

| Module | Owner | Status | Evidence / dependency and next action |
|---|---|---|---|
| Product authority / scope | Lead | DONE | AGENTS, INFO, technical design; no ideation reopened |
| Frozen public records | Lead | DONE | contracts/; original schema unchanged; shared suite |
| Analyzer boundary | Lead/ML | DONE | PA_ANALYZER_V1 + TypedDict/validation; exactly one evidence mode |
| Session/setup wire boundary | Lead | DONE | PA_SESSION_WIRE_V1, PA_SETUP_WIRE_V1; atomic command tests |
| Root dependencies | Lead | DONE | requirements-runtime.txt; native pins validated at 42ba903 |
| Common integration entrypoint | Lead | DONE | scripts/validate.py; complete final suite and Fake HTTP/WS smoke pass |
| Internal bundle/approval handoff | Lead | DONE | MODEL_HANDOFF_INTERNAL_V1; actual ML loader/Runtime integration tests pass |
| English README / architecture | Lead | DONE | root README: architecture, installation, launch, compute roles and limits |
| Source release audit/export | Lead | DONE | scripts/release_audit.py; scan/self-test and clean history-free archive validation |
| Current handoff / reproducibility | Lead | DONE | current handoff, accepted SHA ledger and final validation record |
| License and asset policy | Lead | DONE | docs/release/RELEASE_READINESS.md; explicit rights boundary and source-export route |
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
| Rights-cleared real-audio dataset/evidence acceptance | ML | WAIT_MODEL | Remote provenance, rights review and held-out split/evidence supplied with candidate |
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
| Analyzer injection / ownership/close | Runtime | DONE | actual factory/registry integration, identity-safe replacement and close/error tests |
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
| Song creation/setup | UI/Runtime | DONE | actual browser upload/project/song/reference/session sequence; UI34 |
| Existing song reopen/fallback persistence | UI | DONE | actual browser reload/reopen; validated local catalog, corruption/identity tests |
| Reference upload/analysis UX | UI | DONE | actual WAV upload/job success; errors remain explicit; adapter failure regressions |
| Configured instrument identity UX | UI | DONE | canonical vocals; quantity controls preserve family-group evidence; UI34 |
| Session/PA console switching | UI | DONE | adapter generation/cursor and delayed-response isolation tests |
| Reference versus baseline display | UI | DONE | visible authoritative session/reference/baseline IDs and version bindings |
| Instrument cards / status | UI | DONE | valid-only values; received evidence history; no waveform/source estimation |
| Abstain/inactive/unsupported/unknown | UI | DONE | distinct presentation; no false Normal/recovered on stale/unobservable evidence |
| Native/live source availability | UI | DONE | actual local inventory7; source state and unavailable-device presentation |
| Model/provider/execution display | UI | DONE | actual Runtime identity; explicit simulated/unavailable state |
| Unavailable/loading/degraded/suspended | UI | DONE | canonical snapshot/errors; observed EOF suspension and stale withholding |
| Guided instrument rehearsal | UI/Runtime | DONE | actual GET/POST probe routes; browser cancellation/resume; generation/version tests |
| Full-band calibration probes | UI/Runtime | DONE | shared probe path, quiet/loud prompts, post-request evidence cutoff; guided tests |
| Calibration review | UI/Runtime | DONE | explicit interval and operator draft retained across updates; server coverage gates |
| Explicit Accept as Baseline / Start Live | UI | DONE | human-only controls/bindings; full API/JS Fake loop and invariants pass |
| Adjustment/recheck/verification UX | UI | DONE | real commands; waiting/partial/inconclusive/recovered presentation tests |
| UI reconnect/restart behavior | UI | DONE | saved-song browser reopen; WS cursor recovery; replacement new-session path |
| Fixture fallback / deterministic full app | UI/Runtime | DONE | labeled fixtures stop real events/mutations; full Fake adapter/API/WS smoke |
| Isolated real-audio demo player | UI | DONE | CP1 media execution/isolation tests; no truth data channel |
| Physical-demo hookup instructions | UI | DONE | docs/demo/PHYSICAL_DEMO_RUNBOOK.md; acoustic-only wiring and recovery procedure |
| PN54 inventory script | Runtime | DONE | hardware/provider/device inventory; do not assume hardware |
| Deployment/cache/log/storage layout | Runtime | DONE | explicit local paths/config and offline startup |
| One-command launch/config templates | Runtime | DONE | supported Fake/missing/bundle modes with exact commands |
| Microphone selection/settings | Runtime/UI | DONE | Runtime-discovered IDs and requested capture configuration; no claimed physical verification |
| CPU/test-analyzer fallback | Runtime | DONE | explicit mode and compatible profile; no silent real-to-Fake |
| Runtime parity/sustained harness | Runtime/ML | DONE | portable correctness and sample/clock/profile checks |
| Offline/cache behavior | Runtime/ML | DONE | no runtime downloads/cloud perception; unavailable fail closed |
| PN54 model parity/profile | Runtime | WAIT_HARDWARE | actual PN54 plus selected artifact; local run is not proof |
| Rights-cleared fixture/demo asset ledger | ML/UI | DONE | assets/ASSET_MANIFEST.json generated-fixture provenance; docs/demo/ASSET_INTAKE.md real-media admission |
| Model/evidence manifest templates | ML | DONE | exact missing fields remain pending, not guessed |
| Reproducible run commands | Lead/Runtime/UI | DONE | documented Python3.12 launch and full validation executed; custom-port regression fixed |
| Demo sequence/hardware checklist | UI | DONE | docs/demo/PHYSICAL_DEMO_RUNBOOK.md; complete physical trial and teardown sequence |
| Presentation skeleton/evidence slots | UI | DONE | docs/demo/EVIDENCE_PACKET.md; only actual model/hardware/trial results pending |
| Video shot list/fallback | UI | DONE | EVIDENCE_PACKET.md; permitted prerecorded or clearly illustrative fallback |
| Physical acoustic closed loop | Runtime/UI/ML | WAIT_HARDWARE | approved model, capture geometry, actual PN54 trials |
| Final measured evidence/video | Lead/UI/ML | WAIT_MODEL | accepted artifact/calibration and physical deployment evidence |

## Acceptance and evidence discipline

Passed shared, ML, Runtime, integration and UI suites; actual JS/API/WS/SQLite Fake
loop; native session smoke and sustained Runtime beyond history warmup. Verify
file/mic convergence, overlap IDs, stale/dropout incident exclusion, restart/reconnect,
replaceable/unavailable analyzers, human immutable baseline and fresh observable
verification, UI no-inference and player no-truth leakage. A passing final snapshot
release scan excludes private history and authority PDFs; never publish the old Git
history. Document each exact source revision and measured limitations.

The final remaining path must be only remote training result -> artifact/evidence
acceptance -> winner-specific adapter if needed -> held-out evaluation/calibration
-> bundle freeze -> PN54 model parity/profile -> physical speaker-room-mic validation
-> final measured evidence/video. There are no remaining generic product, Runtime, UI or bundle-plumbing tasks.
Nano4 may unblock engineering first; final competition acceptance still requires
meaningful MI300 adaptation lineage. No ML GO decision has been issued here.
