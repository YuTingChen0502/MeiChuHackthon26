# Runtime / PA Core checkpoint review V1

Reviewed commit: `78a362ea184ec3f5302c0cef271c16a06299d316`.
Parent freeze: `f22f1e161bb69964765ba58305f7f169950f945c`.
Date: 2026-09-19. Reviewer: engineering Lead.

## Disposition

The in-process facade and first Fake-driven loop are useful implementation progress.
Do not merge this checkpoint as a completed closed-loop Runtime or connect browser
mutations yet. The regressions below violate existing frozen lifecycle semantics.
No product-scope or existing public-record amendment is needed to fix them.

## Validation

The declared commit was checked in the Runtime worktree. Supplied tests passed:
shared 21/21, runtime 4/4, integration 7/7 (32 total). Extra temporary probes reused
the committed vertical-slice fixtures, with independent temporary stores per case.
They did not edit Runtime implementation/test files. Their observed results were:

| Probe | Observed at reviewed commit | Required |
|---|---|---|
| Finish the full recovery loop, then feed two new guitar +4 dB observations | Same event remains resolved, zero recommendations | Detect a new persistent incident and permit a new human correction loop |
| Pause, then feed two anomaly observations | Leaves SUSPENDED for ANOMALY_DETECTED; emits recommendation | Stay suspended and suppress recommendations/verification success |
| Stop, then submit a current-version recheck(null) | HTTP 200; workflow returns to REHEARSAL | Reject mutation; STOPPED is terminal |
| Anomaly observation, dropout observation, anomaly observation | Opens an incident using pre-gap persistence | Reset persistence at discontinuity; require fresh contiguous support |

These tests expose gaps that the existing happy-path and all-stale tests do not cover.

## Required Runtime corrections

1. **Repeated incidents/adjustments.** `roles/pa/session.py` detects only when incident
   is null, but recovery retains a resolved incident and completed adjustment. Preserve
   history while clearing/replacing active pointers at the appropriate lifecycle
   boundary. Permit another correction after partial/not_recovered outcomes as well.
2. **State authorization.** Centralize checks for stopped/suspended sessions and
   unresolved adjustments. Audio while paused must not open/resolve an incident;
   free recheck, acceptance or start_live must not resurrect a stopped session or
   discard unresolved work. Resume needs validated fresh input, not just a name change.
3. **Discontinuity.** `roles/pa/policy.py` currently returns from unusable quality
   without resetting persistence. A stale/dropout gap cannot bridge an alert streak.
4. **Atomic mutation and restart.** `apps/api/commands.py` persists the response after
   mutating an in-memory session/baseline store. `RuntimeAPI` recreates counters and
   empty state on construction while existing session-N command-ledger paths remain.
   Restore durable session/baseline/identity state and commit it with the idempotency
   outcome, with no partial mutation on failed commit. Do not reuse old session IDs
   for unrelated new sessions. Restarting only CommandHandler with the same live
   session is not a cold process/session restoration test. Use the stdlib SQLite path
   already allowed by the design, or another genuinely atomic store with equivalent
   tests; no new root storage dependency is required.
5. **Transport migration.** Adopt the Lead-frozen setup schema, explicit reference_id,
   server-owned clock, setup validation and source hash identity. Add the approved
   loopback adapter under apps/api and test actual HTTP/WS error/status/cursor behavior.

Further gates before real-analyzer/physical integration: FrameBuilder's fixed simulated
calibration must never turn non-fake evidence into an asserted 95% confidence; capture
compatibility/provenance must gate Live; overlapping windows must not inflate coverage
or make a valid interval impossible; streaming framing must not buffer an unbounded
capture iterator. These are not claims already established by the finite Fake tests.

## Lead decisions supplied

- `requirements-runtime.txt`: tested Starlette/Uvicorn/websockets dependency set.
- `contracts/PA_SETUP_WIRE_V1.schema.json` and `PA_SETUP_TRANSPORT_V1.md`: setup payloads,
  route statuses, raw WAV upload, reference binding, server clock and WS adapter rules.
- `tests/runtime/` and `tests/integration/` explicitly assigned to Runtime ownership.
- The dependency-selection blocker is resolved. Runtime owns the listener implementation;
  the UI remains fixture-driven until a corrected network checkpoint is available.

Re-review the corrected commit, repeated-loop/state/restart regressions, and actual
HTTP/WS integration before accepting this milestone. The shared Gate-0 freeze remains
ready for parallel work; these are implementation acceptance gates.
