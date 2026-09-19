# ML / Evidence checkpoint review V1

Actual reviewed commit: `39d20f4ae007e51cd7a6047b6a15bf1b81d68338` on
`codex/ml-evidence-foundation`. The handoff's `39d20f48` was a short-SHA typo;
the branch, worktree and commit history identify the full SHA above.
Recorded experiment source: `ffe6d591fdd07d2f0010d31cb08dcfdf49e08880`.
Date: 2026-09-19. Reviewer: engineering Lead.

## Verified

- All 37 changed files are within ML-owned analyzers/, training/, benchmarks/,
  models/ and assets/.
- 39 tests passed on the checkpoint: 21 shared tests and 18 ML tests, using Python
  3.12, NumPy 2.3.5 and the temporary jsonschema validation environment.
- Synthetic band-mask results are explicitly labeled diagnostic-only. The direct
  estimator is an abstaining scaffold, not a fitted pretrained probe or MI300 model.
- The reported HTDemucs smoke is explicitly out of domain. It neither selects nor
  rules out the backend for music; rights-cleared grouped musical multitracks remain
  necessary for empirical P1/direct comparison.

## Integration gate: centering semantics

`analyzers/separation/levels.py:gain_response` uses every separator output to compute
the common-mode median. HTDemucs includes unconfigured piano/other outputs, while
the benchmark's oracle/configuration contains bass/guitar/vocals/drums.

A temporary probe executed the exact committed function with configured raw deltas
`[0,4,0,0]` and unconfigured deltas `[20,20]`. It returned common mode approximately
2 dB and guitar balance approximately +2 dB; the configured oracle requires common
mode 0 dB and guitar balance +4 dB. This is a measurement-definition mismatch, not
evidence about separator accuracy.

Restrict centering to configured valid source IDs, retain invalid masks, and distinguish
numerical availability from identifiable/actionable balance coverage when insufficient
anchors remain. Add the extra-output regression. Preserve old raw runs as superseded
diagnostics; regenerate or appropriately recompute affected aggregates with explicit
provenance before promoting them as the current checkpoint.

The adapter also reports a literal checkpoint SHA without verifying the loaded file.
Verify the artifact actually used, or distinguish expected from unverified provenance.
Do not silently assert a fixed literal is a measured checksum.

## Disposition

Requested integration is held pending the targeted ML-owned correction. The Lead sent
the findings to the existing ML task; it acknowledged the centering/coverage issue
and is correcting the code and evidence. No ML files were edited from the Lead task.
Preserve the full branch history when integrating: the final result commit depends
on four earlier implementation/provenance commits.

Do not use the current smoke aggregates for backend selection. The original recorded
25% coverage, 2.3903 dB covered MAE, 9.5976 dB penalized unconditional error and 33.33%
covered non-neutral sign accuracy are historical diagnostic outputs, additionally
affected by the centering/coverage issue above. No MI300 adaptation or PN54 claim follows.
