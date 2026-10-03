"""
frame_renderer.py - Frame-by-frame crop renderer.
Baca video + timeline, crop tiap frame, pipe ke FFmpeg.
"""
import cv2
import subprocess
import numpy as np
from pathlib import Path
from typing import List, Tuple


def interpolate_x(frame_idx: int, timeline: List[Tuple[float, int]]) -> int:
    """
    Interpolate x untuk frame tertentu.
    timeline: list of (time_sec, x)
    """
    if not timeline:
        return 0
    if frame_idx <= 0:
        return timeline[0][1]
    
    # Cari segment
    for i in range(len(timeline) - 1):
        t1, x1 = timeline[i]
        t2, x2 = timeline[i + 1]
        if t1 <= frame_idx <= t2:
            ratio = (frame_idx - t1) / max(t2 - t1, 1)
            return int(x1 + ratio * (x2 - x1))
    
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
