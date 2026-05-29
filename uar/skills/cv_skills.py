"""Computer vision skills: OpenCV image processing and YOLO detection."""

from typing import Dict, Any

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.skill_utils import require_package, skill_guard


@register_skill("opencv_process")
@skill_guard("OpenCV processing")
def opencv_process(ctx: PipelineContext) -> Dict[str, Any]:
    """OpenCV image processing.

    Metadata:
        cv_image_path:   path to input image
        cv_operation:    'grayscale', 'blur', 'edge', 'contour', 'resize'
        cv_params:       operation-specific params dict
    """
    err = require_package("cv2", install_hint="pip install opencv-python")
    if err:
        return err

    import cv2
    from pathlib import Path

    meta = ctx.goal.metadata or {}
    img_path = meta.get("cv_image_path", "")
    operation = meta.get("cv_operation", "grayscale")
    params = meta.get("cv_params", {})

    if not img_path or not Path(img_path).exists():
        return {"status": "failed", "error": "Image not found"}

    img = cv2.imread(img_path)
    if img is None:
        return {"status": "failed", "error": "Could not read image"}

    if operation == "grayscale":
        out = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    elif operation == "blur":
        k = params.get("kernel", 5)
        out = cv2.GaussianBlur(img, (k, k), 0)
    elif operation == "edge":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        t1 = params.get("threshold1", 100)
        t2 = params.get("threshold2", 200)
        out = cv2.Canny(gray, t1, t2)
    elif operation == "contour":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 127, 255, 0)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
        )
        out = cv2.drawContours(img.copy(), contours, -1, (0, 255, 0), 2)
    elif operation == "resize":
        w = params.get("width", img.shape[1] // 2)
        h = params.get("height", img.shape[0] // 2)
        out = cv2.resize(img, (w, h))
    else:
        return {"status": "failed", "error": "Unknown operation"}

    out_path = params.get("output_path", img_path.replace(".", "_processed."))
    cv2.imwrite(out_path, out)

    return {
        "status": "completed",
        "operation": operation,
        "input_shape": list(img.shape),
        "output_path": out_path,
        "output_shape": list(out.shape),
    }


@register_skill("yolo_detect")
@skill_guard("YOLO detection")
def yolo_detect(ctx: PipelineContext) -> Dict[str, Any]:
    """Object detection with YOLO (ultralytics).

    Metadata:
        cv_image_path: path to input image
        cv_conf:       confidence threshold (default 0.25)
        cv_model:      model name (default 'yolov8n.pt')
    """
    err = require_package("ultralytics")
    if err:
        return err

    from ultralytics import YOLO
    from pathlib import Path

    meta = ctx.goal.metadata or {}
    img_path = meta.get("cv_image_path", "")
    conf = float(meta.get("cv_conf", 0.25))
    model_name = meta.get("cv_model", "yolov8n.pt")

    if not img_path or not Path(img_path).exists():
        return {"status": "failed", "error": "Image not found"}

    model = YOLO(model_name)
    results = model(img_path, conf=conf)
    detections = []
    for r in results:
        for box in r.boxes:
            detections.append({
                "class": int(box.cls),
                "class_name": model.names[int(box.cls)],
                "confidence": float(box.conf),
                "bbox": box.xyxy.tolist()[0],
            })

    return {
        "status": "completed",
        "model": model_name,
        "detections": detections,
        "count": len(detections),
    }


@register_skill("video_analyze")
@skill_guard("Video Analyze")
def video_analyze(ctx: PipelineContext) -> Dict[str, Any]:
    """Video analysis with frame extraction and motion detection.

    Uses OpenCV for frame-level processing and optionally moviepy for
    higher-level clip operations.

    Metadata:
        cv_video_path:  path to input video
        cv_operation:   'extract_frames', 'motion_detect',
                        'histogram', 'duration'
        cv_params:      operation-specific params dict
    """
    cv_err = require_package("cv2", install_hint="pip install opencv-python")
    if cv_err:
        return cv_err

    import cv2
    from pathlib import Path

    meta = ctx.goal.metadata or {}
    video_path = meta.get("cv_video_path", "")
    operation = meta.get("cv_operation", "extract_frames")
    params = meta.get("cv_params", {})

    if not video_path or not Path(video_path).exists():
        return {"status": "failed", "error": "Video not found"}

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"status": "failed", "error": "Could not open video"}

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0

    if operation == "extract_frames":
        interval = int(params.get("interval", 1))
        max_frames = int(params.get("max_frames", 10))
        frames_dir = params.get("output_dir", ".")
        Path(frames_dir).mkdir(parents=True, exist_ok=True)

        saved = []
        for i in range(0, min(frame_count, max_frames * interval), interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret:
                break
            out_path = str(Path(frames_dir) / f"frame_{i:04d}.jpg")
            cv2.imwrite(out_path, frame)
            saved.append(out_path)
        cap.release()

        return {
            "status": "completed",
            "operation": operation,
            "saved_frames": saved,
            "frame_count": len(saved),
            "video_duration": round(duration, 2),
        }

    elif operation == "motion_detect":
        threshold = int(params.get("threshold", 25))
        min_area = int(params.get("min_area", 500))
        ret, prev = cap.read()
        if not ret:
            cap.release()
            return {"status": "failed", "error": "Could not read first frame"}
        prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
        motion_frames = 0
        total_motion = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(prev_gray, gray)
            _, diff = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
            motion_pixels = cv2.countNonZero(diff)
            total_motion += motion_pixels
            if motion_pixels > min_area:
                motion_frames += 1
            prev_gray = gray

        cap.release()
        return {
            "status": "completed",
            "operation": operation,
            "motion_frames": motion_frames,
            "total_motion_pixels": total_motion,
            "video_duration": round(duration, 2),
            "fps": round(fps, 2),
        }

    elif operation == "histogram":
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return {"status": "failed", "error": "Could not read frame"}
        colors = ("b", "g", "r")
        hist_data = {}
        for i, col in enumerate(colors):
            hist = cv2.calcHist([frame], [i], None, [256], [0, 256])
            hist_data[col] = hist.flatten().tolist()
        return {
            "status": "completed",
            "operation": operation,
            "histograms": hist_data,
            "frame_shape": list(frame.shape),
        }

    elif operation == "duration":
        cap.release()
        return {
            "status": "completed",
            "operation": operation,
            "duration_sec": round(duration, 2),
            "frame_count": frame_count,
            "fps": round(fps, 2),
            "resolution": {"width": width, "height": height},
        }

    cap.release()
    return {"status": "failed", "error": "Unknown operation"}


@register_skill("face_recognize")
@skill_guard("Face Recognize")
def face_recognize(ctx: PipelineContext) -> Dict[str, Any]:
    """Face recognition using face_recognition library.

    Metadata:
        cv_image_path:     path to image with faces
        cv_compare_path:   optional path to compare image
        cv_operation:      'detect', 'encode', 'compare'
        cv_tolerance:      match tolerance for compare (default 0.6)
    """
    err = require_package("face_recognition")
    if err:
        return err

    import face_recognition
    from pathlib import Path

    meta = ctx.goal.metadata or {}
    img_path = meta.get("cv_image_path", "")
    operation = meta.get("cv_operation", "detect")
    tolerance = float(meta.get("cv_tolerance", 0.6))

    if not img_path or not Path(img_path).exists():
        return {"status": "failed", "error": "Image not found"}

    image = face_recognition.load_image_file(img_path)

    if operation == "detect":
        face_locations = face_recognition.face_locations(image)
        return {
            "status": "completed",
            "operation": operation,
            "face_count": len(face_locations),
            "face_locations": [
                {"top": t, "right": r, "bottom": b, "left": l}
                for t, r, b, l in face_locations
            ],
        }

    elif operation == "encode":
        face_locations = face_recognition.face_locations(image)
        encodings = face_recognition.face_encodings(image, face_locations)
        return {
            "status": "completed",
            "operation": operation,
            "face_count": len(encodings),
            "encodings": [e.tolist() for e in encodings],
        }

    elif operation == "compare":
        compare_path = meta.get("cv_compare_path", "")
        if not compare_path or not Path(compare_path).exists():
            return {"status": "failed", "error": "Compare image not found"}

        compare_image = face_recognition.load_image_file(compare_path)
        img_encodings = face_recognition.face_encodings(image)
        cmp_encodings = face_recognition.face_encodings(compare_image)

        if not img_encodings or not cmp_encodings:
            return {
                "status": "completed",
                "operation": operation,
                "match": False,
                "distance": None,
                "reason": "No faces found in one or both images",
            }

        distances = face_recognition.face_distance(
            cmp_encodings, img_encodings[0]
        )
        match = any(d <= tolerance for d in distances)
        return {
            "status": "completed",
            "operation": operation,
            "match": match,
            "distance": float(min(distances)),
            "tolerance": tolerance,
        }

    return {"status": "failed", "error": "Unknown operation"}
