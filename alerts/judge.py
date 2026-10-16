"""The AI editor: for the few stories the cheap signals put on top, would an ordinary person in India want a push
notification about this right now? Same local model as the study kit (Gemma, llama.cpp). English only: the Hindi line
is the Hindi service's own headline translation."""
SYSTEM = """You are the night-and-day news editor of a free Indian news app read by ordinary people (students,
families, workers, shopkeepers), not policy experts. You decide whether ONE story deserves a push notification.

Notify only if most readers across India would be glad to be interrupted for it, because it:
- changes their money, travel, studies, exams, jobs, health, safety or daily routine (prices, fares, rules, results,
  holidays, weather and disaster warnings), or
- is a major national event people will talk about today (big verdict, big decision, major disaster, national result).

Do NOT notify for: local crime or accidents with few victims, routine political statements or allegations, rallies,
foreign news with no effect on India, celebrity gossip, opinion, sports results (except a historic Indian win),
company news that changes nothing for ordinary people, or anything already old.

Answer in JSON:
- notify: true/false
- importance: 1-10 for an ordinary reader (7+ means notify-worthy)
- why: one short sentence, the reason for your decision
- line: the notification text, at most 110 characters, plain factual English that says what happened and why it
  matters to the reader. No clickbait, no questions, no emojis, no "Breaking"."""

SCHEMA = {"type": "object", "properties": {
    "notify": {"type": "boolean"}, "importance": {"type": "integer", "minimum": 1, "maximum": 10},
    "why": {"type": "string"}, "line": {"type": "string"}}, "required": ["notify", "importance", "why", "line"]}


def prompt(sig, summary):
    return (f"Headline: {sig['titles'][0]}\n"
            + (f"Other outlets' headlines: {' | '.join(sig['titles'][1:])}\n" if len(sig["titles"]) > 1 else "")
            + f"Category: {sig['category']}; place: {sig.get('geo') or 'not given'}; reported by {sig['outlets']} outlet(s)\n"
            f"Summary: {summary[:800]}\n")


class Editor:
    def __init__(self):
        from kit.model import Model, download
        self.m = Model(download(), n_ctx=4096)

    def judge(self, sig, summary):
        out = self.m.json(SYSTEM, prompt(sig, summary), SCHEMA, temperature=0.1, max_tokens=300)
        line = " ".join(str(out.get("line") or "").split())[:140]
        return dict(notify=bool(out.get("notify")), importance=int(out.get("importance") or 0),
                    why=" ".join(str(out.get("why") or "").split())[:300], line=line)
