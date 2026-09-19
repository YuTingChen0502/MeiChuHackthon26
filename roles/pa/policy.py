"""PA incident persistence and bounded human recommendation policy."""

from __future__ import annotations

import copy

from core.runtime.quality import quality_is_usable


class PersistentAnomalyPolicy:
    def __init__(self, *, required_frames: int = 2) -> None:
        if required_frames < 1:
            raise ValueError("required_frames must be positive")
        self.required_frames = required_frames
        self._key: tuple[str, str] | None = None
        self._frames: list[dict] = []

    def reset(self) -> None:
        self._key = None
        self._frames = []

    def observe(self, frame: dict) -> tuple[dict, list[str]] | None:
        # Unusable evidence is neither Normal nor persistence evidence. In particular,
        # stale frames cannot create an incident or erase pending fresh evidence.
        # A declared capture gap is different: persistence cannot bridge a physical
        # discontinuity, so pending evidence is discarded.
        if frame["quality"]["dropout"]:
            self.reset()
            return None
        if not quality_is_usable(frame["quality"]):
            return None
        candidates = [
            state
            for state in frame["instruments"]
            if state["status"] in ("too_loud", "too_quiet")
            and not state["confidence"]["abstained"]
        ]
        if not candidates:
            self.reset()
            return None
        state = max(candidates, key=lambda item: abs(item["balance_deviation_db"]))
        key = (state["instrument_id"], state["status"])
        if key != self._key:
            self._key = key
            self._frames = []
        self._frames.append(frame)
        if len(self._frames) < self.required_frames:
            return None
        evidence_ids = [item["frame_id"] for item in self._frames[-self.required_frames :]]
        self.reset()
        return copy.deepcopy(state), evidence_ids


def recommendation_for(*, event: dict, state: dict, now_monotonic_s: float) -> dict:
    value = state["balance_deviation_db"]
    if value is None or state["confidence"]["abstained"]:
        action = "wait_for_observable_audio"
        step = None
    else:
        action = "reduce_level" if value > 0 else "increase_level"
        step = -1.0 * (1 if value > 0 else -1) * min(2.0, max(abs(value) - 1.0, 0.0))
    return {
        "record_type": "Recommendation",
        "schema_version": "1.0",
        "recommendation_id": f"recommendation:{event['event_id']}",
        "event_id": event["event_id"],
        "instrument_id": state["instrument_id"],
        "action": action,
        "suggested_step_db": step,
        "human_control_hint": "Adjust the corresponding source conservatively, then recheck.",
        "message_template_id": "pa.relative_level.correction.v1",
        "evidence_frame_ids": list(event["evidence_frame_ids"]),
        "expires_monotonic_s": now_monotonic_s + 30.0,
        "automatic_execution": False,
    }
