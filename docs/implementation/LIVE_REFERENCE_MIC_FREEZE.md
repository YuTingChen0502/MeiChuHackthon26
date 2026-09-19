# Live reference and microphone switch freeze

Lead-approved user product correction, 2026-09-20.
Inspected clean main/origin/main: `95fa5fed576d6e45f608f413bc84167161d34f13`.
Status: shared contract frozen; Runtime/UI implementation and physical acceptance pending.

## Authority and migration

This explicit user decision supersedes rehearsal/baseline requirements in INFO,
AGENTS, the technical design and older shared-interface prose **for the new product
path only**. Measurement, calibration, abstention, no automatic mixing, and ML
competition lineage are unchanged. No fabricated baseline and no bulk deletion.

New UI always requests `workflow_policy: live_reference_v1` when creating a session.
The application enters session_mode=live after reference readiness; workflow state
is LIVE_MONITORING, or SUSPENDED if acquisition is unavailable. Active baseline and
song.baseline_id are null. The immutable selected ReferenceProfile is the target for
live, adjustment and verification. AnalyzerContext uses purpose live/verification,
target_kind=reference, baseline=null and the reference context asset/regime. Entering
Live authorizes listening, **not** numerical advice or a claim of Normal.

The nine original public records and AnalyzerEvidence quantities stay unchanged.
AnalyzerContext's old live-implies-baseline restriction is removed; the session
policy chooses the target. Optional wire additions are a coordinated same-release
extension: old strict clients must not consume new-policy snapshots. No claim that
old validators accept the new extension. `/v1` and schema_version=1.0 remain for
existing records; explicit policy is the semantic discriminator.

Absent policy / `legacy_baseline_v1` preserves existing stored-session and internal
regression semantics. No silent reinterpretation of history. The new UI never
creates legacy sessions or exposes accept_baseline/start_live/guided controls.
Reopening a legacy song offers a new live-reference session reusing the existing
compatible reference/configuration without upload or analysis. Keep legacy audit
records; legacy sessions are not resumed in the new product console. New-policy
handlers reject accept_baseline/start_live and guided-probe commands with 409.
Ordinary adjustment/complete/recheck remain; null-adjustment recheck requests fresh
reference evidence in the new policy. Pause/resume/stop retain explicit semantics.

## Discovery and setup

`GET /v1/audio-devices` keeps legacy raw `devices` for diagnostics/old consumers and
adds `microphones` (LogicalMicrophone[]) and `default_microphone_id` (string|null).
New UI reads only microphones. Each entry: microphone_id, name, is_default
(boolean|null), selection_kind (`system_default`|`logical_group`|`endpoint`),
grouping (`system_route`|`verified_identity`|`name_heuristic`|`none`). All are required.
IDs are opaque resolution handles, not evidence of physical identity. Raw endpoints
retain native device IDs/name/API internally; normal labels never contain hashes.

Use a `system-default` route plus logical physical choices, not one item per host
API. Exclude known loopback/output-only sources. Conservative normalized-name
grouping across APIs may retain all candidates; it must be marked name_heuristic
and must not merge distinct same-host endpoints merely because names match.
Use actual host/device identity when available. Ambiguous physical alternatives
remain distinguishable by a friendly suffix; do not invent hardware serial IDs.
Resolve fresh on every open, never reuse stale PortAudio indices. Deterministic
priority: Windows WASAPI then DirectSound then MME; Linux system default/PipeWire/
PulseAudio routes when actually available, then ALSA/JACK available candidates.
Actual format negotiation AND successful open govern viability; enumerate/inspect
host capabilities rather than assume a provider exists. Keep candidate failures and
the chosen native endpoint in diagnostics. Fallback is within the chosen logical
group only; never silently choose a different physical group.

CreateSessionRequest with new policy may omit source and capture_fingerprint.
Omitted source means system-default microphone. Supplied microphone source ID is a
logical microphone_id; uploaded_file still uses an asset ID and the common pipeline.
Runtime owns actual geometry/profile/fingerprint; client metadata is never proof.
No available mic creates the song/reference session in unavailable/SUSPENDED state,
not a lost setup. Snapshot.source retains actual endpoint binding when resolved;
before resolution use the requested logical handle as an unavailable placeholder,
never attach evidence to it. Model frontend owns the analysis sample rate.

## Atomic source switch

POST `/v1/sessions/{id}/actions`: existing SessionCommand envelope, action
`switch_microphone`, payload `{microphone_id, expected_source_generation}`.
All existing reference/baseline/event/state-version/idempotency checks still apply.
Allowed while monitoring, adjusting, verifying, paused or unavailable; stopped is
terminal. A pending switch is serialized; a different concurrent switch gets 409.
Duplicate keys replay the original response before stale-version checks.

After validation, return the normal 200 applied CommandResponse acknowledging an
accepted operation, **not claiming the device is active**. capture.operation_id is
the command idempotency key; switch_result=pending. Publish switching snapshot and
advance state_version before asynchronous bounded device work. UI observes terminal
snapshots through the existing event/reconnect mechanism. No new event envelope.

1. Fence current acquisition/inference generation immediately; clear latest_frame,
   recommendations, perception and verification pointers. Stop worker, join without
   holding the publication lock, close stream; drain planner/queues/bounded history.
2. Reset persistence/noise/session acoustic history. Archive any unresolved incident
   and adjustment as interrupted/inconclusive with source_changed audit reason;
   clear active incident/adjustment, never label it recovered. New source must build
   its own incident evidence. Same song, reference and configuration remain intact.
3. Resolve/negotiate/open selected logical input. Allocate NEW source_generation,
   clock_id and analysis_run_id for every opening attempt, including rollback.
   Sample origin starts new. Revalidate capture/profile; do not carry approval from
   old hardware. Keep the reference model context; no re-analysis for a mic change.
4. Publish starting/new source binding before any new-generation frame. Reject every
   callback/inference completion whose generation/run/clock/endpoint is not current.
5. First fresh current-generation Runtime frame permits capture.state=active and
   switch_result=applied; analyzer abstention is still allowed. Missing first audio
   within the configured finite startup timeout is failure. Capturing valid PCM
   while inference is pending is listening, not detected/Normal.

On failure close the attempted stream, try the previous actual endpoint once when
feasible, with another NEW generation/run/clock and fresh evidence. Terminal
switch_result=rolled_back names the restored logical input and retains the error
reason; if restoration fails, switch_result=failed, state=unavailable/SUSPENDED.
Keep the song/reference session usable for another switch. Startup retries must be
bounded. A crash/restart during a pending switch recovers suspended, never replays
uncommitted old evidence. Persist command acceptance/operation state atomically.
Pause stays paused across selection: negotiate/open-test/close, publish paused with
selected binding, require explicit resume for ongoing acquisition. Stop cancels
pending work, fences generations and releases all streams; no late restart.

## Capture and perception projection

New-policy SessionSnapshot requires `capture` and `perception` as defined by the
wire schema. capture.state is starting/listening/active/switching/paused/stopped/
unavailable; frame_fresh indicates current authoritative freshness, independent of
recognition. logical microphone/name, actual native endpoint, generation, run,
clock, timestamp capability, operation/result and reason codes are explicit.
requested_microphone_id retains the operation's requested logical ID (null before
any switch); logical_microphone_id/name identify the actual current binding. While
switching, the old source binding may remain as non-current diagnostics only with
frame_fresh=false and no latest frame. Rollback publishes the restored actual binding
without losing the requested ID/error. A selected-but-paused source is identified
as paused, never active.
Clock equals source.clock_id; capture run matches any current frame. File sources
use null logical microphone/native endpoint and retain uploaded-file identity.
Freshness expiry produces an authoritative snapshot; UI may suppress stale display
on connection loss but must never create a positive state. Switching/no current
frame clears old perception even if a delayed WS frame arrives.

Runtime emits one perception entry per configured instrument: instrument_id,
family, state (listening/detected/not_heard/uncertain/unsupported), frame_id|null,
reason_codes. It derives these from current AnalyzerEvidence masks joined to the
downstream calibrated ConfidenceState, not from configuration or animation.
Precedence: explicit family outside actual supported_families -> unsupported;
no fresh current evidence -> listening only when capture is fresh and acquiring,
otherwise uncertain; fresh inactive -> not_heard; fresh active + observable + valid
+ confidence.abstained=false -> detected; otherwise uncertain. Absence of capability
information is uncertainty, not proof of support. A raw valid number with downstream
abstention is never detected. No evidence yet but fresh PCM is listening. Attach
frame_id only to the current frame. Keep Fake/example-only labeling visible.
Uncalibrated probabilities stay null; unsupported numerical values stay null.

## ADC timeline

Sample counts own stream continuity. Anchor missing/zero/nonfinite ADC timestamps
to monotonic callback arrival minus packet duration, then advance by exact sample
counts. Do not fatal on missing ADC alone or fabricate samples. Expose sample_count
timestamp mode; adc_sample_count means valid ADC is also available for diagnostics.
ADC capability appearance/disappearance alone is not an audio gap. Valid ADC drift
checks re-anchor diagnostic comparisons when capability resumes. Real overflow,
invalid packets, dropout, queue loss or discontinuity still fence windows and reset
persistence. Never stretch across unknown audio loss.

## Ownership, dispatch and acceptance

Runtime existing owner `Continue CP2 native audio runtime`: only core/audio,
core/profiles, core/runtime, roles/pa, apps/api, tests/runtime, tests/integration.
Implement this lifecycle and policy, persist/reconnect/restart, exact evidence
projection, bounded native tests and physical evidence. Preserve Fake regression
and legacy tests. Report new-policy smoke separately from legacy CP1 smoke.

Existing CP2 UI owner: only apps/ui, demo_player, docs/demo, tests/ui. Sync frozen
main first. Replace public rehearsal path with setup -> Live reference; keep the
microphone selector available throughout the session. Use logical IDs and
switch_microphone; never recreate/upload/re-analyze on source changes. Render
pending/rollback/error states and Runtime perception, keep simulation labels and
all confidence gates. Ignore legacy-baseline workflow checkpoints for this path.
Test actual API and reconnect; no independent contract inventions. Work concurrently
against shared fixtures; actual integration waits for Runtime endpoint checkpoint.

Lead owns contracts, tests and acceptance integration. No ML research changes.
Merge Runtime then UI after review. Any adapter rejecting live/reference is a narrow
compatibility request to the existing ML owner, never a model-quality task.

| Acceptance | Automated | Windows native | Linux/PN54 native |
|---|---|---|---|
| Logical inventory/no ordinary aliases; real open | resolver + API/UI | required | required |
| Fresh continuous frames; zero ADC fallback | injected zero/missing ADC | >=10 min actual capture | >=10 min actual capture |
| Same song/reference; multiple switches; new identities | delayed-callback race + WS | >=3 switches | >=3 switches |
| No stale evidence/recovery; failed switch rollback | deterministic failure + persistence | unavailable selection/recovery | unavailable selection/recovery |
| Stop/reopen releases device; pause/stop during switch | lifecycle races | actual reopen | actual reopen |
| Perception masks/Fake labels/legacy migration | contracts + API/UI smoke | inspect actual UI | inspect actual UI |

Record exact Git SHA, OS, PortAudio/host API/device/capture geometry, duration,
frames, queue/history bounds, gaps, source identities and failure/recovery log.
Two physical microphones are required to claim physical device-to-device switching;
same-device reopen is separate evidence. Zero-ADC injection tests are not physical
zero-ADC observations. No accessible Linux/PN54 or second mic means that acceptance
cell remains BLOCKED_EXTERNAL_HARDWARE. Never substitute mocks for physical PASS.
