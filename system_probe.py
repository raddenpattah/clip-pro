"""
system_probe.py - Deteksi hardware & auto-tune config ClipForge.
"""
from __future__ import annotations
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import yaml
except ImportError:
    raise SystemExit("pip install pyyaml")


def _cpu_count_physical() -> int:
    if HAS_PSUTIL:
        return psutil.cpu_count(logical=False) or 2
    try:
        import multiprocessing
        return max(1, multiprocessing.cpu_count() // 2)
    except Exception:
        return 2


def _cpu_count_logical() -> int:
    if HAS_PSUTIL:
        return psutil.cpu_count(logical=True) or 2
    import multiprocessing
    return multiprocessing.cpu_count()


def _ram_gb() -> tuple[float, float]:
    if HAS_PSUTIL:
        vm = psutil.virtual_memory()
        return round(vm.total / 1e9, 1), round(vm.available / 1e9, 1)
    return 0.0, 0.0


def _has_avx2() -> bool:
    try:
        with open("/proc/cpuinfo") as f:
            return "avx2" in f.read().lower()
    except Exception:
        return False


def _has_cuda() -> bool:
    if shutil.which("nvidia-smi"):
        try:
            r = subprocess.run(["nvidia-smi"], capture_output=True, timeout=3)
            return r.returncode == 0
        except Exception:
            pass
    return False


def _disk_free_gb(path: Path) -> float:
    try:
        return round(shutil.disk_usage(path).free / 1e9, 1)
    except Exception:
        return 0.0


def _cpu_load() -> tuple[float, int]:
    try:
        l = os.getloadavg()[0]
    except Exception:
        l = 0.0
    return round(l, 2), _cpu_count_logical()


def probe_system(project_dir: Path) -> dict[str, Any]:
    total_ram, avail_ram = _ram_gb()
    load1, cores_log = _cpu_load()
    return {
        "os": f"{platform.system()} {platform.release()}",
        "arch": platform.machine(),
        "cpu_cores_physical": _cpu_count_physical(),
        "cpu_cores_logical": cores_log,
        "cpu_avx2": _has_avx2(),
        "ram_total_gb": total_ram,
        "ram_available_gb": avail_ram,
        "has_cuda": _has_cuda(),
        "disk_free_gb": _disk_free_gb(project_dir),
        "load_1min": load1,
    }


def classify(spec: dict[str, Any]) -> str:
    cores = spec["cpu_cores_physical"]
    ram = spec["ram_total_gb"]
    cuda = spec["has_cuda"]
    if cuda and cores >= 4 and ram >= 8:
        return "strong"
    if cores >= 4 and ram >= 8:
        return "strong"
    if cores >= 4 or ram >= 8:
        return "medium"
    return "weak"


def recommend_config(spec: dict[str, Any]) -> dict[str, Any]:
    tier = classify(spec)
    cores = spec["cpu_cores_physical"]
    ram = spec["ram_total_gb"]
    cuda = spec["has_cuda"]

    if tier == "strong":
        whisper_model = "small"
        compute_type = "float16" if cuda else "int8"
        beam = 5 if cuda else 3
        preset = "medium"
        crf = 21
        sample_fps = 8
        parallel = min(4, cores)
        smart_on = True
        vad = False
        low_prio = False
    elif tier == "medium":
        whisper_model = "base"
        compute_type = "int8"
        beam = 3
        preset = "fast"
        crf = 23
        sample_fps = 5
        parallel = 2
        smart_on = True
        vad = False
        low_prio = False
    else:
        whisper_model = "tiny" if ram < 4 else "base"
        compute_type = "int8"
        beam = 1
        preset = "veryfast"
        crf = 24
        sample_fps = 3
        parallel = 1
        smart_on = ram >= 6
        vad = True
        low_prio = True

    return {
        "_meta": {
            "tier": tier,
            "generated_by": "system_probe",
            "spec": spec,
        },
        "whisper": {
            "model": whisper_model,
            "compute_type": compute_type,
            "beam_size": beam,
            "cpu_threads": cores,
            "vad_filter": vad,
        },
        "encode": {
            "preset": preset,
            "crf": crf,
            "threads": cores,
        },
        "reframe": {
            "enabled": smart_on,
            "detector": "yunet",
            "tracking": "auto",
            "sample_fps": sample_fps,
            "smoothing": {
                "mode": "ema",
                "alpha": 0.3,
                "deadzone_px": 40,
            },
            "fallback": "center",
        },
        "runtime": {
            "parallel_clips": parallel,
            "low_priority": low_prio,
            "temp_cleanup": True,
        },
    }


def write_auto_config(rec: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(rec, f, sort_keys=False, allow_unicode=True)


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_merged_config(user_path: Path, auto_path: Path) -> dict[str, Any]:
    user = {}
    auto = {}
    if user_path.exists():
        user = yaml.safe_load(user_path.read_text()) or {}
    if auto_path.exists():
        auto = yaml.safe_load(auto_path.read_text()) or {}
    return _deep_merge(auto, user)


def print_report(spec: dict[str, Any], rec: dict[str, Any]) -> None:
    tier = rec["_meta"]["tier"]
    tier_label = {"weak": "⚠️  LEMAH", "medium": "🟡 MEDIUM", "strong": "🟢 KUAT"}[tier]
    avx = "OK" if spec["cpu_avx2"] else "NO"
    gpu = "CUDA" if spec["has_cuda"] else "none"

    print(f"\n🔍 System detected:")
    print(f"   CPU    : {spec['cpu_cores_physical']}C / {spec['cpu_cores_logical']}T @ {spec['arch']} (AVX2 {avx})")
    print(f"   RAM    : {spec['ram_total_gb']} GB ({spec['ram_available_gb']} GB free)")
    print(f"   GPU    : {gpu}")
    print(f"   Disk   : {spec['disk_free_gb']} GB free")
    print(f"   Load   : {spec['load_1min']} / {spec['cpu_cores_logical']}")
    print(f"   Tier   : {tier_label}")

    print(f"\n⚙️  Auto-tuned:")
    print(f"   whisper.model        : {rec['whisper']['model']}")
    print(f"   whisper.compute_type : {rec['whisper']['compute_type']}")
    print(f"   encode.preset        : {rec['encode']['preset']} (crf {rec['encode']['crf']})")
    print(f"   reframe.enabled      : {'on' if rec['reframe']['enabled'] else 'OFF'}")
    print(f"   reframe.sample_fps   : {rec['reframe']['sample_fps']}")
    print(f"   runtime.parallel     : {rec['runtime']['parallel_clips']}")
    if rec["runtime"]["low_priority"]:
        print(f"   ⚠️  low_priority ON")
    print()


def prompt_weak_hardware(spec: dict, rec: dict) -> str:
    print("⚠️  Hardware LEMAH terdeteksi. Smart reframe bakal LAMBAT.\n")
    print("Pilihan:")
    print("   [1] Lanjut auto-degrade (matiin smart reframe, preset veryfast)")
    print("   [2] Lanjut paksa (semua fitur ON, resiko lambat/panas)")
    print("   [3] Custom (tanya satu-satu tiap fitur)")
    print("   [4] Batal\n")
    while True:
        try:
            ans = input("Pilihan [1-4]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return "cancel"
        if ans == "1":
            rec["reframe"]["enabled"] = False
            rec["encode"]["preset"] = "veryfast"
            return "degrade"
        if ans == "2":
            rec["reframe"]["enabled"] = True
            return "force"
        if ans == "3":
            return "custom"
        if ans == "4":
            return "cancel"
        print("  ⚠️  Pilihan ga valid, coba lagi.")


def prompt_custom(rec: dict) -> None:
    def ask(question: str, current) -> str:
        try:
            ans = input(f"  {question} [{current}]: ").strip()
            return ans if ans else str(current)
        except (EOFError, KeyboardInterrupt):
            return str(current)

    print("\n🛠️  Custom tuning (Enter = default):")
    rec["whisper"]["model"] = ask("Whisper model (tiny/base/small/medium)", rec["whisper"]["model"])
    rec["encode"]["preset"] = ask("x264 preset (veryfast/fast/medium/slow)", rec["encode"]["preset"])
    ans = ask("Smart reframe on/off (y/n)", "y" if rec["reframe"]["enabled"] else "n")
    rec["reframe"]["enabled"] = ans.lower().startswith("y")
    try:
        rec["reframe"]["sample_fps"] = int(ask("Face sample fps (3/5/8)", rec["reframe"]["sample_fps"]))
    except ValueError:
        pass
    try:
        rec["runtime"]["parallel_clips"] = int(ask("Parallel clips (1/2/4)", rec["runtime"]["parallel_clips"]))
    except ValueError:
        pass
    print()
