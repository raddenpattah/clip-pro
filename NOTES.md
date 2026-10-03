# ClipForge - Development Notes

## Repo
https://github.com/raddenpattah/clip-pro

## Last Session
2026-10-03 - Smart reframe + auto-tune hardware selesai & tested

## Status
MVP + smart reframe + auto-tune hardware. Siap test produksi.

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
- system_probe.py           : Deteksi hardware + auto-tune config
- face_tracker.py           : Deteksi + tracking wajah (YuNet)
- reframe_engine.py         : Crop timeline + FFmpeg sendcmd
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
10. Smart reframe (YuNet face tracking, EMA smoothing, sendcmd dynamic crop)
11. Auto-tune hardware (probe CPU/RAM/GPU → rekomendasi config)
12. Config merge (config.yaml + config.auto.yaml, user menang)
13. CLI flags: --yes, --probe-only, --no-probe, --force-smart

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

## Smart Reframe (2026-10-03)

### Arsitektur
- `system_probe.py` → probe hardware (CPU/RAM/GPU/disk/load)
- `config.auto.yaml` → auto-generated, di-merge dengan `config.yaml` (user menang)
- `face_tracker.py` → YuNet detector (auto-download 230KB ke models/)
- `reframe_engine.py` → sample frame 5fps → crop timeline → FFmpeg `sendcmd`

### Alur
1. Probe hardware → tulis config.auto.yaml
2. Merge: config.yaml (user) OVERRIDE config.auto.yaml (auto)
3. Per klip: sample frame → detect wajah → hitung crop X → smoothing EMA
4. Tulis sendcmd → FFmpeg pakai `crop=w:h:x:y,sendcmd=f=...`
5. Kalau ga ada wajah → fallback center crop

### Config
- `reframe.enabled`: on/off
- `reframe.sample_fps`: 3 (weak) / 5 (medium) / 8 (strong)
- `reframe.smoothing.alpha`: 0.3 (makin kecil = makin halus)
- `reframe.smoothing.deadzone_px`: 40 (toleransi gerak)
- `reframe.fallback`: center

### CLI Flags Baru
- `--yes` / `-y` : skip prompt interaktif
- `--probe-only` : cuma tampilin spec + rekomendasi
- `--no-probe` : skip probe, pakai config.yaml aja
- `--force-smart` : paksa smart reframe walau CPU lemah
- `--config <path>` : custom config path

### Tested
- `input/yt_test_h264.mp4` (120s, Raditya Dika podcast, 4 orang)
  - Hook: 26/26 samples ada wajah
  - Main: 157/237 samples ada wajah
  - Output: crop gerak ngikutin wajah, visual enak ✅

### Known Limits
- Deteksi wajah di FRAME OUTPUT lebih jarang kena daripada di INPUT (karena resize) — bukan bug, visual tetep oke
- Warning OpenCV 5.0 `setPreferableTarget` — harmless, cuma CPU fallback
- Video AV1 tetep perlu convert H.264 dulu (belum di-handle)

## Ide Eksplorasi: Kdenlive/MLT (Belum Diimplementasi)

**Konteks:** Diskusi 2026-10-03, eksplorasi dependency Kdenlive/MLT
buat upgrade ClipForge. Belum ada keputusan final.

### Library MLT yang Relevan

| Library | Guna | Effort | Prioritas |
|---|---|---|---|
| `mlt.affine` | Crop pan smooth (keyframe animasi, interpolasi ease) | Sedang | ⭐ (kalau sendcmd kurang smooth) |
| `mlt.dynamictext` | Subtitle/hook animate (per-kata, pop, fade) | Rendah-sedang | ⭐⭐ (upgrade visual) |
| `mlt.motion_est` | Tracking non-wajah (optical flow) | Tinggi | ⭐⭐⭐ (kalau handle konten non-podcast) |
| `mlt.opencv_tracker` | Duplikasi YuNet (skip, kita udah punya) | - | ❌ |
| `mlt.qtblend` | Compositing layer (background blur, PiP) | Sedang | nice-to-have |
| `mlt.frei0r.*` | 100+ efek visual | Rendah | nice-to-have |
| `mlt.loudness` | Audio normalization | Rendah | bisa pakai FFmpeg `loudnorm` |
| `mlt.audio_waveform` | Waveform visual | Rendah | nice-to-have |

### Status Keputusan
- **TBD** — belum diputuskan migrasi ke MLT atau ngga
- **Alasan belum migrasi:**
  - Pipeline FFmpeg sekarang udah works (smart reframe, hook, subtitle, keyword)
  - Migrasi MLT = rewrite besar (`clipforge.py`, `reframe_engine.py`, `hook_builder.py`)
  - CPU 2-core lu mungkin struggle dengan MLT (lebih berat dari FFmpeg)
  - Belum ada pain point urgent yang butuh MLT

### Kapan MLT Worth Dipertimbangkan
- Kalau crop pan FFmpeg `sendcmd` masih kerasa "patah" setelah tuning alpha/deadzone
- Kalau mau subtitle benar-benar animate (per-kata, pop, fade)
- Kalau mau handle konten non-wajah (produk, gaming, slide)
- Kalau upgrade hardware (RAM/CPU/GPU)

### Urutan Prioritas (kalau mau upgrade feel)
1. Fix crop multi-face (celah kosong) — FFmpeg + logic
2. Tune smoothing (alpha, deadzone) — config
3. Subtitle animate — MLT `dynamictext` (1 hari)
4. Crop pan smooth — MLT `affine` (2-3 hari)
5. Non-face tracking — MLT `motion_est` (1 minggu)

### Ref
- MLT Framework: https://www.mltframework.org/
- MLT Python binding: `pip install mlt` atau `apt install python3-mlt`
- Kdenlive source: https://invent.kde.org/multimedia/kdenlive
