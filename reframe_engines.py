"""
reframe_engines.py - Engine logic buat pilih crop X berdasarkan mode.

Setiap engine nerima list wajah + ukuran frame, return crop X (center)
atau None kalau ga ada wajah.

Config di config.yaml:
  reframe:
    engine: multi    # single | dual | multi | auto
"""
from __future__ import annotations
from typing import Optional, List

from face_tracker import (
    Face, pick_dominant, pick_multi_center, auto_choose_mode,
)


def engine_single(faces: List[Face], fw: int, fh: int) -> Optional[float]:
    """
    Engine 1 orang (talking head).
    Pilih wajah dominan, fokus ke dia. Ga ada fallback multi.
    """
    dom = pick_dominant(faces, fw, fh)
    return dom.cx if dom else None


def engine_dual(faces: List[Face], fw: int, fh: int,
                threshold_ratio: float = 0.30) -> Optional[float]:
    """
    Engine 2 orang (interview/podcast 2 orang).
    - Ambil 2 wajah terbesar.
    - Kalau berjauhan (>30% frame width), crop di antara mereka.
    - Kalau berdekatan, fokus ke dominan.
    """
    if not faces:
        return None
    if len(faces) == 1:
        return faces[0].cx

    top2 = sorted(faces, key=lambda f: -f.area)[:2]
    dist = abs(top2[0].cx - top2[1].cx)
    threshold = fw * threshold_ratio

    if dist > threshold:
        # Crop di rata-rata 2 wajah (biar dua-duanya masuk)
        return (top2[0].cx + top2[1].cx) / 2
    else:
        # Berdekatan, fokus ke dominan
        dom = pick_dominant(faces, fw, fh)
        return dom.cx if dom else top2[0].cx


def engine_multi(faces: List[Face], fw: int, fh: int,
                 threshold_ratio: float = 0.20) -> Optional[float]:
    """
    Engine 3-4 orang (podcast/panel).
    - Pilih dominan.
    - Kalau ada wajah lain yang jaraknya >20% frame width, fallback multi_center.
    """
    if not faces:
        return None

    dom = pick_dominant(faces, fw, fh)
    if not dom:
        return None

    if len(faces) >= 2:
        threshold = fw * threshold_ratio
        far_apart = any(
            abs(f.cx - dom.cx) > threshold
            for f in faces if f is not dom
        )
        if far_apart:
            multi_cx = pick_multi_center(faces, fw)
            return multi_cx if multi_cx is not None else dom.cx

    return dom.cx


def engine_auto(faces: List[Face], fw: int, fh: int) -> Optional[float]:
    """
    Engine auto: pilih single/dual/multi berdasarkan jumlah wajah stabil.
    Fallback kalau user ga yakin tipe video-nya.
    """
    if not faces:
        return None

    if len(faces) == 1:
        return engine_single(faces, fw, fh)

    if len(faces) == 2:
        # Cek jarak, kalau jauh pake dual, kalau deket pake single
        top2 = sorted(faces, key=lambda f: -f.area)[:2]
        dist = abs(top2[0].cx - top2[1].cx)
        if dist > fw * 0.20:
            return engine_dual(faces, fw, fh)
        return engine_single(faces, fw, fh)

    # 3+ wajah -> multi
    return engine_multi(faces, fw, fh)


# ===== DISPATCHER =====

ENGINES = {
    "single": engine_single,
    "dual": engine_dual,
    "multi": engine_multi,
    "auto": engine_auto,
}


def get_engine(name: str):
    """Return engine function berdasarkan nama. Default: multi."""
    return ENGINES.get(name, engine_multi)


def pick_crop_center(faces: List[Face], fw: int, fh: int,
                     engine_name: str = "multi") -> Optional[float]:
    """
    High-level: pilih engine, return crop center X.
    Ini yang dipanggil dari reframe_engine.py.
    """
    engine = get_engine(engine_name)
    return engine(faces, fw, fh)
