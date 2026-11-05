"""Utilidades compartidas del pipeline."""
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EPISODES = ROOT / "episodes"
OUT = ROOT / "out"
CACHE = ROOT / ".cache"
FONTS = ROOT / "assets" / "fonts"

UA = "BibliaChannelBot/1.0 (https://andresrojas101-spec.github.io/Youtube-channel/)"


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def save_json(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def config():
    return load_json(ROOT / "canal" / "config.json")


def run(cmd, **kw):
    """Ejecuta un comando y lanza error con stderr legible si falla."""
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"Falló: {' '.join(map(str, cmd))[:300]}\n{r.stderr[-2000:]}")
    return r.stdout


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def log(*a):
    print("[biblia]", *a, flush=True)
