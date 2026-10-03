"""
face_tracker.py - Deteksi & tracking wajah pakai YuNet (OpenCV).
Model auto-download ke models/face_detection_yunet_2023mar.onnx
"""
from __future__ import annotations
import urllib.request
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import numpy as np
import cv2


YUNET_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/"
    "models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"


@dataclass
class Face:
    x: int
    y: int
    w: int
    h: int
    score: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def area(self) -> int:
        return self.w * self.h


def ensure_yunet_model(models_dir: Path) -> Path:
    models_dir.mkdir(parents=True, exist_ok=True)
    target = models_dir / YUNET_FILENAME
    if target.exists() and target.stat().st_size > 100_000:
        return target
    print(f"   ⬇️  Download YuNet model (~230KB)...")
    try:
        urllib.request.urlretrieve(YUNET_URL, target)
    except Exception as e:
        raise RuntimeError(f"Gagal download YuNet: {e}")
    return target


class FaceTracker:
    def __init__(self, model_path: Path, score_thresh: float = 0.6):
        self.detector = cv2.FaceDetectorYN.create(
            str(model_path), "", (320, 320), score_thresh, 0.3, 5000
        )
        self._size = (320, 320)

    def _prepare(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if (w, h) != self._size:
            self.detector.setInputSize((w, h))
            self._size = (w, h)
        return frame

    def detect(self, frame: np.ndarray) -> list[Face]:
        frame = self._prepare(frame)
        _, raw = self.detector.detect(frame)
        if raw is None:
            return []
        faces = []
        for row in raw:
            x, y, w, h = row[:4].astype(int)
            score = float(row[-1])
            faces.append(Face(x, y, w, h, score))
        return faces


def pick_dominant(faces: list[Face], frame_w: int, frame_h: int) -> Optional[Face]:
    if not faces:
        return None
    cx_frame = frame_w / 2
    best, best_score = None, -1e9
    for f in faces:
        dist = abs(f.cx - cx_frame) / frame_w
        score = f.area * (1 - 0.5 * dist) * f.score
        if score > best_score:
            best, best_score = f, score
    return best


def pick_multi_center(faces: list[Face], frame_w: int) -> Optional[float]:
    if not faces:
        return None
    total = sum(f.area for f in faces)
    if total == 0:
        return None
    return sum(f.cx * f.area for f in faces) / total


def auto_choose_mode(faces_per_sample: list[list[Face]]) -> str:
    counts = [len(f) for f in faces_per_sample if f]
    if not counts:
        return "single"
    avg = sum(counts) / len(counts)
    stable = sum(1 for c in counts if c >= 2) / len(counts)
    if avg >= 1.8 and stable >= 0.6:
        return "multi"
    return "single"
