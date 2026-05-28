"""Tests for cv_skills with mocked OpenCV and Ultralytics.

Covers all operations when deps are mocked as available.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.cv_skills import opencv_process, yolo_detect


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(id="t", user_intent="t", objective="t", metadata=meta)
    )


class TestOpenCVProcessMocked:
    """opencv_process with mocked cv2."""

    def _mock_cv2(self):
        cv2 = MagicMock()
        cv2.imread.return_value = MagicMock(shape=(100, 200, 3))
        cv2.cvtColor.return_value = MagicMock(shape=(100, 200))
        cv2.COLOR_BGR2GRAY = 6
        cv2.GaussianBlur.return_value = MagicMock(shape=(100, 200, 3))
        cv2.Canny.return_value = MagicMock(shape=(100, 200))
        cv2.threshold.return_value = (None, MagicMock(shape=(100, 200)))
        cv2.RETR_TREE = 3
        cv2.CHAIN_APPROX_SIMPLE = 2
        cv2.findContours.return_value = ([], None)
        cv2.drawContours.return_value = MagicMock(shape=(100, 200, 3))
        cv2.resize.return_value = MagicMock(shape=(50, 100, 3))
        cv2.imwrite.return_value = True
        return cv2

    def test_grayscale(self):
        cv2 = self._mock_cv2()
        with patch.dict("sys.modules", {"cv2": cv2}):
            with patch(
                "uar.skills.cv_skills.require_package",
                return_value=None,
            ):
                with tempfile.NamedTemporaryFile(
                    suffix=".jpg", delete=False
                ) as f:
                    f.write(b"fake")
                    img_path = f.name
                try:
                    result = opencv_process(
                        _ctx({
                            "cv_image_path": img_path,
                            "cv_operation": "grayscale",
                        })
                    )
                finally:
                    os.unlink(img_path)
        assert result["status"] == "completed"
        assert result["operation"] == "grayscale"

    def test_blur(self):
        cv2 = self._mock_cv2()
        with patch("pathlib.Path.exists", return_value=True):
            with patch.dict("sys.modules", {"cv2": cv2}):
                with patch(
                    "uar.skills.cv_skills.require_package",
                    return_value=None,
                ):
                    result = opencv_process(
                        _ctx({
                            "cv_image_path": "/fake/img.jpg",
                            "cv_operation": "blur",
                            "cv_params": {"kernel": 7},
                        })
                    )
        assert result["status"] == "completed"
        assert result["operation"] == "blur"

    def test_edge(self):
        cv2 = self._mock_cv2()
        with patch("pathlib.Path.exists", return_value=True):
            with patch.dict("sys.modules", {"cv2": cv2}):
                with patch(
                    "uar.skills.cv_skills.require_package",
                    return_value=None,
                ):
                    result = opencv_process(
                        _ctx({
                            "cv_image_path": "/fake/img.jpg",
                            "cv_operation": "edge",
                            "cv_params": {
                                "threshold1": 50,
                                "threshold2": 150,
                            },
                        })
                    )
        assert result["status"] == "completed"
        assert result["operation"] == "edge"

    def test_contour(self):
        cv2 = self._mock_cv2()
        with patch("pathlib.Path.exists", return_value=True):
            with patch.dict("sys.modules", {"cv2": cv2}):
                with patch(
                    "uar.skills.cv_skills.require_package",
                    return_value=None,
                ):
                    result = opencv_process(
                        _ctx({
                            "cv_image_path": "/fake/img.jpg",
                            "cv_operation": "contour",
                        })
                    )
        assert result["status"] == "completed"
        assert result["operation"] == "contour"

    def test_resize(self):
        cv2 = self._mock_cv2()
        with patch("pathlib.Path.exists", return_value=True):
            with patch.dict("sys.modules", {"cv2": cv2}):
                with patch(
                    "uar.skills.cv_skills.require_package",
                    return_value=None,
                ):
                    result = opencv_process(
                        _ctx({
                            "cv_image_path": "/fake/img.jpg",
                            "cv_operation": "resize",
                            "cv_params": {
                                "width": 100, "height": 50,
                            },
                        })
                    )
        assert result["status"] == "completed"
        assert result["operation"] == "resize"

    def test_unknown_operation(self):
        cv2 = self._mock_cv2()
        with patch("pathlib.Path.exists", return_value=True):
            with patch.dict("sys.modules", {"cv2": cv2}):
                with patch(
                    "uar.skills.cv_skills.require_package",
                    return_value=None,
                ):
                    result = opencv_process(
                        _ctx({
                            "cv_image_path": "/fake/img.jpg",
                            "cv_operation": "rotate",
                        })
                    )
        assert result["status"] == "failed"
        assert "Unknown operation" in result["error"]

    def test_image_not_found(self):
        cv2 = self._mock_cv2()
        cv2.imread.return_value = None
        with patch("pathlib.Path.exists", return_value=True):
            with patch.dict("sys.modules", {"cv2": cv2}):
                with patch(
                    "uar.skills.cv_skills.require_package",
                    return_value=None,
                ):
                    result = opencv_process(
                        _ctx({
                            "cv_image_path": "/fake/img.jpg",
                            "cv_operation": "grayscale",
                        })
                    )
        assert result["status"] == "failed"

    def test_missing_image_path(self):
        cv2 = self._mock_cv2()
        with patch.dict("sys.modules", {"cv2": cv2}):
            with patch(
                "uar.skills.cv_skills.require_package",
                return_value=None,
            ):
                result = opencv_process(
                    _ctx({"cv_image_path": ""})
                )
        assert result["status"] == "failed"


class TestYOLODetectMocked:
    """yolo_detect with mocked ultralytics."""

    def test_basic_detection(self):
        mock_box = MagicMock()
        mock_box.cls = 0
        mock_box.conf = 0.95
        mock_box.xyxy.tolist.return_value = [[10, 20, 30, 40]]
        mock_result = MagicMock()
        mock_result.boxes = [mock_box]

        model_instance = MagicMock()
        model_instance.return_value = [mock_result]
        model_instance.names = {0: "person"}

        mock_model = MagicMock()
        mock_model.return_value = model_instance

        mock_ultra = MagicMock()
        mock_ultra.YOLO = mock_model

        with patch("pathlib.Path.exists", return_value=True):
            with patch.dict("sys.modules", {"ultralytics": mock_ultra}):
                with patch(
                    "uar.skills.cv_skills.require_package",
                    return_value=None,
                ):
                    result = yolo_detect(
                        _ctx({
                            "cv_image_path": "/fake/img.jpg",
                            "cv_conf": 0.5,
                            "cv_model": "yolov8n.pt",
                        })
                    )
        assert result["status"] == "completed"
        assert result["model"] == "yolov8n.pt"
        assert result["count"] == 1
        assert result["detections"][0]["class_name"] == "person"

    def test_missing_image_path(self):
        mock_ultra = MagicMock()
        mock_ultra.YOLO = MagicMock()
        with patch.dict("sys.modules", {"ultralytics": mock_ultra}):
            with patch(
                "uar.skills.cv_skills.require_package",
                return_value=None,
            ):
                result = yolo_detect(
                    _ctx({"cv_image_path": ""})
                )
        assert result["status"] == "failed"
