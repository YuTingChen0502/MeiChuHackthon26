# Harmonix — Live Sound Reference

A local, human-operated PA assistant for a known song and instrument configuration.
The current product policy compares one mixed-room microphone (or an uploaded
recording) against an uploaded ideal reference during Live. The operator can change
microphones without re-uploading or re-analyzing the reference. Perception and PA
action confidence are separate: a source can be detected while numerical advice is
withheld. Humans adjust the sound; Harmonix never controls a mixer.

## Current milestone

**Windows real microphone execution verified; full physical acceptance remains open.**
The [actual acceptance record](docs/implementation/REALTIME_MIC_ACCEPTANCE.md)
contains ten minutes of candidate capture, switching, restart and browser evidence.
The tested CPU does not meet freshness latency; Linux/PN54 and a second physical
microphone are not validated. The user-approved
[Live-reference contract](docs/implementation/LIVE_REFERENCE_MIC_FREEZE.md) supersedes
the historical rehearsal/baseline product flow. Existing baseline sessions remain
explicitly legacy; the new console does not expose rehearsal or acceptance controls.
A passing software test is not musical feasibility, calibrated confidence, MI300
adaptation, PN54 performance or acoustic accuracy. Earlier milestone records describe
their exact historical commits, not completion of this new acceptance gate.

Nano4 and MI300 execute independent experiments at exact repository commits. The
first usable artifact/evidence may unblock engineering integration. The final
competition runtime artifact must descend from meaningful official MI300 adaptation.
Critical inference stays local on PN54; no LLM or cloud roundtrip gates perception.

## Architecture

```mermaid
flowchart LR
    F[Uploaded PCM WAV] --> P[Shared PCM / windows / quality]
    M[One native microphone] --> P
    P --> A[InstrumentAnalyzer]
    B[Validated local model bundle] --> A
    A --> E[Frozen AnalyzerEvidence]
    E --> C[Core deviation / calibrated confidence / abstention]
    R[Uploaded ideal reference] --> C
    E --> PS[Source perception]
    PS --> API
    C --> PA[PA state / recommendation / verification]
    PA --> API[Local HTTP / WebSocket]
    API --> UI[Operator console]
    UI --> H[Explicit human commands]
    H --> PA
    H --> ADJ[Human physical adjustment]
    ADJ --> M
```

Input adapters acquire and frame audio. AnalyzerEvidence contains measurements and
raw uncertainty, not canonical state or recommendations. Core owns common-mode
removal, centered balance, quality and calibrated confidence. The PA role owns the
human workflow. UI displays authoritative state and never estimates audio. The demo
player is isolated: its only input to the system is sound through the room.

## Install and validate

Use Python 3.12 for the tested local Runtime path and a modern Node.js with built-in
test runner, fetch and WebSocket for UI/integration tests (Node 25 was tested).
Use a virtual environment; the commands below do not install GPU drivers.

```text
python -m venv .venv
```

Activate `.venv/Scripts/Activate.ps1` on Windows PowerShell or
`source .venv/bin/activate` on POSIX, then:

```text
python -m pip install -r requirements-runtime.txt
python scripts/validate.py --runtime-only
```

The full ML tooling suite additionally requires NumPy and PyTorch in the chosen
environment. Existing CPU mechanics were tested with NumPy 2.4.3 and PyTorch
2.11.0+cpu on Python 3.14.3; that is not an MI300/PN54 compatibility claim. Keep the
official remote framework/driver stack and record its actual versions. Do not apply
local CPU pins to a provided ROCm environment without validation.

```text
python scripts/validate.py
```

The validation runner executes shared, Runtime, integration, UI, selected ML suites,
the unchanged legacy Fake correction-loop smoke, the Live-reference HTTP/WS smoke,
and the source release audit.

## Frozen candidate integration

The Nano4 P1 candidate adapter and Runtime host mode are integrated for engineering
use. It reconstructs the exact offline HTDemucs base plus adapted projections and
emits frozen AnalyzerEvidence. Compatible microphone PCM executes the real
model, including when reference coverage is unavailable; lack of room calibration is not an execution rejection. Product evidence
validation remains bass-only in the matched-digital evidence, and confidence is
uncalibrated. The user-approved [dataset-family amendment](docs/implementation/DATASET_PERCEPTION_HINT_FREEZE.md)
requires attempts for bass, drums, guitar, keys and vocals instead of a bass-only
execution/publication allowlist. Keys has only a partial piano-source proxy; missing
or unreliable attribution stays uncertain. An experimental raise/lower listening
hint may be shown when current comparative evidence supports it, without a dB amount
or calibrated probability. These attempts do not expand historical accuracy claims. Public numerical
actions remain disabled. Prior CPU observation time was 7.929 seconds per four-second
window; this does not meet the one-second offered hop. Slow results remain stale and
uncertain, with bounded old-window dropping rather than an accumulating backlog.
Install the optional tested model packages listed in
[the candidate runbook](models/P1_CANDIDATE_INTEGRATION.md), then run:

```text
python -m apps.api.launch --mode candidate-p1 --storage .pa-runtime --bundle models/candidates/nano4-p1-adapted-mvp-v1
```

The host fixes 44.1 kHz, four-second windows and a one-second hop. Native capture
negotiation remains separate. The narrow demonstration assumes synchronized entry:
each new capture generation starts at relative sample zero and compares against the
same reference span. Restart playback/performing from the reference beginning after
a microphone restart/switch. Missing reference coverage is alignment unavailable.
Tempo drift, section jumps and arbitrary entry are not solved. Production accuracy,
MI300 lineage, held-out calibration and PN54 performance remain separate gates.

## Run locally

Start the local native-audio application with an explicitly simulated analyzer:

```text
python -m apps.api.launch --storage .pa-runtime --mode fake
```

Open `http://127.0.0.1:8000/apps/ui/`. Reference uploads currently accept bounded
PCM16 WAV. Select a microphone from Runtime's actual inventory. The server stores
state, uploaded audio and context cache under the chosen local storage directory;
the recommended `.pa-runtime/` directory is ignored by Git and excluded from release.
Unscripted Fake capture abstains: it does not invent instrument measurements from
microphone audio. Use the scripted Fake end-to-end test to exercise deterministic
recommendations and recovery; fixture UI is labeled and isolated from real commands.

Use **Delete session** beside an entry in **Recent songs** to remove its saved
session history. Confirming also stops that session if it is running. The song,
uploaded reference and model files are retained; canceling leaves the session intact.

See [Runtime deployment and host review](apps/api/RUNTIME_PRE_MODEL_READY.md) for
model selection, cache, approved capture profiles, native probes and PN54 procedure.
The default `--mode bundle` requires a validated local bundle and host registration;
missing or unaccepted production artifacts remain unavailable/abstained. There is
no automatic download or silent fallback to Fake. Inventory is read-only:

```text
python -m apps.api.inventory
```

Run the isolated playback page separately, not through the Runtime data path:

```text
python -m http.server 8001 --bind 127.0.0.1 --directory demo_player
```

Open `http://127.0.0.1:8001/`. Use permitted audio and follow the
[demo runbook](docs/demo/README.md). Playing audio is not proof of perception.

## Measurement and training methodology

Controlled real-multitrack pairs preserve common amplitude scaling. Raw injected
source gains, common-mode gain, centered balance and valid-source masks are distinct.
All augmentations of one parent recording stay in one grouped split; train,
validation, calibration and untouched test groups are separate. Inference sees only
the legitimate mixed reference, mixed observation and configured instruments.
No stems, injected gains, filenames, player truth or oracle labels enter inference.

Compare separation and direct candidates on identical pairs, then report attribution,
direction, dB error, coverage, abstention, noise/SNR and latency with denominators.
The [ML readiness runbook](benchmarks/CP2_READINESS.md) provides commands. Model intake,
export/parity and calibration handoff follow the
[internal seam](docs/implementation/MODEL_HANDOFF_INTERNAL_V1.md) and the implemented
[bundle layout and commands](models/CP2_ARTIFACT_BUNDLE_V1.md). Real numerical
advice requires held-out evidence, a supported envelope, separate calibration and
host-reviewed matching identities. A sigmoid value is not calibrated confidence.

## Compute and deployment

| Environment | Responsibility |
|---|---|
| Local | Source edits, tests, integration, portable correctness and release preparation |
| Nano4 | Fast empirical probes/sweeps and engineering candidate evidence |
| Official MI300 | Environment validation and meaningful task-specific adaptation with exact artifact lineage |
| PN54 | Actual local provider inventory, microphone, export parity, sustained performance and acoustic demo |

Remote machines execute pushed immutable Git SHAs and hashed configs. They do not
author divergent source changes. A provider installed on one machine is not proof
of actual operator placement, latency or availability on PN54. A matched, measured
CPU profile can be a fallback; remote inference is not a critical-path fallback.

## Claims, limits and release

No absolute per-instrument SPL, specific mixer-fault inference, autonomous mixing,
tone/EQ, section-aware remixing or arbitrary unknown-song recognition is claimed.
Silence, stale data, source inactivity and disconnection cannot establish recovery.
The new Live-reference policy never creates or silently substitutes a baseline.
Historical baseline records are retained under legacy policy. Verification requires
fresh, observable post-adjustment audio. Perception labels do not authorize calibrated
confidence percentages or physical-room numerical accuracy claims.

Assets and model weights have separate rights/provenance requirements. See the
[source release policy and audit](docs/release/RELEASE_READINESS.md). The existing
private Git history must not be made public: excluded organizer material contained
access details. A scanned source-only export is the prepared publication route.
No third-party corpus, restricted raw recording or signed dataset URL belongs in it.
Original project code currently has no separately granted permissive license.

Authority: AGENTS.md, current handoff, locked product INFO, frozen contracts,
technical design and current implementation decisions. Historical status notes are
superseded by the current inventory and exact checkpoint evidence.
