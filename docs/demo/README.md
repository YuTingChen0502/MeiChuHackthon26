# PA physical demo package

This directory owns the operator-facing demo procedure. It does not certify model
accuracy, MI300 lineage, PN54 deployment, capture provenance, or a completed physical
trial. Record those facts only after the responsible lane supplies measured evidence.

## Surfaces

- `/apps/ui/` is the operator console. With Runtime available it renders only
  authoritative health, device discovery, snapshots, events, confidence, and
  verification. A frame marked `example_only` is visibly simulation evidence.
- `/demo_player/` is an independent playback environment. It has no imports, network
  requests, or metadata path to Runtime. Only audible output may reach the microphone.
- Fixture fallback is illustrative and non-mutating. Offline uploaded-file replay is
  a product input, but it is not a physical microphone demonstration.

## Documents

- `PHYSICAL_DEMO_RUNBOOK.md`: reproducible operator sequence, hookup, preflight,
  recovery, and teardown.
- `ASSET_INTAKE.md`: rights and provenance intake before any clip is admitted to the
  player, recording, or public materials.
- `EVIDENCE_PACKET.md`: trial log, video shot list, presentation evidence skeleton,
  and placeholders that must remain unclaimed until measured.

## Design references

The supplied source mockups are preserved under `design-reference/` for traceability.
They establish the dark navy/purple field, teal wave motif, high-distance typography,
status color hierarchy, responsive cards, and focused/dimmed rehearsal language. They
are references, not application code or data contracts. The operator console keeps
the existing dependency-free shell and `RuntimeAdapter`; wording, states, controls,
and payloads remain governed by the repository contracts and authoritative Runtime.

## Local launch

Install the Lead-pinned Runtime environment, then launch the loopback listener:

```text
python -m pip install -r requirements-runtime.txt
python -m uvicorn apps.api.transport:app --host 127.0.0.1 --port 8000 --workers 1 --loop asyncio --http h11 --ws websockets-sansio
```

Open `http://127.0.0.1:8000/apps/ui/`. The listener deliberately does not serve the
independent player. Serve `demo_player/` separately on the playback device or from a
separate static listener. Never add a player-to-Runtime API connection.

For fixture-only development, a repository-root static server may expose both the UI
and frozen shared example. The notice must continue to say that fixture values are
not real-ML or physical-demo evidence.

## Current gate status

Native discovery and bounded local Runtime code are integrated. Local capture reports
do not establish physical provenance or PN54 deployment. Actionable RealAnalyzer
output remains gated on accepted MI300-adapted lineage, empirical calibration,
operating envelope, compatible profiles, PN54 execution, and the recorded acoustic
closed loop. The console must therefore display abstention, unavailable, suspended,
or simulation states whenever Runtime does.

Do not copy official workshop PDFs, credentials, private URLs, or secrets into demo
or presentation artifacts. Those authority files remain local and outside release
exports.
