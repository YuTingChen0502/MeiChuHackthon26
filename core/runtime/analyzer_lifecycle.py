"""Read-only historical session identity without loading a retired model."""
import copy


class HistoricalAnalyzer:
    def __init__(self, state):
        # Old records lack full capabilities. Only archived identity fields are
        # used during reconstruction; this object can never analyze or resume.
        self._caps = copy.deepcopy(state.get("analyzer_capabilities") or {
            "provider": state["execution"]["provider"],
            "model": {**state["execution"], "taxonomy_id": state["reference"]["taxonomy_id"]},
        })

    def capabilities(self):
        return copy.deepcopy(self._caps)

    def analyze(self, *args, **kwargs):
        raise RuntimeError("runtime_restart_requires_new_session")

    prepare_reference = analyze

    def close(self):
        pass
