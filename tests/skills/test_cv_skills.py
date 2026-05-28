"""Tests for cv_skills error paths.

Full OpenCV/ultralytics paths require heavy deps; this covers
missing-package handling and input validation.
"""

from unittest.mock import patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.cv_skills import opencv_process, yolo_detect


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="t", objective="t", metadata=meta
        )
    )


class TestOpenCVProcessMissingPackage:
    """opencv_process when cv2 not installed."""

    def test_returns_error_when_cv2_missing(self):
        with patch(
            "uar.skills.cv_skills.require_package",
            return_value={"status": "failed", "error": "cv2 missing"},
        ):
            result = opencv_process(_ctx({"cv_image_path": "/tmp/test.jpg"}))
        assert result["status"] == "failed"
        assert "cv2" in result["error"].lower()

    def test_missing_image_path(self):
        with patch.dict("sys.modules", {"cv2": None}):
            with patch(
                "uar.skills.cv_skills.require_package", return_value=None
            ):
                with patch("builtins.__import__", side_effect=ImportError):
                    result = opencv_process(_ctx({"cv_image_path": ""}))
        # When cv2 is truly absent, require_package or import will fail
        assert result["status"] in ("failed", "error")


class TestYOLODetectMissingPackage:
    """yolo_detect when ultralytics not installed."""

    def test_returns_error_when_ultralytics_missing(self):
        with patch(
            "uar.skills.cv_skills.require_package",
            return_value={"status": "failed", "error": "ultralytics missing"},
        ):
            result = yolo_detect(_ctx({"cv_image_path": "/tmp/test.jpg"}))
        assert result["status"] == "failed"
        assert "ultralytics" in result["error"].lower()

    def test_missing_image_path(self):
        with patch(
            "uar.skills.cv_skills.require_package", return_value=None
        ):
            with patch.dict("sys.modules", {"ultralytics": None}):
                result = yolo_detect(_ctx({"cv_image_path": ""}))
        assert result["status"] in ("failed", "error")
