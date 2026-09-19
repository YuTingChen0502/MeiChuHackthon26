"""Denominator-explicit diagnostic metrics; these never imply calibrated actions."""
from __future__ import annotations

import math


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def summarize(rows: list[dict], *, alert_db: float, missing_penalty_db: float) -> dict:
    if not math.isfinite(alert_db) or alert_db <= 0:
        raise ValueError("alert_db must be finite and positive")
    if not math.isfinite(missing_penalty_db) or missing_penalty_db <= 0:
        raise ValueError("missing_penalty_db must be finite and positive")
    keys = [(r["pair_id"], r["instrument_id"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate pair/instrument metric row")
    for row in rows:
        for name in ("true_raw_db", "true_balance_db", "predicted_raw_db", "predicted_balance_db"):
            value = row[name]
            if value is not None and not math.isfinite(value):
                raise ValueError("Nonfinite metric input")
    raw_eligible = [r for r in rows if r["true_raw_db"] is not None]
    eligible = [r for r in rows if r["true_balance_db"] is not None]
    raw_covered = [r for r in raw_eligible if r["predicted_raw_db"] is not None]
    covered = [r for r in eligible if r["predicted_balance_db"] is not None]
    raw_errors = [abs(r["predicted_raw_db"] - r["true_raw_db"]) for r in raw_covered]
    errors = [abs(r["predicted_balance_db"] - r["true_balance_db"]) for r in covered]
    directional = [r for r in covered if abs(r["true_balance_db"]) >= alert_db]
    sign_correct = sum(r["predicted_balance_db"] * r["true_balance_db"] > 0 for r in directional)
    tp = fp = fn = wrong_sign = 0
    attribution_rows = [r for r in rows if r.get("attribution_evaluable", True)]
    for r in attribution_rows:
        truth = r["true_balance_db"] is not None and abs(r["true_balance_db"]) >= alert_db
        prediction = r["predicted_balance_db"] is not None and abs(r["predicted_balance_db"]) >= alert_db
        correct = truth and prediction and r["predicted_balance_db"] * r["true_balance_db"] > 0
        tp += int(correct)
        fp += int(prediction and not correct)
        fn += int(truth and not correct)  # includes abstentions AND wrong signs
        wrong_sign += int(truth and prediction and not correct)
    frames = {r["pair_id"] for r in rows}
    eligible_frames = {r["pair_id"] for r in eligible}
    covered_frames = {r["pair_id"] for r in covered}
    false_ineligible = sum(
        r["true_balance_db"] is None and r["predicted_balance_db"] is not None for r in rows
    )
    return {
        "all_frames": len(frames), "eligible_frames": len(eligible_frames),
        "frames_with_any_covered_eligible_source": len(covered_frames),
        "all_frame_coverage": _ratio(len(covered_frames), len(frames)),
        "eligible_frame_coverage": _ratio(len(covered_frames), len(eligible_frames)),
        "all_measurements": len(rows), "raw_eligible_measurements": len(raw_eligible),
        "raw_covered_measurements": len(raw_covered),
        "raw_coverage": _ratio(len(raw_covered), len(raw_eligible)),
        "balance_eligible_measurements": len(eligible), "balance_covered_measurements": len(covered),
        "balance_coverage": _ratio(len(covered), len(eligible)),
        "balance_abstentions": len(eligible) - len(covered),
        "ineligible_numeric_balance_outputs": false_ineligible,
        "raw_mae_db": _ratio(sum(raw_errors), len(raw_errors)),
        "balance_mae_db": _ratio(sum(errors), len(errors)),
        "penalized_raw_mae_db": _ratio(
            sum(raw_errors) + (len(raw_eligible) - len(raw_covered)) * missing_penalty_db,
            len(raw_eligible)),
        "penalized_balance_mae_db": _ratio(
            sum(errors) + (len(eligible) - len(covered)) * missing_penalty_db, len(eligible)),
        "missing_prediction_penalty_db": missing_penalty_db,
        "directional_covered_count": len(directional), "sign_correct_count": sign_correct,
        "sign_accuracy": _ratio(sign_correct, len(directional)),
        "attribution_evaluable_measurements": len(attribution_rows),
        "ambiguous_attribution_measurements": len(rows) - len(attribution_rows),
        "attributed_alert_tp": tp, "attributed_alert_fp": fp, "attributed_alert_fn": fn,
        "wrong_sign_alerts": wrong_sign,
        "attributed_alert_precision": _ratio(tp, tp + fp),
        "attributed_alert_recall_including_abstentions": _ratio(tp, tp + fn),
        "semantics": (
            "Paired-window diagnostics, not independent event recall or action confidence. "
            "Coverage counts frames with any eligible numeric balance; per-source counts are also reported. "
            "Ambiguous attribution is excluded from alert precision/recall and counted separately. Ineligible numeric outputs are retained, not discarded. Missing-output errors are explicit penalties."
        ),
    }
