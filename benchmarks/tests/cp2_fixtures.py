"""Generated tone fixtures only. Simulated permission claims test validation code."""
import json
import wave
from pathlib import Path

import numpy as np

from training.multitrack_assets import sha256_file


def make_inputs(root: Path):
    recordings = []
    for split_index, split in enumerate(("train", "validation", "calibration", "test")):
        stems = []
        time = np.arange(800) / 16000
        for family, frequency in (("bass", 100), ("guitar", 500), ("vocals", 2000), ("drums", 5000)):
            path = root / f"{split}-{family}.wav"
            signal = 0.1 * np.sin(2 * np.pi * (frequency + split_index * 11) * time)
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(np.round(signal * 32768).astype("<i2").tobytes())
            stems.append({"instrument_id": family, "family": family,
                          "relative_path": path.name, "sha256": sha256_file(path)})
        recordings.append({"recording_id": split, "parent_group_id": f"parent-{split}",
                           "split": split, "sample_rate_hz": 16000, "sample_count": 800,
                           "stems": stems})
    manifest = {
        "schema_version": "1.0", "dataset_id": "test-tones-not-real-music",
        "provenance": {"origin": "generated unit-test tones",
                       "license_or_permission": "repository test fixture",
                       "attribution": None, "allowed_publication_status": "publishable"},
        "recordings": recordings,
    }
    config = {
        "schema_version": "1.0", "config_id": "test-only", "root_seed": 17,
        "splits": ["validation"], "excerpt_duration_s": 0.05, "hop_duration_s": 0.05,
        "max_excerpts_per_recording": 1, "shared_scale": 0.2,
        "single_source_gain_grid_db": [-4, 4], "common_gain_grid_db": [4],
        "multi_source_gain_cycles_db": [],
        "noise_profiles": [{"kind": "none", "reference_snr_db": None, "observation_snr_db": None}],
    }
    manifest_path, config_path, review_path = [root / name for name in (
        "manifest.json", "config.json", "review.json")]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    config_path.write_text(json.dumps(config), encoding="utf-8")
    review = {
        "schema_version": "1.0", "manifest_sha256": sha256_file(manifest_path),
        # A simulated data-owner assertion exercises the positive validation branch.
        # The test data themselves are generated tones, never evidence of real music.
        "material_class": "real_recorded", "reviewed_by": "unit-test-simulated-review",
        "provenance_evidence": "unit-test-only",
        "permissions": {use: {"status": "allowed", "evidence": "unit-test-only"} for use in (
            "evaluation", "training", "remote_compute", "demo", "publication")},
    }
    review_path.write_text(json.dumps(review), encoding="utf-8")
    return manifest, config, review, manifest_path, config_path, review_path
