"""Minimal Telegram Bot API client (sendMessage, sendDocument, sendPoll). The token is never logged."""
import json
import os
import time

import requests

API = "https://api.telegram.org/bot{token}/{method}"


class TelegramError(RuntimeError):
    pass


class Bot:
    def __init__(self, token=None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise SystemExit("Missing secret TELEGRAM_BOT_TOKEN")

    def call(self, method, data=None, files=None, tries=4):
        url = API.format(token=self.token, method=method)
        for i in range(tries):
            try:
                r = requests.post(url, data=data, files=files, timeout=120)
                body = r.json()
            except (requests.RequestException, ValueError) as e:
                err = f"network: {type(e).__name__}"  # no URL: it contains the token
            else:
                if body.get("ok"):
                    return body["result"]
                err = f"{body.get('error_code')}: {body.get('description')}"
                retry = (body.get("parameters") or {}).get("retry_after")
                if body.get("error_code") == 429 and retry:
                    time.sleep(int(retry) + 1)
                    continue
                if body.get("error_code") in (400, 401, 403):
                    raise TelegramError(f"{method} failed: {err}")  # bad request / token / not admin: retrying won't help
            time.sleep(5 * (i + 1))
        raise TelegramError(f"{method} failed after {tries} tries: {err}")

    def message(self, chat, html):
        return self.call("sendMessage", {"chat_id": chat, "text": html, "parse_mode": "HTML",
                                         "link_preview_options": json.dumps({"is_disabled": True})})

    def document(self, chat, pdf_bytes, filename, caption_html):
        return self.call("sendDocument", {"chat_id": chat, "caption": caption_html, "parse_mode": "HTML"},
                         files={"document": (filename, pdf_bytes, "application/pdf")})

    def quiz(self, chat, question, options, correct, explanation):
        return self.call("sendPoll", {"chat_id": chat, "question": question, "type": "quiz", "is_anonymous": "true",
                                      "options": json.dumps([{"text": o} for o in options]),
                                      "correct_option_id": correct, "explanation": explanation})
