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
from hook_builder import get_hook_text, write_hook_ass, save_title
from dictionary_manager import (
    load_dictionary,
    normalize_segments,
    find_unknown_words,
    log_unknown_words,
)
from system_probe import (
    probe_system, recommend_config, write_auto_config,
    load_merged_config, print_report, classify,
    prompt_weak_hardware, prompt_custom,
)
from reframe_engine import prepare_smart_crop
from frame_renderer import render_frame_by_frame
import argparse
import builtins

# ====== LOAD CONFIG ======
CONFIG_PATH = Path(__file__).parent / "config.yaml"
AUTO_CONFIG_PATH = Path(__file__).parent / "config.auto.yaml"
MODELS_DIR = Path(__file__).parent / "models"

def parse_args():
    ap = argparse.ArgumentParser(description="ClipForge - auto video cutter")
    ap.add_argument("input", nargs="?", help="Path video input")
    ap.add_argument("--no-probe", action="store_true",
                    help="Skip system probe, pakai config.yaml aja")
    ap.add_argument("--force-smart", action="store_true",
                    help="Paksa smart reframe walau CPU lemah")
    ap.add_argument("--probe-only", action="store_true",
                    help="Cuma tampilin spec + rekomendasi, keluar")
    ap.add_argument("--yes", "-y", action="store_true",
                    help="Skip prompt interaktif (auto-accept)")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--engine", choices=["single", "dual", "multi", "auto"],
                    help="Reframe engine (override config.yaml)")
    ap.add_argument("--batch", metavar="FOLDER",
                    help="Batch mode: proses semua video di folder")
    return ap.parse_args()

def load_runtime_config(args):
    project_dir = Path(__file__).parent
    user_cfg_path = project_dir / args.config

    if args.no_probe:
        if user_cfg_path.exists():
            with open(user_cfg_path, "r") as f:
                return yaml.safe_load(f) or {}
        return {}

    spec = probe_system(project_dir)
    rec = recommend_config(spec)
    print_report(spec, rec)

    if args.probe_only:
        write_auto_config(rec, AUTO_CONFIG_PATH)
        print(f"✅ Ditulis ke {AUTO_CONFIG_PATH}")
        raise SystemExit(0)

    tier = classify(spec)
    if tier == "weak" and not args.yes and not args.force_smart:
        choice = prompt_weak_hardware(spec, rec)
        if choice == "cancel":
            print("❌ Dibatalkan.")
            raise SystemExit(1)
        if choice == "custom":
            prompt_custom(rec)

    write_auto_config(rec, AUTO_CONFIG_PATH)
    cfg = load_merged_config(user_cfg_path, AUTO_CONFIG_PATH)

    # Override engine dari CLI arg
    if getattr(args, "engine", None):
        if "reframe" not in cfg:
            cfg["reframe"] = {}
        cfg["reframe"]["engine"] = args.engine
        print(f"⚙️  Engine override dari CLI: {args.engine}")

    return cfg

def load_config():
    """Fallback buat backward compat - panggil load_runtime_config tanpa probe."""
    class _A: no_probe=True; config="config.yaml"; probe_only=False; yes=False; force_smart=False
    return load_runtime_config(_A())

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
    _enc = _cfg.get("encode", {})
    ENCODE_PRESET = _enc.get("preset", "fast")
    ENCODE_CRF = _enc.get("crf", 23)
    ENCODE_THREADS = _enc.get("threads", 2)
    FONT = _cfg["output"]["font"]
    FONT_SIZE = _cfg["output"]["font_size"]
    FONT_COLOR = _cfg["output"]["font_color"]
    OUTLINE_COLOR = _cfg["output"]["outline_color"]
    OUTLINE_SIZE = _cfg["output"]["outline_size"]
    MARGIN_V = _cfg["output"]["margin_vertical"]

    KEYWORDS = _cfg["keywords"]

    # Hook config
    HOOK_CFG = _cfg.get("hook", {})

    # Dictionary config
    DICT_CFG = _cfg.get("dictionary", {})
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
    ENCODE_PRESET = "fast"
    ENCODE_CRF = 23
    ENCODE_THREADS = 2
    FONT = "Roboto"
    FONT_SIZE = 90
    FONT_COLOR = "&H00FFFFFF"
    OUTLINE_COLOR = "&H00000000"
    OUTLINE_SIZE = 6
    MARGIN_V = 400
    KEYWORDS = {}
    HOOK_CFG = {"enabled": False}
    DICT_CFG = {"enabled": False}
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


def get_video_codec(video_path):
    """Deteksi codec video (h264, hevc, av1, vp9, dll)."""
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=codec_name",
           "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip().lower()


# Codec yang aman untuk OpenCV + FFmpeg pipeline
SAFE_CODECS = {"h264", "hevc", "mpeg4", "vp8", "vp9"}


def ensure_h264(video_path: Path, temp_dir: Path) -> Path:
    """
    Pastikan video bisa diproses:
    - Kalau codec aman (h264, hevc, dll) -> return as-is
    - Kalau AV1 atau codec lain -> convert ke H.264 temporary
    
    Return: Path video yang siap diproses (bisa jadi file baru)
    """
    codec = get_video_codec(video_path)
    print(f"   🎞️  Codec: {codec}")

    if codec in SAFE_CODECS:
        return video_path

    # Perlu convert
    print(f"   ⚠️  Codec '{codec}' ga didukung pipeline, convert ke H.264...")
    temp_path = temp_dir / f"{video_path.stem}_h264_tmp.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        str(temp_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"   ❌ Gagal convert: {r.stderr[-300:]}")
        return video_path  # fallback: coba aja process as-is

    print(f"   ✅ Convert selesai: {temp_path.name}")
    return temp_path

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

def process_clip(video_path, clip_start, clip_end, words, out_path, temp_dir, hook_cfg=None, cfg=None):
    """Proses 1 klip: opening+hook + main content + subtitle (frame-by-frame)."""
    duration = clip_end - clip_start

    # Cek apakah pakai hook
    use_hook = hook_cfg and hook_cfg.get("enabled", False) and hook_cfg.get("_hook_text")

    if not use_hook:
        # === MODE TANPA HOOK ===
        return _render_single(video_path, clip_start, clip_end, words, out_path, temp_dir, cfg=cfg)

    # === MODE DENGAN HOOK ===
    hook_dur = hook_cfg.get("duration", 5)

    # File temporer
    hook_video = temp_dir / f"{out_path.stem}_hook.mp4"
    main_video = temp_dir / f"{out_path.stem}_main.mp4"
    hook_ass = temp_dir / f"{out_path.stem}_hook.ass"
    main_ass = temp_dir / f"{out_path.stem}_main.ass"
    list_file = temp_dir / f"{out_path.stem}_concat.txt"

    # ===== HOOK PART =====
    write_hook_ass(hook_cfg, hook_ass)

    timeline_hook, _ = prepare_smart_crop(
        video_path=video_path,
        clip_start=0.0,
        clip_end=hook_dur,
        models_dir=MODELS_DIR,
        temp_dir=temp_dir,
        out_stem=f"{out_path.stem}_hook",
        cfg=cfg or {},
    )

    print(f"    🎣 Render hook: {hook_video.name} ({hook_dur}s)...")
    ok_hook = render_with_timeline(
        video_path=video_path,
        clip_start=0.0,
        clip_end=hook_dur,
        timeline=timeline_hook,
        ass_path=hook_ass,
        out_path=hook_video,
        temp_dir=temp_dir,
        fps=30,
    )
    if not ok_hook:
        print(f"    ⚠️  Gagal render hook, fallback ke mode lama")
        return _render_single(video_path, clip_start, clip_end, words, out_path, temp_dir, cfg=cfg)

    # ===== MAIN PART =====
    write_ass(words, clip_start, clip_end, main_ass)

    timeline_main, _ = prepare_smart_crop(
        video_path=video_path,
        clip_start=clip_start,
        clip_end=clip_end,
        models_dir=MODELS_DIR,
        temp_dir=temp_dir,
        out_stem=f"{out_path.stem}_main",
        cfg=cfg or {},
    )

    print(f"    🎬 Render main: {main_video.name} ({duration:.1f}s)...")
    ok_main = render_with_timeline(
        video_path=video_path,
        clip_start=clip_start,
        clip_end=clip_end,
        timeline=timeline_main,
        ass_path=main_ass,
        out_path=main_video,
        temp_dir=temp_dir,
        fps=30,
    )
    if not ok_main:
        print(f"    ⚠️  Gagal render main, fallback")
        return _render_single(video_path, clip_start, clip_end, words, out_path, temp_dir, cfg=cfg)

    # ===== CONCAT HOOK + MAIN =====
    list_file.write_text(
        f"file '{hook_video.resolve()}'\nfile '{main_video.resolve()}'\n"
    )
    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        "-movflags", "+faststart",
        str(out_path),
    ]
    print(f"    🔗 Concat ke {out_path.name}...")
    r = run(cmd_concat, silent=True)
    if r.returncode != 0:
        print(f"    ❌ Gagal concat")
        print(r.stderr[-300:])
        return False

    # Cleanup
    for f in [hook_video, main_video, hook_ass, main_ass, list_file]:
        try:
            f.unlink()
        except Exception:
            pass

    total = hook_dur + duration
    print(f"    ✅ {out_path.name} ({total:.1f}s = {hook_dur}s hook + {duration:.1f}s main)")
    return True


def render_with_timeline(
    video_path: Path,
    clip_start: float,
    clip_end: float,
    timeline: list,
    ass_path: Path,
    out_path: Path,
    temp_dir: Path,
    fps: int = 30,
) -> bool:
    """
    Render 1 klip dengan timeline crop + overlay .ass.
    2 step:
      1. frame-by-frame crop -> raw video
      2. FFmpeg overlay .ass -> final video
    """
    raw_path = temp_dir / f"{out_path.stem}_raw.mp4"
    duration = clip_end - clip_start

    # Timeline relatif ke clip_start = 0
    # (prepare_smart_crop udah return relatif, jadi ga perlu adjust)
    if not timeline:
        # Fallback: static center
        cap = cv2.VideoCapture(str(video_path))
        fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        crop_w = int(fh * 9 / 16)
        center_x = max(0, (fw - crop_w) // 2)
        timeline = [(0.0, center_x)]

    # Step 1: Frame-by-frame render (crop only)
    print(f"    🎬 Frame render: {out_path.stem} ({duration:.1f}s)...")
    try:
        # Extract segment dulu (clip_start to clip_end)
        seg_path = temp_dir / f"{out_path.stem}_seg.mp4"
        cmd_seg = [
            "ffmpeg", "-y",
            "-ss", f"{clip_start:.2f}",
            "-to", f"{clip_end:.2f}",
            "-i", str(video_path),
            "-c", "copy",
            str(seg_path),
        ]
        r = run(cmd_seg, silent=True)
        if r.returncode != 0:
            print(f"    ❌ Gagal extract segmen")
            return False

        render_frame_by_frame(
            video_path=seg_path,
            output_path=raw_path,
            timeline_sec=timeline,
            output_w=OUTPUT_W,
            output_h=OUTPUT_H,
            fps=fps,
            audio_from_source=True,
            crf=ENCODE_CRF,
            preset="veryfast",
        )
        # Cleanup segment
        try:
            seg_path.unlink()
        except Exception:
            pass
    except Exception as e:
        print(f"    ❌ Frame render gagal: {e}")
        return False

    # Step 2: Overlay .ass
    ass_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
    cmd_ass = [
        "ffmpeg", "-y",
        "-i", str(raw_path),
        "-vf", f"ass='{ass_escaped}'",
        "-c:v", "libx264", "-preset", ENCODE_PRESET, "-crf", str(ENCODE_CRF),
        "-threads", str(ENCODE_THREADS),
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(out_path),
    ]
    r = run(cmd_ass, silent=True)
    if r.returncode != 0:
        print(f"    ❌ Overlay .ass gagal")
        print(r.stderr[-300:])
        return False

    # Cleanup raw
    try:
        raw_path.unlink()
    except Exception:
        pass

    return True

def _render_single(video_path, clip_start, clip_end, words, out_path, temp_dir, cfg=None):
    """Render 1 klip tanpa hook (mode lama) — pake frame-by-frame renderer."""
    duration = clip_end - clip_start
    ass_path = temp_dir / f"{out_path.stem}.ass"
    write_ass(words, clip_start, clip_end, ass_path)

    # Siapin timeline dari smart reframe
    timeline, _ = prepare_smart_crop(
        video_path=video_path,
        clip_start=clip_start,
        clip_end=clip_end,
        models_dir=MODELS_DIR,
        temp_dir=temp_dir,
        out_stem=out_path.stem,
        cfg=cfg or {},
    )

    # Render pakai helper (frame-by-frame + .ass overlay)
    print(f"    🎬 Render: {out_path.name} ({duration:.1f}s)...")
    return render_with_timeline(
        video_path=video_path,
        clip_start=clip_start,
        clip_end=clip_end,
        timeline=timeline,
        ass_path=ass_path,
        out_path=out_path,
        temp_dir=temp_dir,
        fps=30,
    )

def process_one(video: Path, output_dir: Path, temp_dir: Path) -> tuple[int, int]:
    """Process 1 video. Return (success_clips, total_clips)."""
    # 0. Pastikan codec aman (auto-convert AV1, dll)
    original_video = video
    video = ensure_h264(video, temp_dir)

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

    # 3.5 NORMALIZE pakai kamus (kalau enabled)
    if DICT_CFG.get("enabled", False):
        print(f"\n📖 Normalize pakai kamus...")
        kamus = load_dictionary()
        n_replacements = len(kamus.get("replacements", {}))
        n_filler = len(kamus.get("filler_words", []))
        n_brands = len(kamus.get("brand_capitalize", []))
        print(f"    Kamus: {n_replacements} replacements, {n_filler} filler, {n_brands} brands")

        # Deteksi kata aneh SEBELUM normalize (biar dapet raw)
        unknown = find_unknown_words(
            segments, kamus,
            min_frequency=DICT_CFG.get("min_frequency", 2)
        )

        # Normalize
        segments = normalize_segments(segments, kamus)
        print(f"    ✅ Normalize selesai")

        # Auto-log kata aneh
        if DICT_CFG.get("auto_log", False) and unknown:
            n_logged = log_unknown_words(unknown, video.name)
            print(f"    📝 {n_logged} kata baru di-log ke unknown_words.log")
            if n_logged > 0:
                print(f"       Review: dictionary/unknown_words.log")

    # Flatten semua kata
    all_words = []
    for seg in segments:
        all_words.extend(seg["words"])

    # 4. Tentukan segmen klip — PAKAI KEYWORD DULU
    hits = find_keyword_hits(segments, keywords=KEYWORDS)
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

    # === HOOK GENERATION ===
    hook_text = None
    if HOOK_CFG.get("enabled", False):
        hook_text = get_hook_text(HOOK_CFG, segments)
        if hook_text:
            print(f"🎣 Hook text: {hook_text}")
            HOOK_CFG["_hook_text"] = hook_text

    # 5. Render tiap klip
    success = 0
    for i, (start, end) in enumerate(clips, 1):
        out_path = output_dir / f"{video.stem}_clip{i:02d}.mp4"

        # Hook hanya di klip pertama kalau apply_to = "first_only"
        use_hook_this = True
        if HOOK_CFG.get("apply_to") == "first_only" and i > 1:
            use_hook_this = False

        hook_for_clip = HOOK_CFG if use_hook_this else None

        if process_clip(video, start, end, all_words, out_path, temp_dir, hook_cfg=hook_for_clip, cfg=builtins.CFG):
            print(f"    ✅ {out_path}")
            success += 1

            # Simpen judul ke file .txt
            if hook_for_clip and hook_for_clip.get("save_title"):
                title_path = output_dir / f"{video.stem}_clip{i:02d}_title.txt"
                save_title(hook_for_clip, title_path)

    print(f"\n🎉 Selesai! {success}/{len(clips)} klip di folder output/")
    return success, len(clips)


def run_batch(folder: Path, output_dir: Path, temp_dir: Path) -> None:
    """Batch mode: proses semua video di folder."""
    # Cari semua video
    exts = {".mp4", ".mkv", ".mov", ".avi", ".webm"}
    videos = sorted([
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in exts
    ])

    if not videos:
        print(f"❌ Ga ada video di {folder}")
        return

    print(f"\n{'='*60}")
    print(f"🎬 BATCH MODE: {len(videos)} video ditemukan di {folder}")
    print(f"{'='*60}\n")

    results = []
    for i, video in enumerate(videos, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(videos)}] {video.name}")
        print(f"{'='*60}")
        try:
            success, total = process_one(video, output_dir, temp_dir)
            results.append((video.name, success, total, None))
        except Exception as e:
            print(f"\n❌ Gagal proses {video.name}: {e}")
            results.append((video.name, 0, 0, str(e)))

    # Summary
    print(f"\n{'='*60}")
    print(f"🎉 BATCH SELESAI")
    print(f"{'='*60}")
    total_clips = 0
    success_count = 0
    for name, success, total, err in results:
        if err:
            print(f"  ❌ {name}: GAGAL ({err[:50]})")
        else:
            print(f"  ✅ {name}: {success}/{total} klip")
            total_clips += success
            success_count += 1
    print(f"\n   Sukses: {success_count}/{len(videos)} video")
    print(f"   Total klip: {total_clips}")


def main():
    args = parse_args()

    # Auto-tune config dari hardware (kecuali --no-probe)
    runtime_cfg = load_runtime_config(args)
    builtins.CFG = runtime_cfg if runtime_cfg else {}

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)

    # === BATCH MODE ===
    if args.batch:
        folder = Path(args.batch)
        if not folder.exists() or not folder.is_dir():
            print(f"❌ Folder tidak ditemukan: {folder}")
            sys.exit(1)
        run_batch(folder, output_dir, temp_dir)
        return

    # === SINGLE MODE ===
    if not args.input:
        print("Usage: python3 clipforge.py <video.mp4> [--yes] [--probe-only] [--no-probe] [--engine X]")
        print("       python3 clipforge.py --batch <folder> [--engine X]")
        sys.exit(1)

    video = Path(args.input)
    if not video.exists():
        print(f"❌ File tidak ditemukan: {video}")
        sys.exit(1)

    process_one(video, output_dir, temp_dir)


if __name__ == "__main__":
    main()
