"""Local deployment configuration. Missing production models never select Fake."""
import json
import os
from pathlib import Path

from core.runtime.calibration import ReviewedEvidencePolicy
from core.runtime.fake_analyzer import ContinuousFakeInstrumentAnalyzer


def runtime_options(*, environment=None, registry=None, loader=None):
    env = os.environ if environment is None else environment
    mode = env.get("PA_ANALYZER_MODE", "bundle")
    if mode == "fake":
        return {"analyzer_factory": ContinuousFakeInstrumentAnalyzer}
    if mode != "bundle":
        raise ValueError("PA_ANALYZER_MODE must be bundle or fake")
    bundle_path = env.get("PA_MODEL_BUNDLE")
    settings_path = env.get("PA_HOST_REVIEW")
    # Host-owned review is never read from a path selected by bundle metadata.
    settings = json.loads(Path(settings_path).read_text(encoding="utf-8")) if settings_path else None
    allowed = dict(registry or {})
    def factory():
        if not bundle_path or not Path(bundle_path).is_dir():
            raise RuntimeError("model_bundle_missing")
        selected_loader = loader
        if selected_loader is None:
            from analyzers.bundles import load_bundle
            selected_loader = load_bundle
        return selected_loader(Path(bundle_path), registry=allowed,
            expected_model=settings["model"] if settings else None,
            acceptance=settings["acceptance"] if settings else None)
    return {"analyzer_factory": factory,
            "evidence_policy": ReviewedEvidencePolicy(settings) if settings else None}
