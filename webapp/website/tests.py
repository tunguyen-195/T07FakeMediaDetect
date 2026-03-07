from django.test import SimpleTestCase

from website.ImageForgeryDetection.fusion import (
    LABEL_AUTHENTIC,
    LABEL_FORGED,
    LABEL_REVIEW,
    build_current_only_result,
    fuse_detector_votes,
)
from website.ImageForgeryDetection.FakeImageDetector import (
    resolve_primary_detector_mode,
)


class FusionLogicTests(SimpleTestCase):
    def test_build_current_only_result_returns_structured_payload(self):
        result = build_current_only_result(0.18, "hybrid")

        self.assertEqual(result["final_label"], LABEL_AUTHENTIC)
        self.assertEqual(result["current_source"], "hybrid")
        self.assertFalse(result["hidden_available"])
        self.assertFalse(result["requires_review"])

    def test_both_low_scores_return_authentic(self):
        result = fuse_detector_votes(0.20, "hybrid", 0.22, LABEL_AUTHENTIC)
        self.assertEqual(result["final_label"], LABEL_AUTHENTIC)
        self.assertFalse(result["requires_review"])

    def test_both_high_scores_return_forged(self):
        result = fuse_detector_votes(0.81, "hybrid", 0.78, LABEL_FORGED)
        self.assertEqual(result["final_label"], LABEL_FORGED)
        self.assertFalse(result["requires_review"])

    def test_current_high_hidden_low_returns_review(self):
        result = fuse_detector_votes(0.87, "hybrid", 0.21, LABEL_AUTHENTIC)
        self.assertEqual(result["final_label"], LABEL_REVIEW)
        self.assertTrue(result["requires_review"])

    def test_hidden_very_high_current_mid_returns_forged(self):
        result = fuse_detector_votes(0.48, "hybrid", 0.90, LABEL_FORGED)
        self.assertEqual(result["final_label"], LABEL_FORGED)
        self.assertFalse(result["requires_review"])

    def test_both_mid_scores_return_review(self):
        result = fuse_detector_votes(0.55, "hybrid", 0.51, LABEL_FORGED)
        self.assertEqual(result["final_label"], LABEL_REVIEW)
        self.assertTrue(result["requires_review"])


class PrimaryDetectorModeTests(SimpleTestCase):
    def test_default_primary_detector_is_cnn_only(self):
        mode = resolve_primary_detector_mode({})
        self.assertEqual(mode, "cnn_only")

    def test_explicit_primary_detector_env_wins(self):
        mode = resolve_primary_detector_mode(
            {
                "T07_PRIMARY_IMAGE_DETECTOR": "legacy_current",
                "T07_USE_BENFORD_RICH_PRIMARY": "1",
            }
        )
        self.assertEqual(mode, "legacy_current")

    def test_legacy_benford_flag_kept_for_backward_compatibility(self):
        mode = resolve_primary_detector_mode(
            {
                "T07_USE_BENFORD_RICH_PRIMARY": "1",
            }
        )
        self.assertEqual(mode, "benford_rich")
