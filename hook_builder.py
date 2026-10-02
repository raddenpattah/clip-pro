"""
Hook Builder - generate teks hook overlay + judul video
"""
from pathlib import Path
from typing import List, Dict, Optional


def get_hook_text(cfg: dict, segments: List[Dict]) -> Optional[str]:
    """
    Ambil teks hook dari config.
    
    Args:
        cfg: config dict dari YAML (bagian 'hook')
        segments: list segment dari Whisper (buat transcript mode)
    
    Returns:
        string hook atau None
    """
    if not cfg.get("enabled", False):
        return None
    
    source = cfg.get("text_source", "none")
    
    if source == "none":
        return None
    elif source == "manual":
        return cfg.get("text_manual", "")
    elif source == "transcript":
        if not segments:
            return None
        # Ambil kalimat pertama dari transkrip
        first_text = segments[0]["text"].strip()
        # Batasi max 50 karakter buat judul
        if len(first_text) > 100:
            first_text = first_text[:97] + '...'
        return first_text.upper()  # KAPITAL biar kayak hook
    else:
        return None


def format_time_ass(sec: float) -> str:
    """Format detik ke H:MM:SS.cc untuk .ass"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def wrap_text(text: str, max_chars_per_line: int = 20) -> List[str]:
    """Potong teks jadi beberapa baris biar gak kepanjangan."""
    words = text.split()
    lines = []
    current = []
    current_len = 0
    for w in words:
        if current_len + len(w) + 1 > max_chars_per_line and current:
            lines.append(" ".join(current))
            current = [w]
            current_len = len(w)
        else:
            current.append(w)
            current_len += len(w) + 1
    if current:
        lines.append(" ".join(current))
    return lines


def write_hook_ass(hook_cfg: dict, out_path: Path) -> None:
    """
    Bikin file .ass khusus untuk overlay teks hook (opening).
    Durasi = hook_cfg['duration'] (default 5s).
    """
    if not hook_cfg.get("enabled", False):
        return
    
    text = hook_cfg.get("_hook_text", "")
    if not text:
        return
    
    duration = hook_cfg.get("duration", 5)
    font_size = hook_cfg.get("font_size", 80)
    font_color = hook_cfg.get("font_color", "&H0000FFFF")
    outline_color = hook_cfg.get("outline_color", "&H00000000")
    outline_size = hook_cfg.get("outline_size", 4)
    position = hook_cfg.get("position", 8)
    margin_top = hook_cfg.get("margin_top", 200)
    box_enabled = hook_cfg.get("box_enabled", True)
    box_color = hook_cfg.get("box_color", "&H80000000")
    
    # Border style: 1=outline+shadow, 3=opaque box
    border_style = 3 if box_enabled else 1
    back_color = box_color if box_enabled else "&H80000000"
    
    # Wrap text jadi beberapa baris
    lines = wrap_text(text, max_chars_per_line=22)
    # Gabung dengan \N (line break di .ass)
    text_multiline = "\\N".join(lines)
    
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hook,Roboto,{font_size},{font_color},{outline_color},{back_color},-1,0,{border_style},{outline_size},2,{position},50,50,{margin_top},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{format_time_ass(0)},{format_time_ass(duration)},Hook,,0,0,0,,{text_multiline}
"""
    out_path.write_text(header, encoding="utf-8")
    print(f"    📝 Hook overlay: {out_path.name}")


def save_title(hook_cfg: dict, out_path: Path) -> None:
    """Simpen judul (teks hook) ke file .txt."""
    if not hook_cfg.get("save_title", False):
        return
    text = hook_cfg.get("_hook_text", "")
    if not text:
        return
    out_path.write_text(text + "\n", encoding="utf-8")
    print(f"    📄 Title: {out_path.name}")


if __name__ == "__main__":
    # Test manual
    test_cfg = {
        "enabled": True,
        "duration": 5,
        "text_source": "manual",
        "text_manual": "TONTON SAMPE HABIS! 3 RAHASIA AI 100 JUTA",
        "font_size": 80,
        "font_color": "&H0000FFFF",
        "outline_color": "&H00000000",
        "outline_size": 4,
        "position": 8,
        "margin_top": 200,
        "box_enabled": True,
        "box_color": "&H80000000",
        "save_title": True,
    }
    
    test_segments = [
        {"start": 0, "end": 5, "text": "Halo semuanya, kali ini gue mau share", "words": []},
    ]
    
    hook_text = get_hook_text(test_cfg, test_segments)
    print(f"Hook text: {hook_text}")
    
    test_cfg["_hook_text"] = hook_text
    write_hook_ass(test_cfg, Path("/tmp/test_hook.ass"))
    print("\n--- Isi /tmp/test_hook.ass ---")
    print(Path("/tmp/test_hook.ass").read_text())
