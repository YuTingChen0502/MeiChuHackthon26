# Implementation plan V1

Status: shared interfaces frozen; ready for three parallel write lanes.
Date: 2026-09-19. Owner: engineering Lead.

## Authority and scope

Follow AGENTS.md, docs/product/INFO.md, the restored public schema and technical design.
The first deliverable is the existing PA volume correction loop, using a known song,
uploaded ideal reference, shared file/microphone pipeline, human-approved baseline,
local sensing, recommendations and fresh-audio verification. No scope reopening,
automatic mixing, section targets or LLM audio judgment.

The shared freeze is `contracts/PA_SHARED_INTERFACES_V1.md`, its two companion schemas
and `core/contracts/analyzer.py`. Existing public records are unchanged. Shared fixtures
are illustrative and are never accuracy, calibration or physical-demo evidence.

## Exclusive ownership: exactly three write lanes

All paths are repository-relative. Each lane keeps its own tests/configuration inside
its assigned directories; directories are not permission to alter another boundary.

| Lane | Exclusive writable directories | Responsibility |
|---|---|---|
| ML / Evidence | analyzers/, training/, benchmarks/, models/, assets/ | Pair/oracle generation, separation/direct/hybrid adapters, fine-tuning, calibration experiments, benchmark manifests and licensed asset provenance |
| Runtime / PA Core | core/audio/, core/profiles/, core/runtime/, roles/pa/, apps/api/ | Shared inputs/frontend, model execution orchestration, profiles, deviation/confidence/state/verification, PA policy, session API and persistence |
| UI / Demo | apps/ui/, demo_player/ | Operator presentation/session controls and separate human-operated physical playback environment |

The Lead exclusively owns `contracts/`, `core/contracts/`, `docs/implementation/`,
authority/design documents and root build/dependency configuration. Root changes are
integrated by the Lead, not made opportunistically by a lane. FakeInstrumentAnalyzer
lives in `core/runtime/` and emits the shared evidence type; production analyzer
adapters live in `analyzers/`. Runtime adapters in ML analyzer packages encapsulate
model-specific execution; orchestration/capture providers belong to Runtime.

Create one isolated `codex/` branch/worktree per lane from the same Lead-integrated
freeze commit. No remote machine is a separate source of code changes. Ownership
applies across worktrees; do not edit another lane's files or undo its work.

## First checkpoints

### ML / Evidence

Deliver a deterministic pair generator with synthetic P0 assertions for zero change,
common gain, one-source gain, centered multi-source labels and silent masks. Record
raw gains, common gain, centered balance and validity separately. Use shared scaling,
stable within-pair paths and independent noise/SNR. Synthetic math can start without
recorded stems; empirical probes require rights-cleared multitracks and provenance.

Deliver a tiny reproducible separation/direct gain-response table on identical splits
when assets are available, including noise controls, coverage and unconditional errors.
Expose adapters through AnalyzerContext/AnalyzerEvidence; no public InstrumentState
construction in an analyzer. Calibration results are versioned model evidence, not
permission to bypass Core confidence gates.

### Runtime / PA Core

Deliver a deterministic FakeInstrumentAnalyzer-driven local loop:

uploaded reference -> rehearsal -> human adjustment -> fresh recheck -> explicit
Accept as Baseline -> explicit Live -> anomaly -> bounded recommendation -> human
adjustment -> fresh verification.

Use the same input/frontend/downstream infrastructure for file and microphone paths.
Fixture-driven evidence must be marked `example_only`. Include adverse cases: abstention,
source inactivity, capture gaps, stale commands, incompatible profiles and duplicate
acceptance retries. Silence/disconnection cannot recover an incident. Acceptance must
be atomic and immutable; target changes cannot corrupt an active incident.

Provide schema-valid API snapshots/responses/events and actual command-handler tests
for retry persistence, server clocks, reconnect cursors and snapshot/event consistency.
Runtime defines the remaining setup/upload/job endpoint payloads under apps/api first;
Lead reviews/freezes any shared surface before UI binds to them. This is ordinary
sequenced interface work, not permission for independent conflicting definitions.

### UI / Demo

Render the shared fixtures with session/workflow state, capture/provider, reference
versus baseline, unknown/unsupported states, data age and human-only controls. Bind
session commands to current snapshot versions and exact incident/baseline identities;
refresh on conflict rather than guessing. Do not calculate instrument state in UI.

Prepare the independent playback scenario and rights-cleared asset references.
No playback filenames, gain labels or mixer/control state enter the analyzer.
Fixture screens are not the physical demo and must be identified as illustrative.

## Merge and integration order

1. Lead integrates this shared freeze, examples and passing contract checks. All lanes
   start from that exact commit; no shared-contract forks.
2. Lanes work concurrently: ML P0/data/model probes; Runtime Fake/core/API loop;
   UI fixture rendering and isolated demo player. Inventory on available hardware
   proceeds concurrently with these repository changes.
3. Integrate Runtime's Fake loop and UI against the frozen session boundary. Runtime
   publishes any setup endpoint definitions before UI connects those endpoints.
   Verify explicit acceptance, retries, recheck/verification freshness and reconnects.
4. Integrate ML adapters against the unchanged evidence boundary. Compare separation
   and direct paths on shared evidence/metrics; hybrid depends on useful results from
   both. Do not delay MI300 preparation waiting for a separator to succeed.
5. Select and calibrate the adapted artifact with held-out data. Export and check CPU
   parity; integrate the exact model/frontend/taxonomy/execution bundle and reanalyze
   profiles as needed. Never use a profile generated by an incompatible backend.
6. As soon as PN54 is accessible, run compatibility smoke tests in parallel. Final
   integration requires actual PN54 microphone input, sustained throughput, acoustic
   replay and the complete human correction loop with the MI300-adapted artifact.

Each lane runs shared contract tests plus its relevant tests before integration.
Only measured reproducible results support model selection or claims. A fake loop
does not establish ML feasibility; a frozen/pretrained-only runtime does not satisfy
the chosen MI300 adaptation path. Thresholds and minimum SNR remain experiments.

## Compute responsibilities and hard dependencies

| Environment | Immediate work | What it cannot establish |
|---|---|---|
| Local | Shared contracts; synthetic oracle; pair generator; Fake loop; UI fixtures; CPU/export smoke; licensed-data preparation | Final PN54 performance or physical operating envelope |
| Nano4 | Inventory first; checkpoint/load/audio/portable inference probes and empirical experiments if resources permit | PN54 compatibility/performance or MI300 adaptation compliance |
| MI300 | Access/inventory/budget ledger; forward/backward/optimizer smoke; task-specific partial-backbone fine-tuning after data/labels are validated | Final local critical inference or physical PN54 feasibility |
| PN54 | On access: inventory, native mic settings, CPU/export parity, optional provider checks; later sustained execution and acoustic trials | Accuracy beyond measured conditions or guaranteed NPU support |

Empirical model/noise experiments depend on rights-cleared material, grouped splits
and passing label math. MI300 training additionally depends on a working checkpoint,
approved finite compute budget and optimizer smoke. Calibration and final test sets
are separate. PN54 access is not a prerequisite for the Fake slice or ML preparation.

Every experiment records exact Git commit/config version, seed, dataset provenance
and split, augmentation/gains/noise/SNR, label procedure, checkpoint, environment,
thresholds and metrics. Remote runs execute repository commits, never divergent
ad-hoc edits. The demonstrated runtime artifact must descend from meaningful MI300
adaptation. Critical live inference remains local on PN54.

## Cross-lane escalation and routine fixes

Within owned files and frozen semantics, diagnose local reversible problems, apply
the smallest fix, run relevant validation and continue. Report resolved issues in
the lane checkpoint; do not stop for routine environment/test/code corrections.

If a change crosses ownership or a frozen interface, pause only the affected work.
Send the Lead the exact file/field, failing fixture or evidence, smallest proposed
change and dependent lanes. Continue independent work. Lead adjudicates against the
authority chain, updates shared contracts/tests first when justified, and provides
one integration commit for all dependent lanes before they resume.

Escalate scope/semantic changes, destructive actions, unavailable credentials/resources,
ground-truth invalidation or materially different product behaviors. Do not conceal
such a change in an adapter, UI default or remote experiment. No lane unilaterally
changes units, confidence meaning, baseline acceptance or automatic-action policy.

## Non-blocking follow-ups

Final instrument support, matching robustness, calibration thresholds, usable SNR,
window/hop tuning, optional hybrid/acceleration and complete guided-probe UX are later
evidence-dependent work. The guided-probe context already uses the common analyzer.
Tone, language explanation and Conductor/section control stay outside this checkpoint.
