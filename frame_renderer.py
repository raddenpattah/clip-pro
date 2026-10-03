"""
frame_renderer.py - Frame-by-frame crop renderer.
Baca video + timeline, crop tiap frame, pipe ke FFmpeg.
"""
import cv2
import subprocess
import numpy as np
from pathlib import Path
from typing import List, Tuple


def _catmull_rom(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    """
    Catmull-Rom spline interpolation.
    p0, p1, p2, p3: 4 control points
    t: 0.0 to 1.0 (posisi antara p1 dan p2)
    """
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2 * p1) +
        (-p0 + p2) * t +
        (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
        (-p0 + 3 * p1 - 3 * p2 + p3) * t3
    )


def interpolate_x(frame_idx: int, timeline: List[Tuple[float, int]]) -> int:
    """
    Interpolate x untuk frame tertentu pakai Catmull-Rom spline.
    timeline: list of (frame_idx, x) — sorted by frame_idx
    """
    if not timeline:
        return 0
    if len(timeline) == 1:
        return timeline[0][1]
    if frame_idx <= timeline[0][0]:
        return timeline[0][1]
    if frame_idx >= timeline[-1][0]:
        return timeline[-1][1]

    # Cari segment (i, i+1) di mana frame_idx berada
    for i in range(len(timeline) - 1):
        f1, x1 = timeline[i]
        f2, x2 = timeline[i + 1]
        if f1 <= frame_idx <= f2:
            # Hitung t (0.0 - 1.0)
            t = (frame_idx - f1) / max(f2 - f1, 1)

            # Ambil control points
            # p1 = x1, p2 = x2
            # p0 = titik sebelum x1 (atau x1 kalau ga ada)
            # p3 = titik setelah x2 (atau x2 kalau ga ada)
            p1 = float(x1)
            p2 = float(x2)
            p0 = float(timeline[i - 1][1]) if i > 0 else p1
            p3 = float(timeline[i + 2][1]) if i + 2 < len(timeline) else p2

            # Spline interpolation
            result = _catmull_rom(p0, p1, p2, p3, t)
            return int(round(result))

    return timeline[-1][1]



def render_frame_by_frame(
    video_path: Path,
    output_path: Path,
    timeline_sec: List[Tuple[float, int]],
    output_w: int = 1080,
    output_h: int = 1920,
    fps: int = 30,
    audio_from_source: bool = True,
    crf: int = 23,
    preset: str = "ultrafast",
) -> None:
    """
    Render video dengan crop dinamis frame-by-frame.
    
    Args:
        video_path: source video
        output_path: output video
        timeline_sec: [(time_sec, x), ...] — crop X position per waktu
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Ga bisa buka video: {video_path}")
    
    in_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    in_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    in_fps = cap.get(cv2.CAP_PROP_FPS) or fps
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Crop width di source (9:16 aspect dari height)
    crop_w = int(in_h * 9 / 16)
    max_x = max(0, in_w - crop_w)
    
    # Convert timeline dari detik ke frame
    timeline_frames = [(int(t * in_fps), x) for t, x in timeline_sec]
    if not timeline_frames:
        timeline_frames = [(0, max_x // 2)]
    
    # FFmpeg command
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{output_w}x{output_h}", "-r", str(in_fps),
        "-i", "pipe:0",
    ]
    
    if audio_from_source:
        cmd.extend(["-i", str(video_path), "-map", "0:v", "-map", "1:a"])
    else:
        cmd.extend(["-map", "0:v"])
    
    cmd.extend([
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(output_path),
    ])
    
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )
    
    frame_idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            x = interpolate_x(frame_idx, timeline_frames)
            x = max(0, min(max_x, x))
            
            cropped = frame[:, x:x + crop_w]
            if cropped.shape[1] != crop_w:
                # Fallback: pad kalau crop keluar batas
                cropped = cv2.copyMakeBorder(
                    cropped, 0, 0, 0, crop_w - cropped.shape[1],
                    cv2.BORDER_CONSTANT, value=(0, 0, 0)
                )
            
            resized = cv2.resize(
                cropped, (output_w, output_h),
                interpolation=cv2.INTER_LINEAR
            )
            
            proc.stdin.write(resized.tobytes())
            frame_idx += 1
    finally:
        cap.release()
        proc.stdin.close()
        proc.wait()
