# ClipForge

Aplikasi CLI Linux untuk ubah video 16:9 jadi klip pendek 9:16 (TikTok/Shorts/Reels), 100% offline.

## Fitur
- Auto-transcribe offline (faster-whisper)
- Auto-cut jadi klip pendek
- Auto-reframe 16:9 -> 9:16
- Dynamic subtitle gaya TikTok

## Install

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

## Usage

    python3 clipforge.py input/video.mp4

## Config

Edit bagian atas clipforge.py: CLIP_DURATION, MAX_CLIPS, WHISPER_MODEL.
