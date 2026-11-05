"""Miniatura 1280x720: imagen en sepia + texto grande."""
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from . import images
from .common import FONTS

W, H = 1280, 720
YELLOW = (255, 206, 64)


def _cover(im, w, h):
    return ImageOps.fit(im, (w, h), method=Image.LANCZOS, centering=(0.5, 0.4))


def _sepia(im):
    g = ImageOps.grayscale(im)
    return ImageOps.colorize(g, black=(25, 15, 8), mid=(150, 110, 70), white=(255, 238, 205))


def _wrap(draw, text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return [l for l in lines if l]


def make(spec, out):
    img_path, _ = images.resolve(spec["imagen"])
    base = Image.open(img_path).convert("RGB")
    im = _cover(_sepia(base) if images.is_grayscale(img_path) else base, W, H)
    im = ImageEnhance.Contrast(im).enhance(1.25)
    # degradado oscuro a la izquierda para que el texto se lea
    shade = Image.new("L", (W, H))
    sd = ImageDraw.Draw(shade)
    for x in range(W):
        sd.line([(x, 0), (x, H)], fill=int(215 * max(0, 1 - x / (W * 0.72))))
    im = Image.composite(Image.new("RGB", (W, H), (8, 5, 2)), im, shade)
    d = ImageDraw.Draw(im)
    text = spec["texto"].upper()
    size = 132
    while size > 60:
        font = ImageFont.truetype(str(FONTS / "Anton-Regular.ttf"), size)
        lines = _wrap(d, text, font, W * 0.56)
        if len(lines) <= 3:
            break
        size -= 8
    y = (H - len(lines) * size * 1.08) / 2
    for i, line in enumerate(lines):
        color = YELLOW if i == len(lines) - 1 else (255, 255, 255)
        d.text((60, y), line, font=font, fill=color, stroke_width=7, stroke_fill=(0, 0, 0))
        y += size * 1.08
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=60))
    im.save(out, "JPEG", quality=92)
    return out
