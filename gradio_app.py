"""
gradio_app.py - Web UI buat ClipForge.
"""
import gradio as gr
import subprocess
import sys
from pathlib import Path
import yaml
import os

PROJECT_DIR = Path(__file__).parent
VENV_PYTHON = PROJECT_DIR / "venv" / "bin" / "python3"
CLIPFORGE = PROJECT_DIR / "clipforge.py"
CONFIG = PROJECT_DIR / "config.yaml"
OUTPUT_DIR = PROJECT_DIR / "output"


def update_config(engine: str, hook_text: str, hook_position: str):
    """Update config.yaml dari UI."""
    with open(CONFIG, "r") as f:
        cfg = yaml.safe_load(f)
    
    # Update engine
    if "reframe" not in cfg:
        cfg["reframe"] = {}
    cfg["reframe"]["engine"] = engine
    
    # Update hook
    if "hook" not in cfg:
        cfg["hook"] = {}
    cfg["hook"]["text_source"] = "manual"
    cfg["hook"]["text_manual"] = hook_text
    pos_map = {"bawah": 2, "tengah": 5, "atas": 8}
    cfg["hook"]["position"] = pos_map.get(hook_position, 2)
    
    with open(CONFIG, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)


def process_video(video_file, engine, hook_text, hook_position):
    """Process video via clipforge.py."""
    if video_file is None:
        return "❌ Upload video dulu!", None
    
    # Update config
    update_config(engine, hook_text, hook_position)
    
    # Pindah video ke input/
    src = Path(video_file)
    input_dir = PROJECT_DIR / "input"
    input_dir.mkdir(exist_ok=True)
    dst = input_dir / src.name
    
    if src != dst:
        import shutil
        shutil.copy(src, dst)
    
    # Jalanin clipforge
    log = f"🚀 Processing: {dst.name}\n"
    log += f"   Engine: {engine}\n"
    log += f"   Hook: {hook_text}\n"
    log += f"   Posisi: {hook_position}\n\n"
    
    cmd = [
        str(VENV_PYTHON),
        str(CLIPFORGE),
        str(dst),
        "--engine", engine,
        "--yes",
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(PROJECT_DIR),
            timeout=1800,  # 30 menit max
        )
        log += result.stdout
        if result.stderr:
            log += "\n=== STDERR ===\n" + result.stderr
        
        # Cari output file
        output_files = sorted(OUTPUT_DIR.glob(f"{dst.stem}_clip*.mp4"))
        if output_files:
            log += f"\n\n✅ Selesai! {len(output_files)} klip dihasilkan."
            return log, str(output_files[0])
        else:
            log += "\n\n⚠️  Ga ada output file."
            return log, None
    except subprocess.TimeoutExpired:
        return log + "\n\n❌ Timeout (lebih dari 30 menit)", None
    except Exception as e:
        return log + f"\n\n❌ Error: {e}", None


# ===== UI =====
with gr.Blocks(title="ClipForge", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 🎬 ClipForge")
    gr.Markdown("Auto clipper video YouTube/podcast jadi klip 9:16 (TikTok/Shorts/Reels)")
    
    with gr.Row():
        with gr.Column(scale=1):
            video_input = gr.File(
                label="📹 Upload Video",
                file_types=["video"],
            )
            
            engine_input = gr.Dropdown(
                choices=["single", "dual", "multi", "auto"],
                value="single",
                label="🎯 Engine",
                info="single=1 orang fokus, dual=2 orang, multi=3-4 orang",
            )
            
            hook_text_input = gr.Textbox(
                value="TONTON SAMPE HABIS! 🔥",
                label="🎣 Hook Text",
                max_lines=2,
            )
            
            hook_position_input = gr.Dropdown(
                choices=["bawah", "tengah", "atas"],
                value="bawah",
                label="📍 Posisi Hook",
            )
            
            process_btn = gr.Button("🚀 Process Video", variant="primary", size="lg")
        
        with gr.Column(scale=2):
            log_output = gr.Textbox(
                label="📋 Log",
                lines=20,
                max_lines=30,
                autoscroll=True,
            )
            
            video_output = gr.Video(
                label="🎬 Preview Klip Pertama",
            )
    
    process_btn.click(
        fn=process_video,
        inputs=[video_input, engine_input, hook_text_input, hook_position_input],
        outputs=[log_output, video_output],
    )
    
    gr.Markdown("---")
    gr.Markdown("💡 **Tips:** Engine `single` paling stabil buat podcast multi-orang.")


if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )
