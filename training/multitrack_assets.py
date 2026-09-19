"""Rights/provenance-aware multitrack WAV ingestion for empirical experiments."""

from __future__ import annotations

import hashlib
import json
import wave
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

import numpy as np


ALLOWED_SPLITS = {"train", "validation", "calibration", "test"}
ALLOWED_PUBLICATION = {"publishable", "private_eval_only", "restricted_no_redistribution"}


@dataclass(frozen=True)
class LoadedRecording:
    dataset_id: str
    recording_id: str
    parent_group_id: str
    split: str
    sample_rate_hz: int
    sample_start: int
    sample_end: int
    stems: dict[str, np.ndarray]
    families: dict[str, str]
    asset_provenance: dict[str, object]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_asset_path(dataset_root: Path, relative_path: str) -> Path:
    posix = PurePosixPath(relative_path)
    _require(relative_path == posix.as_posix(), "Asset paths must use normalized forward slashes")
    _require(not posix.is_absolute() and ".." not in posix.parts, "Asset path must be relative and contained")
    root = dataset_root.resolve()
    resolved = root.joinpath(*posix.parts).resolve()
    _require(resolved.is_relative_to(root), "Asset path resolves outside dataset root")
    return resolved


def load_manifest(path: Path) -> dict[str, object]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: Mapping[str, object]) -> None:
    _require(manifest.get("schema_version") == "1.0", "Unsupported manifest schema_version")
    dataset_id = manifest.get("dataset_id")
    _require(isinstance(dataset_id, str) and bool(dataset_id), "dataset_id is required")
    provenance = manifest.get("provenance")
    _require(isinstance(provenance, dict), "provenance object is required")
    for field in ("origin", "license_or_permission", "allowed_publication_status"):
        _require(isinstance(provenance.get(field), str) and bool(provenance[field]),
                 f"provenance.{field} is required")
    _require(provenance["allowed_publication_status"] in ALLOWED_PUBLICATION,
             "Unsupported publication status")
    recordings = manifest.get("recordings")
    _require(isinstance(recordings, list) and bool(recordings), "recordings must be non-empty")
    recording_ids: set[str] = set()
    group_splits: dict[str, str] = {}
    for recording in recordings:
        _require(isinstance(recording, dict), "Each recording must be an object")
        recording_id = recording.get("recording_id")
        group_id = recording.get("parent_group_id")
        split = recording.get("split")
        _require(isinstance(recording_id, str) and bool(recording_id), "recording_id is required")
        _require(recording_id not in recording_ids, f"Duplicate recording_id: {recording_id}")
        recording_ids.add(recording_id)
        _require(isinstance(group_id, str) and bool(group_id), "parent_group_id is required")
        _require(split in ALLOWED_SPLITS, f"Unsupported split: {split}")
        if group_id in group_splits:
            _require(group_splits[group_id] == split,
                     f"Split leakage: parent group {group_id} occurs in multiple splits")
        group_splits[group_id] = str(split)
        _require(isinstance(recording.get("sample_rate_hz"), int)
                 and recording["sample_rate_hz"] > 0, "Positive sample_rate_hz is required")
        _require(isinstance(recording.get("sample_count"), int)
                 and recording["sample_count"] > 0, "Positive sample_count is required")
        stems = recording.get("stems")
        _require(isinstance(stems, list) and bool(stems), "Each recording needs stems")
        instrument_ids: set[str] = set()
        for stem in stems:
            _require(isinstance(stem, dict), "Each stem must be an object")
            instrument_id = stem.get("instrument_id")
            family = stem.get("family")
            relative_path = stem.get("relative_path")
            digest = stem.get("sha256")
            _require(isinstance(instrument_id, str) and bool(instrument_id),
                     "stem.instrument_id is required")
            _require(instrument_id not in instrument_ids,
                     f"Duplicate instrument_id {instrument_id} in {recording_id}")
            instrument_ids.add(instrument_id)
            _require(isinstance(family, str) and bool(family), "stem.family is required")
            _require(isinstance(relative_path, str) and bool(relative_path),
                     "stem.relative_path is required")
            _require(isinstance(digest, str) and len(digest) == 64
                     and all(character in "0123456789abcdef" for character in digest),
                     "stem.sha256 must be a lowercase SHA-256")
            # Structural path validation does not require the dataset to exist.
            posix = PurePosixPath(relative_path)
            _require(relative_path == posix.as_posix() and not posix.is_absolute()
                     and ".." not in posix.parts, "Unsafe or non-normalized stem path")


def _decode_pcm(frames: bytes, sample_width: int, channels: int) -> np.ndarray:
    if sample_width == 1:
        values = (np.frombuffer(frames, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    elif sample_width == 2:
        values = np.frombuffer(frames, dtype="<i2").astype(np.float64) / 32768.0
    elif sample_width == 3:
        raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        values_i32 = raw[:, 0] | (raw[:, 1] << 8) | (raw[:, 2] << 16)
        values_i32 = np.where(values_i32 & 0x800000, values_i32 - 0x1000000, values_i32)
        values = values_i32.astype(np.float64) / 8388608.0
    elif sample_width == 4:
        values = np.frombuffer(frames, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        raise ValueError(f"Unsupported PCM sample width: {sample_width} bytes")
    shaped = values.reshape(-1, channels)
    return shaped.mean(axis=1) if channels > 1 else shaped[:, 0]


def _read_wav_excerpt(
    path: Path,
    *,
    expected_rate: int,
    expected_count: int,
    sample_start: int,
    sample_count: int,
) -> np.ndarray:
    with wave.open(str(path), "rb") as wav:
        _require(wav.getcomptype() == "NONE", f"Compressed WAV is unsupported: {path}")
        _require(wav.getnchannels() in (1, 2), f"Only mono/stereo WAV is supported: {path}")
        _require(wav.getframerate() == expected_rate, f"Sample-rate mismatch: {path}")
        _require(wav.getnframes() == expected_count, f"Sample-count mismatch: {path}")
        _require(sample_start >= 0 and sample_count > 0
                 and sample_start + sample_count <= expected_count,
                 f"Excerpt outside recording bounds: {path}")
        wav.setpos(sample_start)
        frames = wav.readframes(sample_count)
        signal = _decode_pcm(frames, wav.getsampwidth(), wav.getnchannels())
    _require(signal.size == sample_count, f"Short WAV read: {path}")
    return signal


def load_recording_excerpt(
    manifest: Mapping[str, object],
    *,
    dataset_root: Path,
    recording_id: str,
    sample_start: int,
    sample_count: int,
) -> LoadedRecording:
    validate_manifest(manifest)
    recordings = manifest["recordings"]
    matches = [item for item in recordings if item["recording_id"] == recording_id]  # type: ignore[index]
    _require(len(matches) == 1, f"Unknown recording_id: {recording_id}")
    recording = matches[0]
    rate = int(recording["sample_rate_hz"])
    total = int(recording["sample_count"])
    stems: dict[str, np.ndarray] = {}
    families: dict[str, str] = {}
    verified_assets = []
    for stem in recording["stems"]:
        path = _safe_asset_path(dataset_root, stem["relative_path"])
        _require(path.is_file(), f"Missing stem asset: {stem['relative_path']}")
        actual_hash = sha256_file(path)
        _require(actual_hash == stem["sha256"], f"SHA-256 mismatch: {stem['relative_path']}")
        instrument_id = stem["instrument_id"]
        stems[instrument_id] = _read_wav_excerpt(
            path,
            expected_rate=rate,
            expected_count=total,
            sample_start=sample_start,
            sample_count=sample_count,
        )
        families[instrument_id] = stem["family"]
        verified_assets.append({
            "instrument_id": instrument_id,
            "family": stem["family"],
            "relative_path": stem["relative_path"],
            "sha256": actual_hash,
        })
    provenance = manifest["provenance"]
    return LoadedRecording(
        dataset_id=manifest["dataset_id"],  # type: ignore[arg-type]
        recording_id=recording_id,
        parent_group_id=recording["parent_group_id"],
        split=recording["split"],
        sample_rate_hz=rate,
        sample_start=sample_start,
        sample_end=sample_start + sample_count,
        stems=stems,
        families=families,
        asset_provenance={
            "dataset_id": manifest["dataset_id"],
            "recording_id": recording_id,
            "parent_group_id": recording["parent_group_id"],
            "split": recording["split"],
            "origin": provenance["origin"],
            "license_or_permission": provenance["license_or_permission"],
            "attribution": provenance.get("attribution"),
            "allowed_publication_status": provenance["allowed_publication_status"],
            "verified_assets": verified_assets,
        },
    )

