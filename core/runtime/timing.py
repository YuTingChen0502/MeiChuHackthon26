"""Host-selected bounded analysis timing profiles."""

from __future__ import annotations

import copy


_PROFILES = {
    "strict_v1": {
        "profile_id": "strict_v1",
        "queue_max_age_s": 2.0,
        "result_max_age_s": 2.0,
        "hint_hold_s": 10.0,
        "receipt_max_age_s": 5.0,
    },
    "candidate_delayed_v1": {
        "profile_id": "candidate_delayed_v1",
        "queue_max_age_s": 2.0,
        "result_max_age_s": 20.0,
        "hint_hold_s": 10.0,
        "receipt_max_age_s": 12.0,
    },
}


def analysis_timing_profile(profile_id: str) -> dict:
    """Return a fresh host policy value; analyzer metadata never selects it."""
    try:
        return copy.deepcopy(_PROFILES[profile_id])
    except KeyError as exc:
        raise ValueError("unknown analysis timing profile") from exc
