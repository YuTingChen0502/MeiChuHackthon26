import unittest

import numpy as np

from training.controlled_pairs import NoiseSpec, PairSpec, generate_controlled_pair


class ControlledPairTests(unittest.TestCase):
    def setUp(self):
        time = np.arange(16000, dtype=np.float64) / 16000
        self.stems = {
            "bass": 0.1 * np.sin(2 * np.pi * 100 * time),
            "guitar": 0.1 * np.sin(2 * np.pi * 500 * time),
        }
        self.provenance = {"asset_id": "generated-test", "origin": "unit-test"}

    def _spec(self, **changes):
        values = {
            "pair_id": "pair-1",
            "split_id": "test",
            "seed": 7,
            "source_injected_gain_db": {"bass": 0.0, "guitar": 4.0},
            "shared_scale": 0.25,
        }
        values.update(changes)
        return PairSpec(**values)

    def test_generation_is_byte_deterministic(self):
        spec = self._spec(
            noise=NoiseSpec("white_gaussian", reference_snr_db=10, observation_snr_db=10)
        )
        first = generate_controlled_pair(self.stems, spec, asset_provenance=self.provenance)
        second = generate_controlled_pair(self.stems, spec, asset_provenance=self.provenance)
        np.testing.assert_array_equal(first.reference_mix, second.reference_mix)
        np.testing.assert_array_equal(first.observation_mix, second.observation_mix)
        self.assertEqual(first.metadata, second.metadata)

    def test_reference_and_observation_noise_are_independent(self):
        clean = generate_controlled_pair(
            self.stems, self._spec(), asset_provenance=self.provenance
        )
        noisy = generate_controlled_pair(
            self.stems,
            self._spec(noise=NoiseSpec("white_gaussian", 10, 10)),
            asset_provenance=self.provenance,
        )
        reference_noise = noisy.reference_mix - clean.reference_mix
        observation_noise = noisy.observation_mix - clean.observation_mix
        self.assertFalse(np.array_equal(reference_noise, observation_noise))

    def test_shared_scale_and_injected_gain_are_preserved(self):
        pair = generate_controlled_pair(
            self.stems, self._spec(), asset_provenance=self.provenance
        )
        ref_rms = np.sqrt(np.mean(pair.reference_stems["guitar"] ** 2))
        obs_rms = np.sqrt(np.mean(pair.observation_stems["guitar"] ** 2))
        self.assertAlmostEqual(4.0, 20 * np.log10(obs_rms / ref_rms), places=10)
        np.testing.assert_allclose(pair.reference_stems["bass"], self.stems["bass"] * 0.25)

    def test_silent_source_is_invalid_not_extreme_db(self):
        stems = dict(self.stems)
        stems["guitar"] = np.zeros_like(stems["guitar"])
        pair = generate_controlled_pair(
            stems, self._spec(), asset_provenance=self.provenance
        )
        self.assertIsNone(pair.labels.raw_source_delta_db["guitar"])
        self.assertIsNone(pair.labels.centered_balance_db["guitar"])
        self.assertFalse(pair.labels.valid_source_mask["guitar"])


if __name__ == "__main__":
    unittest.main()

