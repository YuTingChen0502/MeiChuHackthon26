# First ML/evidence checkpoint

Source commit for both recorded runs:
`ffe6d591fdd07d2f0010d31cb08dcfdf49e08880`.

## Gain-response summary

| Probe | Conditions | Coverage | Covered MAE | Unconditional MAE | Non-neutral sign accuracy | Attribution F1 |
|---|---|---:|---:|---:|---:|---:|
| Synthetic fixed-band separator | clean, 20 dB, 5 dB SNR; 108 eligible source measurements | 100% | 0.0905 dB | 0.0905 dB | 100% | 0.9600 |
| Official `htdemucs_6s` | clean synthetic smoke; 20 eligible source measurements | 25% | 2.3903 dB | 9.5976 dB | 33.33% | 0.8571 |

Synthetic fixed-band MAE by condition was effectively 0 dB clean, 0.0171 dB at
20 dB SNR, and 0.2543 dB at 5 dB SNR. This validates the controlled-pair, separation,
level, centering, masking, noise and metric plumbing only. The separator is deliberately
matched to generated non-overlapping bands and is not a product candidate.

The HTDemucs smoke used Demucs 4.0.1, Torch/Torchaudio 2.11.0 CPU, official checkpoint
SHA-256 `34c22ccb381c6f9fdbf324f04e1e2fe21aaaf293f5ded163a162697ff9a02ddd`,
zero shifts, deterministic algorithms, and one intra/inter-op thread. A second process
produced identical table rows and metrics. The +4 dB guitar case was predicted as
-1.0817 dB and the multi-source +3 dB centered guitar label as -2.5484 dB.

These HTDemucs inputs are mathematical band signals, not rights-cleared musical stems.
The result therefore proves that the adapter/checkpoint executes and that this
out-of-domain smoke is not a sufficient gain estimator; it neither selects nor rejects
HTDemucs for music. A decision requires rights-cleared real multitracks, grouped splits,
the full gain/noise matrix, and matched direct-estimator comparison.

Raw row tables and full metadata are in the adjacent CSV/JSON files. The JSON records
config, seed, asset provenance, split identity, injected/common/centered gains, validity
masks, noise/SNR, checkpoint/runtime, environment and exact command.
