# First ML/evidence checkpoint

Source commit for both recorded runs:
`043e154117dcf2dcfeb5d8dd82ba13d649ff354a`.

## Gain-response summary

| Probe | Conditions | Numeric coverage | Actionable coverage | Raw-delta MAE on numeric values | Centered-balance MAE | Sign / F1 |
|---|---|---:|---:|---:|---:|---:|
| Synthetic fixed-band separator | clean, 20 dB, 5 dB SNR; 108 eligible source measurements | 100% | 100% | 0.0867 dB | 0.0905 dB | 100% / 0.9600 |
| Official `htdemucs_6s` | clean synthetic smoke; 20 eligible source measurements | 25% | 0% | 2.5992 dB | unavailable | unavailable |

Synthetic fixed-band MAE by condition was effectively 0 dB clean, 0.0171 dB at
20 dB SNR, and 0.2543 dB at 5 dB SNR. This validates the controlled-pair, separation,
level, centering, masking, noise and metric plumbing only. The separator is deliberately
matched to generated non-overlapping bands and is not a product candidate.

The HTDemucs smoke used Demucs 4.0.1, Torch/Torchaudio 2.11.0 CPU, zero shifts,
deterministic algorithms, and one intra/inter-op thread. The adapter hashed the artifact
actually loaded, verified it against expected SHA-256
`34c22ccb381c6f9fdbf324f04e1e2fe21aaaf293f5ded163a162697ff9a02ddd`, and rejected
mismatches. A second process produced identical table rows and metrics.

Only the configured guitar output remained numerically available; fewer than three
reliable configured sources means common mode and centered balance are not identifiable.
The +4 dB guitar raw source delta was predicted as -0.1500 dB and the multi-source
guitar raw target +5 dB as -1.5385 dB. No centered HTDemucs MAE, sign accuracy or
anomaly F1 is reported. The earlier aggregates at commit `39d20f4` are preserved but
explicitly superseded under `benchmarks/results/historical/39d20f4/`.

These HTDemucs inputs are mathematical band signals, not rights-cleared musical stems.
The result therefore proves that the adapter/checkpoint executes and that this
out-of-domain smoke is not a sufficient gain estimator; it neither selects nor rejects
HTDemucs for music. A decision requires rights-cleared real multitracks, grouped splits,
the full gain/noise matrix, and matched direct-estimator comparison.

Raw row tables and full metadata are in the adjacent CSV/JSON files. The JSON records
config, seed, asset provenance, split identity, injected/common/centered gains, validity
masks, noise/SNR, checkpoint/runtime, environment and exact command.
