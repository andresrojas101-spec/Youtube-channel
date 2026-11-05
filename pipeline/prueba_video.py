"""Junta los clips de prueba en un video, lo sube como no listado y deja una hoja de revisión."""
import json
import sys
from pathlib import Path

from PIL import Image

from . import youtube
from .common import ROOT, config, duration, log, run, save_json


def main(carpeta="out/prueba"):
    d = ROOT / carpeta
    clips = sorted(d.glob("*.mp4"))
    if not clips:
        raise SystemExit("No hay clips")
    resumen = json.loads((d / "resumen.json").read_text())
    # 1) video de muestra con música suave
    lista = d / "lista.txt"
    norm = []
    for c in clips:
        n = d / f"n_{c.name}"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(c), "-vf",
             "scale=1080:1920:flags=lanczos,fps=24,format=yuv420p", "-an", "-c:v", "libx264",
             "-crf", "17", "-preset", "medium", str(n)])
        norm.append(n)
    lista.write_text("".join(f"file '{n}'\n" for n in norm))
    total = sum(duration(n) for n in norm)
    music = ROOT / config()["musica"]["archivo"]
    final = d / "prueba_animacion.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
         "-stream_loop", "-1", "-i", str(music), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-af", f"volume=-8dB,afade=t=out:st={max(total - 2, 0):.2f}:d=2", "-c:a", "aac",
         "-t", f"{total:.2f}", "-movflags", "+faststart", str(final)])
    # 2) hoja de revisión: 4 cuadros de cada clip
    rev = ROOT / "pruebas"
    rev.mkdir(exist_ok=True)
    filas = []
    for n in norm:
        dur = duration(n)
        fila = []
        for k in range(4):
            fr = d / f"{n.stem}_{k}.jpg"
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{dur * (k + 0.5) / 4:.2f}", "-i", str(n),
                 "-frames:v", "1", "-vf", "scale=270:480", str(fr)])
            fila.append(Image.open(fr))
        filas.append(fila)
    hoja = Image.new("RGB", (270 * 4, 480 * len(filas)))
    for i, fila in enumerate(filas):
        for k, im in enumerate(fila):
            hoja.paste(im, (k * 270, i * 480))
    hoja.save(rev / "animacion_hoja.jpg", quality=85)
    info = {"clips": resumen, "duracion_s": round(total)}
    # 3) subir como no listado
    if youtube.available():
        cfg = config()
        up = youtube.upload(final, "Prueba de animación (no publicar)",
                            "Prueba interna de animación con modelos abiertos.", ["prueba"], cfg,
                            "unlisted", None, True)
        info["youtube"] = up
    save_json(rev / "animacion.json", info)
    log(json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:])
