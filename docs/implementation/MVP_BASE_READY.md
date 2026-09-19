# Final MVP integration base: frozen Nano4 candidate

The Lead accepts publication `01eaf5ddcc439efe799be61e54589d331c8556c6`
as **engineering candidate material only**. Merge `80f6df0103c3cd436a919b92db9fb82e8e703536`
preserves both publication commits and their evidence history. This record supersedes
the previous waiting-for-artifact status; it does not authorize production inference.

## Review

- Common ancestor: `3d161dd86c941e4a72ac4053ac795b0c3f7e5cb0`.
- All 53 publication files are within `models/candidates/`; no shared contract,
  Core, Runtime, UI or root dependency was changed by the publication.
- All 45 artifact manifest entries verify, including the two checkpoint files
  stored inside `results/model_bundle.tar.gz`. Archived metadata matches Git.
- Adapted checkpoint SHA-256:
  `b8293c362802e863109c9bec82b50c8211b63ad3947a53a12bd5d81eab0a6229`.
- Exact upstream checkpoint SHA-256:
  `34c22ccb381c6f9fdbf324f04e1e2fe21aaaf293f5ded163a162697ff9a02ddd`.
- Archive SHA-256:
  `5963e80929e2fa987f223056dacf70659066ef07154b169447e1864dd5e933ad`.
- Recorded two-run logical-output hashes were recomputed and agree; all twelve
  recorded smoke checks pass. No local H200 inference rerun is claimed.
- JSON/Python syntax, archive paths/link types, and redacted credential/signed-URL
  scanning passed. `NANO4_MVP_BASE_REVIEW.json` records the bounded review.
- Lead added narrowly scoped `.gitattributes` rules to preserve these frozen bytes
  under Windows `core.autocrlf=true`; all 45 hashes also passed after checkout.

The existing full suite passed on this integration: 209 Python tests, 34 UI tests,
unchanged complete Fake HTTP/WS/SQLite correction-loop smoke and release scanner
self-tests. Existing TorchScript/Python 3.14 deprecation warnings remain non-failing.

## Evidence and authorization boundaries

P1_ADAPTED is selected: exact upstream HTDemucs 6-source reconstruction plus adapted
`decoder.3.conv_tr.{weight,bias}` and `tdecoder.3.conv_tr.{weight,bias}`.
The frozen frontend is 44.1 kHz, four seconds/176,400 samples, amplitude-preserving
matched reference/observation, mono duplicated to the model's dual-mono input.
These requirements belong to model/frontend configuration, not an ordinary user
sample-rate preference. Native hardware capture negotiation remains Runtime-owned.

Only **bass** has support evidence, and only in the tested matched-digital regime.
Drums, guitar, vocals and keys remain unsupported; unknown families have insufficient
evidence. Unsupported numerical evidence is null, with an explicit reason. Confidence
is uncalibrated: public probability stays null, and no numerical correction or Normal
state is authorized by this publication. H200's approximately 82 ms observation
measurement is retained as remote evidence, never relabeled PN54 performance.

The experimental harness computes its own diagnostic common mode before support
masking. It is not the frozen `AnalyzerEvidence` interface. Product adapters must not
copy that centered balance, use unsupported sources as valid anchors, or bypass
Core's at-least-three-valid-source rule. Candidate-mode raw bass evidence may be
implemented explicitly; Core may consequently abstain from centered balance. Keep
the existing confidence, baseline, comparability and fresh-verification gates.

The two committed smoke WAVs are MoisesDB-derived validation research fixtures.
Their provenance is retained; the dataset manifest marks publication restricted.
This private integration is not demo/public redistribution approval. Existing
source-only release tooling excludes WAVs, checkpoints and the binary bundle archive.
Do not publish private history or turn benchmark fixture labels into inference input.

Meaningful official MI300 adaptation, held-out confidence calibration, PN54 execution
and physical speaker-room-microphone validation remain separate gates. Existing
fresh-final exposure cannot be relabeled untouched post-MI300 evidence.

## Existing lane dispatch

Use the existing worktrees/branches, fetch origin, preserve any uncommitted owned
work, then merge the exact Lead-announced base SHA. Do not reset or recreate a lane.
Verify that base is an ancestor before implementation checkpoints. Never regenerate
frozen manifests merely to accommodate line-ending conversion.

| Lane | Immediate work | Ownership |
|---|---|---|
| ML | Verified offline reconstruction, portable HTDemucs adapter, prepared-reference cache, frozen raw AnalyzerEvidence, candidate-only support/uncertainty gates and deterministic tests; no new research | analyzers/, training/, benchmarks/, models/, assets/ |
| Runtime | Consume ML factory/profile, enforce source/frontend identity, candidate availability, model-change reference/baseline invalidation, actual file/native orchestration and sustained tests; preserve already accepted acquisition and Fake path | core/audio/, core/profiles/, core/runtime/, roles/pa/, apps/api/, tests/runtime/, tests/integration/ |
| UI | Current Runtime API parity, model-owned sample-rate presentation, explicit candidate/uncalibrated/unsupported states, reconnect and physical-demo flow; no inference or redesign | apps/ui/, demo_player/, docs/demo/, tests/ui/ |

Work proceeds concurrently. ML publishes the exact loader/profile invocation directly
to Runtime through Lead routing. Runtime publishes any required existing-API usage
to UI. Shared changes require Lead review; no lane edits another owner's files.
Acceptance/merge order remains ML adapter, Runtime integration, then UI parity.
Report coherent clean checkpoints with SHA, ownership, tests and remaining gates.
No candidate-specific implementation is included in this base integration.
