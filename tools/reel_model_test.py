"""Which model writes the reel scripts best for the money (Yash, 23 Oct 2026: OpenAI key added, budget ₹1-2 per reel).

Takes the last few dispatched reels (the scripts Gemma actually wrote are the baseline) plus a political story, and
has each OpenAI model write the same script with the live prompt (the same rules, the original article, the legal pass
in code). Prints every script and its real cost from OpenAI's token counts. Writes nothing to the DB.

  python -m tools.reel_model_test [--ids 1,2,3] [--models auto|a,b]
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request

from common.db import close_all, main_db, upsc_db
from tools.reel_scorer import (SCRIPT_POLITICAL_EXTRA, SCRIPT_SCHEMA, SCRIPT_SOURCE_RULES, SCRIPT_SYSTEM_CHARLIE,
                               clean_original, decompress, is_political, legal_pass)

API = "https://api.openai.com/v1"
INR = float(os.environ.get("USD_INR", "88"))
# $ per 1M tokens (input, output). GPT-5.6 launch prices from openai.com/index/gpt-5-6 (9 Jul 2026), with the cuts the
# page announces (Luna -80% on 30 Jul, Terra -20%, Sol >-20% temporarily). The usage numbers are exact; the prices
# are the best known and shown for both cases where unsure.
PRICES = {"luna": [(0.20, 1.20), (1.00, 6.00)], "terra": [(2.00, 12.00), (2.50, 15.00)], "sol": [(4.00, 24.00), (5.00, 30.00)],
          "gpt-5-mini": [(0.25, 2.00)], "gpt-5-nano": [(0.05, 0.40)], "gpt-4.1-mini": [(0.40, 1.60)], "gpt-4.1": [(2.00, 8.00)],
          "gpt-4o-mini": [(0.15, 0.60)], "gpt-5": [(1.25, 10.00)]}


def call(path, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None, method="POST" if body else "GET",
                                 headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}"}


def price_key(model):
    m = model.lower()
    for k in ("luna", "terra", "sol", "gpt-5-nano", "gpt-5-mini", "gpt-4.1-mini", "gpt-4o-mini", "gpt-4.1", "gpt-5"):
        if k in m:
            return k
    return None


def strict(schema):
    s = json.loads(json.dumps(schema))
    s["additionalProperties"] = False
    s["required"] = list(s["properties"])
    return s


def write(model, system, user, effort):
    body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "reel_script", "schema": strict(SCRIPT_SCHEMA), "strict": True}},
            "max_completion_tokens": 4000}
    if effort:
        body["reasoning_effort"] = effort
    t0 = time.time()
    r = call("/chat/completions", body)
    if "error" in r and effort:  # this model doesn't take that effort level: its default
        print(f"   ({model} {effort}: {r['error'][:120]}; retrying without reasoning_effort)")
        body.pop("reasoning_effort")
        r = call("/chat/completions", body)
        effort = "default"
    if "error" in r:
        return None, r["error"], {}
    u = r.get("usage", {})
    usage = {"in": u.get("prompt_tokens", 0), "cached": (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
             "out": u.get("completion_tokens", 0), "reasoning": (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
             "secs": round(time.time() - t0), "effort": effort}
    try:
        return json.loads(r["choices"][0]["message"]["content"]), None, usage
    except Exception as ex:
        return None, f"bad JSON: {ex}", usage


def cost(model, usage):
    k = price_key(model)
    if not k or not usage:
        return "price unknown"
    parts = []
    for pin, pout in PRICES[k]:
        usd = usage["in"] * pin / 1e6 + usage["out"] * pout / 1e6
        parts.append(f"₹{usd * INR:.2f}")
    return " / ".join(parts) + (" (after cut / launch price)" if len(PRICES[k]) > 1 else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--models", default="auto")
    a = ap.parse_args()
    m_db, u_db = main_db(), upsc_db()
    if a.ids:
        ids = [int(x) for x in a.ids.split(",") if x.strip().isdigit()]
    else:
        ids = [int(r[0]) for r in u_db.execute("SELECT article_id FROM reel_posts ORDER BY dispatched_at DESC LIMIT 3").rows]
        ids.append(137919)  # Jagan Reddy, ₹43,000 crore: the political test story
    avail = sorted(m["id"] for m in call("/models").get("data", []))
    print("## models this key can use (GPT-5.x / 4.x)\n" + ", ".join(m for m in avail if m.startswith(("gpt-5", "gpt-4"))) + "\n")
    if a.models == "auto":
        want = []
        for k in ("luna", "terra", "sol"):
            c = [m for m in avail if "5.6" in m and k in m]
            want += c[:1]
        want += [m for m in ("gpt-5-mini", "gpt-4.1-mini") if m in avail]
    else:
        want = [m for m in a.models.split(",") if m]
    print(f"testing: {want}\n")
    total = 0.0
    for aid in ids:
        r = m_db.execute("SELECT title, rephrased_title, rephrased_article, url, content FROM articles WHERE id = ?", [aid]).rows
        if not r:
            continue
        r = r[0]
        c = u_db.execute("SELECT topic, wow_fact FROM reel_candidates WHERE article_id = ?", [aid]).rows
        topic, fact = (str(c[0][0]), str(c[0][1])) if c else ("politics", "")
        title, political = r[1] or r[0], is_political(topic)
        src = "इंडियन एक्सप्रेस" if "indianexpress" in str(r[3] or "").lower() else "द हिंदू"
        body, original = decompress(r[2], limit=4000), clean_original(decompress(r[4], limit=12000))[:4000]
        system = SCRIPT_SYSTEM_CHARLIE + SCRIPT_SOURCE_RULES + (SCRIPT_POLITICAL_EXTRA.replace("{source}", src) if political else "")
        user = (f"NEWS ARTICLE\nTitle: {title}\nTopic: {topic}\nSource: {src}\nKey Fact: {fact}\nVoice Persona: charlie\n"
                f"SUMMARY:\n{body[:1500]}" + (f"\n\nORIGINAL ARTICLE:\n{original}" if original else ""))
        print(f"# Story {aid}: {title} [{topic}{', political' if political else ''}]\n")
        for model in want:
            for effort in (["low"] if ("sol" in model or "terra" in model) else ["low", "medium"] if "luna" in model else ["low"]):
                if "sol" in model and aid != ids[-1]:
                    continue  # the flagship only on the political story: enough to judge, keeps the test cheap
                sc, err, usage = write(model, system, user, effort)
                if err:
                    print(f"## {model} ({effort}): ERROR {err}\n")
                    continue
                notes = []
                if political:
                    sc, notes, ok = legal_pass(sc)
                    if not ok:
                        notes.append("REJECTED: abusive label")
                k = price_key(model)
                if k:
                    total += (usage["in"] * PRICES[k][0][0] + usage["out"] * PRICES[k][0][1]) / 1e6 * INR
                print(f"## {model} (reasoning {usage['effort']}): {usage['in']} in, {usage['out']} out "
                      f"({usage['reasoning']} thinking), {usage['secs']}s, cost {cost(model, usage)}"
                      + (f"\nlegal pass: {notes}" if notes else ""))
                for f in ("headline_hi", "hook_say", "core_title_hi", "core_points_hi", "core_say", "twist_stat", "twist_label",
                          "twist_detail_hi", "twist_say", "question_hi", "engagement_say"):
                    v = sc.get(f)
                    print(f"- **{f}**: {' | '.join(v) if isinstance(v, list) else v}")
                print()
    print(f"\ntest total ≈ ₹{total:.1f} (after-cut prices)")
    close_all()


if __name__ == "__main__":
    main()
