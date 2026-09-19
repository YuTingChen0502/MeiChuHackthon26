"""Provider parity hook for identical held-out PCM; not calibration or accuracy evidence."""
import copy
import hashlib
import struct
from core.contracts.validation import validate_analyzer_pair


def compare_window(window, *, left_factory, right_factory, context_factory, tolerance_db):
    if tolerance_db < 0:
        raise ValueError("nonnegative parity tolerance required")
    evidence, capabilities = [], []
    for factory in (left_factory, right_factory):
        analyzer = factory()
        try:
            caps = analyzer.capabilities()
            context = context_factory(analyzer, window)
            value = analyzer.analyze(window, context)
            validate_analyzer_pair(context, value)
            capabilities.append(copy.deepcopy(caps));evidence.append(value)
        finally:
            analyzer.close()
    identities = [dict(c["model"]) for c in capabilities]
    for model in identities:
        model.pop("execution_profile_id")
    if identities[0] != identities[1] or evidence[0]["evidence_mode"] != evidence[1]["evidence_mode"]:
        raise ValueError("parity requires the same model/frontend/taxonomy/scale and evidence mode")
    differences = []
    comparable = True
    for left,right in zip(evidence[0]["measurements"], evidence[1]["measurements"], strict=True):
        if (left["instrument_id"] != right["instrument_id"] or left["validity"] != "valid" or right["validity"] != "valid"):
            comparable = False
            continue
        for key in ("source_level_delta_db", "source_level_db", "target_source_level_db"):
            if key in left and left[key] is not None and right.get(key) is not None:
                differences.append(abs(left[key]-right[key]))
    available = comparable and bool(differences)
    digest=hashlib.sha256(b"".join(struct.pack("<f",v) for v in window.samples)).hexdigest()
    return {"pcm_sha256":digest, "window":window.identity(), "capabilities":capabilities,
            "status":"pass" if available and max(differences)<=tolerance_db else "fail" if available else "unavailable",
            "maximum_delta_db":max(differences) if available else None, "tolerance_db":tolerance_db,
            "claim":"Provider numerical parity only; no held-out accuracy or calibration claim."}
