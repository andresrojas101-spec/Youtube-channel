"""Descarga las métricas del canal a analytics/ (las lee el agente analista)."""
import datetime as dt

from . import youtube
from .common import ROOT, log, save_json

METRICS = ("views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,"
           "likes,comments,shares,subscribersGained")


def main():
    if not youtube.available():
        log("Sin secretos de YouTube; nada que hacer.")
        return
    today = dt.date.today()
    start = (today - dt.timedelta(days=28)).isoformat()
    ch = youtube.channel_info()
    a = youtube.yta()
    by_video = a.reports().query(ids="channel==MINE", startDate=start, endDate=today.isoformat(),
                                 metrics=METRICS, dimensions="video", sort="-views",
                                 maxResults=50).execute()
    daily = a.reports().query(ids="channel==MINE", startDate=start, endDate=today.isoformat(),
                              metrics="views,estimatedMinutesWatched,subscribersGained",
                              dimensions="day", sort="day").execute()
    cols = [h["name"] for h in by_video.get("columnHeaders", [])]
    rows = [dict(zip(cols, r)) for r in by_video.get("rows", [])]
    ids = [r["video"] for r in rows]
    titles = {}
    for i in range(0, len(ids), 50):
        r = youtube.yt().videos().list(part="snippet,contentDetails", id=",".join(ids[i:i + 50])).execute()
        for it in r.get("items", []):
            titles[it["id"]] = {"titulo": it["snippet"]["title"],
                                "publicado": it["snippet"]["publishedAt"],
                                "duracion": it["contentDetails"]["duration"]}
    for r in rows:
        r.update(titles.get(r["video"], {}))
    dcols = [h["name"] for h in daily.get("columnHeaders", [])]
    data = {"generado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "periodo": [start, today.isoformat()], "canal": ch, "videos": rows,
            "diario": [dict(zip(dcols, r)) for r in daily.get("rows", [])]}
    d = ROOT / "analytics"
    d.mkdir(exist_ok=True)
    save_json(d / f"{today.isoformat()}.json", data)
    save_json(d / "latest.json", data)
    log(f"métricas guardadas: {len(rows)} videos, {ch.get('subscriberCount')} suscriptores")


if __name__ == "__main__":
    main()
