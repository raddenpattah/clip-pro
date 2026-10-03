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

## Kamus — Status & Keputusan (2026-10-03)

### Konsep Final: Visi X (To-Do List)
- Log `unknown_words.log` = kata yang **belum di kamus** (to-do list)
- Kata yang **udah di kamus** → ga di-log lagi (langsung di-replace)
- **Alasan:** log tetap bersih & fokus, ga numpuk history

### Alur
1. Whisper transkrip
2. `apply_normalization()` → replace kata yang ada di kamus
3. `find_unknown_words()` → deteksi kata baru (belum di kamus, bukan stopwords)
4. `log_unknown_words()` → tulis ke log
5. User review log → tambahin ke `kamus.json` (manual edit)
6. Next run: kata yang udah di kamus → auto-replace

### Komponen
- `dictionary/kamus.json` — 15 replacements, 9 filler, 9 brands
- `dictionary/stopwords_id.txt` — 345 kata umum Indonesia (filter log)
- `dictionary/unknown_words.log` — to-do list (di-ignore git)
- `dictionary_manager.py` — load, normalize, detect unknown, log

### Tested (2026-10-03)
- ✅ Replace kata: `tesuara` → `tes suara`, `TripFolga` → `ClipForge`
- ✅ Filler removal: `eee`, `kan`, `hmm`, `deh` ke-hapus
- ✅ Brand capitalize: `tiktok` → `TikTok`, `youtube` → `YouTube`
- ✅ Unknown detection: `qwerty` ke-detect, `tesuara` (udah di kamus) **ga ke-detect**

### Keputusan (yang BELUM dikerjain)
- ❌ Visi Y (log semua kejadian) — over-engineering, skip dulu
- ❌ CLI `--review` — belum perlu, manual edit cukup
- ❌ Auto-promote dari log ke kamus — risky, skip
- ❌ Database/UI/cloud — over-engineering

### Kalau Nanti Perlu Upgrade
- Visi Y: ubah `find_unknown_words()` biar ga skip kata yang ada di kamus, tambah tanda `[SOLVED]`
- CLI review: parse log, prompt user per kata, tulis ke `kamus.json`
- Statistik: parse log, hitung frequency & trend

### Prinsip
"Make it work, make it right, make it fast."
- Sekarang: **work** ✅
- Next: **right** (kalau ada bug)
- Nanti: **fast** (kalau kerasa lambat)

## Rencana Pindah ke PC Baru (Future)

### Target Hardware
- OS: Windows + WSL2 (udah ada)
- CPU: Intel i5 gen 12 (10-12C / 16-20T)
- RAM: 32 GB DDR5
- GPU: Intel Arc A580 (8GB VRAM)
- Storage: 512 GB

### Strategi: WSL2
- ClipForge jalan tanpa ubah kode (Linux di atas Windows)
- GPU Arc support: DirectML atau oneAPI (opsional)

### Checklist Setup di PC Baru
1. [ ] Buka WSL2 Ubuntu
2. [ ] Install Python 3.12+ (apt atau pyenv)
3. [ ] Install FFmpeg (apt install ffmpeg)
4. [ ] Install yt-dlp (pipx install yt-dlp)
5. [ ] git clone https://github.com/raddenpattah/clip-pro.git
6. [ ] cd clip-pro && python3 -m venv venv
7. [ ] source venv/bin/activate
8. [ ] pip install faster-whisper pyyaml opencv-python-headless psutil
9. [ ] Test: python3 clipforge.py --probe-only
10. [ ] Test: python3 clipforge.py input/video_test.mp4 --yes

### GPU Arc Setup (Opsional, Advanced)
- Intel GPU driver (Windows side, versi terbaru)
- WSL2: install oneAPI atau DirectML
- faster-whisper: coba backend OpenVINO
- FFmpeg: coba h264_qsv encode (kalau support)

### Yang Perlu Diupdate di system_probe.py
- [ ] Deteksi Intel Arc (lspci / clinfo)
- [ ] Deteksi QSV (ffmpeg -hwaccels)
- [ ] Tier baru: "high_end" (cores >= 8, ram >= 32, gpu != none)
- [ ] Auto-tune hardware baru

### Estimasi Effort
- Setup dasar: 1-2 jam (download + install)
- GPU Arc tuning: 2-4 jam (opsional)
- Total: 1-6 jam tergantung mau pake GPU atau ngga

### Prinsip
- Jangan optimasi buat hardware yang belum ada
- Test dulu di laptop sekarang
- Pas PC dateng, baru setup

## Status Terkini (2026-10-03 - Sesi 2)

### Yang Baru Dikerjain
- Fix false positive YuNet: score_thresh 0.6 -> 0.7, min_area 15000
- Fix pick_dominant(): prioritas area besar, tie-break centrality
- Fallback multi_center kalau 2+ wajah berjauhan
- Threshold 60% -> 20% (2 wajah jarak >20% fallback multi)
- Hapus output_backup/ dari git

### Tested
- Podcast Mamat 4 orang: 7/8 frame bagus
- False positive filter works (205/226 vs 226/226 = 21 frame noise ke-filter)
- Frame 30s: dari 'pinggir kanan' -> 'tengah' (FIXED)
- Frame 20s: masih agak pinggir (1 dari 8, minor)
- Frame 40s, 45s: bagus (2 orang beneran)

### Commit Terakhir
- 6dcd4c8: fix false positive + threshold 20%

### Rencana Besok: Multi-Engine Reframe

**Konsep:** engine terpisah per skenario, user pilih.

**Engine:**
- `single` - 1 orang (talking head)
- `dual`   - 2 orang (interview)
- `multi`  - 3-4 orang (podcast/panel) <- logic sekarang
- `auto`   - fallback

**Struktur:**
reframe_engine/
  __init__.py    # dispatcher
  base.py
  single.py
  dual.py
  multi.py
  auto.py

**Config:**
reframe:
  engine: multi    # single | dual | multi | auto

**CLI:**
--engine single|dual|multi|auto

**Roadmap:**
1. [ ] Refactor: bikin folder reframe_engine/
2. [ ] Split logic sekarang ke multi.py
3. [ ] Bikin single.py (1 orang, simple)
4. [ ] Bikin dual.py (2 orang, threshold 30%)
5. [ ] Bikin auto.py (fallback)
6. [ ] Test tiap engine
7. [ ] CLI flag --engine
8. [ ] UI (Gradio) - nanti

**Effort estimasi:** 3-4 jam

### Referensi: Repo clipforge
- Repo: raddenpattah/clipforge (lebih mature, ada Web UI)
- Struktur: backend + frontend (Next.js)
- Fitur lebih: API, Docker, testing, LLM
- **Keputusan:** skip migrasi, fokus clip-pro dulu
- **Kalau nanti butuh:** adopsi Docker + testing

### Prinsip
"Make it work, make it right, make it fast."
- Sekarang: work + right (sebagian)
- Next: multi-engine

### Test Podcast 2 Orang (Engine single)
- Video: podcast_2orang_2min.mp4 (Deddy Corbuzier? atau podcast 2 orang)
- Layout: 1 orang per frame, shot gantian (host -> tamu)
- Engine: single
- Hasil: 6/6 frame bagus, wajah di TENGAH
- Transisi host->tamu: MULUS (smoothing EMA works)
- Kesimpulan: engine single SOLID

## CLI --engine (2026-10-03)

### Cara Pakai
python3 clipforge.py input.mp4 --engine single
python3 clipforge.py input.mp4 --engine dual
python3 clipforge.py input.mp4 --engine multi
python3 clipforge.py input.mp4 --engine auto

- Tanpa --engine -> pake config.yaml (reframe.engine)
- Dengan --engine -> override config

### Engine Recommendation
- single : 1 orang (talking head, motivasi, video gantian shot)
- dual   : 2 orang (interview, podcast 2)
- multi  : 3-4 orang (panel, podcast multi)
- auto   : fallback (deteksi otomatis)

### Tested
- Podcast Mamat (4 orang) -> multi -> 7/8 frame bagus
- Podcast 2 orang -> single -> 6/6 frame bagus
- Podcast Deddy (3 orang) -> multi -> 6/6 frame bagus

### Status Commit
- 06d79db: CLI --engine
- c9f3c10: multi-engine reframe
- 49d4126, 6dcd4c8: false positive fix + NOTES

## Rencana UI: Hook Config (Future)

### Masalah
- Hook text position (atas) kadang ketutup kepala orang
- Box background kadang terlalu tebal
- Tuning manual di YAML ga user-friendly
- Butuh preview visual

### Solusi: UI Config Hook
Menu di UI (Gradio/Web) buat atur:
- [ ] Posisi text (atas/tengah/bawah)
- [ ] Font (family, size, weight)
- [ ] Warna text
- [ ] Outline (ada/ga, tebal, warna)
- [ ] Box background (ada/ga, warna, padding, opacity)
- [ ] Preview real-time
- [ ] Preset (TikTok, Reels, dll)
- [ ] Auto-position (hindari wajah)

### Target User
Content creator yang ga mau edit YAML.
Klik-klik, preview, save preset.

### Status
- Belum diimplementasi
- Nunggu UI framework (Gradio/Next.js)
- Pri: MEDIUM (setelah core works)

### Catatan
- Hook sekarang: kuning + outline hitam + box hitam 50%
- Masalah: posisi atas ketutup kepala (kalau orang duduk di kursi)
- Solusi sementara: box_enabled false / box_padding tipis

## Sesi 2026-10-03 - Recap Akhir

### Yang Dikerjain Hari Ini
- Smart reframe multi-engine (single/dual/multi/auto)
- CLI --engine + --batch
- Batch mode (loop folder)
- Auto-handle AV1 (convert ke H.264)
- Fix durasi mismatch (clip near-end video)
- Fix false positive YuNet (score 0.7 + min_area 15000)
- Fix keyword hardcoded bug (baca dari config)
- Fix edge case near-end keyword
- Dictionary stopwords (345 kata)
- Auto-tune hardware (probe CPU/RAM/GPU)

### Tested
- Podcast Mamat (4 orang): multi -> 7/8 frame bagus
- Podcast 2 orang: single -> 6/6 frame bagus
- Podcast Deddy (3 orang): multi -> 6/6 frame bagus
- Batch 3 video: 3/3 sukses
- Unit test: clip near-end fixed

### Personal Tool Status: SELESAI ✅
Yang udah works:
- Auto-transcribe + dictionary normalize
- Keyword detection + smart boundaries
- Smart reframe (4 engine)
- Hook overlay + subtitle + title
- Batch mode + CLI flags
- Auto-tune hardware

### Next (Kalau Lanjut)
1. [ ] Test AV1 di video real
2. [ ] UI Hook Config (Gradio/Next.js)
3. [ ] Preset platform (TikTok/Shorts/Reels)
4. [ ] Model small/medium (nunggu PC baru)
5. [ ] Testing (pytest)
6. [ ] Docker (adopsi dari clipforge)
7. [ ] Pindah ke PC baru (i5 gen 12 + Arc A580)

### Cara Pakai
python3 clipforge.py input.mp4                  # single video
python3 clipforge.py input.mp4 --engine single  # 1 orang
python3 clipforge.py input.mp4 --engine dual    # 2 orang
python3 clipforge.py input.mp4 --engine multi   # 3-4 orang
python3 clipforge.py --batch input/             # batch mode

### Prinsip
"Make it work, make it right, make it fast."
- Sekarang: work ✅ + right ✅
- Next: fast (nunggu PC baru)

## Hook Customization (2026-10-03)

### Yang Diubah
- Font: Roboto -> Montserrat Black
- Position: 8 (atas) -> 2 (tengah bawah, TikTok-style)
- margin_top: 200 -> 590
- text_source: "transcript" -> "manual" (user atur)
- text_manual: "TONTON SAMPE HABIS! 🔥"

### Requirement Baru
- Font Montserrat: sudo apt install fonts-montserrat

### Cara Atur Hook
Edit config.yaml:
hook:
  text_source: "manual"
  text_manual: "TEXT HOOK LU"    # max 60-70 char
  font_size: 80
  font_color: "&H0000FFFF"        # kuning BGR
  position: 2                     # 2=bawah, 5=tengah, 8=atas
  margin_top: 590                 # makin gede makin turun
  box_enabled: true

### Tips Text Hook
- Max 60-70 char (2-3 baris)
- Pakai emoji
- Pakai angka ("100 JUTA", "3 TIPS")
- Pakai pertanyaan ("MAU KAYA?")

### Tested
- Video 30 detik: hook di tengah bawah
- Kepala kelihatan (ga ketutup)
- Font Montserrat Black kebaca
- Text manual ke-pake

### Next: UI Hook Config (Future)
- Gradio/Next.js
- Preview real-time
- Drag & drop position
- Color picker
- Preset platform (TikTok/Reels/Shorts)

## Smooth Crop - SOLVED (2026-10-03 malam)

### Masalah
- FFmpeg sendcmd = KAKU (snap per sample, ga interpolate)
- MLT = gagal (ga interpolate, segfault)
- Crop geser bikin kepala kepotong

### Solusi FINAL: Frame-by-Frame Python + Catmull-Rom
- `frame_renderer.py` (BARU):
  * Baca video via OpenCV
  * Crop tiap frame sesuai timeline
  * Interpolasi Catmull-Rom spline (kurva halus)
  * Pipe raw frame ke FFmpeg stdin
  * 25 fps di laptop 2-core (35s untuk video 30s)
- `reframe_engine.py`:
  * `prepare_smart_crop()` return timeline [(t, x), ...]
  * Bukan vf filter
- `clipforge.py`:
  * `render_with_timeline()` helper
  * `process_clip()` + `_render_single()` pake helper
  * 2 step: frame-by-frame crop -> FFmpeg overlay .ass

### Engine Recommendation
- `single` - PALING STABIL buat podcast multi-orang
  * Fokus 1 wajah dominan
  * Ga ada celah kosong
  * Ga ada kepala kepotong
- `dual` - 2 orang dekat (interview)
- `multi` - bisa celah kosong (skip dulu)
- `auto` - fallback

### Config Default
reframe:
  engine: single

### Tested
- Podcast Mamat (4 orang, 2 menit): 2/2 klip sukses
- 451 samples, 450 berisi wajah (99.8%)
- Smooth crop, no kaku

### MLT (GAGAL - skip)
- Coba MLT affine via CLI + Python binding
- CLI: crop ga interpolate
- Python: segfault
- Skip, pake frame-by-frame Python

### Next (PC Baru)
1. Setup WSL2 + deps
2. Test smooth crop di PC (jauh lebih cepet)
3. Production konten
4. (Optional) Active speaker detection

## Gradio UI (2026-10-03 malam)

### File
- gradio_app.py (159 baris)

### Fitur
- Upload video (drag & drop)
- Pilih engine (single/dual/multi/auto)
- Atur hook text + posisi
- Process button
- Log real-time
- Preview klip

### Cara Pakai
python3 gradio_app.py
# Buka http://localhost:7860

### Known Issue
- Timeout 30 menit (perlu naikin ke 2 jam)
- Video 60 detik = ~22 menit (laptop lemah)

### Belum
- Progress bar visual
- Download button
- Preview gallery (multi klip)
- Custom CSS (biar ganteng)

### Next
- Fix timeout (30 detik)
- Test UI full
- Polish UI (kalau perlu)
