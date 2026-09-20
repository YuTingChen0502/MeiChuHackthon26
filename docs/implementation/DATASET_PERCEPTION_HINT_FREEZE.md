# Dataset-family perception and experimental direction hints

User-authorized amendment, 2026-09-20. This supersedes the candidate's former
bass-only product publication mask, not the historical evaluation results.

## Attempted perception is distinct from empirical validation

Attempt perception for every family represented by the repository's dataset
provenance. Resolve dataset labels through a documented model-source mapping.
Do not use a hard-coded non-bass `unsupported` branch or an empirical support
allowlist to suppress execution or discard actual source measurements.

Keep all frozen candidate manifests, weights, hashes and historical measured
support decisions unchanged. Adapter capability metadata may add
`attempted_families` and `validated_families`: the former describes the executable
mapping, the latter describes existing empirical evidence. Neither configuration
nor separated energy establishes reliable instrument identification.

Ambiguous labels, multiple instances sharing one model source, and dataset families
without a separable output remain `unknown`/`uncertain` with an explicit reason.
Do not label a broad residual source as a specific instrument without evidence.
Inference may still execute. Unvalidated families are not automatically unsupported
or Normal. Confidence probabilities and public numerical deviations stay null
while confidence abstains. Existing calibrated recommendation gates remain intact.

The committed MoisesDB handoff manifest contains bass, drums, guitar, keys, vocals.
Its existence is dataset provenance, not proof all those sources were supervised
in the frozen Nano4 adaptation. Exact bass/drums/guitar/vocals source estimates may
be numerically usable under the existing activity floor and matched-reference
rules, with `family_attribution_unvalidated` retaining uncertain presentation for
unvalidated families. `validity` describes numerical measurement usability, not
verified physical instrument identity. `keys -> piano` is only a partial proxy:
attempt it, but return invalid/null whole-keys levels with
`partial_source_representation`. No claim of an exhaustive raw-corpus inventory.

ML invalidates all rows sharing one model source (including aliases), so Runtime
does not invent backend-specific independence rules. Cache v2 must pin the adapter
attempt-policy identity without changing or falsifying archived model taxonomy.
Song setup may retain historical `supported_families`; `unsupported_families` must
not be its complement for attempt-capable analyzers. Missing empirical support is
uncertain. Explicit measurement unsupported may remain for other genuine backends.

Reference caches must retain the actual per-source results needed for comparison.
Older bass-only caches must not acquire invented values for additional sources;
re-prepare through the existing reference lifecycle or explicitly report missing
comparison coverage. Preserve amplitude, timeline, model/profile and target binding.

Explicit cache migration reuses `POST /v1/songs/{song_id}/reference` with additive
`StartReferenceRequest {reference_id: old_reference_id}`, mutually exclusive with
the existing `{asset_id}`. Runtime must verify the reference belongs to that song
and resolve the retained audio by its exact content hash, including a check of
the retained bytes before analysis. Missing/incompatible assets fail explicitly.
The response remains ReferenceJob and prepares a new immutable reference ID. UI
may explicitly start a new session for the same song after completion; it must
not silently retarget an old session. No re-upload or new song is required. Normal
microphone switches with a compatible reference retain the same session/reference.

## Optional non-numeric human suggestion

`InstrumentPerception.adjustment_hint` is optional and nullable. A non-null value is
a closed object containing `direction` (`increase_level` or `reduce_level`),
`status: experimental`, `basis: relative_balance`, `evidence_frame_id`, nonempty
`reason_codes`, and `automatic_execution: false`. It has no dB amount or probability.

Runtime alone derives this hint from current source-level evidence and the existing
relative-balance computation: at least three distinct independently attributable,
active, observable, valid sources; median common-mode subtraction; existing anomaly
threshold. Multiple aliases of one model source never count as independent anchors.
The majority-unchanged assumption remains explicit. No new measurement formula.

Hints may accompany uncertain/uncalibrated presentation when the raw comparative
direction is available. Invalid attribution, missing reference alignment, ambiguous
source identity, insufficient anchors, clipping, dropout, stale/disconnected capture,
incompatible capture or non-comparable audio prohibit hints. Direction must never be
guessed from confidence alone. Source switching, pause, stop and restart clear hints.
Capture compatibility remains mandatory; unverified native capture and stale CPU
results do not become advice through this amendment. Uncalibrated estimation is
the only gate this optional non-numeric hint bypasses, not audio-quality gates.

Hints are advisory listening trials, not calibrated PA recommendations, incidents,
recovery or verification success. Existing `action_abstained`,
`numerical_advice_allowed`, Recommendation and ConfidenceState meanings do not change.
UI renders the authoritative hint as "May try lowering/raising this instrument,
then listen again — experimental, uncalibrated" and never calculates its direction.
Absent/null means no directional advice. Fake examples remain explicitly simulated.

## Ownership and acceptance

Lead owns this amendment, additive wire schema and shared validation. Existing ML
owner audits dataset/model mappings, exposes per-source evidence, handles old caches
and tests actual model source output without new training. Existing Runtime owner
removes empirical allowlist gating, implements current-frame hint derivation and
tests source/quality/lifecycle gates. Existing UI owner finishes the session-deletion
checkpoint first, then renders dataset-family uncertainty and authoritative hints.

Acceptance: dataset-backed families reach inference; unmappable/ambiguous results
remain honest; all known source outputs are tested; historical empirical records
are unmodified; hint directions invert with actual relative-level changes; global
gain alone yields no direction; stale/dropout/unaligned/insufficient evidence yields
no hint; UI performs no inference and displays no invented numerical confidence.
