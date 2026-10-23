"""Universal Viral Reels Scorer (Gemma 4 12B).

Scores incoming raw news articles across all topics (cinema, infrastructure, science,
curiosities, consumer hacks, defense, sports, etc.) on viral potential (0 to 10)
for Instagram Reels & YouTube Shorts, enforcing a strict zero-defamation/zero-blame gate.

Results are saved to `reel_candidates` in the UPSC DB.
"""
import argparse
import json
import os
import re
import time

from common.db import close_all, in_chunks, main_db, upsc_db
from kit.model import MODEL_NAME, Model, download

SYSTEM = """You are an expert executive producer for viral short-form news videos (Instagram Reels & YouTube Shorts) for ordinary Indian audiences.
Your goal is to evaluate news stories across ALL topics (politics & political funding/chanda, cinema/Bollywood, infrastructure, science, space, quirky/bizarre curiosities, defense, sports, consumer hacks, economy, nature) and score their viral potential.

EVALUATION CRITERIA (0 to 10):
1. Scroll-Stopping Hook (0-3): Does the story start with a fascinating contrast, question, or paradox that immediately stops someone scrolling?
2. Scale & Wow Factor (0-3): Does it feature an impressive physical scale, record, massive budget, high number, or unusual feat?
3. Talkability & Shareability (0-4): Would an ordinary Indian share this on WhatsApp with friends or family saying "Did you know this?" (e.g. mind-blowing political donation/chanda figures, electoral bond disclosures, declared neta assets vs reality, giant taxpayer spending, viral cinema/sports milestones, tech wonders).

WHAT TO REJECT (Score 0):
- Routine partisan name-calling, spokesperson bickering, or unverified verbal allegations without official records.
- Mundane procedural press releases or local party committee reshuffles.
- Violent crimes, murders, sexual offenses, tragic deaths, accidents with casualties, grief/mourning.
- Personal celebrity scandals, divorces, custody battles.
- Defamation hazards (claims must be grounded in official records, EC filings, CAG audits, affidavits, or established data).

Answer in JSON:
- "viral_score": Integer 0 to 10 (7+ means excellent reel material, 0 if rejection criteria met)
- "topic": Short category string (e.g. "politics_funding", "cinema", "infrastructure", "science_space", "consumer_hack", "defence", "curiosity", "sports", "economy")
- "hook_angle": A compelling opening hook or question in conversational Hindi (Devanagari)
- "wow_fact": The single most impressive number, record, or fact in the story
- "why": One short sentence explaining the score
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "viral_score": {"type": "integer", "minimum": 0, "maximum": 10},
        "topic": {"type": "string"},
        "hook_angle": {"type": "string"},
        "wow_fact": {"type": "string"},
        "why": {"type": "string"}
    },
    "required": ["viral_score", "topic", "hook_angle", "wow_fact", "why"]
}


def decompress(blob, limit=1200):
    if not blob:
        return ""
    import zlib
    raw = []
    if isinstance(blob, (bytes, bytearray, memoryview)):
        raw.append(bytes(blob))
    else:
        import base64
        try:
            raw.append(base64.b64decode(str(blob), validate=True))
        except Exception:
            return str(blob)[:limit]
    for b in raw:
        for wbits in (15, 47):
            try:
                return zlib.decompress(b, wbits).decode("utf-8", "replace")[:limit]
            except Exception:
                pass
        try:
            return b.decode("utf-8")[:limit]
        except Exception:
            pass
    return ""


SCRIPT_SYSTEM_CHARLIE = """You are an expert Indian short-form news storyteller who writes high-retention Instagram Reel scripts in natural, conversational Hindi.

TASK
Read the news article below and write a Reel narration script in Hindi (Devanagari script). The script has 4 parts: Hook, Core, Twist, Engagement. Return it as a single JSON object with the exact keys listed under OUTPUT FIELDS.

LANGUAGE AND TONE
- Write the way an Indian creator actually talks to the camera: simple, warm, direct. Use everyday Hindi, not formal or bureaucratic Hindi (avoid words like "तत्पश्चात", "उपरोक्त", "संपन्न").
- Keep sentences short, so they are easy to speak in one breath.
- Do not use English words unless they are common in everyday Hindi speech (e.g. dialysis, center, doctor, hospital, ticket). Write those in Devanagari too (डायलिसिस, सेंटर, डॉक्टर).
- Do not use hashtags, emojis, or stage directions in any field.

VOICE / TTS ENGINE LIMITATIONS & PHONETIC RULES (Critical)
The *_say fields are synthesized directly by an AI voice model. Neural TTS engines struggle with literary grammar, complex inflections, and stacked character markers:
- Spoken Flow over Literary Grammar: Write strictly how an Indian creator speaks conversationally on camera. Avoid rare grammatical declensions, literary plural forms, or stiff bureaucratic phrasing that cause AI voices to mispronounce or slur.
- Phonetic Simplicity: Choose simple, everyday spoken vocabulary over complex consonant clusters or stacked character modifiers. If a concept can be expressed with a standard, clean colloquial word, always prefer the simpler one.
- Conversational Calls-to-Action: Keep engagement prompts conversational and natural (e.g. inviting viewers to share their thoughts or experiences in the comments), rather than abrupt or forceful single-word imperative commands.
- Symbols and Units: NEVER use symbols such as ₹, $, %, &, or abbreviations like "Rs." or "km". Always write them out as spoken Hindi words: "4000 रुपये" (not ₹4000), "20 प्रतिशत" (not 20%), "5 किलोमीटर" (not 5 km).
- Punctuation for Breathing: Use commas and short sentences to provide natural breath pauses for the AI voice. Avoid long, complex multi-clause sentences.
The ₹ symbol may appear ONLY in the on-screen fields: headline_hi and twist_stat.

OUTPUT FIELDS
- headline_hi: catchy on-screen headline, max 8 words.
- hook_say: 1-2 spoken lines that grab attention immediately (a surprising fact, a question, or a contrast).
- core_title_hi: short title for the core news card, max 8 words.
- core_points_hi: exactly 2 or 3 very short on-screen bullet points in Hindi (e.g. ["22 नए सरकारी केंद्र शुरू", "किडनी के मरीज़ों को सीधा फ़ायदा", "सत्यापित डेटा"]). Max 8 words per bullet.
- core_say: 3-4 spoken lines: what actually happened, in simple and concrete terms (who, what, where, how much), plus one line of background (how we got here).
- twist_stat: the single key number or word shown on screen (e.g. "₹999" or "22 केंद्र").
- twist_label: short label for that number (e.g. "डायलिसिस फ़ीस" or "नए केंद्र").
- twist_detail_hi: 1 short on-screen line in Hindi summarizing the ground reality, budget, or contrast (max 10 words, e.g. "प्राइवेट में ₹4,000 तक खर्च, सरकारी से बड़ी राहत").
- twist_say: 2-3 spoken lines: the ground reality, the key number or the contrast, and what happens next (a hearing, deadline, vote, decision or rollout), if the article says.
- question_hi: short on-screen question for the engagement card.
- engagement_say: one natural, thought-provoking question that invites viewers to comment.

RULES
- Use only facts from the article. Do not invent numbers, names, or quotes.
- Keep the whole spoken script (hook_say + core_say + twist_say + engagement_say) to 110-140 Hindi words in total,
  roughly 45-55 seconds of speech. Never more than 140 words: count them. hook_say max 25 words, core_say max 55,
  twist_say max 40, engagement_say max 20.
- Make it rich, not padded. Every script carries: (1) one line of background, (2) at least one concrete detail from the
  article: a date, a figure, or a named person or institution, (3) what happens next, if the article says. Skip a point
  rather than invent it.
- Output ONLY the JSON object. No explanation, no markdown, no code fences, no text before or after.
"""

SCRIPT_SYSTEM = SCRIPT_SYSTEM_CHARLIE

# Political reels (Yash, 22 Oct 2026: political stories get the most traction; make them sharper, but legally safe)
POLITICAL_TOPICS = {"politics", "politics_funding", "governance", "elections", "election", "parliament", "policy"}


def is_political(topic):
    t = str(topic or "").lower()
    return t in POLITICAL_TOPICS or "politic" in t or "election" in t


SCRIPT_POLITICAL_EXTRA = """
POLITICAL STORY MODE (this story is political)
Make it sharp and questioning, the way a fearless Hindi news creator talks: open on a contradiction, a broken promise,
a U-turn, a big number, or "who said what". Hold power to account with questions. But it must be legally safe:
1. Attribute every claim. core_say MUST start with "{source} की रिपोर्ट के मुताबिक". Tie each statement or accusation to
   whoever made it: "कांग्रेस का आरोप है", "भाजपा का दावा है", "मंत्री ने कहा". Never present a claim as your own.
2. An allegation stays an allegation: use "आरोप है", "दावा किया गया", "सवाल उठ रहे हैं". Never say or imply that a named
   person or party is guilty, corrupt or a criminal unless the article reports a court conviction.
3. Never use abusive or loaded labels for anyone (चोर, घोटालेबाज़, भ्रष्ट, गद्दार, जुमलेबाज़ and the like).
4. Criticise only actions, decisions, policies, public statements and public records; never anyone's family, caste,
   religion, looks or private life.
5. If the article gives the other side's reply or denial, include it in one short line ("सरकार/पार्टी का कहना है ...").
6. End with a question to the viewer, never a verdict (e.g. "क्या जनता को इसका जवाब नहीं मिलना चाहिए?").
7. Be equally sharp with every party and government; no cheering or mocking any side.
8. headline_hi may be a pointed question. Facts, numbers and names only from the article.
9. The on-screen text (headline_hi, core_points_hi, twist_stat, twist_label, twist_detail_hi) follows the same rules:
   any accusation carries "आरोप" or "दावा" ("43,000 करोड़ के भ्रष्टाचार का आरोप", never "43,000 करोड़ का भ्रष्टाचार").
10. Criminal cases (murder, assault, fraud): only what the investigation or court has done, as reported, attributed;
   never connect a named person to a crime beyond what the report itself says.
"""

SCRIPT_SOURCE_RULES = """
SOURCE TEXT
You get SUMMARY (our short rewrite) and, when available, ORIGINAL ARTICLE (the full report: quotes, who said what,
the other side's reply, numbers). Use the ORIGINAL for details and attribution. Write everything in your own words:
never translate its sentences word for word; quote only short statements, always naming who said them.
STYLE: make the hook and the closing question specific to THIS story. Never open with "क्या आप यकीन करेंगे" and never
close with a generic "इस पूरे मामले पर आपकी क्या राय है?".
"""

JUNK_LINE = re.compile(r"^(also read|read more|read also|click here|subscribe|follow us|published|updated|copyright|"
                       r"advertisement|watch:|listen:|photo:|image:|file photo|representative image|for representational)",
                       re.I)


def clean_original(text):
    """The scraped article without its page furniture (read-more links, captions, bylines), whitespace squeezed."""
    out = []
    for line in str(text or "").splitlines():
        line = " ".join(line.split())
        if len(line) < 25 or JUNK_LINE.match(line):
            continue
        out.append(line)
    return "\n".join(out)


def fit_prompt(model, system, head, summary, original, max_tokens, margin=160):
    """The user prompt, cut so that system + prompt + the answer fit the model's context window (4,096 tokens on
    the GitHub runner; going over makes llama.cpp refuse the call). The ORIGINAL is trimmed first, at a paragraph
    end, then the SUMMARY. Token counts come from the model's own tokenizer."""
    def n(t):
        return len(model.llm.tokenize(t.encode("utf-8"), add_bos=False))
    budget = model.llm.n_ctx() - max_tokens - margin - n(system) - 40  # 40: the chat template's own tokens

    def build(sm, og):
        return head + f"SUMMARY:\n{sm}" + (f"\n\nORIGINAL ARTICLE:\n{og}" if og else "")
    sm, og = summary, original
    while og and n(build(sm, og)) > budget:
        cut = og.rfind("\n", 0, int(len(og) * 0.8))
        og = og[:cut] if cut > 400 else ""
    while n(build(sm, og)) > budget and len(sm) > 300:
        sm = sm[: int(len(sm) * 0.8)]
    return build(sm, og)


LOADED = re.compile(r"(भ्रष्टाचार|घोटाल[ाेो]|घपल[ाेो]|घूसखोरी|रिश्वतखोरी|धोखाधड़ी|हेराफेरी|लूट)")
HEDGED = re.compile(r"आरोप|दावा|दावे|कथित|जांच|जाँच|सवाल")
LABELS = {"चोर", "चोरों", "गद्दार", "जुमलेबाज़", "जुमलेबाज", "घोटालेबाज़", "घोटालेबाज", "भ्रष्ट", "लुटेरा", "लुटेरे", "देशद्रोही"}


def legal_pass(script):
    """The political rules the model doesn't always keep, applied in code (22 Oct 2026: an on-screen bullet read
    '43,000 करोड़ का भ्रष्टाचार' and the review still approved it). A field that names wrongdoing without 'आरोप/दावा/
    कथित/जांच' gets 'कथित' (alleged) in front of it; an abusive label rejects the script. -> (script, notes, ok)"""
    notes, ok = [], True

    def fix(v):
        nonlocal ok
        if not isinstance(v, str):
            return v
        words = set(re.findall(r"[\u0900-\u097F]+", v))
        if words & LABELS:
            ok = False
            notes.append(f"label {sorted(words & LABELS)} in: {v[:60]}")
        if LOADED.search(v) and not HEDGED.search(v):
            nv = LOADED.sub(lambda m: "कथित " + m.group(1), v, count=1)
            notes.append(f"'{v[:50]}' -> '{nv[:56]}'")
            return nv
        return v
    out = {k: ([fix(x) for x in v] if isinstance(v, list) else fix(v)) for k, v in script.items()}
    return out, notes, ok


# Script writer: OpenAI GPT-5.6 Luna (Yash, 24 Oct 2026, after the model test: best Hindi for the money), Gemma 12B as
# the fallback. ~Rs 0.2 per reel at medium. Rs 2 is a target, not a hard limit (Yash, 24 Oct): the only cap is a runaway
# guard (REEL_BUDGET_INR, default Rs 10 per reel, counted at Luna's launch price $1 / $6 per 1M tokens).
OPENAI_MODEL = os.environ.get("REEL_SCRIPT_MODEL", "gpt-5.6-luna")
OPENAI_EFFORT = os.environ.get("REEL_SCRIPT_EFFORT", "medium")  # low | medium | high
OPENAI_PRICE = {"gpt-5.6-luna": (1.0, 6.0), "gpt-5.6-terra": (2.5, 15.0), "gpt-5.6-sol": (5.0, 30.0)}  # $/1M, launch prices
REEL_BUDGET_INR = float(os.environ.get("REEL_BUDGET_INR") or "10")
USD_INR = float(os.environ.get("USD_INR", "88"))
SPENT = {"inr": 0.0}  # this reel's OpenAI spend (one dispatch = one reel)


def openai_script(system, user):
    """The reel script from OpenAI, or (None, why). The answer may use up to 8,000 tokens (room for high reasoning);
    only a runaway is stopped (REEL_BUDGET_INR per reel)."""
    import urllib.error
    import urllib.request
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None, "no OPENAI_API_KEY"
    pin, pout = OPENAI_PRICE.get(OPENAI_MODEL, (5.0, 30.0))
    left_usd = (REEL_BUDGET_INR - SPENT["inr"]) / USD_INR
    in_tokens = len(system + user) / 2.5  # generous estimate (Hindi/English mix)
    max_out = int((left_usd - in_tokens * pin / 1e6) / (pout / 1e6))
    if max_out < 1500:
        return None, f"reel budget used (Rs {SPENT['inr']:.2f} of {REEL_BUDGET_INR})"
    schema = json.loads(json.dumps(SCRIPT_SCHEMA))
    schema["additionalProperties"], schema["required"] = False, list(schema["properties"])
    body = {"model": OPENAI_MODEL, "reasoning_effort": OPENAI_EFFORT, "max_completion_tokens": min(max_out, 8000),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "reel_script", "schema": schema, "strict": True}}}
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            out = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return None, f"OpenAI HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"
    except Exception as e:
        return None, f"OpenAI {type(e).__name__}"
    u = out.get("usage") or {}
    cost = (u.get("prompt_tokens", 0) * pin + u.get("completion_tokens", 0) * pout) / 1e6 * USD_INR
    SPENT["inr"] += cost
    print(f"  OpenAI {OPENAI_MODEL} ({OPENAI_EFFORT}): {u.get('prompt_tokens')} in, {u.get('completion_tokens')} out "
          f"({(u.get('completion_tokens_details') or {}).get('reasoning_tokens')} thinking), at most Rs {cost:.2f} "
          f"(reel so far Rs {SPENT['inr']:.2f})", flush=True)
    try:
        return json.loads(out["choices"][0]["message"]["content"]), None
    except Exception as e:
        return None, f"OpenAI answer unreadable: {type(e).__name__}"


SUITABILITY_POLITICAL_EXTRA = """
5. LEGAL SAFETY (this is a political story; reject_story if ANY point fails):
   - core_say starts with the source attribution ("... की रिपोर्ट के मुताबिक") and every accusation is tied to whoever made it;
   - no named person or party is called or implied guilty, corrupt or criminal (unless the script says a court convicted them),
     in the spoken lines AND the on-screen text (headline, points, stat label, detail line);
   - no abusive or loaded labels; nothing about anyone's family, caste, religion or private life;
   - it ends on a question, not a verdict, and does not cheer or mock a party.
"""

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "headline_hi": {"type": "string"},
        "hook_say": {"type": "string"},
        "core_title_hi": {"type": "string"},
        "core_points_hi": {
            "type": "array",
            "items": {"type": "string"}
        },
        "core_say": {"type": "string"},
        "twist_stat": {"type": "string"},
        "twist_label": {"type": "string"},
        "twist_detail_hi": {"type": "string"},
        "twist_say": {"type": "string"},
        "question_hi": {"type": "string"},
        "engagement_say": {"type": "string"}
    },
    "required": [
        "headline_hi", "hook_say", "core_title_hi", "core_points_hi", "core_say",
        "twist_stat", "twist_label", "twist_detail_hi", "twist_say", "question_hi", "engagement_say"
    ]
}

SUITABILITY_SYSTEM = """You are the Senior Editorial Quality Director at SatyaDheesh, an elite Indian news channel.
Your task is to critically review a generated Hindi news Reel script and its selected voice persona before it is produced.

VOICE PERSONAS:
- 'charlie' (Male): Energetic, confident, modern, authoritative Hindi creator. Best for: national news, defense, economy, infrastructure, science, space, geopolitics.
- 'matilda' (Female): Warm, articulate, engaging, knowledgeable Hindi creator. Best for: consumer rights, health, public schemes, civic alerts, environment, culture.

EVALUATION CRITERIA:
1. Tone & Credibility: Is the script professional, engaging, and worthy of a credible news brand? Reject ANY script with cheap movie catchphrases, slapstick humor, clownish slang, or cringe drama.
2. Voice Match: Is the language, pacing, and vibe genuinely suitable for the assigned voice persona?
3. Story Fit: Is this story actually worth a 30-40s video reel, or does it sound awkward, trivial, or forced?
4. TTS Phonetic Naturalness: Does the spoken narration flow naturally without awkward grammatical phrasing, stiff literary inflections, or tongue-twisters that would sound robotic or mispronounced on an AI voice?

Return a JSON object:
{
  "is_suitable": true or false,
  "verdict": "Clear 1-sentence assessment of tone and voice match",
  "action": "approve" or "change_voice" or "reject_story",
  "suggested_voice": "charlie" or "matilda"
}
"""

SUITABILITY_SCHEMA = {
    "type": "object",
    "properties": {
        "is_suitable": {"type": "boolean"},
        "verdict": {"type": "string"},
        "action": {"type": "string", "enum": ["approve", "change_voice", "reject_story"]},
        "suggested_voice": {"type": "string", "enum": ["charlie", "matilda"]}
    },
    "required": ["is_suitable", "verdict", "action", "suggested_voice"]
}

CATEGORY_HI = {
    "politics": "राजनीति",
    "politics_funding": "चुनावी चंदा",
    "infrastructure": "इंफ्रास्ट्रक्चर",
    "economy": "अर्थव्यवस्था",
    "cinema": "सिनेमा",
    "bollywood": "सिनेमा",
    "curiosity": "रोचक पड़ताल",
    "science": "विज्ञान",
    "science_space": "विज्ञान और स्पेस",
    "space": "अंतरिक्ष",
    "defence": "रक्षा",
    "defense": "रक्षा",
    "sports": "खेल",
    "consumer_hack": "काम की खबर",
    "crime": "विशेष रिपोर्ट",
    "judiciary": "अदालत और कानून",
    "education": "शिक्षा",
    "environment": "पर्यावरण",
    "nature": "पर्यावरण और प्रकृति",
}


def send_telegram_alert(text):
    """Sends an error alert directly to Telegram."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or "8553388061:AAGzoTrdaUABEj8QbPidn6wT1R9Q8oREqNI"
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_TEST_CHAT_ID") or os.environ.get("CHAT_ID") or "6634664206"
    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  Telegram alert error: {e}")
        return False


def dispatch_daily_reel(u_db, m_db, model=None, force=False):
    SPENT["inr"] = 0.0
    """Dispatches the top viral story of the day to Satyadheesh/reels via repository_dispatch."""
    token = os.environ.get("CORE_TOKEN") or os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_PAT_CLASSIC")
    if not token:
        print("  Notice: No GitHub PAT found (CORE_TOKEN); skipping reel dispatch.")
        return

    now = int(time.time())
    # Ensure at most 1 reel per 6 hours unless force=True
    if not force:
        # Check 1: Turso DB reel_posts
        try:
            recent = u_db.execute("SELECT max(dispatched_at) FROM reel_posts").rows
            if recent and recent[0][0] and (now - int(recent[0][0])) < 6 * 3600:
                last_ago_hrs = (now - int(recent[0][0])) / 3600
                print(f"  Daily reel already dispatched {last_ago_hrs:.1f}h ago (< 6 hours). Skipping duplicate dispatch.")
                return
        except Exception:
            pass

        # Check 2: Satyadheesh/reels GitHub Actions runs (in case run was triggered directly)
        try:
            import datetime
            import urllib.request
            gh_url = "https://api.github.com/repos/Satyadheesh/reels/actions/workflows/daily-reel.yml/runs?status=success&per_page=1"
            req = urllib.request.Request(gh_url, headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "satya-reel-scorer"
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                runs = data.get("workflow_runs", [])
                if runs:
                    updated = datetime.datetime.fromisoformat(runs[0]["updated_at"].replace("Z", "+00:00"))
                    diff_hrs = (datetime.datetime.now(datetime.timezone.utc) - updated).total_seconds() / 3600.0
                    if diff_hrs < 6.0:
                        print(f"  Reel already posted to Telegram {diff_hrs:.1f}h ago (< 6 hours). Skipping dispatch.")
                        return
        except Exception as e:
            print(f"  Note: GitHub Actions run check: {e}")

    # Find the top viral score candidates (>= 7) from the last 24h not yet reeled
    since = now - 24 * 3600
    try:
        candidates = u_db.execute(
            "SELECT c.article_id, c.topic, c.viral_score, c.hook_angle, c.wow_fact, c.why, c.published_at "
            "FROM reel_candidates c "
            "WHERE c.viral_score >= 6 AND c.created_at >= ? "
            "  AND c.article_id NOT IN (SELECT article_id FROM reel_posts) "
            "ORDER BY c.viral_score DESC, c.published_at DESC "
            "LIMIT 40",
            [since]
        ).rows
        # political stories get the most traction (Yash, 22 Oct 2026): +1 when ranking, and they qualify from 6
        candidates = [c for c in candidates if int(c[2]) >= 7 or (is_political(c[1]) and int(c[2]) >= 6)]
        candidates.sort(key=lambda c: (int(c[2]) + (1 if is_political(c[1]) else 0), c[6] or 0), reverse=True)
        candidates = [c[:6] for c in candidates[:5]]
    except Exception as e:
        print(f"  Error querying reel_candidates for dispatch: {e}")
        return

    if not candidates:
        print("  No new high viral candidate (score >= 7) available to dispatch right now.")
        return

    approved_candidate = None
    approved_script = None
    approved_persona = None
    approved_row = None

    female_topics = {"consumer_hack", "education", "environment", "nature", "health", "cinema", "lifestyle"}

    for cand in candidates:
        aid, topic, score, hook, fact, why = int(cand[0]), str(cand[1]), int(cand[2]), str(cand[3]), str(cand[4]), str(cand[5])
        art_rows = m_db.execute(
            "SELECT title, rephrased_title, rephrased_article, category, image_url, url, content "
            "FROM articles WHERE id = ?",
            [aid]
        ).rows
        if not art_rows:
            continue

        r = art_rows[0]
        title = r[1] or r[0]
        body = decompress(r[2], limit=4000)
        original = clean_original(decompress(r[6], limit=12000))[:4000]  # ~1,000 tokens: richer context, runner time in check
        political = is_political(topic)
        src_name = "इंडियन एक्सप्रेस" if "indianexpress" in str(r[5] or "").lower() else "द हिंदू"

        # Initial persona selection based on topic
        persona = "matilda" if str(topic).lower() in female_topics else "charlie"

        last_openai = None
        for voice_attempt in range(2):
            print(f"  Evaluating candidate #{aid} [{topic}] with persona: {persona} (attempt {voice_attempt + 1})...")
            script_data = None
            system = SCRIPT_SYSTEM_CHARLIE + SCRIPT_SOURCE_RULES + (SCRIPT_POLITICAL_EXTRA.replace("{source}", src_name) if political else "")
            head = (f"NEWS ARTICLE\nTitle: {title}\nTopic: {topic}\nSource: {src_name}\nKey Fact: {fact}\n"
                    f"Voice Persona: {persona}\n")
            if last_openai:  # only the voice changed: the OpenAI script stays (no second payment)
                script_data = last_openai
            else:
                script_data, why = openai_script(system, head + f"SUMMARY:\n{body[:1500]}" + (f"\n\nORIGINAL ARTICLE:\n{original}" if original else ""))
                if script_data:
                    last_openai = script_data
                else:
                    print(f"  OpenAI script not used ({why}); Gemma writes it")
            if not script_data and model:
                try:
                    sprompt = fit_prompt(model, system, head, body[:1500], original, max_tokens=800)
                    script_data = model.json(system, sprompt, SCRIPT_SCHEMA, temperature=0.25, max_tokens=800)
                except Exception as e:
                    print(f"  Script generation warning: {e}")
            if script_data:
                try:
                    if political and script_data:
                        script_data, notes, legal_ok = legal_pass(script_data)
                        for note in notes:
                            print(f"  legal pass #{aid}: {note}")
                        if not legal_ok:
                            print(f"  Story #{aid}: abusive label in the script, trying next candidate...")
                            script_data = None
                except Exception as e:
                    print(f"  Script generation warning: {e}")

            if not script_data:
                break

            # Editorial & Voice Suitability Evaluation (Gemma Quality Gate)
            if model:
                try:
                    eval_prompt = (
                        f"NEWS ARTICLE: {title}\n"
                        f"TOPIC: {topic}{' (POLITICAL: apply the legal safety check)' if political else ''}\n"
                        f"ASSIGNED VOICE: {persona}\n"
                        f"HEADLINE: {script_data.get('headline_hi')}\n"
                        f"ON-SCREEN: {script_data.get('core_title_hi')} | {' | '.join(script_data.get('core_points_hi') or [])} | "
                        f"{script_data.get('twist_stat')} {script_data.get('twist_label')} | {script_data.get('twist_detail_hi')}\n"
                        f"HOOK: {script_data.get('hook_say')}\n"
                        f"CORE: {script_data.get('core_say')}\n"
                        f"TWIST: {script_data.get('twist_say')}\n"
                        f"ENGAGEMENT: {script_data.get('engagement_say')}"
                    )
                    suitability = model.json(SUITABILITY_SYSTEM + (SUITABILITY_POLITICAL_EXTRA if political else ""), eval_prompt,
                                             SUITABILITY_SCHEMA, temperature=0.1, max_tokens=200)
                    is_ok = suitability.get("is_suitable") is True or suitability.get("action") == "approve"
                    verdict = suitability.get("verdict", "")
                    action = suitability.get("action", "")
                    print(f"  Gemma review for #{aid} ({persona}): suitable={is_ok}, action={action} -> {verdict}")

                    if is_ok:
                        approved_candidate = cand
                        approved_script = script_data
                        approved_persona = persona
                        approved_row = r
                        break
                    elif action == "change_voice" and voice_attempt == 0:
                        suggested = suitability.get("suggested_voice")
                        if suggested and suggested != persona:
                            print(f"  Gemma suggested voice change: switching {persona} -> {suggested}...")
                            persona = suggested
                            continue
                    else:
                        print(f"  Story #{aid} rejected by Gemma editorial review ({verdict}). Trying next candidate...")
                        break
                except Exception as e:
                    print(f"  Suitability check note: {e}")
                    if political:  # a political script is never made without its legal check
                        print(f"  Story #{aid}: political and unchecked, trying next candidate...")
                        break
                    approved_candidate = cand
                    approved_script = script_data
                    approved_persona = persona
                    approved_row = r
                    break
            else:
                approved_candidate = cand
                approved_script = script_data
                approved_persona = persona
                approved_row = r
                break

        if approved_candidate:
            break

    if not approved_candidate or not approved_script:
        err_msg = (
            "⚠️ *SatyaDheesh Reel Alert: No Candidate Approved*\n\n"
            f"• *Evaluated*: {len(candidates)} high-viral candidates\n"
            "• *Reason*: None passed Gemma's brand dignity & voice fit review.\n"
            "• *Action*: Reel dispatch halted to protect brand quality."
        )
        print(f"❌ {err_msg}")
        send_telegram_alert(err_msg)
        return

    aid, topic, score, hook, fact, why = int(approved_candidate[0]), str(approved_candidate[1]), int(approved_candidate[2]), str(approved_candidate[3]), str(approved_candidate[4]), str(approved_candidate[5])
    r = approved_row
    title = r[1] or r[0]
    cat = r[3] or topic
    img = r[4] or ""
    source_url = r[5] or ""
    persona = approved_persona
    script_data = approved_script

    headline_hi = script_data.get("headline_hi") or title[:40]
    hook_say = script_data.get("hook_say") or hook
    core_title = script_data.get("core_title_hi") or "पूरी जानकारी"
    core_say = script_data.get("core_say") or f"इस मामले की पूरी जानकारी ये है कि {fact}।"
    twist_stat = script_data.get("twist_stat") or "बड़ा बदलाव"
    twist_label = script_data.get("twist_label") or "का असर"
    twist_say = script_data.get("twist_say") or f"ज़मीनी सच्चाई ये है कि {fact}।"
    q_hi = script_data.get("question_hi") or "आपकी क्या राय है?"
    eng_say = script_data.get("engagement_say") or "इस पूरे मामले पर आपकी क्या सोच है? कमेंट में बताइए और फ़ॉलो कीजिए सत्याधीश।"

    category_hi = CATEGORY_HI.get(str(topic).lower(), "विशेष पड़ताल")

    # Clean Hindi core bullet points for Card 2
    raw_pts = script_data.get("core_points_hi")
    if raw_pts and isinstance(raw_pts, list) and len(raw_pts) > 0:
        core_points = [str(p).strip() for p in raw_pts if str(p).strip()][:3]
        if len(core_points) == 1:
            core_points.append("सत्यापित सरकारी डेटा")
    else:
        core_points = ["सटीक सरकारी रिपोर्ट", "सत्यापित डेटा"]

    # Clean Hindi detail line under big stat for Card 3
    twist_detail = script_data.get("twist_detail_hi")
    if not twist_detail:
        twist_detail = "सत्यापित ज़मीनी रिपोर्ट"

    source_label = "TheHindu"
    if "indianexpress" in source_url.lower():
        source_label = "TheIndianExpress"

    hook_badge = "ताज़ा पड़ताल"
    twist_badge = "ज़मीनी हक़ीक़त"

    payload = {
        "article_id": aid,
        "persona": persona,
        "force": force,
        "category": category_hi,
        "headline": headline_hi,
        "image_url": img,
        "hook": {
            "badge": hook_badge,
            "title": headline_hi,
            "subtitle": "सत्याधीश रिपोर्ट",
            "say": hook_say
        },
        "core": {
            "badge": "मुख्य जानकारी",
            "title": core_title,
            "points": core_points,
            "source": source_label,
            "say": core_say
        },
        "twist": {
            "badge": twist_badge,
            "big_stat": twist_stat,
            "stat_label": twist_label,
            "detail": twist_detail,
            "say": twist_say
        },
        "engagement": {
            "headline": "सत्याधीश चर्चा",
            "question": q_hi,
            "cta": "कमेंट में अपनी राय ज़रूर लिखें!",
            "say": eng_say
        }
    }

    print(f"\n🚀 Dispatching top viral reel to Satyadheesh/reels:")
    print(f"   Article #{aid} (Score {score}/10) [{topic}]")
    print(f"   Hook: {hook_say[:70]}")

    import urllib.request
    req = urllib.request.Request(
        "https://api.github.com/repos/Satyadheesh/reels/dispatches",
        data=json.dumps({"event_type": "generate_reel", "client_payload": payload}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "satya-reel-scorer"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status in (200, 204):
                print(f"✅ Successfully dispatched reel event for #{aid} to Satyadheesh/reels!")
                u_db.execute(
                    "INSERT OR REPLACE INTO reel_posts (article_id, title, topic, viral_score, hook_angle, dispatched_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [aid, title, topic, score, hook, now]
                )
            else:
                err_msg = f"⚠️ *Reel Dispatch Warning*: Satyadheesh/reels returned HTTP status {resp.status} for article #{aid}"
                print(err_msg)
                send_telegram_alert(err_msg)
    except Exception as e:
        err_msg = (
            "🚨 *SatyaDheesh Reel Dispatch Error*\n\n"
            f"• *Article*: #{aid} ({title[:60]})\n"
            f"• *Voice*: {persona}\n"
            f"• *Error*: `{str(e)[:250]}`"
        )
        print(f"❌ Failed to dispatch to Satyadheesh/reels: {e}")
        send_telegram_alert(err_msg)


def script_test(m_db, u_db, ids):
    """Write (and review) the reel script for these article ids and print it, with prompt sizes and timings.
    Nothing is saved or dispatched."""
    model = Model(download())
    for aid in ids:
        c = u_db.execute("SELECT topic, wow_fact FROM reel_candidates WHERE article_id = ?", [aid]).rows
        topic, fact = (str(c[0][0]), str(c[0][1])) if c else ("politics", "")
        r = m_db.execute("SELECT title, rephrased_title, rephrased_article, url, content FROM articles WHERE id = ?", [aid]).rows
        if not r:
            print(f"## {aid}: not found")
            continue
        r = r[0]
        title, political = r[1] or r[0], is_political(topic)
        src_name = "इंडियन एक्सप्रेस" if "indianexpress" in str(r[3] or "").lower() else "द हिंदू"
        body, original = decompress(r[2], limit=4000), clean_original(decompress(r[4], limit=12000))[:4000]
        system = SCRIPT_SYSTEM_CHARLIE + SCRIPT_SOURCE_RULES + (SCRIPT_POLITICAL_EXTRA.replace("{source}", src_name) if political else "")
        head = f"NEWS ARTICLE\nTitle: {title}\nTopic: {topic}\nSource: {src_name}\nKey Fact: {fact}\nVoice Persona: charlie\n"
        prompt = fit_prompt(model, system, head, body[:1500], original, max_tokens=550)
        n = lambda t: len(model.llm.tokenize(t.encode("utf-8"), add_bos=False))
        print(f"## {aid} [{topic}] political={political}: original {len(original)} chars, prompt {n(system)} + {n(prompt)} tokens "
              f"(context {model.llm.n_ctx()}), original kept: {'ORIGINAL ARTICLE' in prompt}", flush=True)
        t0 = time.time()
        sc = model.json(system, prompt, SCRIPT_SCHEMA, temperature=0.25, max_tokens=550)
        if political:
            sc, notes, legal_ok = legal_pass(sc)
            print(f"legal pass: ok={legal_ok} {notes}", flush=True)
        print(f"script in {time.time() - t0:.0f}s:\n{json.dumps(sc, ensure_ascii=False, indent=1)}", flush=True)
        ev = (f"NEWS ARTICLE: {title}\nTOPIC: {topic}{' (POLITICAL: apply the legal safety check)' if political else ''}\n"
              f"ASSIGNED VOICE: charlie\nHEADLINE: {sc.get('headline_hi')}\n"
              f"ON-SCREEN: {sc.get('core_title_hi')} | {' | '.join(sc.get('core_points_hi') or [])} | {sc.get('twist_stat')} "
              f"{sc.get('twist_label')} | {sc.get('twist_detail_hi')}\nHOOK: {sc.get('hook_say')}\nCORE: {sc.get('core_say')}\n"
              f"TWIST: {sc.get('twist_say')}\nENGAGEMENT: {sc.get('engagement_say')}")
        rv = model.json(SUITABILITY_SYSTEM + (SUITABILITY_POLITICAL_EXTRA if political else ""), ev, SUITABILITY_SCHEMA,
                        temperature=0.1, max_tokens=200)
        print(f"review: {json.dumps(rv, ensure_ascii=False)}\n", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=30, help="Number of unscored articles to evaluate")
    ap.add_argument("--dry-run", action="store_true", help="Print scores without writing to DB")
    ap.add_argument("--dispatch", action="store_true", help="Force dispatch of top candidate")
    ap.add_argument("--no-dispatch", action="store_true", help="Do not trigger reels repo")
    ap.add_argument("--script-test", default="", help="comma-separated article ids: write and review their scripts, print only")
    args = ap.parse_args()
    if args.script_test:
        script_test(main_db(), upsc_db(), [int(x) for x in args.script_test.split(",") if x.strip().isdigit()])
        return

    now = int(time.time())
    m_db = main_db()
    u_db = upsc_db()

    # Find articles from the last 24 hours not yet scored in reel_candidates
    since = now - 24 * 3600
    already = {r[0] for r in u_db.execute("SELECT article_id FROM reel_candidates WHERE created_at >= ?", [since - 86400]).rows}

    # Fetch candidate articles across all categories
    rows = m_db.execute(
        "SELECT id, title, rephrased_title, rephrased_article, category, scraped_at "
        "FROM articles WHERE scraped_at >= ? ORDER BY id DESC LIMIT 150",
        [since]
    ).rows

    candidates = []
    for r in rows:
        aid = int(r[0])
        if aid not in already:
            candidates.append({
                "id": aid,
                "title": r[2] or r[1],
                "body": decompress(r[3]),
                "category": r[4],
                "scraped_at": int(r[5])
            })
        if len(candidates) >= args.batch:
            break

    if not candidates:
        print(f"No new unscored articles found in the last 24h.")
        if not args.no_dispatch and not args.dry_run:
            dispatch_daily_reel(u_db, m_db, force=args.dispatch)
        return

    print(f"Evaluating {len(candidates)} new articles with Gemma 4 12B ({MODEL_NAME})...")
    model = Model(download())

    scored_count = 0
    high_score_count = 0

    for idx, art in enumerate(candidates, start=1):
        prompt = (
            f"Title: {art['title']}\n"
            f"Category: {art['category']}\n"
            f"Article Body:\n{art['body'][:1000]}\n"
        )
        try:
            res = model.json(SYSTEM, prompt, SCHEMA, temperature=0.1, max_tokens=250)
            score = int(res.get("viral_score") or 0)
            topic = str(res.get("topic") or art["category"])
            hook = str(res.get("hook_angle") or "")
            fact = str(res.get("wow_fact") or "")
            why = str(res.get("why") or "")

            print(f"[{idx}/{len(candidates)}] ID {art['id']} -> Score {score}/10 [{topic}] {art['title'][:70]}")
            if score >= 7:
                print(f"    🌟 High Viral Score: {hook}")
                high_score_count += 1

            if not args.dry_run:
                u_db.execute(
                    "INSERT OR REPLACE INTO reel_candidates "
                    "(article_id, published_at, topic, viral_score, hook_angle, wow_fact, why, model, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [art["id"], art["scraped_at"], topic, score, hook, fact, why, MODEL_NAME, now]
                )
            scored_count += 1
        except Exception as e:
            print(f"  Error scoring article {art['id']}: {e}")

    print(f"\nDone: {scored_count} articles scored ({high_score_count} with viral score >= 7).")

    if not args.no_dispatch and not args.dry_run:
        dispatch_daily_reel(u_db, m_db, model=model, force=args.dispatch)


if __name__ == "__main__":
    try:
        main()
    finally:
        close_all()
