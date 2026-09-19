# CP2-ML readiness checkpoint

Date: 2026-09-19.
Authorized CP2 base: `8c8226d18c0b2def5098368cebe6699be6498c15`.
Implementation/evidence source: `1aedfc431fe59833f67092b7cf49612c496809e7`.
Lane: `codex/cp2-ml-real-audio`.
Workspace: `C:/Coding/MeiChuHackathon26-wt-cp2-ml`.

## Disposition

IMPLEMENTED and TESTED local ingestion/probe readiness.
**Gate A: BLOCKED_EXTERNAL_ASSETS.**
This is the plan's assets-unavailable readiness deliverable, not a passed ML-2A
real-audio comparison, Gate B, or overall Checkpoint 2 completion.

No empirical GO / NO-GO / NARROW_ENVELOPE selection is made. The dominant musical
feasibility question is still unanswered. Numerical RealAnalyzer recommendations,
meaningful MI300 adaptation and physical deployment remain gated.

## Implemented

- A manifest-bound usage review template with separate evaluation, training,
  remote-compute, demo and publication permissions. No actual asset/license
  assertions were added; the template remains pending.
- Full-payload, bounded-memory WAV integrity audit, four-way grouped-split counts,
  non-silent duplicate PCM detection across splits, permission-conflict detection,
  and explicit Lead-review status. Existing manifest/public schemas are unchanged.
- Deterministic validation-only clean and white-noise configs using the CP1 pair
  planner; independent stem-gain arithmetic and clipping audit.
- One fixed-pair evaluation harness for existing HTDemucs separation and a supplied
  exported direct candidate. Only mixture PCM/rate/configuration reaches predictors.
  The direct adapter is CPU diagnostic infrastructure, not a fitted EfficientAT
  model or production InstrumentAnalyzer.
- Raw versus centered measurement coverage; per-instrument/condition errors;
  explicit abstention penalties; wrong-sign and inactive false alerts; ambiguous
  attribution counts; matched comparison rejecting different actual audio/labels.
- Clean exact-SHA/tracked-config guard, environment inventory and an inventory-only
  remote launcher. No jobs, installs, downloads or driver changes are performed.

Commands, model adapter expectations and metric semantics are in
[CP2_READINESS.md](../../CP2_READINESS.md).

## Validation

Existing CP1 Python environment:
`C:/Users/USER/AppData/Local/Programs/Python/Python314/python.exe`,
Python 3.14.3, NumPy 2.4.3, Torch 2.11.0+cpu, jsonschema 4.23.0.

| Command suffix | Passed |
|---|---:|
| `-m unittest discover -s training/tests -v` | 23 |
| `-m unittest discover -s analyzers/tests -v` | 7 |
| `-m unittest discover -s benchmarks/tests -v` | 30 |
| `-m unittest discover -s core/contracts/tests -v` | 24 |
| Total | 84 |

All executed without skipped tests in this environment. New coverage includes a
generated TorchScript artifact loaded/executed on CPU, provenance binding,
truncation, split leakage, deterministic audio identity, clipping, abstention and
source/metric guards. Generated tones and simulated unit-test permission records
are test fixtures only and were not added to the project asset manifest.

Git Bash `bash -n benchmarks/launch_exact_readiness.sh` passed.
Staged `git diff --check` passed. Every changed path is inside lane ownership.

[local-inventory.json](local-inventory.json) records a clean source checkout at
the implementation SHA above. The exact-SHA/config guard was exercised with the
existing direct-smoke config. Dependency presence is not GPU/device execution.

[local-cpu-optimizer.json](local-cpu-optimizer.json) records an explicit CPU-only
eight-step optimizer smoke at that same SHA:
12/12 parameter tensors have nonzero gradients and changed weights;
loss 2.1650998592 -> 1.2777589560; seed 260919; AdamW.
Input features are synthetic and the head starts randomly.
No pretrained encoder was loaded. This repeats training mechanics, not meaningful
adaptation or musical perception.

The recorded config hash is the actual local file-byte hash
`52a623acbec5c37f8d0742727bbcde126a431fe259e8e630123c3bf7d3ab394c`.
Compute expected config hashes for the exact execution copy; historical raw-byte
hashes may differ with line endings. New CP2 configs and the shell launcher have
lane-local LF rules for portability.

## Routine issues resolved locally

The PATH MSYS Python lacked Torch/jsonschema; reused the existing CP1 Python
environment without changing dependencies. The default Windows bash attempted WSL
and failed to start; used installed Git Bash for shell syntax validation.
TorchScript emits upstream deprecation warnings on Python 3.14, documented in the
runbook; the CPU diagnostic tests passed. This does not freeze the final export format.

## Remaining work and external dependencies

- No authoritative rights-cleared real-multitrack root/manifest was supplied.
  No real audio was downloaded, relabeled or measured. Gate A remains
  BLOCKED_EXTERNAL_ASSETS.
- No real P1 gain-response result, actual pretrained direct feature/head comparison,
  real-noise/SNR experiment, calibrated confidence, export parity for an adapted
  model or RealAnalyzer artifact exists from this checkpoint.
- White noise is an explicit mathematical condition. Recorded speech/crowd/room
  noise, acoustic-path mismatch, unsupported/inactive challenges, continuous event
  metrics and independent held-out data remain required for a complete Gate B.
- Nano4 inventory/minimal smoke is authorized, but no connection/run was attempted
  without a supplied endpoint. A material-experiment allocation/budget remains
  unspecified; historic scheduler feasibility is not a CP2 training allocation.
- Official MI300 access/quota/budget remain absent. The existing bounded optimizer
  procedure is packaged, but no MI300 smoke or adaptation was executed.
- No PN54 deployment or physical acoustic demonstration was performed.
- No production analyzer, public contract, runtime/core, UI, PA policy, root config
  or product scope changed. No cross-lane request is required for this checkpoint.

Claims: IMPLEMENTED / TESTED only; not EMPIRICALLY VALIDATED, DEPLOYED, or
PHYSICALLY DEMONSTRATED.
