# MVP_PRE_MODEL_READY acceptance evidence

Date: 2026-09-20. Lead decision: **READY for model-independent software**.
Executable integration: `af342d89b0504d51af3319061dd8ce7b18527899`.
Subsequent readiness/release documentation does not change that executable source.

## Accepted sources and ownership

| Lane | Accepted checkpoint | Integration |
|---|---|---|
| ML | `fa7068155461e42ece413235347a6bd5f43667ee` | `fc6e4ad97bbe9165e6de0b9fe196aa1b2691918a` |
| Runtime | `25f8808b751e25abb287c1b3126b898509640637` | `3b12c787f7bb69bef75114088e0d57d6dc05d163` |
| UI | `947dae26f2410023d71f0b4a024e14f5e7e75592` | `6e49fb270d2f1a428a085e1d0f5837d5b88a8e9e` |
| Runtime launcher correction | `eaf5b73dd6bc398498771ebd38b26b8e8f7e501b` | `af342d89b0504d51af3319061dd8ce7b18527899` |

Clean worker checkpoints, frozen-base ancestry and exclusive writable paths were
checked before acceptance. No worker was replaced. The original public schemas and
shared typed contracts have no diff from the guided companion freeze `53577717`.
UI-owned supplied design references were integrated; matching untracked originals
were preserved in a separate temporary backup before merge, not deleted.

## Final automated validation

Command: `python -B scripts/validate.py` on the executable integration above.
Environment: Windows 11, Python 3.14.3, Node 25, NumPy 2.4.3, PyTorch 2.11.0+cpu.
The documented native launch was also independently tested using Python 3.12.14.

| Suite | Result |
|---|---|
| Shared contracts | 28 PASS |
| Runtime | 30 PASS |
| Integration | 54 PASS |
| Training infrastructure | 29 PASS |
| Analyzer infrastructure | 30 PASS |
| Benchmarks | 38 PASS |
| Total Python | **209 PASS** |
| UI | **34 PASS** |
| Unchanged CP1 JS adapter + HTTP/WS + SQLite + scripted Fake loop | PASS, final `LIVE_MONITORING` |
| Release scanner and actual archive-boundary self-tests | PASS, zero eligible-source findings |
| Git whitespace validation | PASS |

The CP1 smoke traverses upload/reference job, rehearsal anomaly, human adjustment,
recheck, explicit baseline acceptance, Live anomaly, adjustment and fresh observable
verification. It uses actual transport and the current JavaScript adapter. It is not
a real-music accuracy result. Existing synthetic optimizer/export regressions were
preserved; no remote research or model training campaign was duplicated locally.
PyTorch's Python 3.14 TorchScript deprecation warnings are confined to existing test
export mechanics; the selected trained backend must choose its supported export path.

The [19 acceptance checks](MVP_ACCEPTANCE_CHECKS.md) map to these suites and the
reports below: converged inputs, bounded history/queues, overlap identity, stale/gap
gates, human immutable baseline, fresh verification, session isolation, reconnect,
safe model failure, replaceability, UI no-inference and demo truth isolation.
Actual ML `BackendRegistry`/`load_bundle` objects are exercised through Runtime
configuration, including accepted reference coverage and durable opaque contexts.

## Browser and launch checks

Lead tested the integrated UI against the one-command local Runtime/Fake launch:

- Health and UI returned HTTP 200; discovery returned seven actual local inputs.
- Setup quantity changes did not submit the form. Canonical `vocals` remained a
  configured family; multiple performers did not become fabricated separated states.
- Browser upload of a generated 12-second PCM16, mono, 48 kHz sine reference
  created the project, song, asset, reference job and rehearsal session through the
  real API. Its SHA-256 was
  `25b402d182e4483a624f7c7d40328ecc7b8df16583d21c73b135d1565d34e29b`.
  This is synthetic transport input, not musical evidence or an empirical label.
- The UI displayed the real session/reference IDs, explicit Fake provider and
  unknown/abstained states with unavailable numerical balance.
- End of file produced `audio_eof` suspension and stale-value withholding.
  Explicit Resume restarted replay. Reload restored the saved song entry, and
  reopening fetched its authoritative suspended state instead of inventing recovery.
- UI owner independently exercised actual probe/action routes through the browser:
  guitar probe -> Pause -> suspension and Runtime cancellation notice -> Resume ->
  ready state -> fresh probe. Its browser console had no warnings/errors. Regression
  tests cover same-session out-of-order probe results and session-generation changes.

Browser validation uncovered the launcher's non-default-port origin mismatch. The
canonical Runtime owner fixed it; Lead reran all suites and launched the integrated
code on port 8096 **without** `PA_ALLOWED_ORIGINS`: health/UI 200, same-origin project
creation 201, foreign-origin request 403. Explicit origin overrides remain preserved.

One pre-merge in-app browser origin retained the old CP1 document/module despite
reload. HTTP content and fresh-origin browsing both served the correct integrated
files; UI independently confirmed the cache issue. A fresh origin was used for the
checks above. This was not an application source regression or a model dependency.

## Native and sustained execution evidence

Accepted source: clean `7809b168e3531d5c09c207d6903929206718bcd7`.
The final integrated capture/frontend/worker/Core/PA/service/config/transport code
and the two used probe scripts have no Git content difference from that source.
The later launcher correction only sets the selected loopback origin allowlist.

- `tests/runtime/reports/native_session_7809b16.json`: actual local microphone,
  12.313 seconds, two acquisition runs with ten windows each, Pause/Resume/Stop,
  zero drops/stale windows/discontinuities; maximum ADC residual 3.213 ms against
  the 50 ms budget. No microphone PCM was saved. Fake evidence abstained.
- `tests/runtime/reports/runtime_300s_7809b16.json`: 300.344 seconds, 297 windows,
  zero drops/stale windows/gaps, peak queue depth 1 of 2, history capped at 128.
  Processing p95 125 ms; publication age p95 156 ms. RSS was 50.82 MiB initially,
  54.18 MiB finally, 58.48 MiB peak; bounded post-warmup range 53.82–58.48 MiB.
  Input was generated constant PCM with no instrument labels.

These are local ASUS/Intel/Realtek transport results, **not PN54 validation**.
Capture gain/AGC/geometry are not claimed verified. Earlier 20-minute evidence stays
bound to its historical source; it is not relabeled as this release. Sustained test
results show no obvious growth over the observed run, not an unlimited-duration proof.

## Release and remaining acceptance

The reviewed release path is `scripts/release_audit.py --export <outside-repo>.zip`
from a clean committed tree. It verifies included file hashes and rescans the actual
archive. The archive and external audit report bind the exact documentation/release
SHA; archive generation is checked before pushing the readiness record. Original
private Git history, local settings, authority PDFs, raw data/audio and model caches
are excluded. The archive does not grant third-party rights. The existing private
history must remain private; no destructive rewrite or public-visibility change was
performed. See `docs/release/RELEASE_READINESS.md` for the bounded audit policy.

No generic product, Runtime, UI, intake, deployment-script or release-documentation
task is held behind training. Remaining acceptance is exclusively:

1. **TRAINED_MODEL:** remote candidate checkpoint/evidence and rights/provenance;
   winner-specific numerical adapter/frontend/cache/export where genuinely needed.
2. **EMPIRICAL_CALIBRATION:** real held-out evaluation, operating envelope/family
   support, fitted independently evaluated confidence and reviewed model-bundle freeze.
3. **PN54_MODEL_DEPLOYMENT:** actual hardware inventory, supported provider, selected
   artifact export parity/performance, native capture profile and sustained deployment.
4. **PHYSICAL_VALIDATION:** permitted playback material, speaker-room-one-microphone
   trials, measured outcomes, final evidence/video. Runbooks and evidence slots exist.

Nano4 can supply the first engineering candidate. Final competition acceptance still
requires meaningful official MI300 task-specific adaptation in the demonstrated
model's lineage. No model capability GO decision, trained weights, fitted confidence
or supported musical-family claim is made by this software milestone.
