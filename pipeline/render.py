"""Arma videos (largo 16:9 y Shorts 9:16) con ffmpeg."""
import re
from pathlib import Path

from . import images, tts
from .common import FONTS, ROOT, duration, log, run

FPS = 25
XF = 0.6          # duración del fundido entre escenas (s)
LEAD = 0.15       # silencio antes de cada frase (s)
TAIL = 0.55       # silencio después de cada frase (s)

FORMATS = {
    "largo": {"W": 1920, "H": 1080, "S": 2.0, "zoom": 0.12, "words": 6,
              "font": "DejaVu Sans", "size": 50, "marginv": 60, "align": 2},
    "short": {"W": 1080, "H": 1920, "S": 1.6, "zoom": 0.10, "words": 3,
              "font": "Anton", "size": 104, "marginv": 560, "align": 2},
}
MOTIONS = ["in", "right", "out", "left", "in", "down", "out", "up"]


def _zoompan(motion, frames, W, H, zoom):
    F = max(frames - 1, 1)
    p = f"(on/{F})"
    zc = f"{1 + zoom:.3f}"
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if motion == "in":
        z, x, y = f"1+{zoom}*{p}", cx, cy
    elif motion == "out":
        z, x, y = f"{zc}-{zoom}*{p}", cx, cy
    elif motion == "right":
        z, x, y = zc, f"(iw-iw/zoom)*{p}", cy
    elif motion == "left":
        z, x, y = zc, f"(iw-iw/zoom)*(1-{p})", cy
    elif motion == "down":
        z, x, y = zc, cx, f"(ih-ih/zoom)*{p}"
    elif motion == "up":
        z, x, y = zc, cx, f"(ih-ih/zoom)*(1-{p})"
    else:  # fija
        z, x, y = "1", cx, cy
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS}"


def _grade(gray):
    if gray:  # grabados en blanco y negro -> sepia cálido, la firma visual del canal
        return ("colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131,"
                "eq=contrast=1.08:brightness=-0.03,vignette=PI/4.5")
    return "eq=saturation=0.88:contrast=1.06,colorbalance=rs=.05:bs=-.05,vignette=PI/5"


def scene_clip(img, length, fmt, motion, out):
    f = FORMATS[fmt]
    W, H, S = f["W"], f["H"], f["S"]
    sw, sh = int(W * S) // 2 * 2, int(H * S) // 2 * 2
    frames = int(round(length * FPS))
    vf = (f"scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=lanczos,"
          f"crop={sw}:{sh},{_zoompan(motion, frames, W, H, f['zoom'])},"
          f"{_grade(images.is_grayscale(img))},format=yuv420p,setsar=1")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(img), "-vf", vf,
         "-frames:v", str(frames), "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "18", str(out)])
    return out


# ---------- subtítulos ----------

def _chunks(text, maxw):
    words = text.split()
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= maxw or (len(cur) >= max(2, maxw - 2) and re.search(r"[.,;:!?]$", w)):
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def _ts(t):
    h, rem = divmod(max(t, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_ass(timeline, fmt, path):
    f = FORMATS[fmt]
    upper = fmt == "short"
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {f['W']}", f"PlayResY: {f['H']}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{f['font']},{f['size']},&H00FFFFFF,&H00FFFFFF,&H00101010,&H64000000,"
        f"{-1 if fmt == 'largo' else 0},0,0,0,100,100,0,0,1,{4 if upper else 3},1,{f['align']},80,80,{f['marginv']},1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for start, dur, text in timeline:
        parts = _chunks(text, f["words"])
        total = sum(len(p) for p in parts) or 1
        t = start
        for p in parts:
            d = dur * len(p) / total
            txt = p.replace("{", "(").replace("}", ")")
            if upper:
                txt = txt.upper()
            lines.append(f"Dialogue: 0,{_ts(t)},{_ts(t + d)},Default,,0,0,0,,{txt}")
            t += d
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------- armado completo ----------

def build(scenes, fmt, work, cfg, out_mp4):
    """scenes: lista de {texto, imagen, movimiento?}. Devuelve (mp4, créditos, duración)."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    n = len(scenes)
    segs, wavs, credits, clips, timeline = [], [], [], [], []
    t0 = 0.0
    for i, sc in enumerate(scenes):
        wav = tts.synth(sc["texto"], work / f"v{i:03d}.wav", cfg["voz"])
        ad = duration(wav)
        seg = LEAD + ad + TAIL
        img, credit = images.resolve(sc["imagen"])
        credits.append(credit)
        length = seg + (XF if i < n - 1 else 0)
        motion = sc.get("movimiento") or MOTIONS[i % len(MOTIONS)]
        if fmt == "short" and not sc.get("movimiento"):
            motion = ["right", "left", "in"][i % 3]
        clips.append(scene_clip(img, length, fmt, motion, work / f"c{i:03d}.mp4"))
        wavs.append(wav)
        segs.append(seg)
        timeline.append((t0 + LEAD, ad, sc["texto"]))
        t0 += seg
        log(f"{fmt} escena {i + 1}/{n} ({seg:.1f}s)")
    total = sum(segs)

    # Narración: cada frase con su silencio, luego un toque de sala y normalización
    a_in, a_f = [], []
    for i, (w, s) in enumerate(zip(wavs, segs)):
        a_in += ["-i", str(w)]
        a_f.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,"
                   f"adelay={int(LEAD * 1000)}:all=1,apad=whole_dur={s:.3f}[a{i}]")
    a_f.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1,"
               "aecho=0.8:0.5:40:0.12,loudnorm=I=-15:TP=-1.5[nar]")
    narr = work / "narracion.wav"
    run(["ffmpeg", "-y", "-loglevel", "error", *a_in, "-filter_complex", ";".join(a_f),
         "-map", "[nar]", str(narr)])

    ass = work / "subs.ass"
    write_ass(timeline, fmt, ass)

    # Video: cadena de fundidos + subtítulos; audio: narración + música de fondo
    v_in, v_f = [], []
    for c in clips:
        v_in += ["-i", str(c)]
    prev, off = "[0:v]", 0.0
    for i in range(1, n):
        off += segs[i - 1]
        v_f.append(f"{prev}[{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[x{i}]")
        prev = f"[x{i}]"
    fontsdir = str(FONTS).replace(":", r"\:")
    v_f.append(f"{prev}subtitles={ass}:fontsdir={fontsdir}[v]")
    music = ROOT / cfg["musica"]["archivo"]
    mvol = cfg["musica"].get("volumen_db", -24)
    v_f.append(f"[{n + 1}:a]volume={mvol}dB,atrim=0:{total:.3f},afade=t=in:d=2,"
               f"afade=t=out:st={max(total - 3, 0):.3f}:d=3[mus]")
    v_f.append(f"[{n}:a][mus]amix=inputs=2:duration=first:normalize=0[a]")
    run(["ffmpeg", "-y", "-loglevel", "error", *v_in, "-i", str(narr),
         "-stream_loop", "-1", "-i", str(music), "-filter_complex", ";".join(v_f),
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
         "-t", f"{total:.3f}", str(out_mp4)])
    log(f"{fmt} listo: {out_mp4} ({total:.0f}s)")
    return Path(out_mp4), credits, total
