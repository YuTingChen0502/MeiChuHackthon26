# ML/evidence benchmark entry points

Run the dependency-light diagnostic from the repository root:

```text
python -m benchmarks.run_gain_response --backend synthetic_band_masks_v1
```

This diagnostic consumes only mixed audio, but it is deliberately matched to
repository-generated non-overlapping bands. It validates gain labels, pair scaling,
noise/SNR generation, source-level extraction and metrics. It is not evidence that a
music separator works on real instruments.

The approved first candidate probe is:

```text
python -c "import torch, demucs; print(torch.__version__, demucs.__version__)"
python -m benchmarks.run_gain_response \
  --config training/configs/htdemucs_gain_response.json \
  --backend htdemucs_6s \
  --output-dir benchmarks/results/htdemucs_6s_synthetic_smoke
```

Run that command on Nano4 after inventorying its existing Torch runtime and making
the official `htdemucs_6s` checkpoint available. The adapter reads in-memory tensors;
it never uses independently rescaled saved stems. Replace the synthetic assets with a
rights-cleared grouped split before treating results as music-domain evidence.

After validating a rights-cleared four-family recording, run the same measurement
path without exposing stems to the separator:

```text
python -m benchmarks.run_gain_response \
  --config training/configs/htdemucs_gain_response.json \
  --backend htdemucs_6s \
  --asset-manifest assets/manifests/my_dataset.json \
  --dataset-root D:/pa-datasets/my_dataset \
  --recording-id held-out-take-001 \
  --sample-start 0 \
  --output-dir benchmarks/results/htdemucs_6s_held_out_take_001
```

The runner verifies every stem hash, loads one stable excerpt, builds reference and
observation mixtures, and passes only mixtures to the separator. Exactly one manifested
stem must map to each of `bass`, `guitar`, `vocals` and `drums`. Results retain dataset,
parent-group, split, excerpt, manifest and per-stem hash provenance.

Before a remote training or systematic benchmark run, freeze deterministic pair work:

```text
python -m training.pair_plan \
  --manifest assets/manifests/my_dataset.json \
  --config training/configs/manifested_pair_plan_v1.json \
  --output assets/manifests/my_dataset_pair_plan.json
```

The plan fixes grouped splits, exact excerpts, scenario/noise grids, seeds, gains,
manifest/config hashes and asset identities. Audio is still hash-verified when a plan
entry is materialized. Requested gains do not imply observability: silent stems receive
null regression labels from the oracle and remain useful abstention examples.
