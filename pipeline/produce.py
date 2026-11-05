"""Orquestador: produce y sube los episodios con status "listo".

Uso: python -m pipeline.produce [--episodio ID] [--sin-subir]
"""
import argparse
import datetime as dt
import shutil
import traceback

from . import render, thumbnail, validate, youtube
from .common import EPISODES, OUT, config, load_json, log, save_json


def _credit_lines(credits):
    seen, lines = set(), []
    for c in credits:
        key = c.get("titulo")
        if key in seen or c.get("licencia") in ("propia",):
            continue
        seen.add(key)
        if c.get("generada"):
            lines.append("• Algunas ilustraciones fueron generadas con IA.")
        else:
            autor = c.get("autor") or "autor desconocido"
            lines.append(f"• {autor} — {c.get('licencia')} — {c.get('fuente')}")
    return list(dict.fromkeys(lines))


def _description(piece, ep, credits, extra=""):
    parts = [piece["descripcion"].strip()]
    if extra:
        parts.append(extra)
    parts.append("📖 Lectura: " + "; ".join(ep["referencias"]))
    parts.append("Texto bíblico: Reina-Valera 1909 (dominio público). Narración con voz sintética.")
    cl = _credit_lines(credits)
    if cl:
        parts.append("Ilustraciones (vía Wikimedia Commons):\n" + "\n".join(cl[:15]))
    tags = " ".join("#" + t.replace(" ", "") for t in piece.get("hashtags", []))
    if tags:
        parts.append(tags)
    return "\n\n".join(parts)


def _when(iso):
    if not iso:
        return None
    t = dt.datetime.fromisoformat(iso)
    if t <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=30):
        return None
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def produce(ep_path, cfg, upload):
    ep = load_json(ep_path)
    errs = validate.check(ep)
    if errs:
        raise ValueError("Revisión automática falló:\n- " + "\n- ".join(errs))
    out = OUT / ep["id"]
    out.mkdir(parents=True, exist_ok=True)
    res = {"producido_en": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}

    largo_mp4, credits, dur = render.build(ep["largo"]["escenas"], "largo", out / "work_largo",
                                           cfg, out / "largo.mp4")
    thumb = thumbnail.make(ep["largo"]["miniatura"], out / "miniatura.jpg")
    res["largo"] = {"duracion_s": round(dur), "archivo": "largo.mp4",
                    "imagenes": [c.get("titulo") for c in credits]}
    shorts = []
    for i, s in enumerate(ep["shorts"]):
        mp4, c, d = render.build(s["escenas"], "short", out / f"work_short{i + 1}", cfg,
                                 out / f"short{i + 1}.mp4")
        shorts.append((s, mp4, c, d))
        res.setdefault("shorts", []).append({"duracion_s": round(d), "archivo": mp4.name,
                                             "imagenes": [x.get("titulo") for x in c]})
    rev = ep_path.parent / "revision"
    rev.mkdir(exist_ok=True)
    shutil.copy(out / "work_largo" / "hoja.jpg", rev / "largo.jpg")
    for i in range(len(shorts)):
        shutil.copy(out / f"work_short{i + 1}" / "hoja.jpg", rev / f"short{i + 1}.jpg")
    shutil.copy(thumb, rev / "miniatura.jpg")
    if any(d > 178 for *_, d in shorts):
        raise ValueError("Un Short pasa de 3 minutos")

    if upload and youtube.available():
        modo = cfg.get("modo", "piloto")
        pub = ep.get("publicacion", {})
        synth = cfg.get("divulgar_ia_siempre", False) or any(c.get("generada") for c in credits)
        if modo == "piloto":
            priv, when = "unlisted", None
        else:
            priv, when = "public", _when(pub.get("largo"))
        up = youtube.upload(largo_mp4, ep["largo"]["titulo"], _description(ep["largo"], ep, credits),
                            ep["largo"]["etiquetas"], cfg, priv, when, synth)
        up["miniatura"] = youtube.set_thumbnail(up["id"], thumb)
        res["largo"]["youtube"] = up
        for i, (s, mp4, c, d) in enumerate(shorts):
            when_s = None if modo == "piloto" else _when((pub.get("shorts") or [None] * 9)[i])
            extra = f"▶️ Historia completa: {up['url']}"
            title = s["titulo"] if "#shorts" in s["titulo"].lower() else s["titulo"][:90] + " #Shorts"
            us = youtube.upload(mp4, title, _description(s, ep, c, extra), s["etiquetas"], cfg,
                                priv, when_s, synth or any(x.get("generada") for x in c))
            res["shorts"][i]["youtube"] = us
        ep["status"] = "subido"
        bloqueado = [u for u in [up] + [r["youtube"] for r in res["shorts"]]
                     if u["privacidad_resultante"] != u["privacidad_pedida"]]
        if bloqueado:
            res["aviso"] = ("YouTube cambió la privacidad pedida: el proyecto de Google Cloud "
                            "probablemente necesita la auditoría de la API para publicar.")
    else:
        ep["status"] = "producido"
        res["aviso"] = "No se subió (sin secretos de YouTube o --sin-subir)."
    ep["resultado"] = res
    save_json(ep_path, ep)
    return ep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodio")
    ap.add_argument("--sin-subir", action="store_true")
    a = ap.parse_args()
    cfg = config()
    paths = sorted(EPISODES.glob("*/episode.json"))
    if a.episodio:
        paths = [p for p in paths if p.parent.name == a.episodio]
    else:
        paths = [p for p in paths if load_json(p).get("status") == "listo"]
    if not paths:
        log("No hay episodios para producir.")
        return
    failed = 0
    for p in paths:
        log("=== produciendo", p.parent.name)
        try:
            ep = produce(p, cfg, not a.sin_subir)
            log("resultado:", ep["status"], ep["resultado"].get("aviso", ""))
        except Exception as e:  # noqa: BLE001
            failed += 1
            traceback.print_exc()
            ep = load_json(p)
            ep["status"] = "error"
            ep["error"] = str(e)[:1500]
            save_json(p, ep)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
