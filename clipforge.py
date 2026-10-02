#!/usr/bin/env python3
"""
ClipForge - Auto video cutter & reframer 16:9 -> 9:16
"""
import os
import sys
import json
import subprocess
import yaml
from pathlib import Path
from faster_whisper import WhisperModel
from keyword_detector import find_keyword_hits, make_clips_from_hits

# ====== LOAD CONFIG ======
CONFIG_PATH = Path(__file__).parent / "config.yaml"

def load_config():
    if not CONFIG_PATH.exists():
        print(f"⚠️  Config {CONFIG_PATH} gak ada, pakai default")
        return None
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

_cfg = load_config()
if _cfg:
    CLIP_DURATION = _cfg["clip"]["duration"]
    MIN_DURATION = _cfg["clip"]["min_duration"]
    MAX_DURATION = _cfg["clip"]["max_duration"]
    TOLERANCE = _cfg["clip"]["tolerance"]
    CONTEXT_BEFORE = _cfg["clip"]["context_before"]
    MAX_CLIPS = _cfg["clip"]["max_clips"]

    WHISPER_MODEL = _cfg["whisper"]["model"]
    WHISPER_LANG = _cfg["whisper"]["language"]
    BEAM_SIZE = _cfg["whisper"]["beam_size"]
    VAD_FILTER = _cfg["whisper"]["vad_filter"]
    INITIAL_PROMPT = _cfg["whisper"]["initial_prompt"]

    OUTPUT_W = _cfg["output"]["width"]
    OUTPUT_H = _cfg["output"]["height"]
    FONT = _cfg["output"]["font"]
    FONT_SIZE = _cfg["output"]["font_size"]
    FONT_COLOR = _cfg["output"]["font_color"]
    OUTLINE_COLOR = _cfg["output"]["outline_color"]
    OUTLINE_SIZE = _cfg["output"]["outline_size"]
    MARGIN_V = _cfg["output"]["margin_vertical"]

    KEYWORDS = _cfg["keywords"]
else:
    # Fallback default
    CLIP_DURATION = 45
    MIN_DURATION = 30
    MAX_DURATION = 60
    TOLERANCE = 5
    CONTEXT_BEFORE = 5
    MAX_CLIPS = 5
    WHISPER_MODEL = "base"
    WHISPER_LANG = "id"
    BEAM_SIZE = 5
    VAD_FILTER = True
    INITIAL_PROMPT = ""
    OUTPUT_W = 1080
    OUTPUT_H = 1920
    FONT = "Roboto"
    FONT_SIZE = 90
    FONT_COLOR = "&H00FFFFFF"
    OUTLINE_COLOR = "&H00000000"
    OUTLINE_SIZE = 6
    MARGIN_V = 400
    KEYWORDS = {}
# =========================

def run(cmd, silent=False):
    """Helper jalankan ffmpeg"""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and not silent:
        print("❌ FFmpeg error:")
        print(result.stderr[-500:])
    return result

def get_duration(video_path):
    """Ambil durasi video dalam detik"""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return float(r.stdout.strip())

def transcribe(video_path, model):
    """Transkripsi video, return list of segments dengan word timestamps"""
    print(f"🎙️  Transkripsi: {video_path.name}")
    segments, info = model.transcribe(
        str(video_path),
        language=WHISPER_LANG,
        beam_size=BEAM_SIZE,
        vad_filter=VAD_FILTER,
        word_timestamps=True,
        initial_prompt=INITIAL_PROMPT,
    )
    segs = []
    for s in segments:
        words = []
        if s.words:
            for w in s.words:
                words.append({"word": w.word, "start": w.start, "end": w.end})
        segs.append({
            "start": s.start,
            "end": s.end,
            "text": s.text.strip(),
            "words": words,
        })
    print(f"    ✅ {len(segs)} segment, bahasa: {info.language}")
    return segs

def format_time_ass(sec):
    """Format detik ke H:MM:SS.cc untuk .ass"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def write_ass(words, offset_start, offset_end, out_path):
    """Bikin file .ass dari word timestamps (relative ke klip)"""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {OUTPUT_W}
PlayResY: {OUTPUT_H}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TikTok,{FONT},{FONT_SIZE},{FONT_COLOR},{OUTLINE_COLOR},&H80000000,-1,0,1,{OUTLINE_SIZE},3,2,50,50,{MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for w in words:
        # skip kata di luar range klip
        if w["end"] < offset_start or w["start"] > offset_end:
            continue
        # clamp ke range klip & jadikan relative
        start = max(w["start"], offset_start) - offset_start
        end = min(w["end"], offset_end) - offset_start
        text = w["word"].strip().replace("\n", " ")
        if not text:
            continue
        lines.append(
            f"Dialogue: 0,{format_time_ass(start)},{format_time_ass(end)},TikTok,,0,0,0,,{text}"
        )
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")

def process_clip(video_path, clip_start, clip_end, words, out_path, temp_dir):
    """Proses 1 klip: cut + reframe + burn subtitle"""
    duration = clip_end - clip_start
    ass_path = temp_dir / f"{out_path.stem}.ass"
    write_ass(words, clip_start, clip_end, ass_path)

    # FFmpeg: cut -> crop 9:16 -> scale -> burn subtitle
    # Pakai ass filter dengan escape path
    ass_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
    vf = (
        f"crop=ih*9/16:ih,"
        f"scale={OUTPUT_W}:{OUTPUT_H},"
        f"ass='{ass_escaped}'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{clip_start:.2f}",
        "-to", f"{clip_end:.2f}",
        "-i", str(video_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    print(f"    🎬 Render: {out_path.name} ({duration:.1f}s)...")
    result = run(cmd, silent=True)
    if result.returncode != 0:
        print(f"    ❌ Gagal render {out_path.name}")
        print(result.stderr[-300:])
        return False
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 clipforge.py <video.mp4>")
        sys.exit(1)

    video = Path(sys.argv[1])
    if not video.exists():
        print(f"❌ File tidak ditemukan: {video}")
        sys.exit(1)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)

    # 1. Ambil durasi
    total_dur = get_duration(video)
    print(f"📹 Video: {video.name}")
    print(f"   Durasi: {total_dur:.1f}s")
    print(f"   Config: {CLIP_DURATION}s/klip, max {MAX_CLIPS} klip\n")

    # 2. Load Whisper
    print(f"🧠 Loading Whisper '{WHISPER_MODEL}'...")
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    print("   ✅ Model siap\n")

    # 3. Transkripsi
    segments = transcribe(video, model)

    # Flatten semua kata
    all_words = []
    for seg in segments:
        all_words.extend(seg["words"])

    # 4. Tentukan segmen klip — PAKAI KEYWORD DULU
    hits = find_keyword_hits(segments)
    print(f"\n🔍 Ketemu {len(hits)} keyword hit")

    if hits:
        clip_dicts = make_clips_from_hits(
            hits, segments, total_dur,
            target_duration=CLIP_DURATION,
            max_clips=MAX_CLIPS,
            context_before=CONTEXT_BEFORE,
            min_duration=MIN_DURATION,
            max_duration=MAX_DURATION,
            tolerance=TOLERANCE,
        )
        clips = [(c["start"], c["end"]) for c in clip_dicts]
        print(f"✂️  Mode: KEYWORD-BASED")
        for c in clip_dicts:
            print(f"    [{c['start']:6.1f}s - {c['end']:6.1f}s] {c['duration']:.1f}s | {c['reason']}")
    else:
        # Fallback: cut by duration aja
        clips = []
        num_clips = min(MAX_CLIPS, int(total_dur // CLIP_DURATION) or 1)
        for i in range(num_clips):
            start = i * CLIP_DURATION
            end = min(start + CLIP_DURATION, total_dur)
            if end - start < 5:
                break
            clips.append((start, end))
        print(f"✂️  Mode: DURATION-BASED (gak ada keyword)")

    print(f"\n🎬 Akan render {len(clips)} klip\n")

    # 5. Render tiap klip
    success = 0
    for i, (start, end) in enumerate(clips, 1):
        out_path = output_dir / f"{video.stem}_clip{i:02d}.mp4"
        if process_clip(video, start, end, all_words, out_path, temp_dir):
            print(f"    ✅ {out_path}")
            success += 1

    print(f"\n🎉 Selesai! {success}/{len(clips)} klip di folder output/")

if __name__ == "__main__":
    main()
