import unittest

from training.oracle import compute_gain_labels


SOURCES = ("bass", "drums", "guitar", "vocals")


class OracleMathTests(unittest.TestCase):
    def test_zero_change(self):
        labels = compute_gain_labels({name: 0.0 for name in SOURCES})
        self.assertEqual(0.0, labels.common_mode_gain_db)
        self.assertEqual({name: 0.0 for name in SOURCES}, labels.centered_balance_db)

    def test_common_gain_is_not_balance_change(self):
        labels = compute_gain_labels(
            {name: 0.0 for name in SOURCES}, common_gain_db=4.0
        )
        self.assertEqual(4.0, labels.common_mode_gain_db)
        self.assertEqual({name: 4.0 for name in SOURCES}, labels.raw_source_delta_db)
        self.assertEqual({name: 0.0 for name in SOURCES}, labels.centered_balance_db)

    def test_one_source_gain_with_stable_anchors(self):
        gains = {name: 4.0 if name == "guitar" else 0.0 for name in SOURCES}
        labels = compute_gain_labels(gains)
        self.assertEqual(0.0, labels.common_mode_gain_db)
        self.assertEqual(4.0, labels.centered_balance_db["guitar"])
        self.assertTrue(all(labels.valid_source_mask.values()))

    def test_multi_source_labels_are_median_centered(self):
        gains = {"bass": -2.0, "drums": 2.0, "guitar": 4.0, "vocals": 0.0}
        labels = compute_gain_labels(gains, common_gain_db=1.0)
        self.assertEqual(2.0, labels.common_mode_gain_db)
        self.assertEqual(
            {"bass": -3.0, "drums": 1.0, "guitar": 3.0, "vocals": -1.0},
            labels.centered_balance_db,
        )

    def test_inactive_source_is_masked_and_excluded_from_center(self):
        labels = compute_gain_labels(
            {"bass": 0.0, "drums": 0.0, "guitar": 40.0, "vocals": 4.0},
            active_sources={"bass": True, "drums": True, "guitar": False, "vocals": True},
        )
        self.assertIsNone(labels.raw_source_delta_db["guitar"])
        self.assertIsNone(labels.centered_balance_db["guitar"])
        self.assertFalse(labels.valid_source_mask["guitar"])
        self.assertEqual(0.0, labels.common_mode_gain_db)

    def test_all_inactive_has_no_numeric_center(self):
        labels = compute_gain_labels(
            {"bass": 6.0}, active_sources={"bass": False}
        )
        self.assertIsNone(labels.common_mode_gain_db)
        self.assertIsNone(labels.centered_balance_db["bass"])


if __name__ == "__main__":
    unittest.main()

