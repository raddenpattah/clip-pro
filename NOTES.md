# ClipForge - Development Notes

## Repo
https://github.com/raddenpattah/clip-pro

## Last Session
2026-10-03 - Fitur dictionary manager selesai

## Status
MVP + fitur lengkap, siap test produksi.

## Environment
- OS: Ubuntu 26.04
- Python: 3.14.4 (venv di ~/clip-pro/venv)
- FFmpeg: 8.0.1
- faster-whisper: 1.2.1
- yt-dlp: 2026.08.19 (via pipx)
- Fonts: Roboto, DejaVu

## Struktur Project
- clipforge.py              : Main entry
- hook_builder.py           : Hook overlay + title
- keyword_detector.py       : Keyword detection + smart boundaries
- dictionary_manager.py     : Normalize transkrip + auto-log
- config.yaml               : Semua setting
- dictionary/kamus.json     : Kamus (di-commit)
- dictionary/unknown_words.log : Log lokal (di-ignore)
- input/, output/, models/  : Di-ignore

## Fitur yang Udah Jadi
1. Auto-transcribe offline (faster-whisper)
2. Keyword detection + prioritas weight
3. Smart boundaries (durasi fleksibel, cari jeda natural)
4. Reframe 9:16 (1080x1920, yuv420p)
5. Subtitle dinamis (word-by-word, .ass)
6. Hook overlay 5s (dari transkrip / manual)
7. Title auto-generate
8. Config YAML (semua fleksibel)
9. Dictionary normalize + auto-log

## Config Utama (config.yaml)
- clip.duration: 45s
- clip.max_clips: 5
- whisper.model: base
- whisper.language: id
- hook.enabled: true
- hook.duration: 5
- hook.text_source: transcript
- dictionary.enabled: true
- dictionary.auto_log: true
- dictionary.min_frequency: 2

## Command Utama
    python3 clipforge.py input/video.mp4
    cat dictionary/unknown_words.log
    nano dictionary/kamus.json

## Bug yang Udah Difix
1. metadata_errors di faster_whisper/audio.py (PyAV v19 + Python 3.14)
2. pix_fmt yuv444p -> yuv420p (kompatibilitas HP)
3. Hook text kepotong 50 char -> 100 char
4. Koma/titik ganda setelah filler removal

## Known Issues
- Whisper base masih ada typo (~70-80% akurasi)
- CPU 2 core = transkripsi lambat (~2-3x realtime)
- Video AV1 harus di-convert dulu ke H.264
- Concat kadang ada A-V glitch kecil

## Next Features (Belum)
1. Rapihin struktur (src/ modular)
2. Batch mode (proses banyak video)
3. Smart reframe (deteksi wajah OpenCV)
4. TUI/Gradio UI
5. Preset platform (TikTok/Shorts/Reels)
6. Model small (akurasi lebih tinggi)

## Cara Balik ke Context
Bilang ke AI: 'Bro, gw balik. Baca NOTES.md di repo gw, lanjutin dari situ.'
