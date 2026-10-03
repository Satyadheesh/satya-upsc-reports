"""Instagram API with Instagram Login (graph.instagram.com): carousel publishing + token refresh.
Free; needs a Professional (Business or Creator) account and a token with instagram_business_content_publish.
The token is never printed."""
import hashlib
import os
import time

import requests

VERSION = os.environ.get("IG_API_VERSION", "v23.0")
BASE = f"https://graph.instagram.com/{VERSION}"
REFRESH_EVERY = 7 * 86400   # long-lived tokens last 60 days; refresh weekly


class IGError(RuntimeError):
    pass


class IG:
    def __init__(self, token):
        self.token = token
        me = self.get("me", fields="user_id,username")
        self.user_id, self.username = str(me.get("user_id") or me.get("id")), me.get("username")

    def _call(self, method, path, **params):
        params["access_token"] = self.token
        for i in range(4):
            try:
                r = requests.request(method, f"{BASE}/{path}", params=params, timeout=120)
                body = r.json()
            except (requests.RequestException, ValueError) as e:
                err = f"network: {type(e).__name__}"
            else:
                if r.ok and "error" not in body:
                    return body
                er = body.get("error") or {}
                err = f"{er.get('code')}/{er.get('error_subcode')}: {er.get('message')}"
                if er.get("code") not in (1, 2, 4, 17, 32, 613, 9004, 2207003, 2207027):  # only transient ones are retried
                    raise IGError(f"{method} {path.split('?')[0]} failed: {err}")
            time.sleep(10 * (i + 1))
        raise IGError(f"{method} {path} failed after retries: {err}")

    def get(self, path, **params):
        return self._call("GET", path, **params)

    def post(self, path, **params):
        return self._call("POST", path, **params)

    def carousel(self, image_urls, caption):
        """Create one container per image, then the carousel, wait until Instagram has fetched everything, publish."""
        children = []
        for url in image_urls:
            children.append(self.post(f"{self.user_id}/media", image_url=url, is_carousel_item="true")["id"])
        for c in children:
            self.wait(c)
        cid = self.post(f"{self.user_id}/media", media_type="CAROUSEL", children=",".join(children), caption=caption)["id"]
        self.wait(cid)
        media_id = self.post(f"{self.user_id}/media_publish", creation_id=cid)["id"]
        link = self.get(media_id, fields="permalink").get("permalink")
        return media_id, link

    def wait(self, cid, limit=300):
        t0 = time.time()
        while time.time() - t0 < limit:
            st = self.get(cid, fields="status_code,status").get("status_code")
            if st == "FINISHED":
                return
            if st in ("ERROR", "EXPIRED"):
                raise IGError(f"container {cid} {st}")
            time.sleep(5)
        raise IGError(f"container {cid} not ready after {limit}s")


def _seed_hash(t):
    return hashlib.sha256(t.encode()).hexdigest()[:16]


def current_token(upsc):
    """The newest token: the IG_TOKEN secret seeds the DB copy (again whenever the secret is replaced); the DB copy is
    refreshed weekly so it never reaches its 60-day expiry."""
    secret = (os.environ.get("IG_TOKEN") or "").strip()
    rows = {r[0]: (r[1], r[2]) for r in upsc.execute("SELECT k, token, refreshed_at FROM ig_auth").rows}
    seed = rows.get("seed_hash", ("", 0))[0]
    if secret and _seed_hash(secret) != seed:
        for k, v in (("long_lived", secret), ("seed_hash", _seed_hash(secret))):
            upsc.execute("INSERT OR REPLACE INTO ig_auth (k, token, refreshed_at) VALUES (?, ?, ?)", [k, v, int(time.time())])
        return secret
    if "long_lived" not in rows:
        raise SystemExit("Missing secret IG_TOKEN")
    token, at = rows["long_lived"]
    if time.time() - at > REFRESH_EVERY:
        try:
            r = requests.get("https://graph.instagram.com/refresh_access_token",
                             params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60).json()
            if r.get("access_token"):
                token = r["access_token"]
                upsc.execute("INSERT OR REPLACE INTO ig_auth (k, token, refreshed_at) VALUES ('long_lived', ?, ?)", [token, int(time.time())])
                print(f"token refreshed (valid {int(r.get('expires_in', 0)) // 86400} days)")
            else:
                print(f"::warning::token refresh failed: {(r.get('error') or {}).get('message')}")
        except requests.RequestException as e:
            print(f"::warning::token refresh failed: {type(e).__name__}")
    return token
