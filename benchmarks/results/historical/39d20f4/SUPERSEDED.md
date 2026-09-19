# Superseded first-checkpoint aggregates

Commit `39d20f4ae007e51cd7a6047b6a15bf1b81d68338` preserves the original raw CSV/JSON
runs. Their aggregate centered-balance metrics are superseded because unconfigured
HTDemucs outputs (`piano` and `other`) were allowed into the median and numerical
availability with fewer than three reliable configured sources was reported as
coverage.

Retrieve the historical artifacts without rewriting them:

```text
git show 39d20f4:benchmarks/results/htdemucs_6s_synthetic_smoke/htdemucs_6s.json
git show 39d20f4:benchmarks/results/first_gain_response/synthetic_band_masks_v1.json
```

The corrected benchmark restricts centering to configured valid sources and reports
numeric coverage separately from identifiable/actionable centered-balance coverage.
