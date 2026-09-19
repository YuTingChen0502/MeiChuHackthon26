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
    settings = None
    review_error = None
    try:
        settings = json.loads(Path(settings_path).read_text(encoding="utf-8")) if settings_path else None
    except (OSError, ValueError) as exc:
        review_error = exc
    allowed = registry
    context_path = env.get("PA_MODEL_CONTEXT_CACHE", str(Path(env.get("PA_RUNTIME_STORAGE_DIR", ".pa-runtime")) / "context-cache"))
    def factory():
        if review_error is not None:
            raise RuntimeError("host_review_unavailable") from review_error
        if not bundle_path or not (Path(bundle_path).is_dir() or (loader is not None and Path(bundle_path).is_file())):
            raise RuntimeError("model_bundle_missing")
        selected_loader = loader
        selected_registry = allowed
        acceptance = settings["acceptance"] if settings else None
        if selected_loader is None:
            from analyzers.bundles import BackendRegistry, BundleAcceptance, load_bundle
            from analyzers.reference_contexts import ReferenceContextStore
            selected_loader = load_bundle
            if not isinstance(selected_registry, BackendRegistry):
                host_registry = BackendRegistry(context_store=ReferenceContextStore(context_path))
                for adapter_id, factory in (selected_registry or {}).items():
                    host_registry.register(adapter_id, factory)
                selected_registry = host_registry
            if acceptance is not None:
                acceptance = BundleAcceptance(**acceptance)
        return selected_loader(Path(bundle_path), registry=selected_registry,
            expected_model=settings["model"] if settings else None, acceptance=acceptance)
    return {"analyzer_factory": factory,
            "evidence_policy": ReviewedEvidencePolicy(settings) if settings else None}
