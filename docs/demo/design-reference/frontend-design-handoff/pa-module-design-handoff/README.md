# AI PA Module: design handoff

Design files for the PA Module web app (Physical AI hackathon). Build the frontend from these; do not redesign.

## Read in this order

1. `DESIGN-SYSTEM.md`: voice, visual rules, the three screens and their states, build notes.
2. `tokens.css` (and `tokens.json`): colors, type, spacing, radius, glow. Use the CSS variables; do not copy hex values into components.
3. `screens/*.html`: the six screen mockups. Open them in a browser and click through. They are static references (inline styles, 1440 x 900), not production code: rebuild them as React components.

## Screens and flow

| File | Screen | Goes to |
|---|---|---|
| `screens/song-setup.html` | Song Setup | Rehearsal (Continue to rehearsal) |
| `screens/rehearsal.html` | Rehearsal | Live normal (Accept as baseline) |
| `screens/live-normal.html` | Live, normal: quiet, no advice | Live anomaly (the "Prototype: simulate drift" link exists only in the mockup) |
| `screens/live-anomaly.html` | Live, anomaly: `+3.1 dB` hero, recommendation, `Recheck` | Live recovered |
| `screens/live-recovered.html` | Live, recovered | Live normal |
| `screens/live-abstain.html` | Live, abstain: `Not enough evidence. No advice.` | (no link) |

## Suggested components

`AppHeader` with `StepNav`, `Panel` (default / active), `Button` (primary / secondary), `Label`, `InstrumentRow`, `ConfidenceChip`, `StatusHero` (normal, anomaly, recovered, abstain), `WaveArt`, `Sparkle`.

## Rules that matter

- The Live screen is quiet in the normal state. Only anomalies produce a recommendation.
- Signed relative dB only, always with a unit (`+3.1 dB`). Never show absolute levels.
- `signal-alert` only for drift, `signal-ok` only for recovered or accepted.
- No control in the app changes the audio. The PA moves the fader.
- Announce state changes with text (`aria-live="polite"`), not color alone.

## Sample data and open items

- `+3.1 dB` and `Reduce guitar about 3 dB` come from the product definition. Rehearsal values and the `High` / `Medium` confidence chips in the mockups are illustrative.
- `surface-panel`, `signal-alert` and `signal-ok` were added for the app; the pitch deck does not have them.
- The analyzer output fields and the session wire format are not frozen yet. Use placeholders and align field names with the Session wire contract when it is ready.
- Stack from the product definition: React + Vite, FastAPI, WebSocket; the PN54 captures the microphone natively.
- The mockups were not rendered and checked in a browser before packaging.
