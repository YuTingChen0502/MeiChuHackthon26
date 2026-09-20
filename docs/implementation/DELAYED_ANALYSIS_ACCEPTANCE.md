# Delayed candidate analysis and semantic audit follow-up

Status: integration validation pending. This record will be completed after the
existing lane checkpoints are reviewed and tested on canonical main.

The session was not expiring after four seconds. Four seconds is the model input
window; the session continues. Roughly six-second CPU inference exceeded the old
two-second completed-result budget, and intentionally skipped analysis windows
were incorrectly treated as missing microphone PCM. Both prevented useful current
publication. The candidate-only timing amendment separates bounded scheduling from
result validity and fixed hint display lifetime.

The user-provided semantic audit on `d267da4` additionally identified diagnostic
timestamp changes creating lifecycle-version churn (MIC-005) and compatible old
reference caches preventing source separation (MIC-007). These narrow corrections
retain state/reference/generation binding, artifact integrity and invalid comparison
for reference data that must be prepared again. Generic unaccepted-bundle policy
(MIC-009) is a separate route and is unchanged.

## Reference position

P1 currently compares equal relative sample spans, not recognized song position.
At 44.1 kHz, observation `[441000,617400)` compares against reference seconds
10–14. Each fresh source generation begins at zero. Restart/switch requires the
operator to restart synchronized performance/playback from the reference beginning.
No matching span means comparison unavailable; it does not fabricate alignment or
stop otherwise compatible model execution. Late entry, tempo drift, seeking and
section jumps remain unsolved. Session duration cannot solve this limitation.

## Claim boundary

The new profile does not accelerate the model to one-second throughput. Delayed
results are explicitly labelled; the queue remains bounded and discards obsolete
work. Numerical confidence and physical-room accuracy remain unvalidated. Fresh
perception does not guarantee a hint: native capture compatibility, comparison
coverage, clipping/dropout and sufficient independently eligible sources still
gate directions. In particular, unverified native capture withholds advice.

No raw microphone recording is required for the timing receipt. A generated
reference used in native tests is transport material, not musical ground truth.
