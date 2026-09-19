"""Gate-A input audit. A permission record is supplied by the data owner, never inferred.

This is an ML-internal companion to the unchanged multitrack manifest V1.
Passing technical checks requests Lead review; it does not accept Gate A.
"""
from __future__ import annotations

import hashlib
import json
import wave
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from training.multitrack_assets import (
    ALLOWED_SPLITS, _decode_pcm, _safe_asset_path, load_manifest, sha256_file,
)

USES = ("evaluation", "training", "remote_compute", "demo", "publication")


def validate_use_review(review: dict, manifest_hash: str) -> None:
    if review.get("schema_version") != "1.0":
        raise ValueError("Unsupported asset-use review version")
    if review.get("manifest_sha256") != manifest_hash:
        raise ValueError("Asset-use review is not bound to this manifest hash")
    if review.get("material_class") not in {"real_recorded", "synthetic", "unknown"}:
        raise ValueError("Declare real_recorded, synthetic or unknown material_class")
    for field in ("reviewed_by", "provenance_evidence"):
        if not isinstance(review.get(field), str) or not review[field].strip():
            raise ValueError(f"Missing {field}")
    permissions = review.get("permissions", {})
    if set(permissions) != set(USES):
        raise ValueError("Review must separately declare all five usage permissions")
    for use in USES:
        item = permissions[use]
        if not isinstance(item, dict) or item.get("status") not in {"allowed", "denied", "pending"}:
            raise ValueError(f"Invalid permission status: {use}")
        if item["status"] != "pending" and (
            not isinstance(item.get("evidence"), str) or not item["evidence"].strip()
        ):
            raise ValueError(f"Permission {use} needs an evidence reference")


def audit_assets(manifest_path: Path, dataset_root: Path, review_path: Path) -> dict:
    """Verify full PCM payloads with bounded memory, rights records and split leakage.

    Duplicate non-silent decoded mono PCM across splits is rejected even when WAV
    headers differ. This cannot discover related performances or pretrained overlap;
    those remain data-owner grouping/provenance responsibilities.
    """
    manifest = load_manifest(manifest_path)
    manifest_hash = sha256_file(manifest_path)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    validate_use_review(review, manifest_hash)
    blockers = []
    if review["material_class"] != "real_recorded":
        blockers.append("real_recorded_material_not_supplied")
    if review["permissions"]["evaluation"]["status"] != "allowed":
        blockers.append("evaluation_permission_not_allowed")
    if (review["permissions"]["publication"]["status"] == "allowed"
            and manifest["provenance"]["allowed_publication_status"] != "publishable"):
        blockers.append("publication_permission_conflicts_with_manifest")
    split_groups = defaultdict(set)
    split_recordings = Counter()
    split_samples = Counter()
    pcm_splits = defaultdict(set)
    rows = []
    for recording in manifest["recordings"]:
        split = recording["split"]
        split_groups[split].add(recording["parent_group_id"])
        split_recordings[split] += 1
        split_samples[split] += recording["sample_count"]
        for stem in recording["stems"]:
            path = _safe_asset_path(dataset_root, stem["relative_path"])
            if not path.is_file() or sha256_file(path) != stem["sha256"]:
                raise ValueError(f"Missing asset or SHA-256 mismatch: {stem['relative_path']}")
            digest = hashlib.sha256()
            count = 0
            energy = 0.0
            peak = 0.0
            rail_samples = 0
            with wave.open(str(path), "rb") as wav:
                rate, frames = wav.getframerate(), wav.getnframes()
                width, channels = wav.getsampwidth(), wav.getnchannels()
                if (wav.getcomptype() != "NONE" or channels not in (1, 2)
                        or width not in (1, 2, 3, 4)
                        or rate != recording["sample_rate_hz"]
                        or frames != recording["sample_count"]):
                    raise ValueError(f"WAV header mismatch/unsupported: {stem['relative_path']}")
                digest.update(str(rate).encode("ascii"))
                while True:
                    payload = wav.readframes(65536)
                    if not payload:
                        break
                    samples = _decode_pcm(payload, width, channels)
                    count += samples.size
                    digest.update(np.ascontiguousarray(samples, dtype="<f8").tobytes())
                    energy += float(np.dot(samples, samples))
                    peak = max(peak, float(np.max(np.abs(samples))))
                    # Check channels before downmix; cancellation must not hide rails.
                    channel_values = _decode_pcm(payload, width, 1)
                    rail_samples += int(np.count_nonzero(
                        (channel_values <= -1.0)
                        | (channel_values >= 1.0 - 2.0 ** (1 - 8 * width))
                    ))
            if count != recording["sample_count"]:
                raise ValueError(f"Truncated PCM payload: {stem['relative_path']}")
            pcm_hash = digest.hexdigest()
            if energy > 0.0:
                pcm_splits[pcm_hash].add(split)
            rows.append({
                "recording_id": recording["recording_id"],
                "parent_group_id": recording["parent_group_id"],
                "split": split, "instrument_id": stem["instrument_id"],
                "family": stem["family"], "asset_sha256": stem["sha256"],
                "mono_pcm_sha256_with_rate": pcm_hash, "samples": count,
                "rms": float(np.sqrt(energy / count)), "peak": peak,
                "channel_rail_samples": rail_samples,
            })
    missing = sorted(ALLOWED_SPLITS - set(split_groups))
    if missing:
        blockers.append("missing_grouped_splits:" + ",".join(missing))
    duplicates = [
        {"pcm_sha256": digest, "splits": sorted(splits)}
        for digest, splits in sorted(pcm_splits.items()) if len(splits) > 1
    ]
    if duplicates:
        blockers.append("duplicate_non_silent_pcm_across_splits")
    for split in sorted(set(split_groups)):
        if not any(row["rms"] > 0 and row["split"] == split for row in rows):
            blockers.append("all_assets_silent_in_split:" + split)
    permissions = {use: review["permissions"][use]["status"] for use in USES}
    return {
        "record_type": "CP2AssetReadiness", "schema_version": "1.0",
        "status": "BLOCKED" if blockers else "READY_FOR_LEAD_REVIEW",
        "gate_a_accepted": False, "blockers": blockers,
        "manifest_sha256": manifest_hash, "review_sha256": sha256_file(review_path),
        "dataset_id": manifest["dataset_id"], "provenance": manifest["provenance"],
        "use_review": review, "permissions": permissions,
        "split_identity": {
            split: {"parent_group_ids": sorted(split_groups[split]),
                    "recordings": split_recordings[split], "samples": split_samples[split]}
            for split in sorted(ALLOWED_SPLITS)
        },
        "duplicate_pcm_across_splits": duplicates, "assets": rows,
        "limitations": [
            "Technical checks do not independently verify supplied permissions or parent identity.",
            "PCM equality cannot detect related takes, shifted/rescaled duplicates or pretrained overlap.",
            "Rail samples are diagnostics; planned pairs still require clipping and label checks.",
            "No model, musical-feasibility, calibration or physical claim.",
        ],
    }
