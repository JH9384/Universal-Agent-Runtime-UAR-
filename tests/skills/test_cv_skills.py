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


class TestVideoAnalyzeMissingPackage:
    """video_analyze when cv2 not installed."""

    def test_returns_error_when_cv2_missing(self):
        with patch(
            "uar.skills.cv_skills.require_package",
            return_value={"status": "failed", "error": "cv2 missing"},
        ):
            from uar.skills.cv_skills import video_analyze
            result = video_analyze(
                _ctx({"cv_video_path": "/tmp/test.mp4"})
            )
        assert result["status"] == "failed"


class TestFaceRecognizeMissingPackage:
    """face_recognize when face_recognition not installed."""

    def test_returns_error_when_face_recognition_missing(self):
        with patch(
            "uar.skills.cv_skills.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            from uar.skills.cv_skills import face_recognize
            result = face_recognize(
                _ctx({"cv_image_path": "/tmp/test.jpg"})
            )
        assert result["status"] == "failed"


class TestVideoAnalyzeBranches:
    """video_analyze error branches with mocked cv2."""

    def test_cannot_open_video(self):
        mock_cap = type(
            "Cap", (), {
                "isOpened": lambda self: False,
                "release": lambda self: None,
            }
        )()
        with patch("uar.skills.cv_skills.require_package", return_value=None):
            with patch.dict("sys.modules", {"cv2": type(
                "cv2", (), {
                    "VideoCapture": staticmethod(lambda p: mock_cap),
                    "CAP_PROP_FPS": 5,
                    "CAP_PROP_FRAME_COUNT": 100,
                    "CAP_PROP_FRAME_WIDTH": 640,
                    "CAP_PROP_FRAME_HEIGHT": 480,
                }
            )()}):
                with patch("pathlib.Path.exists", return_value=True):
                    from uar.skills.cv_skills import video_analyze
                    result = video_analyze(
                        _ctx({"cv_video_path": "/tmp/test.mp4"})
                    )
        assert result["status"] == "failed"
        assert "open" in result["error"].lower()

    def test_extract_frames_read_fails(self):
        mock_cap = type(
            "Cap", (), {
                "isOpened": lambda self: True,
                "get": lambda self, p: {
                    "fps": 30, "count": 100, "w": 640, "h": 480
                }[p],
                "set": lambda self, p, v: None,
                "read": lambda self: (False, None),
                "release": lambda self: None,
            }
        )()
        fake_cv2 = type("cv2", (), {
            "VideoCapture": staticmethod(lambda p: mock_cap),
            "CAP_PROP_FPS": "fps",
            "CAP_PROP_FRAME_COUNT": "count",
            "CAP_PROP_FRAME_WIDTH": "w",
            "CAP_PROP_FRAME_HEIGHT": "h",
            "CAP_PROP_POS_FRAMES": "pos",
            "imwrite": staticmethod(lambda p, f: True),
        })()
        with patch("uar.skills.cv_skills.require_package", return_value=None):
            with patch.dict("sys.modules", {"cv2": fake_cv2}):
                with patch("pathlib.Path.exists", return_value=True):
                    from uar.skills.cv_skills import video_analyze
                    result = video_analyze(
                        _ctx({
                            "cv_video_path": "/tmp/test.mp4",
                            "cv_operation": "extract_frames",
                        })
                    )
        assert result["status"] == "completed"
        assert result["frame_count"] == 0

    def test_motion_detect_first_frame_fails(self):
        mock_cap = type(
            "Cap", (), {
                "isOpened": lambda self: True,
                "get": lambda self, p: {
                    "fps": 30, "count": 100, "w": 640, "h": 480
                }[p],
                "read": lambda self: (False, None),
                "release": lambda self: None,
            }
        )()
        fake_cv2 = type("cv2", (), {
            "VideoCapture": staticmethod(lambda p: mock_cap),
            "CAP_PROP_FPS": "fps",
            "CAP_PROP_FRAME_COUNT": "count",
            "CAP_PROP_FRAME_WIDTH": "w",
            "CAP_PROP_FRAME_HEIGHT": "h",
            "cvtColor": staticmethod(lambda img, code: img),
            "absdiff": staticmethod(lambda a, b: a),
            "threshold": staticmethod(
                lambda src, t, maxv, typ: (None, src)
            ),
            "countNonZero": staticmethod(lambda src: 0),
        })()
        with patch("uar.skills.cv_skills.require_package", return_value=None):
            with patch.dict("sys.modules", {"cv2": fake_cv2}):
                with patch("pathlib.Path.exists", return_value=True):
                    from uar.skills.cv_skills import video_analyze
                    result = video_analyze(
                        _ctx({
                            "cv_video_path": "/tmp/test.mp4",
                            "cv_operation": "motion_detect",
                        })
                    )
        assert result["status"] == "failed"
        assert "first frame" in result["error"].lower()

    def test_motion_detect_with_motion(self):
        call_count = 0

        def _read(self):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (True, "frame1")
            if call_count == 2:
                return (True, "frame2")
            return (False, None)

        mock_cap = type(
            "Cap", (), {
                "isOpened": lambda self: True,
                "get": lambda self, p: {
                    "fps": 30, "count": 3, "w": 640, "h": 480
                }[p],
                "read": _read,
                "release": lambda self: None,
            }
        )()
        fake_cv2 = type("cv2", (), {
            "VideoCapture": staticmethod(lambda p: mock_cap),
            "CAP_PROP_FPS": "fps",
            "CAP_PROP_FRAME_COUNT": "count",
            "CAP_PROP_FRAME_WIDTH": "w",
            "CAP_PROP_FRAME_HEIGHT": "h",
            "COLOR_BGR2GRAY": "gray",
            "THRESH_BINARY": "binary",
            "cvtColor": staticmethod(lambda img, code: img),
            "absdiff": staticmethod(lambda a, b: b),
            "threshold": staticmethod(
                lambda src, t, maxv, typ: (None, src)
            ),
            "countNonZero": staticmethod(lambda src: 1000),
        })()
        with patch("uar.skills.cv_skills.require_package", return_value=None):
            with patch.dict("sys.modules", {"cv2": fake_cv2}):
                with patch("pathlib.Path.exists", return_value=True):
                    from uar.skills.cv_skills import video_analyze
                    result = video_analyze(
                        _ctx({
                            "cv_video_path": "/tmp/test.mp4",
                            "cv_operation": "motion_detect",
                        })
                    )
        assert result["status"] == "completed"
        assert result["motion_frames"] > 0

    def test_histogram_read_fails(self):
        mock_cap = type(
            "Cap", (), {
                "isOpened": lambda self: True,
                "get": lambda self, p: {
                    "fps": 30, "count": 100, "w": 640, "h": 480
                }[p],
                "read": lambda self: (False, None),
                "release": lambda self: None,
            }
        )()
        fake_cv2 = type("cv2", (), {
            "VideoCapture": staticmethod(lambda p: mock_cap),
            "CAP_PROP_FPS": "fps",
            "CAP_PROP_FRAME_COUNT": "count",
            "CAP_PROP_FRAME_WIDTH": "w",
            "CAP_PROP_FRAME_HEIGHT": "h",
        })()
        with patch("uar.skills.cv_skills.require_package", return_value=None):
            with patch.dict("sys.modules", {"cv2": fake_cv2}):
                with patch("pathlib.Path.exists", return_value=True):
                    from uar.skills.cv_skills import video_analyze
                    result = video_analyze(
                        _ctx({
                            "cv_video_path": "/tmp/test.mp4",
                            "cv_operation": "histogram",
                        })
                    )
        assert result["status"] == "failed"
        assert "frame" in result["error"].lower()


class TestFaceRecognizeBranches:
    """face_recognize branches with mocked face_recognition."""

    def test_compare_missing_image(self):
        with patch("uar.skills.cv_skills.require_package", return_value=None):
            with patch.dict("sys.modules", {"face_recognition": type(
                "fr", (), {
                    "load_image_file": staticmethod(lambda p: None),
                    "face_encodings": staticmethod(lambda img: []),
                    "face_locations": staticmethod(lambda img: []),
                    "face_distance": staticmethod(lambda a, b: [0.5]),
                }
            )()}):
                with patch("pathlib.Path.exists", return_value=True):
                    from uar.skills.cv_skills import face_recognize
                    result = face_recognize(
                        _ctx({
                            "cv_image_path": "/tmp/a.jpg",
                            "cv_operation": "compare",
                            "cv_compare_path": "",
                        })
                    )
        assert result["status"] == "failed"
        assert "compare" in result["error"].lower()

    def test_compare_no_faces(self):
        with patch("uar.skills.cv_skills.require_package", return_value=None):
            with patch.dict("sys.modules", {"face_recognition": type(
                "fr", (), {
                    "load_image_file": staticmethod(lambda p: None),
                    "face_encodings": staticmethod(lambda img: []),
                    "face_locations": staticmethod(lambda img: []),
                    "face_distance": staticmethod(lambda a, b: [0.5]),
                }
            )()}):
                with patch("pathlib.Path.exists", return_value=True):
                    from uar.skills.cv_skills import face_recognize
                    result = face_recognize(
                        _ctx({
                            "cv_image_path": "/tmp/a.jpg",
                            "cv_operation": "compare",
                            "cv_compare_path": "/tmp/b.jpg",
                        })
                    )
        assert result["match"] is False
        assert result["reason"] == "No faces found in one or both images"
