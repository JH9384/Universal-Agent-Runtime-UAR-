"""Computer vision skills: OpenCV image processing and YOLO detection."""

import logging
from typing import Dict, Any

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext

logger = logging.getLogger(__name__)


@register_skill("opencv_process")
def opencv_process(ctx: PipelineContext) -> Dict[str, Any]:
    """OpenCV image processing.

    Metadata:
        cv_image_path:   path to input image
        cv_operation:    'grayscale', 'blur', 'edge', 'contour', 'resize'
        cv_params:       operation-specific params dict
    """
    import importlib.util
    if importlib.util.find_spec("cv2") is None:
        return {
            "status": "failed",
            "error": "OpenCV not installed. pip install opencv-python",
        }

    import cv2
    from pathlib import Path

    meta = ctx.goal.metadata or {}
    img_path = meta.get("cv_image_path", "")
    operation = meta.get("cv_operation", "grayscale")
    params = meta.get("cv_params", {})

    if not img_path or not Path(img_path).exists():
        return {"status": "failed", "error": f"Image not found: {img_path}"}

    try:
        img = cv2.imread(img_path)
        if img is None:
            return {
                "status": "failed",
                "error": f"Could not read image: {img_path}",
            }

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
            return {
                "status": "failed",
                "error": f"Unknown operation: {operation}",
            }

        out_path = params.get(
            "output_path", img_path.replace(".", "_processed.")
        )
        cv2.imwrite(out_path, out)

        return {
            "status": "completed",
            "operation": operation,
            "input_shape": list(img.shape),
            "output_path": out_path,
            "output_shape": list(out.shape),
        }
    except Exception as exc:
        logger.warning(f"cv_inference failed: {exc}")
        return {"status": "failed", "error": "Inference failed"}


@register_skill("yolo_detect")
def yolo_detect(ctx: PipelineContext) -> Dict[str, Any]:
    """Object detection with YOLO (ultralytics).

    Metadata:
        cv_image_path: path to input image
        cv_conf:       confidence threshold (default 0.25)
        cv_model:      model name (default 'yolov8n.pt')
    """
    import importlib.util
    if importlib.util.find_spec("ultralytics") is None:
        return {
            "status": "failed",
            "error": "ultralytics not installed. pip install ultralytics",
        }

    from ultralytics import YOLO
    from pathlib import Path

    meta = ctx.goal.metadata or {}
    img_path = meta.get("cv_image_path", "")
    conf = float(meta.get("cv_conf", 0.25))
    model_name = meta.get("cv_model", "yolov8n.pt")

    if not img_path or not Path(img_path).exists():
        return {"status": "failed", "error": f"Image not found: {img_path}"}

    try:
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
    except Exception as exc:
        logger.warning(f"yolo_detect failed: {exc}")
        return {"status": "failed", "error": "Detection failed"}
