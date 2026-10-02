"""
Dictionary Manager - normalisasi transkrip pakai kamus + auto-log kata baru
"""
import json
import re
from pathlib import Path
from typing import List, Dict
from datetime import datetime


DICT_DIR = Path(__file__).parent / "dictionary"
DICT_PATH = DICT_DIR / "kamus.json"
LOG_PATH = DICT_DIR / "unknown_words.log"


# Kata umum Indonesia (biar gak dianggap "aneh")
COMMON_WORDS = {
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dengan", "ini", "itu",
    "ada", "tidak", "bukan", "sudah", "belum", "akan", "bisa", "harus", "mau",
    "saya", "kamu", "dia", "kami", "kita", "mereka", "kalian", "gue", "lu",
    "apa", "siapa", "kapan", "dimana", "kemana", "kenapa", "bagaimana",
    "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh",
    "hari", "bulan", "tahun", "jam", "menit", "detik", "waktu", "sekarang",
    "baik", "bagus", "jelek", "besar", "kecil", "panjang", "pendek",
    "banyak", "sedikit", "semua", "setiap", "beberapa", "lain", "sama", "beda",
    "video", "konten", "channel", "subscriber", "view", "like", "share",
    "uang", "duit", "juta", "miliar", "ribu", "rupiah", "dollar", "dolar",
    "cara", "tips", "trik", "rahasia", "penting", "gratis", "sukses", "gagal",
    "bisnis", "kerja", "usaha", "produk", "jual", "beli", "untung", "rugi",
    "orang", "teman", "keluarga", "anak", "istri", "suami", "saudara",
    "makan", "minum", "tidur", "jalan", "datang", "pergi", "pulang",
    "lihat", "dengar", "bicara", "ngomong", "tanya", "jawab", "bilang",
    "mulai", "selesai", "lanjut", "stop", "berhenti", "jalan", "buat",
    "sangat", "banget", "amat", "agak", "cukup", "terlalu", "kurang",
    "juga", "saja", "cuma", "hanya", "masih", "pernah", "selalu", "sering",
    "kadang", "mungkin", "pasti", "tentu", "jelas", "benar", "salah",
    "kalau", "jika", "ketika", "saat", "setelah", "sebelum", "sampai",
    "tapi", "tetapi", "namun", "karena", "sebab", "jadi", "makanya",
    "oh", "oke", "ok", "sip", "mantap", "keren", "hebat", "bagus",
    "belajar", "ajar", "tahu", "tau", "paham", "ngerti", "mengerti",
    "buat", "bikin", "cipta", "karya", "hasil", "proses", "bikin",
    "mudah", "susah", "sulit", "gampang", "cepat", "lambat", "pelan",
    "pertama", "kedua", "ketiga", "keempat", "kelima", "terakhir",
    "nah", "kan", "lah", "sih", "tuh", "deh", "dong", "yah", "ya",
    "bagian", "bagi", "kasih", "beri", "ambil", "pakai", "gunakan",
    "tahu", "lihat", "dengar", "rasa", "pikir", "mikir", "coba", "coba",
    "tentang", "soal", "hal", "masalah", "solusi", "jalan", "cara",
    "kalian", "kita", "mereka", "kamu", "saya", "aku", "gue",
    "teman-teman", "teman", "bro", "sis", "guys", "semua",
}


def load_dictionary(path: Path = DICT_PATH) -> Dict:
    """Load kamus dari JSON."""
    if not path.exists():
        print(f"⚠️  Kamus gak ada di {path}, bikin kosong")
        DICT_DIR.mkdir(parents=True, exist_ok=True)
        default = {
            "replacements": {},
            "filler_words": [],
            "brand_capitalize": [],
        }
        save_dictionary(default, path)
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_dictionary(kamus: Dict, path: Path = DICT_PATH) -> None:
    """Save kamus ke JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(kamus, f, ensure_ascii=False, indent=2)


def apply_normalization(text: str, kamus: Dict) -> str:
    """Apply replacements + filler removal + brand capitalize ke teks."""
    if not text:
        return text

    # 1. Replacements (typo -> benar) - case insensitive
    for typo, fix in kamus.get("replacements", {}).items():
        pattern = re.compile(re.escape(typo), re.IGNORECASE)
        text = pattern.sub(fix, text)

    # 2. Brand capitalize
    for brand in kamus.get("brand_capitalize", []):
        pattern = re.compile(re.escape(brand), re.IGNORECASE)
        text = pattern.sub(brand, text)

    # 3. Filler words - hapus dengan word boundary
    for filler in kamus.get("filler_words", []):
        pattern = re.compile(r'\b' + re.escape(filler) + r'\b', re.IGNORECASE)
        text = pattern.sub("", text)

    # 4. Rapikan spasi & tanda baca ganda
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s+([.,!?])', r'\1', text)
    # Hapus koma/titik ganda atau kombinasi aneh
    text = re.sub(r'[,]{2,}', ',', text)
    text = re.sub(r'[.]{2,}', '.', text)
    text = re.sub(r',\s*\.', '.', text)
    text = re.sub(r'\.\s*,', '.', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    return text


def normalize_segments(segments: List[Dict], kamus: Dict) -> List[Dict]:
    """Normalize semua segment. Return yang baru (gak modif aslinya)."""
    normalized = []
    for seg in segments:
        new_seg = dict(seg)
        new_seg["text"] = apply_normalization(seg["text"], kamus)

        if seg.get("words"):
            new_words = []
            for w in seg["words"]:
                new_w = dict(w)
                new_w["word"] = apply_normalization(w["word"], kamus)
                if new_w["word"]:
                    new_words.append(new_w)
            new_seg["words"] = new_words

        normalized.append(new_seg)
    return normalized


def find_unknown_words(segments: List[Dict], kamus: Dict,
                       min_frequency: int = 2) -> Dict[str, int]:
    """
    Deteksi kata aneh (muncul >= min_frequency, bukan kata umum, gak di kamus).
    """
    known = set()
    for typo, fix in kamus.get("replacements", {}).items():
        known.add(typo.lower())
        known.add(fix.lower())
    for brand in kamus.get("brand_capitalize", []):
        known.add(brand.lower())

    counts = {}
    for seg in segments:
        words = re.findall(r'\b[a-zA-Z]+\b', seg["text"])
        for w in words:
            wl = w.lower()
            if len(wl) < 4:
                continue
            if wl in COMMON_WORDS:
                continue
            if wl in known:
                continue
            if not re.search(r'[aiueo]', wl):  # no vokal = noise
                continue
            counts[wl] = counts.get(wl, 0) + 1

    # Filter by min frequency
    return {w: c for w, c in counts.items() if c >= min_frequency}


def log_unknown_words(unknown: Dict[str, int], video_name: str,
                      path: Path = LOG_PATH) -> int:
    """Append kata aneh ke log. Return jumlah yang di-log."""
    if not unknown:
        return 0

    sorted_words = sorted(unknown.items(), key=lambda x: -x[1])
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [f"\n[{timestamp}] Video: {video_name}"]
    for word, freq in sorted_words:
        lines.append(f"  -> \"{word}\" (muncul {freq}x)")

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return len(sorted_words)


if __name__ == "__main__":
    print("=== Test Kamus ===")
    kamus = load_dictionary()
    print(f"Replacements: {len(kamus.get('replacements', {}))}")
    print(f"Filler: {len(kamus.get('filler_words', []))}")
    print(f"Brand: {len(kamus.get('brand_capitalize', []))}")

    test_text = "Halo bro, ini tesuara untuk aplikasi TripFolga, eee gitu kan. Kita pakai tiktok dan youtube."
    print(f"\nAsli:   {test_text}")
    print(f"Bersih: {apply_normalization(test_text, kamus)}")

    print("\n=== Test Unknown Detection ===")
    test_segments = [
        {"start": 0, "end": 5, "text": "Halo semuanya qwerty qwerty asdfg zxcvb", "words": []},
        {"start": 5, "end": 10, "text": "Ini qwerty lagi dan asdfg", "words": []},
    ]
    unknown = find_unknown_words(test_segments, kamus, min_frequency=2)
    print(f"Unknown (freq >= 2): {unknown}")

    print("\n=== Test Auto-Log ===")
    n = log_unknown_words(unknown, "test_video.mp4")
    print(f"Logged {n} words")
