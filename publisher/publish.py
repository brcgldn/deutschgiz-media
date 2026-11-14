#!/usr/bin/env python3
"""Deutschgiz Instagram yayın robotu.

schedule.json içindeki, zamanı gelmiş ve henüz yayınlanmamış gönderileri
Instagram API (Instagram Login, graph.instagram.com) ile yayınlar ve
sonucu state/published.json'a yazar. Yalnızca standart kütüphane kullanır.

Ortam değişkenleri:
  IG_ACCESS_TOKEN  Instagram erişim anahtarı (GitHub secret)       [zorunlu]
  DRY_RUN          "1" ise hiçbir şey yayınlanmaz, sadece plan yazılır
  ONLY_ID          Sadece bu kimliği (ör. "P1") değerlendir
  FORCE            "1" ise ONLY_ID'deki gönderi zamanı beklenmeden yayınlanır
  NOW              Test için şimdiki zaman (ISO 8601)
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEDULE = os.path.join(ROOT, "schedule.json")
STATE = os.path.join(ROOT, "state", "published.json")
API = "https://graph.instagram.com/v21.0"
MAX_LATE = dt.timedelta(hours=6)       # bundan daha geç kalmış gönderi otomatik yayınlanmaz
POLL_EVERY, POLL_MAX = 10, 60          # konteyner hazır olana kadar 10 sn arayla en fazla 10 dk


def log(msg):
    print(msg, flush=True)


def api(method, path, params, token):
    params = dict(params, access_token=token)
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {body}") from None


def wait_ready(container, token):
    for _ in range(POLL_MAX):
        st = api("GET", container, {"fields": "status_code,status"}, token)
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Konteyner {container} hata verdi: {st}")
        time.sleep(POLL_EVERY)
    raise RuntimeError(f"Konteyner {container} {POLL_EVERY * POLL_MAX} sn içinde hazır olmadı")


def publish(item, user_id, token):
    if item["type"] == "reel":
        params = {
            "media_type": "REELS",
            "video_url": item["video_url"],
            "caption": item["caption"],
            "share_to_feed": "true",
        }
        if item.get("cover_url"):
            params["cover_url"] = item["cover_url"]
        container = api("POST", f"{user_id}/media", params, token)["id"]
    elif item["type"] == "carousel":
        urls = item["image_urls"]
        if not 2 <= len(urls) <= 10:
            raise RuntimeError("Karusel 2–10 görsel olmalı")
        children = []
        for u in urls:
            c = api("POST", f"{user_id}/media", {"image_url": u, "is_carousel_item": "true"}, token)["id"]
            children.append(c)
        for c in children:
            wait_ready(c, token)
        container = api("POST", f"{user_id}/media", {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": item["caption"],
        }, token)["id"]
    else:
        raise RuntimeError(f"Bilinmeyen tür: {item['type']}")
    wait_ready(container, token)
    return api("POST", f"{user_id}/media_publish", {"creation_id": container}, token)["id"]


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    now = dt.datetime.fromisoformat(os.environ["NOW"]) if os.environ.get("NOW") else dt.datetime.now(dt.timezone.utc)
    dry = os.environ.get("DRY_RUN") == "1"
    only = os.environ.get("ONLY_ID") or None
    force = os.environ.get("FORCE") == "1"
    if force and not only:
        sys.exit("FORCE için ONLY_ID de verilmeli")

    schedule = load(SCHEDULE, {})
    state = load(STATE, {})
    if schedule.get("paused"):
        log("schedule.json: paused=true, hiçbir şey yapılmadı.")
        return 0

    due, failed = [], False
    for item in schedule.get("items", []):
        iid = item["id"]
        if only and iid != only:
            continue
        rec = state.get(iid, {})
        if rec.get("media_id") or rec.get("status") == "skipped_late":
            continue
        if rec.get("status") == "publishing":
            # Önceki çalışma yayın sırasında yarıda kaldı: tekrar denemek çift gönderi riski taşır.
            log(f"⚠️  {iid}: önceki denemenin sonucu belirsiz, otomatik tekrar YOK. Instagram'ı kontrol et; "
                f"yayınlanmadıysa state/published.json'dan {iid} kaydını sil.")
            failed = True
            continue
        at = dt.datetime.fromisoformat(item["publish_at"])
        if force:
            due.append(item)
        elif at <= now:
            if now - at > MAX_LATE:
                log(f"⏭️  {iid}: {item['publish_at']} çok geride kaldı (>{MAX_LATE}), atlandı.")
                state[iid] = {"status": "skipped_late", "checked_at": now.isoformat()}
                failed = True
            else:
                due.append(item)

    if dry and os.environ.get("IG_ACCESS_TOKEN"):
        me = api("GET", "me", {"fields": "user_id,username"}, os.environ["IG_ACCESS_TOKEN"])
        log(f"🔑 Anahtar çalışıyor: @{me.get('username')} ({me.get('user_id') or me.get('id')})")
    if dry:
        pending = [i["id"] for i in schedule.get("items", [])
                   if not state.get(i["id"], {}).get("media_id") and state.get(i["id"], {}).get("status") != "skipped_late"]
        log(f"Sırada bekleyen: {', '.join(pending) or '—'}")

    if not due:
        log(f"{now.isoformat()}: zamanı gelmiş gönderi yok.")
        if not dry:
            save_state(state)
        return 1 if failed else 0

    if dry:
        for item in due:
            log(f"[DRY RUN] yayınlanacaktı: {item['id']} ({item['type']}) – {item['publish_at']}")
        return 0

    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        sys.exit("IG_ACCESS_TOKEN tanımlı değil (GitHub › Settings › Secrets and variables › Actions).")
    me = api("GET", "me", {"fields": "user_id,username"}, token)
    user_id = me.get("user_id") or me["id"]
    log(f"Hesap: @{me.get('username')} ({user_id})")

    for item in sorted(due, key=lambda i: i["publish_at"]):
        iid = item["id"]
        state[iid] = {"status": "publishing", "started_at": now.isoformat()}
        save_state(state)
        try:
            media_id = publish(item, user_id, token)
        except Exception as e:  # noqa: BLE001
            # Yayın çağrısından önce düştüyse kaydı temizle ki sonraki çalışma tekrar denesin.
            msg = str(e)
            state[iid] = {"status": "error", "error": msg[:500], "at": now.isoformat()}
            if "media_publish" in msg:
                state[iid]["status"] = "publishing"  # yayın adımında düştü: sonuç belirsiz, elle kontrol
            save_state(state)
            log(f"❌ {iid}: {msg}")
            failed = True
            continue
        state[iid] = {"status": "published", "media_id": media_id,
                      "published_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        save_state(state)
        log(f"✅ {iid} yayınlandı (media id {media_id})")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
