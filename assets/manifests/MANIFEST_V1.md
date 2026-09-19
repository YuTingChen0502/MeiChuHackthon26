# Multitrack asset manifest V1

Empirical ML evidence requires a JSON manifest with:

- dataset origin, permission/license, attribution and publication status;
- one immutable recording ID and parent group ID per recording;
- exactly one split per parent group across all recordings;
- sample rate and sample count shared by every stem in a recording;
- one normalized relative WAV path and lowercase SHA-256 per configured stem.

Allowed splits are `train`, `validation`, `calibration` and `test`. Allowed publication
states are `publishable`, `private_eval_only` and `restricted_no_redistribution`.
Asset paths cannot be absolute, contain `..`, use backslashes or resolve outside the
declared dataset root. The current loader accepts uncompressed mono/stereo integer PCM
WAV at 8, 16, 24 or 32 bits and deterministically downmixes stereo by channel mean.

Validate a populated manifest before pair generation:

```text
python -m benchmarks.validate_multitrack_assets \
  --manifest assets/manifests/my_dataset.json \
  --dataset-root D:/pa-datasets/my_dataset \
  --output benchmarks/results/assets/my_dataset_validation.json
```

The dataset root and audio are local inputs and are not committed unless publication
rights explicitly permit it. Validation does not make a dataset appropriate for public
redistribution or prove model feasibility.

