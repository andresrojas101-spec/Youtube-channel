"""Narración con Piper (gratis, corre local en el runner)."""
import sys
import urllib.request
from pathlib import Path

from .common import CACHE, run, log

HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
VOICE_PATHS = {
    "es_ES-davefx-medium": "es/es_ES/davefx/medium/es_ES-davefx-medium",
    "es_MX-claude-high": "es/es_MX/claude/high/es_MX-claude-high",
    "es_MX-ald-medium": "es/es_MX/ald/medium/es_MX-ald-medium",
}


def ensure_voice(name):
    d = CACHE / "voices"
    d.mkdir(parents=True, exist_ok=True)
    model = d / f"{name}.onnx"
    for suffix in (".onnx", ".onnx.json"):
        f = d / f"{name}{suffix}"
        if not f.exists() or f.stat().st_size == 0:
            log("descargando voz", f.name)
            urllib.request.urlretrieve(HF + VOICE_PATHS[name] + suffix, f)
    return model


def clean_for_speech(text):
    # Piper lee mejor sin comillas tipográficas ni guiones largos
    for a, b in (("«", ""), ("»", ""), ("“", ""), ("”", ""), ("—", ", "), ("–", ", ")):
        text = text.replace(a, b)
    return " ".join(text.split())


def synth(text, out_wav, voz_cfg):
    model = ensure_voice(voz_cfg["modelo"])
    run([sys.executable, "-m", "piper", "-m", str(model),
         "--length-scale", str(voz_cfg.get("velocidad", 1.08)),
         "--sentence-silence", str(voz_cfg.get("silencio", 0.35)),
         "-f", str(out_wav)], input=clean_for_speech(text))
    return Path(out_wav)
