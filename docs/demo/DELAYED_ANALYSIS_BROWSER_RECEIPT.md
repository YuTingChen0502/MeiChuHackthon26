# Delayed-analysis browser receipt — 2026-09-20

Status: **PASS — read-only UI receipt**

The in-app browser opened the Runtime-provided `session-1` at the temporary local
probe endpoint while the integrated code was running at
`be58f3e196d6e333d6fc0d57acf3716878239b07`. No Runtime action, microphone
selection, pause, resume, restart, or session mutation was performed from the UI.

## Fresh authoritative state observed

- Candidate/experimental identity and the warning that physical performance was
  not validated remained visible.
- The Realtek microphone source was authoritative and active after Runtime reported
  that its attempted source change had rolled back.
- The UI rendered observation age **7.6 s**, publication delay **5.6 s**, model
  processing time **5.4 s**, and local receipt age **0.1 s** as separate values.
- Reference context rendered as **Assumed synchronized-start interval 5.0–9.0 s**.
  The adjacent copy explicitly said this was not recognized song position and did
  not solve late entry, drift, seeking, loops, or section jumps.
- Bass rendered `Detected · uncalibrated`; guitar, drums, vocals, and keys rendered
  uncertain. Every family withheld numerical advice. No confidence percentage or
  positive adjustment direction was shown.

Runtime then stopped the probe. Without a browser action, the page transitioned to
`Session ended`, disabled microphone use, and changed the reference state to
`Reference comparison unavailable`. This confirmed that the visible workflow and
evidence cleared with the authoritative lifecycle state.

## Scope

This receipt establishes browser rendering and Runtime transport behavior for the
observed integrated candidate session. It does not establish model accuracy,
calibrated confidence, a successful corrective hint, acoustic operating-envelope
validation, Linux/PN54 execution, or second-microphone coverage. Those claims require
their separate Runtime/physical evidence records.
