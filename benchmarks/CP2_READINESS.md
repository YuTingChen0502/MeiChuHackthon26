# CP2 ML readiness runbook

Status: IMPLEMENTED / TESTED readiness only. Gate A is
**BLOCKED_EXTERNAL_ASSETS** under the Lead resource authorization.
No populated authoritative real multitrack manifest/root is available.
No real-music P1/P2 comparison, calibration, adapted artifact or RealAnalyzer is
delivered by these tools.

## Input audit

Keep restricted recordings outside Git. Supply the existing V1 multitrack manifest
and a copy of `assets/manifests/cp2_use_review.template.json` completed from actual
verified provenance. Bind the review to the exact manifest SHA-256. Record evaluation,
training, remote-compute, demo and publication permissions separately; unknown
permissions stay pending. An evaluation permission never authorizes training/upload.
The template is deliberately unusable as approval.

`training.asset_readiness.audit_assets` reads every WAV payload in bounded chunks,
verifies hashes/header/counts, reports rail samples, checks all four grouped splits,
and detects identical non-silent downmixed PCM across splits even under different
filenames/groups. Declared parent grouping must still account for related songs,
takes, artists and any pretrained overlap. Duplicate detection cannot establish
independence. It returns READY_FOR_LEAD_REVIEW, never Gate-A acceptance.

Run a pair arithmetic/readiness audit with real supplied paths:

```text
python -m benchmarks.audit_real_audio --manifest <manifest.json> --dataset-root <root> --use-review <review.json> --config training/configs/cp2_validation_clean_v1.json --output runs/cp2/input-audit.json
```

The audit materializes only train/validation pairs, records actual mixture hashes,
gain/noise seeds and oracle masks, independently checks measured stem gain response,
and flags clipping without changing levels. Full asset integrity checks read
calibration/test PCM to hash it, but do not evaluate models on those reserved splits.

## Common P1/P2 evaluation path

The existing pair planner generates both candidates' exact validation excerpts,
interventions and noise seeds from the same config. The clean grid includes zero,
common +/-4 dB, each configured source +/-2/4/6 dB and a multi-source control.
No model receives stems, gain labels, noise/SNR labels, seed or filenames.

After Gate-A review and a finite experiment authorization, run clean P1 first:

```text
python -m benchmarks.paired_probe --backend htdemucs_6s --device cpu --manifest <manifest.json> --dataset-root <root> --use-review <review.json> --config training/configs/cp2_validation_clean_v1.json --thresholds training/configs/cp2_probe_thresholds_v1.json --output runs/cp2/p1-clean.json
```

The runner requires a clean committed source tree. Use the existing tested
Torch/Demucs stack and approved locally cached HTDemucs artifact; this checkpoint
does not install packages, alter host drivers or execute a separator experiment.
The existing HTDemucs adapter requires its declared model sample rate (44100 Hz);
the new runner does not silently resample or normalize sources independently.
Multiple instrument IDs of the same family require prior explicit grouping.

A direct candidate uses the same runner and pairs:

```text
python -m benchmarks.paired_probe --backend direct --direct-artifact <paired_model.pt> --direct-manifest <model.json> --manifest <manifest.json> --dataset-root <root> --use-review <review.json> --config training/configs/cp2_validation_clean_v1.json --thresholds training/configs/cp2_probe_thresholds_v1.json --output runs/cp2/p2-clean.json
python -m benchmarks.compare_paired_probes runs/cp2/p1-clean.json runs/cp2/p2-clean.json --output runs/cp2/clean-comparison.json
```

This is an **offline CPU adapter**, not a selected export strategy or production
InstrumentAnalyzer. Supply an explicitly reviewed local TorchScript artifact
containing the actual frontend and paired estimator. Its call takes reference and
observation float32 mono tensors [1, samples], returning (source_delta_db, valid_mask)
with shape [1, family_count]. The boolean mask is numerical-measurement validity;
it is not calibrated confidence. Invalid/unsupported outputs become null.
The manifest requires artifact_sha256, model_id, frontend_id,
pretrained_checkpoint_sha256, training_git_sha, families, and sample_rate_hz.
These declarations preserve identity but do not prove adaptation or calibration.
No such real candidate is supplied or fabricated here. Actual EfficientAT feature
extraction/head fitting/partial-backbone adaptation remain subsequent work.
Tests export a generated toy module solely to validate this adapter's call boundary.
Torch 2.11 on Python 3.14 emits TorchScript deprecation warnings; this tested
diagnostic path does not choose the final portable deployment format.

Comparison rejects different source commits, plan/config/manifest identities,
thresholds, actual PCM hashes, labels or metric populations. Output requests a Lead
decision and never selects a backend automatically.

After clean comparison, the same invocation can use
`training/configs/cp2_validation_white_noise_v1.json` on both candidates:
clean reference versus independently generated observation white noise at
20/10/5/0 dB SNR. This is **not** a crowd/speech/room-noise benchmark.
Recorded-noise provenance/splits, stable acoustic paths, path mismatch, clipping,
inactive/unsupported challenges, continuous normal dynamics and event-level
metrics remain required for a complete Gate-B packet. Do not call these two configs
the entire validated operating envelope.

## Metric meaning

Reports retain all rows, pair hashes/provenance, seeds/gains/noise/SNR, thresholds,
model identity, environment and exact source SHA. They include per-instrument and
per-condition metrics, raw and centered errors, all/eligible frame counts, source
coverage, abstentions and latency. Timing is offline pair prediction including both
branches; it is not sustained PN54 throughput or capture-to-alert latency.

Raw numerical coverage remains reportable with fewer than three valid sources.
Centered predictions require at least three configured numerical sources. Truth
attribution additionally requires a majority of active sources unchanged. For
ambiguous multi-source cases, raw/oracle-centered values remain diagnostic; alert
precision/recall exclude unknown attribution and report that denominator separately.
Numerical balance outputs on ineligible rows remain visible as unsafe diagnostics.
Wrong-sign alerts count as both a false alert and a missed correctly directed alert.
Abstentions count as missed alerts; unconditional errors use a clearly named 12 dB
missing-output penalty, not an invented measured error.

Frame coverage means at least one eligible source received numerical balance.
Per-source coverage accompanies it; this is not calibrated accepted-action coverage.
Overlapping/related windows are not independent statistical trials.
No joint-correctness probabilities, intervals or musical success claims are emitted.

## Remote source and resource discipline

Code originates in this worktree. Commit, push an explicit experiment ref, and use a
dedicated clone checked out at its full SHA on the execution host. Do not edit source
on Nano4 or MI300. The launcher below fetches only the supplied ref and requires
FETCH_HEAD and HEAD to equal that SHA, clean source, a tracked config, and its hash.
It refuses to switch a working checkout silently.

```text
bash benchmarks/launch_exact_readiness.sh <40-char-SHA> <origin-ref> training/configs/direct_training_smoke_v1.json <config-SHA256> <outside-source-output.json>
```

This executes **inventory only**. It does not submit Slurm jobs, download models,
install dependencies or run an optimizer. A local inventory uses:

```text
python -m benchmarks.readiness_environment --output runs/cp2/local-inventory.json
```

The inventory whitelists scheduler fields and dependency versions. It never dumps
credentials or all environment variables. Package presence is not device execution.
The resource ledger template remains unpopulated and grants no authorization.

Nano4 authorization covers inventory/minimal non-destructive readiness only.
The historic gov115094 scheduler probe does not authorize a 32-GPU job.
Before any material run, record exact SHA/config/checkpoint, actual account and
partition, nodes/GPUs, wall time, memory, environment and explicit finite budget.
No host/access instructions are invented here; no Nano4 connection or job was run.

MI300 access, allocation and budget are not supplied. Once provided, use the existing
8-step synthetic head smoke in the approved allocation after the exact-source guard:

```text
python -m training.direct_smoke --config training/configs/direct_training_smoke_v1.json --device auto --output <outside-source-smoke.json>
```

Before running it remotely, bind an actual finite allocation/time/memory cap to the
resource ledger. Inspect the recorded resolved device and torch_hip_version: CPU
fallback is not an MI300 pass. This smoke only proves finite gradients/weight updates
in a random head. Meaningful adaptation requires Gate C, real audited training
pairs, a reachable pretrained checkpoint, partial-encoder weight changes and an
exported descendant used in runtime. The current tools do not bypass those gates.

## Validation

Use the existing CP1 environment where available; the PATH MSYS Python lacks Torch
and jsonschema. No root dependency configuration was changed.

```text
python -m unittest discover -s training/tests -v
python -m unittest discover -s analyzers/tests -v
python -m unittest discover -s benchmarks/tests -v
python -m unittest discover -s core/contracts/tests -v
```

The generated unit fixtures test hash drift, full-payload truncation, renamed
cross-split duplicates, permission conflicts, clipping, missing splits, deterministic
pair generation, model input isolation, null/nonfinite outputs, wrong-sign/missed
alerts, matched comparison rejection, CPU direct artifact loading and source guards.
They are TESTED mechanics, never EMPIRICALLY VALIDATED music.
