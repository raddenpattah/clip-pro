"""
Keyword Detector - cari momen di video yang mengandung kata kunci
dengan SMART BOUNDARIES + PRIORITAS keyword.
"""
import re
from typing import List, Dict

# ====== KONFIGURASI ======
# Keyword + bobot prioritas (makin tinggi, makin diprioritasin)
KEYWORD_WEIGHTS = {
    "rahasia": 10,
    "jangan lupa": 10,
    "penting": 10,
    "100 juta": 9,
    "miliar": 9,
    "tips": 8,
    "trik": 8,
    "hack": 8,
    "cara": 6,
    "gratis": 6,
    "sukses": 6,
    "gagal": 6,
    "kesimpulan": 5,
    "intinya": 5,
    "kuncinya": 5,
    "pertama": 4,
    "kedua": 4,
    "ketiga": 4,
    "terakhir": 4,
}

CONTEXT_BEFORE = 5
TARGET_DURATION = 45
TOLERANCE = 5
MIN_DURATION = 30
MAX_DURATION = 60
# =========================


def find_keyword_hits(segments: List[Dict], keywords: Dict[str, int] = None) -> List[Dict]:
    """Cari segment yang mengandung keyword, dengan bobot prioritas."""
    if keywords is None:
        keywords = KEYWORD_WEIGHTS

    kw_lower = {k.lower(): w for k, w in keywords.items()}
    hits = []

    for idx, seg in enumerate(segments):
        text_lower = seg["text"].lower()
        for kw, weight in kw_lower.items():
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, text_lower):
                hits.append({
                    "keyword": kw,
                    "weight": weight,
                    "time": seg["start"],
                    "text": seg["text"],
                    "segment_idx": idx,
                })

    # Dedup per segment — ambil keyword dengan bobot tertinggi
    best_per_seg = {}
    for h in hits:
        idx = h["segment_idx"]
        if idx not in best_per_seg or h["weight"] > best_per_seg[idx]["weight"]:
            best_per_seg[idx] = h

    return list(best_per_seg.values())


def find_natural_end(segments: List[Dict], target_end: float,
                     min_end: float, max_end: float) -> float:
    """Cari titik potong natural paling dekat dengan target_end."""
    candidates = [s["end"] for s in segments if min_end <= s["end"] <= max_end]
    if not candidates:
        return target_end
    return min(candidates, key=lambda x: abs(x - target_end))


def make_clips_from_hits(
    hits: List[Dict],
    segments: List[Dict],
    total_duration: float,
    target_duration: int = TARGET_DURATION,
    max_clips: int = 5,
) -> List[Dict]:
    """Bikin clip ranges dengan GREEDY + SMART OVERLAP HANDLING.
    
    Logika:
    1. Sort hits by weight DESC
    2. Ambil hit terbaik, bikin klip-nya
    3. Hit berikutnya: coba bikin klip, kalau overlap → SKIP
    4. Terus sampe max_clips atau hits abis
    """
    hits_sorted = sorted(hits, key=lambda h: (-h["weight"], h["time"]))

    clips = []
    for h in hits_sorted:
        if len(clips) >= max_clips:
            break

        start = max(0, h["time"] - CONTEXT_BEFORE)
        target_end = start + target_duration
        min_end = max(start + MIN_DURATION, target_end - TOLERANCE)
        max_end = min(total_duration, start + MAX_DURATION, target_end + TOLERANCE)

        # Kalau gak ada ruang (video abis), skip
        if max_end - start < MIN_DURATION:
            continue

        end = find_natural_end(segments, target_end, min_end, max_end)

        # Cek overlap dengan klip yang udah ada
        overlap = False
        for c in clips:
            # Overlap kalau range saling bersinggungan
            if start < c["end"] and end > c["start"]:
                overlap = True
                break

        if overlap:
            continue

        clips.append({
            "start": start,
            "end": end,
            "duration": end - start,
            "reason": f"keyword: {h['keyword']} (weight={h['weight']})",
            "weight": h["weight"],
        })

    clips.sort(key=lambda c: c["start"])
    return clips


if __name__ == "__main__":
    test_segments = [
        {"start": 0.0,   "end": 4.5,   "text": "Halo semuanya", "words": []},
        {"start": 4.5,   "end": 8.2,   "text": "Hari ini gue mau kasih tips penting", "words": []},
        {"start": 8.2,   "end": 12.0,  "text": "Tentang cara cari 100 juta dari AI", "words": []},
        {"start": 12.0,  "end": 16.5,  "text": "Langsung aja ya", "words": []},
        {"start": 16.5,  "end": 21.0,  "text": "Pertama, kalian harus tau", "words": []},
        {"start": 21.0,  "end": 26.0,  "text": "Apa itu AI sebenernya", "words": []},
        {"start": 26.0,  "end": 31.5,  "text": "Dan gimana cara pakainya", "words": []},
        {"start": 31.5,  "end": 36.0,  "text": "Rahasia pertama adalah", "words": []},
        {"start": 36.0,  "end": 41.0,  "text": "Fokus ke satu skill dulu", "words": []},
        {"start": 41.0,  "end": 46.0,  "text": "Jangan kebanyakan cabang", "words": []},
        {"start": 46.0,  "end": 50.5,  "text": "Itu tips dari gue", "words": []},
    ]

    hits = find_keyword_hits(test_segments)
    print(f"Ketemu {len(hits)} keyword hit (after dedup):")
    for h in sorted(hits, key=lambda x: -x["weight"]):
        print(f"  w={h['weight']:2d} [{h['time']:6.2f}s] '{h['keyword']}'")

    print("\nClip ranges:")
    clips = make_clips_from_hits(hits, test_segments, total_duration=60, max_clips=5)
    for c in clips:
        print(f"  [{c['start']:6.2f} - {c['end']:6.2f}] durasi={c['duration']:.1f}s | {c['reason']}")
