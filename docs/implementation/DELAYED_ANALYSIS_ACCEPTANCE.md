# Delayed candidate analysis and semantic audit follow-up

Status: **PASS — bounded delayed execution, controls and UI; advice gates retained.**

Executable integration: `be58f3e196d6e333d6fc0d57acf3716878239b07`.
HTTP hint test-harness correction: `f4d74a71d648c42f2fe3c2da3a97476a2623b53b`.
Canonical validation completed at `dfa8290890d1ec113b4f2b71d098d95b12cffdd8`;
intervening merges added evidence/documentation only.

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

## Accepted changes and validation

- ML `4bfdd532ee8b8bb9bfacc0880b84b0699065bca2`: genuine compatible v1 cache
  permits six-source execution; comparison stays invalid/null. Exact integer cache
  versions, integrity, target binding, clipping and geometry remain guarded.
- Runtime `ff7df18ea19390544fac6668215510b4898f5e8c`: separate 2 s admission and
  20 s candidate completion budgets, fixed hints up to 10 s, skipped inference vs
  physical loss, immediate gap suppression/in-flight fence, and no diagnostic-only
  timestamp transition churn. Strict profiles remain unchanged.
- UI `ffd82e1575ad727e2e6fa78d703b9bbf8c078dbc`, smoke correction
  `9d740329675e352e25e083dacb74d9d8c124e09c`: server deadlines, non-renewing reconnect,
  distinct observation/processing/receipt times and explicit assumed reference span.
- `python -B scripts/validate.py`: **314 Python tests** (35 shared, 48 Runtime,
  106 integration, 29 training, 58 analyzer, 38 benchmark), **102 UI tests**, all
  three HTTP/WebSocket smokes and release audit/self-tests PASS. Source scan was
  clean with zero findings. Actual-weight regressions are execution evidence only.

Windows [native receipt](../../tests/runtime/reports/candidate-delayed-native-be58f3e.md)
and [scalar trace](../../tests/runtime/reports/candidate-delayed-native-be58f3e.json):
six approximately 20 s segments, **120.361 s total**, 22 completed real backend calls
(including retired/fenced work), 15 worker publications, 12 sampled unique fresh
frames. Processing p50/p95 **5.060/5.573 s**, completion age p50/p95 **5.615/6.190 s**.
Queue maximum 2, 70 obsolete analysis windows dropped, 7 stale/fenced windows, zero
native callback drops. Two physical discontinuities were gated. Pause/resume,
two applied source selections, failed selection rollback, stop and reopen passed.
One Realtek array was tested; API aliases are not distinct physical microphones.

The [actual browser receipt](../demo/DELAYED_ANALYSIS_BROWSER_RECEIPT.md) confirmed
fresh delayed results, the assumed 5–9 s reference interval, uncalibrated/uncertain
states and authoritative stop clearing. Displayed publication delay is not measured
browser-render latency. Native hints remained absent because capture compatibility
was not verified; simulated HTTP tests separately prove bounded hint lifetime.

## Claim boundary

The new profile does not accelerate the model to one-second throughput. Delayed
results are explicitly labelled; the queue remains bounded and discards obsolete
work. Numerical confidence and physical-room accuracy remain unvalidated. Fresh
perception does not guarantee a hint: native capture compatibility, comparison
coverage, clipping/dropout and sufficient independently eligible sources still
gate directions. In particular, unverified native capture withholds advice.

No raw microphone recording is required for the timing receipt. A generated
reference used in native tests is transport material, not musical ground truth.
