import psutil


def get_status():
    cpu = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    gpu_temp = gpu_load = vram_pct = vram_used = vram_total = 0.0

    try:
        import subprocess
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3
        )
        if r.returncode == 0:
            p = r.stdout.strip().split(", ")
            gpu_temp = float(p[0])
            gpu_load = float(p[1])
            vram_used = float(p[2])
            vram_total = float(p[3])
            vram_pct = (vram_used / vram_total * 100) if vram_total > 0 else 0
    except Exception:
        pass

    return {
        "cpu": cpu,
        "ram_pct": mem.percent,
        "ram_used": round(mem.used / 1073741824, 1),
        "ram_total": round(mem.total / 1073741824, 1),
        "gpu_temp": gpu_temp,
        "gpu_load": round(gpu_load, 1),
        "vram_pct": round(vram_pct, 1),
        "vram_used": round(vram_used),
        "vram_total": round(vram_total),
    }
