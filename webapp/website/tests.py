from unittest import mock

from django.test import RequestFactory, SimpleTestCase

from website.ImageForgeryDetection.fusion import (
    LABEL_AUTHENTIC,
    LABEL_FORGED,
    LABEL_REVIEW,
    build_current_only_result,
    fuse_detector_votes,
)
from website.ImageForgeryDetection.FakeImageDetector import (
    FID,
    resolve_primary_detector_mode,
)
from website.ImageForgeryDetection.display_labels import (
    DEFAULT_PRIMARY_DISPLAY_NAME,
    get_primary_detector_display_name,
)
from website import views


class FusionLogicTests(SimpleTestCase):
    def test_build_current_only_result_returns_structured_payload(self):
        result = build_current_only_result(0.18, "hybrid", hidden_backend="noiseprint")

        self.assertEqual(result["final_label"], LABEL_AUTHENTIC)
        self.assertEqual(result["current_source"], "hybrid")
        self.assertEqual(result["hidden_backend"], "noiseprint")
        self.assertFalse(result["hidden_available"])
        self.assertFalse(result["requires_review"])

    def test_both_low_scores_return_authentic(self):
        result = fuse_detector_votes(0.20, "hybrid", 0.22, LABEL_AUTHENTIC, hidden_backend="noiseprint")
        self.assertEqual(result["final_label"], LABEL_AUTHENTIC)
        self.assertFalse(result["requires_review"])

    def test_both_high_scores_return_forged(self):
        result = fuse_detector_votes(0.81, "hybrid", 0.78, LABEL_FORGED, hidden_backend="noiseprint")
        self.assertEqual(result["final_label"], LABEL_FORGED)
        self.assertFalse(result["requires_review"])

    def test_current_high_hidden_low_returns_review(self):
        result = fuse_detector_votes(0.87, "hybrid", 0.21, LABEL_AUTHENTIC, hidden_backend="noiseprint")
        self.assertEqual(result["final_label"], LABEL_REVIEW)
        self.assertTrue(result["requires_review"])

    def test_hidden_very_high_current_mid_returns_forged(self):
        result = fuse_detector_votes(0.48, "hybrid", 0.90, LABEL_FORGED, hidden_backend="noiseprint")
        self.assertEqual(result["final_label"], LABEL_FORGED)
        self.assertFalse(result["requires_review"])

    def test_near_threshold_scores_return_review(self):
        result = fuse_detector_votes(0.52, "hybrid", 0.49, LABEL_FORGED, hidden_backend="noiseprint")
        self.assertEqual(result["final_label"], LABEL_REVIEW)
        self.assertTrue(result["requires_review"])

    def test_decision_mode_contains_backend_tag(self):
        result = fuse_detector_votes(0.66, "hybrid", 0.71, LABEL_FORGED, hidden_backend="comprint")
        self.assertEqual(result["decision_mode"], "fused_hidden_comprint")


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



class PrimaryDisplayLabelTests(SimpleTestCase):
    def test_default_primary_display_name(self):
        value = get_primary_detector_display_name({})
        self.assertEqual(value, DEFAULT_PRIMARY_DISPLAY_NAME)

    def test_primary_display_name_can_be_overridden(self):
        value = get_primary_detector_display_name({"T07_PRIMARY_DISPLAY_NAME": "Custom Detector Name"})
        self.assertEqual(value, "Custom Detector Name")


class HiddenFallbackTests(SimpleTestCase):
    def test_predict_result_structured_falls_back_when_hidden_backend_blocked(self):
        fid = FID()
        with mock.patch.object(
            fid,
            "_run_primary_detector",
            return_value={
                "score_forged": 0.81,
                "label": LABEL_FORGED,
                "confidence": 81.0,
                "source": "cnn_only",
                "release_id": "unit_test_release",
            },
        ), mock.patch(
            "website.ImageForgeryDetection.FakeImageDetector.describe_hidden_backend_state",
            return_value=(False, "Gate blocked"),
        ):
            result = fid.predict_result_structured(
                "dummy.jpg",
                source_type="image",
                require_hidden=False,
            )

        self.assertEqual(result["decision_mode"], "current_only")
        self.assertEqual(result["current_release_id"], "unit_test_release")
        self.assertFalse(result["hidden_available"])
        self.assertIn("Gate blocked", result["hidden_error"])


class RunAnalysisResponseTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_runanalysis_get_always_returns_http_response(self):
        request = self.factory.get("/runAnalysis")
        with mock.patch("website.views.render") as render_mock:
            render_mock.return_value = object()
            response = views.runAnalysis(request)
        self.assertIsNotNone(response)
        context = render_mock.call_args.args[2]
        self.assertEqual(context["detector_display_name"], DEFAULT_PRIMARY_DISPLAY_NAME)

    def test_runanalysis_post_without_run_always_returns_http_response(self):
        request = self.factory.post("/runAnalysis", data={})
        with mock.patch("website.views.render") as render_mock:
            render_mock.return_value = object()
            response = views.runAnalysis(request)
        self.assertIsNotNone(response)
        context = render_mock.call_args.args[2]
        self.assertEqual(context["detector_display_name"], DEFAULT_PRIMARY_DISPLAY_NAME)
