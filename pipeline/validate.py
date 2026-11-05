"""Revisión automática de un episodio antes de producirlo (control de calidad)."""
import sys

from .common import load_json

LIMITES = {"largo": (900, 2200), "short": (55, 170)}


def _words(scenes):
    return sum(len(s["texto"].split()) for s in scenes)


def check(ep):
    errs = []
    for k in ("id", "historia", "referencias", "largo", "shorts"):
        if k not in ep:
            errs.append(f"falta '{k}'")
    if errs:
        return errs
    if not ep["referencias"]:
        errs.append("sin referencias bíblicas")
    pieces = [("largo", ep["largo"])] + [(f"short {i + 1}", s) for i, s in enumerate(ep["shorts"])]
    for name, p in pieces:
        kind = "largo" if name == "largo" else "short"
        for k in ("titulo", "descripcion", "etiquetas", "escenas"):
            if not p.get(k):
                errs.append(f"{name}: falta '{k}'")
        if not p.get("escenas"):
            continue
        if len(p["titulo"]) > 100:
            errs.append(f"{name}: título de más de 100 caracteres")
        if len(", ".join(p["etiquetas"])) > 450:
            errs.append(f"{name}: etiquetas demasiado largas")
        lo, hi = LIMITES[kind]
        w = _words(p["escenas"])
        if not ep.get("prueba") and not lo <= w <= hi:
            errs.append(f"{name}: {w} palabras (esperado {lo}-{hi})")
        for j, sc in enumerate(p["escenas"]):
            if not sc.get("texto", "").strip():
                errs.append(f"{name} escena {j + 1}: sin texto")
            if not sc.get("imagen"):
                errs.append(f"{name} escena {j + 1}: sin imagen")
    if "miniatura" not in ep["largo"]:
        errs.append("largo: falta 'miniatura'")
    return errs


if __name__ == "__main__":
    bad = 0
    for path in sys.argv[1:]:
        e = check(load_json(path))
        print(path, "OK" if not e else "\n  - " + "\n  - ".join(e))
        bad += bool(e)
    sys.exit(1 if bad else 0)
