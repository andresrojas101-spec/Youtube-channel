"""Cliente de YouTube (subida, miniaturas, estadísticas) con el refresh token de los secretos."""
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .common import log

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def available():
    return all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def _creds():
    return Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                       token_uri="https://oauth2.googleapis.com/token",
                       client_id=os.environ["YT_CLIENT_ID"],
                       client_secret=os.environ["YT_CLIENT_SECRET"], scopes=SCOPES)


def yt():
    return build("youtube", "v3", credentials=_creds(), cache_discovery=False)


def yta():
    return build("youtubeAnalytics", "v2", credentials=_creds(), cache_discovery=False)


def channel_info():
    r = yt().channels().list(part="snippet,statistics", mine=True).execute()
    it = r["items"][0]
    return {"id": it["id"], "titulo": it["snippet"]["title"], **it["statistics"]}


def upload(path, title, description, tags, cfg, privacy, publish_at=None, synthetic=False):
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
              "containsSyntheticMedia": bool(synthetic)}
    if publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at
    body = {
        "snippet": {"title": title[:100], "description": description[:4900],
                    "tags": tags, "categoryId": cfg.get("categoria", "27"),
                    "defaultLanguage": cfg.get("idioma", "es"),
                    "defaultAudioLanguage": cfg.get("idioma", "es")},
        "status": status,
    }
    req = yt().videos().insert(part="snippet,status", body=body,
                               media_body=MediaFileUpload(str(path), chunksize=8 * 1024 * 1024,
                                                          resumable=True, mimetype="video/mp4"))
    resp = None
    while resp is None:
        st, resp = req.next_chunk()
        if st:
            log(f"subiendo {int(st.progress() * 100)}%")
    vid = resp["id"]
    final = resp.get("status", {}).get("privacyStatus")
    log(f"subido {vid} (privacidad pedida={status['privacyStatus']}, resultante={final})")
    return {"id": vid, "privacidad_pedida": status["privacyStatus"], "privacidad_resultante": final,
            "publicar_en": publish_at, "url": f"https://youtu.be/{vid}"}


def set_thumbnail(video_id, path):
    try:
        yt().thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(path))).execute()
        return True
    except Exception as e:  # noqa: BLE001 - requiere canal verificado por teléfono
        log("no se pudo poner miniatura:", str(e)[:300])
        return False
