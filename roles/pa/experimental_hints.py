"""Current-frame experimental listening directions, separate from PA incidents."""
from collections import Counter
import math

from core.contracts.validation import validate_analyzer_pair
from core.runtime.deviation import measurement_deltas, median_common_mode
from core.runtime.quality import hard_gate_reasons

# These documented candidate/calibration limitations may coexist with a trial
# direction. Unknown reasons fail closed; no quality or ambiguity gate is waived.
SOFT_REASONS = frozenset({"uncalibrated_candidate", "family_attribution_unvalidated",
    "partial_source_representation", "real_room_not_validated", "empirical_calibration_unavailable",
    "uncalibrated_uncertainty", "insufficient_stable_anchors"})


def adjustment_hints(*, context, evidence, frame, anomaly_threshold_db):
    validate_analyzer_pair(context, evidence)
    if hard_gate_reasons(frame["quality"]) or set(frame["quality"]["reason_codes"]) - SOFT_REASONS:return {}
    if context["comparison_regime"] == "unvalidated":return {}
    if context["comparison_regime"] == "matched_excerpt" and not evidence["matched_context_window_id"]:return {}
    if any(frame.get(key) != value for key,value in evidence["observation"].items()
           if key in frame):raise ValueError("hint frame observation mismatch")
    if any(frame[key] != evidence["model"][key] for key in
           ("model_bundle_id", "frontend_id", "execution_profile_id")):
        raise ValueError("hint model identity mismatch")
    if frame["reference_id"] != context["target"]["reference"]["reference_id"]:
        raise ValueError("hint reference identity mismatch")
    states={row["instrument_id"]:row for row in frame["instruments"]}
    families=Counter(row["family"] for row in evidence["measurements"])
    changes=measurement_deltas(evidence);eligible={}
    for row in evidence["measurements"]:
        identity=row["instrument_id"];state=states.get(identity)
        if (row["activity"] != "active" or row["observability"] != "observable" or row["validity"] != "valid"
                or families[row["family"]] != 1 or not state or state["family"] != row["family"]):continue
        if state["confidence"]["calibration_status"] != "uncalibrated" or not state["confidence"]["abstained"]:continue
        if set(row["reason_codes"]) - SOFT_REASONS or set(state["confidence"]["reasons"]) - SOFT_REASONS:continue
        if identity in changes and math.isfinite(changes[identity]):eligible[identity]=changes[identity]
    # ML invalidates all rows mapping to a shared model source, including aliases.
    # Runtime neither guesses a model taxonomy nor duplicates an ambiguous anchor.
    common=median_common_mode(eligible)
    # With fewer than three observable anchors, a global-gain correction cannot
    # be identified. Still provide a clearly experimental direction from the
    # matched reference delta; never turn it into an incident or numeric advice.
    estimated_without_common_mode=common is None
    if not eligible:return {}
    result={}
    for identity,delta in eligible.items():
        balance=delta if estimated_without_common_mode else delta-common
        if abs(balance) < anomaly_threshold_db:continue
        result[identity]=dict(direction="reduce_level" if balance > 0 else "increase_level",
            status="experimental",basis="relative_balance",evidence_frame_id=frame["frame_id"],
            reason_codes=["experimental_uncalibrated_direction",
                "reference_delta_without_common_mode" if estimated_without_common_mode else "majority_active_sources_unchanged"],
            automatic_execution=False)
    return result
