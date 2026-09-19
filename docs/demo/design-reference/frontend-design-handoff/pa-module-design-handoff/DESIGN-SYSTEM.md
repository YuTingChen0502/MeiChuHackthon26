# AI PA Module

Which instrument drifted, and by how much. The PA Module listens through one microphone, compares the live sound with a rehearsal baseline, and tells the sound engineer the smallest fix. This system styles its web app and matches the team's pitch deck.

This is a first, small system: colors, type, spacing, radius, one glow, and the screen specs below. It has no coded components yet. Values marked "added for the app" are new; everything else is read from the pitch deck (navy `#010C1D`, soft blue `#A4C2F4`, white, Darker Grotesque and Barlow).

## Content fundamentals

- **Language.** The UI is English. The presenter speaks Chinese, the slides and the app stay English. Chinese text, if any, falls back to Microsoft JhengHei; the two brand fonts have no Chinese glyphs.
- **Voice.** Short, calm, diagnostic. Say what is off and what to do, never how the model works. No exclamation marks, no emoji.
- **Numbers.** Always signed and with the unit: `+3.1 dB`, `-2.4 dB`. The value is relative to the rehearsal baseline, never an absolute level. Never show SPL.
- **Recommendations** are imperative and small: `Reduce guitar about 3 dB`, `Raise vocal about 2 dB`.
- **Silence is a feature.** While the mix matches the baseline, the Live screen shows no recommendation. When evidence is weak the system says so: `Not enough evidence. No advice.`
- **Sample copy.** `Guitar +3.1 dB`, `Reduce guitar about 3 dB`, `Recovered`, `Accept as baseline`, `Recheck`.

## Visual foundations

- **Ground.** `surface-ground` everywhere. Panels use `surface-panel` with a 1px `line-hairline` frame and square corners (`radius-none`). Panels are outlines first, fills second.
- **Focus and active.** The active panel switches its frame to `line-strong` and takes `glow-edge`. Only one panel glows at a time.
- **Ornament.** Thin sparkle stars in the corners of hero panels and thin wave line art, as in the deck. Keep them at 1px stroke in `accent` or `line-hairline`, behind the content, never under text.
- **Color roles.** `ink` for text, `ink-muted` for units and captions, `accent` for key figures and controls. `signal-alert` appears only when the mix has drifted; `signal-ok` only when it recovered or was accepted. Nothing else is colored.
- **Type.** Darker Grotesque bold for figures and titles, Barlow for everything else. `figure-hero` is used once per screen. Load both from Google Fonts.
- **Motion.** Minimal: a 200ms fade for state changes. No looping animation on the Live screen; a moving screen defeats "mostly quiet".
- **Contrast.** Every text pair above is at least 8:1. `line-hairline` is decorative; controls use `line-strong`.

## Iconography

Thin 1.5px line icons, square caps, in `accent` or `ink-muted`. Draw them inline as SVG. Icons never replace a text label on a button. No emoji, no filled icons.

## Screens

Three screens, one flow: Song Setup, Rehearsal, Live. Desktop, 1280px and up, one panel grid per screen. These layouts are design decisions; the flow and states come from the product definition.

### 1. Song Setup
Before the show. Upload the full reference audio and confirm the instruments.
- Left panel: reference upload (drop zone, file name, duration once loaded).
- Right panel: instrument list, one row per instrument with an include toggle.
- Bottom right: primary button `Continue to rehearsal`.
- Uploaded audio and the live microphone go through the same analysis, so the copy says `Reference audio` and never `Track`.

### 2. Rehearsal
Build the baseline in the real room.
- Left: the per-instrument list. Each row shows the instrument, the relative dB value against the reference (`title-md` name, `body-lg` value) and a confidence chip (`radius-md`).
- Right: status and controls. `Analyze`, then the human adjusts the mixer, then `Accept as baseline`.
- States: idle, analyzing, result, baseline accepted (`signal-ok`). After acceptance the baseline is fixed for the show; the UI does not offer a way to edit it.

### 3. Live
Mostly quiet. Four states, and the demo walks through them in order.
1. **Normal.** Calm screen: status line `Matches baseline`, the waveform line art, no recommendation. Nothing in `signal-alert`.
2. **Anomaly.** A single hero panel takes `glow-edge`. `figure-hero` shows the deviation, for example `+3.1 dB`, with the instrument name (`title-md`) above it in `signal-alert`, and the confidence in a caption.
3. **Recommendation.** Below the figure, `body-lg`: `Reduce guitar about 3 dB`. One button: `Recheck`.
4. **Recovered.** The figure returns to the baseline state, `signal-ok` status `Recovered`, then the screen goes quiet again.
- **Abstain.** If confidence is too low or the noise check fails, show `Not enough evidence. No advice.` in `ink-muted`. Never guess.
- The person adjusts the mixer, not the app. There is no control that changes audio.

## Build notes for the web app

- **Stack (from the product definition).** React with Vite, FastAPI, WebSocket. The PN54 captures the microphone natively; the browser only displays results.
- **Tokens.** Use the generated `tokens.css` of this system as the single source of colors, spacing, radius and glow. Do not copy hex values into components. Type styles are available as classes named after the styles (`figure-hero`, `body`, ...).
- **Fonts.** Load Darker Grotesque (700) and Barlow (400, 600) from Google Fonts. The stacks in `tokens.json` already include fallbacks.
- **Accessibility.** Real `<button>`, `<label>` and `<input>` elements. Keep a visible `line-strong` focus ring. The state changes on Live (anomaly, recovered) must also be announced with text, not only color: use an `aria-live="polite"` region.
- **Not decided yet.** The analyzer output fields and the session wire format are still being frozen by the team. Treat the values in these screens (instrument, relative dB, confidence, status) as what the UI needs to show, and align field names with the Session wire contract when it is ready. Tone, section-wise mixing and unknown songs are out of scope.
