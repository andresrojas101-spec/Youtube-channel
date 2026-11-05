"""Obtiene imágenes: Wikimedia Commons (dominio público) o generadas.

Especificación de imagen en episode.json (una de estas):
  {"archivo": "File:Nombre exacto.jpg"}            -> archivo concreto de Commons
  {"buscar": "Gustave Doré David Goliath", "n": 0} -> n-ésimo resultado de búsqueda en Commons
  {"generar": "prompt en inglés"}                   -> imagen generada (Pollinations, gratis)
  {"local": "assets/img/x.jpg"}                     -> archivo del repo
Se puede añadir "respaldo": {...otra especificación...}.
"""
import hashlib
import json
import random
import re
import urllib.parse
from pathlib import Path

import requests
from PIL import Image

from .common import CACHE, ROOT, UA, log

API = "https://commons.wikimedia.org/w/api.php"
S = requests.Session()
S.headers["User-Agent"] = UA

OK_LICENSES = ("public domain", "pd", "cc0", "cc by", "cc-by")
ESTILO = (", 19th century biblical engraving in the style of Gustave Doré, dramatic chiaroscuro, "
          "fine crosshatching, epic composition, no text, no watermark")


def _key(spec):
    return hashlib.sha1(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:16]


def _strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def _commons_pages(params):
    base = {"action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 2600}
    base.update(params)
    r = S.get(API, params=base, timeout=40)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    return sorted(pages.values(), key=lambda p: p.get("index", 0))


def _usable(page):
    ii = (page.get("imageinfo") or [{}])[0]
    if ii.get("mime") not in ("image/jpeg", "image/png", "image/tiff"):
        return None
    if ii.get("width", 0) < 900 or ii.get("height", 0) < 600:
        return None
    meta = ii.get("extmetadata", {})
    lic = _strip_html(meta.get("LicenseShortName", {}).get("value", "")).lower()
    if not any(l in lic for l in OK_LICENSES):
        return None
    return {
        "url": ii.get("thumburl") or ii.get("url"),
        "titulo": page.get("title"),
        "autor": _strip_html(meta.get("Artist", {}).get("value", ""))[:120],
        "licencia": _strip_html(meta.get("LicenseShortName", {}).get("value", "")),
        "fuente": ii.get("descriptionurl"),
    }


def _download(url, dest):
    r = S.get(url, timeout=120)
    r.raise_for_status()
    dest.write_bytes(r.content)
    Image.open(dest).verify()
    return dest


def _from_commons(spec, dest):
    if "archivo" in spec:
        pages = _commons_pages({"titles": spec["archivo"]})
        cands = [c for c in (_usable(p) for p in pages) if c]
    else:
        pages = _commons_pages({"generator": "search", "gsrsearch": spec["buscar"] + " filetype:bitmap",
                                "gsrnamespace": 6, "gsrlimit": 30})
        cands = [c for c in (_usable(p) for p in pages) if c]
    if not cands:
        raise LookupError(f"Commons sin resultados útiles para {spec}")
    c = cands[min(spec.get("n", 0), len(cands) - 1)]
    _download(c["url"], dest)
    return c


def _generate(spec, dest):
    prompt = spec["generar"] + ESTILO
    seed = spec.get("semilla", random.randint(1, 10**6))
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) +
           f"?width=1920&height=1080&nologo=true&seed={seed}")
    _download(url, dest)
    return {"titulo": "Ilustración generada", "autor": "IA", "licencia": "generada",
            "fuente": None, "generada": True, "prompt": spec["generar"]}


def resolve(spec):
    """Devuelve (ruta_local, credito). Usa caché por especificación."""
    d = CACHE / "images"
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"{_key(spec)}.img"
    meta = d / f"{_key(spec)}.json"
    if dest.exists() and meta.exists():
        return dest, json.loads(meta.read_text())
    try:
        if "local" in spec:
            dest = ROOT / spec["local"]
            credit = {"titulo": spec["local"], "licencia": "propia"}
        elif "generar" in spec:
            credit = _generate(spec, dest)
        else:
            credit = _from_commons(spec, dest)
    except Exception as e:  # noqa: BLE001
        if "respaldo" in spec:
            log("imagen falló, usando respaldo:", e)
            return resolve(spec["respaldo"])
        if "buscar" in spec:
            log("búsqueda falló, generando:", e)
            return resolve({"generar": spec["buscar"]})
        if "generar" in spec:
            log("generación falló, usando un grabado de Doré:", e)
            return resolve({"buscar": "Gustave Doré Bible illustration",
                            "n": int(_key(spec), 16) % 12})
        raise
    meta.write_text(json.dumps(credit, ensure_ascii=False))
    log("imagen ok:", credit.get("titulo"))
    return dest, credit


def is_grayscale(path):
    im = Image.open(path).convert("RGB").resize((64, 64))
    px = list(im.getdata())
    return sum(max(p) - min(p) for p in px) / len(px) < 18
