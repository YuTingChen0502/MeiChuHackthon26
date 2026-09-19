"""Deterministic controlled reference/observation pair generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping

import numpy as np

from training.oracle import GainLabels, compute_gain_labels


@dataclass(frozen=True)
class NoiseSpec:
    kind: str = "none"
    reference_snr_db: float | None = None
    observation_snr_db: float | None = None


@dataclass(frozen=True)
class PairSpec:
    pair_id: str
    split_id: str
    seed: int
    source_injected_gain_db: Mapping[str, float]
    common_gain_db: float = 0.0
    shared_scale: float = 1.0
    noise: NoiseSpec = NoiseSpec()


@dataclass(frozen=True)
class ControlledPair:
    reference_mix: np.ndarray
    observation_mix: np.ndarray
    reference_stems: dict[str, np.ndarray]
    observation_stems: dict[str, np.ndarray]
    labels: GainLabels
    metadata: dict[str, object]


def _stable_seed(root_seed: int, pair_id: str, branch: str) -> int:
    digest = hashlib.sha256(f"{root_seed}:{pair_id}:{branch}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _power(signal: np.ndarray) -> float:
    return float(np.mean(np.square(signal, dtype=np.float64)))


def _noise_at_snr(signal: np.ndarray, snr_db: float, seed: int) -> np.ndarray:
    signal_power = _power(signal)
    if signal_power <= 0.0:
        raise ValueError("Cannot define SNR for a silent mixture")
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(signal.shape).astype(np.float64)
    noise_power = _power(noise)
    target_power = signal_power / (10.0 ** (snr_db / 10.0))
    return noise * np.sqrt(target_power / noise_power)


def _array_hash(signal: np.ndarray) -> str:
    canonical = np.ascontiguousarray(signal, dtype="<f8")
    return hashlib.sha256(canonical.tobytes()).hexdigest()


def generate_controlled_pair(
    stems: Mapping[str, np.ndarray],
    spec: PairSpec,
    *,
    asset_provenance: Mapping[str, object],
) -> ControlledPair:
    """Generate a stable pair without independently normalizing either member."""

    if not stems:
        raise ValueError("At least one stem is required")
    names = tuple(sorted(stems))
    arrays = {name: np.asarray(stems[name], dtype=np.float64) for name in names}
    shapes = {array.shape for array in arrays.values()}
    if len(shapes) != 1 or len(next(iter(shapes))) != 1:
        raise ValueError("All stems must be one-dimensional and have equal length")
    if not 0.0 < spec.shared_scale <= 1.0:
        raise ValueError("shared_scale must be in (0, 1]")
    if set(spec.source_injected_gain_db) != set(names):
        raise ValueError("Gain map must cover every stem exactly")

    active = {name: _power(array) > 0.0 for name, array in arrays.items()}
    labels = compute_gain_labels(
        spec.source_injected_gain_db,
        common_gain_db=spec.common_gain_db,
        active_sources=active,
    )
    reference_stems = {name: spec.shared_scale * array for name, array in arrays.items()}
    observation_stems = {
        name: reference_stems[name] * 10.0 ** (
            (spec.common_gain_db + float(spec.source_injected_gain_db[name])) / 20.0
        )
        for name in names
    }
    reference_mix = np.sum(list(reference_stems.values()), axis=0)
    observation_mix = np.sum(list(observation_stems.values()), axis=0)

    if spec.noise.kind == "none":
        if spec.noise.reference_snr_db is not None or spec.noise.observation_snr_db is not None:
            raise ValueError("Clean noise spec cannot declare SNR")
    elif spec.noise.kind == "white_gaussian":
        if spec.noise.reference_snr_db is not None:
            reference_mix = reference_mix + _noise_at_snr(
                reference_mix,
                spec.noise.reference_snr_db,
                _stable_seed(spec.seed, spec.pair_id, "reference_noise"),
            )
        if spec.noise.observation_snr_db is not None:
            observation_mix = observation_mix + _noise_at_snr(
                observation_mix,
                spec.noise.observation_snr_db,
                _stable_seed(spec.seed, spec.pair_id, "observation_noise"),
            )
    else:
        raise ValueError(f"Unsupported deterministic noise kind: {spec.noise.kind}")

    metadata = {
        "pair_id": spec.pair_id,
        "split_id": spec.split_id,
        "seed": spec.seed,
        "asset_provenance": dict(asset_provenance),
        "source_injected_gain_db": labels.source_injected_gain_db,
        "common_gain_input_db": spec.common_gain_db,
        "raw_source_delta_db": labels.raw_source_delta_db,
        "label_common_mode_gain_db": labels.common_mode_gain_db,
        "centered_balance_db": labels.centered_balance_db,
        "valid_source_mask": labels.valid_source_mask,
        "noise": {
            "kind": spec.noise.kind,
            "reference_snr_db": spec.noise.reference_snr_db,
            "observation_snr_db": spec.noise.observation_snr_db,
            "independent_within_pair": True,
        },
        "shared_scale": spec.shared_scale,
        "reference_mix_sha256_f64le": _array_hash(reference_mix),
        "observation_mix_sha256_f64le": _array_hash(observation_mix),
        "label_procedure": "raw=common+source_injection; center=median(active raw); balance=raw-center; inactive=null",
    }
    # Prove metadata remains JSON-compatible before returning it to experiment code.
    json.dumps(metadata, sort_keys=True, allow_nan=False)
    return ControlledPair(
        reference_mix=reference_mix,
        observation_mix=observation_mix,
        reference_stems=reference_stems,
        observation_stems=observation_stems,
        labels=labels,
        metadata=metadata,
    )

