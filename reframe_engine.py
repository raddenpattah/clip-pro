"""
reframe_engine.py - Generate crop timeline + FFmpeg sendcmd script.
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import cv2

from face_tracker import (
    FaceTracker, Face, pick_dominant, pick_multi_center, auto_choose_mode,
    ensure_yunet_model,
)


@dataclass
class CropSample:
    t: float
    x: int
    face_seen: bool


def _grab_frames(video_path: Path, t_start: float, t_end: float, sample_fps: float):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Ga bisa buka video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, int(round(fps / sample_fps)))

    cap.set(cv2.CAP_PROP_POS_MSEC, t_start * 1000)
    frame_idx = 0
    while True:
        pos_msec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        if pos_msec >= t_end:
            break
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % step == 0:
            yield pos_msec - t_start, frame
        frame_idx += 1
    cap.release()


def build_crop_timeline(
    video_path: Path,
    t_start: float,
    t_end: float,
    models_dir: Path,
    sample_fps: int = 5,
    tracking: str = "auto",
    score_thresh: float = 0.6,
    fallback: str = "center",
) -> list[CropSample]:
    model_path = ensure_yunet_model(models_dir)
    tracker = FaceTracker(model_path, score_thresh=score_thresh)

    samples: list[tuple[float, list[Face], int, int]] = []
    for t_rel, frame in _grab_frames(video_path, t_start, t_end, sample_fps):
        h, w = frame.shape[:2]
        faces = tracker.detect(frame)
        samples.append((t_rel, faces, w, h))

    if not samples:
        return []

    fw, fh = samples[0][2], samples[0][3]

    mode = tracking
    if tracking == "auto":
        mode = auto_choose_mode([s[1] for s in samples])

    crop_w = int(fh * 9 / 16)
    max_x = max(0, fw - crop_w)
    center_x = max_x // 2

    raw: list[tuple[float, int, bool]] = []
    last_x = center_x
    for t_rel, faces, _, _ in samples:
        if not faces:
            raw.append((t_rel, last_x, False))
            continue
        if mode == "multi":
            cx = pick_multi_center(faces, fw)
        else:
            # Mode single: pilih dominan, TAPI kalau ada 2+ wajah
            # berjauhan (>40% frame width), fallback ke multi-center
            # biar ga celah kosong di tengah.
            dom = pick_dominant(faces, fw, fh)
            if dom and len(faces) >= 2:
                threshold = fw * 0.60
                far_apart = any(
                    abs(f.cx - dom.cx) > threshold
                    for f in faces if f is not dom
                )
                if far_apart:
                    multi_cx = pick_multi_center(faces, fw)
                    cx = multi_cx if multi_cx is not None else dom.cx
                else:
                    cx = dom.cx
            else:
                cx = dom.cx if dom else None

        if cx is None:
            raw.append((t_rel, last_x, False))
            continue

        x = int(round(cx - crop_w / 2))
        x = max(0, min(max_x, x))
        last_x = x
        raw.append((t_rel, x, True))

    any_face = any(r[2] for r in raw)
    if not any_face and fallback == "center":
        return [CropSample(t, center_x, False) for t, _, _ in raw]

    return [CropSample(t, x, seen) for t, x, seen in raw]


def smooth_timeline(
    timeline: list[CropSample],
    alpha: float = 0.3,
    deadzone_px: int = 40,
) -> list[CropSample]:
    if not timeline:
        return []
    out = []
    ema = float(timeline[0].x)
    last_applied = timeline[0].x
    for s in timeline:
        ema = alpha * s.x + (1 - alpha) * ema
        if abs(ema - last_applied) >= deadzone_px:
            last_applied = int(round(ema))
        out.append(CropSample(s.t, last_applied, s.face_seen))
    return out


def write_sendcmd(timeline: list[CropSample], path: Path) -> None:
    lines = []
    for s in timeline:
        lines.append(f"{s.t:.3f} crop x {s.x};")
    path.write_text("\n".join(lines) + "\n")


def build_crop_filter(
    fw: int,
    fh: int,
    sendcmd_path: Optional[Path],
    smart: bool,
) -> str:
    if not smart or sendcmd_path is None:
        return "crop=ih*9/16:ih"

    p = str(sendcmd_path).replace("\\", "/").replace(":", "\\:")
    crop_w = int(fh * 9 / 16)
    center_x = max(0, (fw - crop_w) // 2)
    return (
        f"crop=w={crop_w}:h={fh}:x={center_x}:y=0,"
        f"sendcmd=f='{p}'"
    )


def prepare_smart_crop(
    video_path: Path,
    clip_start: float,
    clip_end: float,
    models_dir: Path,
    temp_dir: Path,
    out_stem: str,
    cfg: dict,
) -> tuple[str, bool]:
    if not cfg.get("reframe", {}).get("enabled", False):
        return "crop=ih*9/16:ih", False

    try:
        cap = cv2.VideoCapture(str(video_path))
        fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        if fw == 0 or fh == 0:
            return "crop=ih*9/16:ih", False

        rcfg = cfg["reframe"]
        timeline = build_crop_timeline(
            video_path=video_path,
            t_start=clip_start,
            t_end=clip_end,
            models_dir=models_dir,
            sample_fps=rcfg.get("sample_fps", 5),
            tracking=rcfg.get("tracking", "auto"),
            fallback=rcfg.get("fallback", "center"),
        )

        if not timeline:
            print("   ⚠️  Smart reframe: timeline kosong, fallback static")
            return "crop=ih*9/16:ih", False

        sm = rcfg.get("smoothing", {})
        timeline = smooth_timeline(
            timeline,
            alpha=sm.get("alpha", 0.3),
            deadzone_px=sm.get("deadzone_px", 40),
        )

        sendcmd_path = temp_dir / f"{out_stem}.sendcmd.txt"
        write_sendcmd(timeline, sendcmd_path)

        vf_crop = build_crop_filter(fw, fh, sendcmd_path, smart=True)
        faces_seen = sum(1 for s in timeline if s.face_seen)
        print(f"   🎯 Smart reframe: {len(timeline)} samples, {faces_seen} berisi wajah")
        return vf_crop, True

    except Exception as e:
        print(f"   ⚠️  Smart reframe gagal ({e}), fallback static")
        return "crop=ih*9/16:ih", False
