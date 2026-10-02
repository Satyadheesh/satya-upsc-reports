"""Turso/libsql clients. libsql_client's sync client runs a background thread: always close_all()."""
import os

_clients = []


def _client(url_env, token_env):
    import libsql_client  # imported here so pure-logic modules and tests don't need it
    url = os.environ.get(url_env)
    if not url:
        raise SystemExit(f"Missing secret {url_env}")
    c = libsql_client.create_client_sync(url=url.replace("libsql://", "https://"), auth_token=os.environ.get(token_env))
    _clients.append(c)
    return c


def upsc_db():
    return _client("SATYA_UPSC_DB_URL", "SATYA_UPSC_DB_TOKEN")


def main_db():
    return _client("SATYA_DB_URL", "SATYA_DB_TOKEN")


def translation_db():
    """Hindi translations (read-only here): translations, upsc_translations, event_translations."""
    return _client("SATYA_TRANSLATION_DB_URL", "SATYA_TRANSLATION_DB_TOKEN")


def close_all():
    for c in _clients:
        try:
            c.close()
        except Exception:
            pass
    _clients.clear()


def in_chunks(c, sql, ids, size=400):
    """Run `sql` (with {ph} for the IN list) over ids in chunks; returns all rows."""
    out = []
    ids = list(ids)
    for i in range(0, len(ids), size):
        part = ids[i:i + size]
        out.extend(c.execute(sql.format(ph=",".join("?" * len(part))), part).rows)
    return out
