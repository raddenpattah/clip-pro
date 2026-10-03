# ClipForge

Aplikasi CLI Linux untuk ubah video 16:9 jadi klip pendek 9:16 (TikTok/Shorts/Reels), 100% offline.

## Fitur Utama

- Auto-transcribe offline (faster-whisper, bahasa Indonesia)
- Keyword detection - cari momen menarik dari transkrip
- Smart reframe multi-engine:
  - single - 1 orang (talking head, motivasi)
  - dual - 2 orang (interview)
  - multi - 3-4 orang (podcast, panel)
  - auto - deteksi otomatis
- Hook overlay - text hook 5 detik pertama (manual atau transkrip)
- Subtitle dinamis - word-by-word, gaya TikTok (.ass)
- Dictionary - auto-normalize typo Whisper + stopwords filter
- Auto-tune hardware - deteksi CPU/RAM/GPU, auto-setting
- Batch mode - proses banyak video sekaligus
- Auto-handle codec - AV1 auto-convert ke H.264

## Requirement

- OS: Linux (Ubuntu/Debian tested)
- Python: 3.12+
- FFmpeg: 8.0+
- Font: Montserrat (buat hook overlay)

## Install

    git clone https://github.com/raddenpattah/clip-pro.git
    cd clip-pro
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    sudo apt install fonts-montserrat
    python3 clipforge.py --probe-only

## Cara Pakai

### Single video

    python3 clipforge.py input/video.mp4
    python3 clipforge.py input/video.mp4 --engine single
    python3 clipforge.py input/video.mp4 --engine dual
    python3 clipforge.py input/video.mp4 --engine multi
    python3 clipforge.py input/video.mp4 --engine auto
    python3 clipforge.py input/video.mp4 --yes

### Batch mode

    python3 clipforge.py --batch input/ --engine multi

### CLI Flags

| Flag | Deskripsi |
|---|---|
| --engine {single,dual,multi,auto} | Pilih reframe engine |
| --batch FOLDER | Batch mode: proses semua video di folder |
| --yes, -y | Skip prompt interaktif |
| --no-probe | Skip hardware probe |
| --probe-only | Tampilin spec hardware, keluar |
| --force-smart | Paksa smart reframe walau CPU lemah |
| --config PATH | Custom config path |

## Config

Semua setting di config.yaml:

- clip.duration - durasi ideal klip (default: 45s)
- clip.max_clips - maksimal klip per video
- whisper.model - tiny/base/small/medium
- reframe.engine - single/dual/multi/auto
- hook.text_manual - text hook lu
- hook.position - 2=bawah, 5=tengah, 8=atas
- dictionary.enabled - auto-koreksi typo

## Struktur Project

    clip-pro/
      clipforge.py           # Main entry
      hook_builder.py        # Hook overlay
      keyword_detector.py    # Keyword detection
      dictionary_manager.py  # Normalize transkrip
      system_probe.py        # Auto-tune hardware
      face_tracker.py        # Deteksi wajah (YuNet)
      reframe_engine.py      # Crop timeline
      reframe_engines.py     # Multi-engine logic
      config.yaml            # Setting
      dictionary/            # Kamus + stopwords
      input/                 # Video input
      output/                # Hasil klip
      temp/                  # Temporary
      models/                # Model Whisper + YuNet

## Output

    output/
      video_clip01.mp4
      video_clip01_title.txt
      video_clip02.mp4
      video_clip02_title.txt

Setiap klip: 5s hook + main content.

## Troubleshooting

### Video AV1 ga bisa diproses

Auto-handle - ClipForge convert otomatis ke H.264.

### Whisper typo banyak

- Naikin whisper.model ke small/medium
- Tambahin koreksi di dictionary/kamus.json

### CPU lemah, proses lambat

- Turunin whisper.model ke tiny
- Matiin smart reframe: reframe.enabled: false

### Font Montserrat ga kedetect

    sudo apt install fonts-montserrat
    fc-cache -f -v
    fc-list | grep -i montserrat

## Roadmap

- [x] Smart reframe multi-engine
- [x] Batch mode
- [x] Auto-handle AV1
- [x] Hook customization
- [ ] UI (Gradio/Next.js)
- [ ] Preset platform (TikTok/Shorts/Reels)
- [ ] Testing (pytest)
- [ ] Docker

## Lisensi

MIT
