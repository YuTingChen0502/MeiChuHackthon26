"""Atomic immutable baseline records created only by an explicit human command."""

from __future__ import annotations

import copy
import json
from threading import RLock

from core.contracts.validation import PUBLIC, validate_record


class BaselineStore:
    """Stores canonical JSON bytes so callers can never mutate accepted records."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, int], bytes] = {}
        self._lock = RLock()

    def save(self, profile: dict) -> None:
        validate_record(profile, PUBLIC, "BaselineProfile")
        key = (profile["baseline_id"], profile["version"])
        encoded = json.dumps(profile, sort_keys=True, separators=(",", ":")).encode("utf-8")
        with self._lock:
            existing = self._records.get(key)
            if existing is not None and existing != encoded:
                raise ValueError("immutable baseline identity already exists")
            self._records[key] = encoded

    def get(self, baseline_id: str, version: int) -> dict:
        with self._lock:
            encoded = self._records[(baseline_id, version)]
        return json.loads(encoded.decode("utf-8"))

    def count(self) -> int:
        with self._lock:
            return len(self._records)


def build_baseline_profile(
    *,
    baseline_id: str,
    version: int,
    song: dict,
    instrument_config: dict,
    reference: dict,
    accepted_by: str,
    accepted_at: str,
    execution: dict,
    taxonomy_id: str,
    capture: dict,
    source_audio_hashes: list[str],
    frames: list[dict],
    reference_difference_accepted: bool,
    acceptance_note: str | None,
) -> dict:
    if not frames:
        raise ValueError("baseline interval has no frames")
    instrument_ids = [item["instrument_id"] for item in instrument_config["instruments"]]
    duration_by_instrument = {instrument_id: 0.0 for instrument_id in instrument_ids}
    windows_by_instrument = {instrument_id: 0 for instrument_id in instrument_ids}
    for frame in frames:
        duration = (frame["sample_end"] - frame["sample_start"]) / frame["sample_rate_hz"]
        if frame["quality"]["stale"] or frame["quality"]["dropout"]:
            raise ValueError("baseline interval contains stale or disconnected audio")
        if frame["quality"]["comparability"] != "comparable":
            raise ValueError("baseline interval is not comparable")
        if not frame["quality"]["capture_compatible"] or frame["quality"]["clipped_fraction"] > 0:
            raise ValueError("baseline interval has incompatible or clipped capture")
        for state in frame["instruments"]:
            if state["instrument_id"] not in duration_by_instrument:
                continue
            if state["activity"] == "active" and not state["confidence"]["abstained"]:
                duration_by_instrument[state["instrument_id"]] += duration
                windows_by_instrument[state["instrument_id"]] += 1
            if not reference_difference_accepted and state["status"] != "normal":
                raise ValueError("reference difference requires explicit human acceptance")
    if any(count == 0 for count in windows_by_instrument.values()):
        raise ValueError("baseline interval lacks active observable source coverage")
    coverage = [
        {
            "instrument_id": instrument_id,
            "valid_active_seconds": duration_by_instrument[instrument_id],
            "qualified_nonoverlap_windows": windows_by_instrument[instrument_id],
            "status": "adequate",
        }
        for instrument_id in duration_by_instrument
    ]
    profile = {
        "record_type": "BaselineProfile",
        "schema_version": "1.0",
        "baseline_id": baseline_id,
        "version": version,
        "song_id": song["song_id"],
        "reference_id": reference["reference_id"],
        "accepted_by": accepted_by,
        "accepted_at": accepted_at,
        "model_bundle_id": execution["model_bundle_id"],
        "frontend_id": execution["frontend_id"],
        "execution_profile_id": execution["execution_profile_id"],
        "taxonomy_id": taxonomy_id,
        "instrument_config_version": song["instrument_config_version"],
        "capture": copy.deepcopy(capture),
        "source_audio_hashes": sorted(set(source_audio_hashes)),
        "coverage": coverage,
        "normal_envelopes": [
            {
                "instrument_id": instrument_id,
                "center_db": 0.0,
                "lower_db": -1.5,
                "upper_db": 1.5,
            }
            for instrument_id in duration_by_instrument
        ],
        "reference_difference_accepted": reference_difference_accepted,
        "acceptance_note": acceptance_note,
        "validity": "valid",
        "immutable": True,
        "limitations": ["Simulated fake-analyzer checkpoint baseline; example only."],
        "comparison_regime": reference["comparison_regime"],
        "model_specific_context_asset": f"fake-simulated-baseline-context:{baseline_id}:v{version}",
    }
    validate_record(profile, PUBLIC, "BaselineProfile")
    return profile
