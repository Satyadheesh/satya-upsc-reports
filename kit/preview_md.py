"""Turn preview JSONL files into one readable markdown page (published to the `previews` branch)."""
import glob
import json
import statistics
import sys

L = "abcd"


def render(rows):
    ok = [r for r in rows if r["kit"]]
    secs = [r["seconds"] for r in rows]
    out = [f"# Study kit preview\n",
           f"{len(ok)}/{len(rows)} notes passed · median {statistics.median(secs):.0f}s per note · "
           f"first-try pass {sum(1 for r in ok if r['tries'] == 1)}/{len(rows)}\n"]
    fails = [r for r in rows if not r["kit"]]
    if fails:
        out.append("## Failed\n" + "\n".join(f"- {r['article_id']}: {r['error']}" for r in fails) + "\n")
    for r in ok:
        n, k, m = r["note"], r["kit"], r["kit"]["mcq"]
        out.append(f"---\n## {k['short_title']}\n")
        out.append(f"`{n['article_id']}` · {n['gs_paper']} · {n['subject']} · {r['tries']} tries · {r['seconds']}s  \n"
                   f"Original title: {n.get('title') or n.get('original_title')}\n")
        out.append(f"**Why it matters:** {k['takeaway']}  \n**In brief:** **{k['brief_lead']}** {k['brief_text']}\n")
        out.append("**Facts**\n" + "\n".join(f"- *{f['label']}* — {f['text']}" for f in k["facts"]) + "\n")
        q = f"**MCQ ({m['type']})** {m['question']}\n"
        if m.get("statements"):
            q += "\n".join(f"{i + 1}. {s}" for i, s in enumerate(m["statements"])) + f"\n\n{m['ask']}\n"
        q += "\n" + "\n".join(f"- ({L[i]}) {o}{'  ✅' if i == m['answer'] else ''}" for i, o in enumerate(m["options"]))
        q += f"\n\n*{m['explanation']}*\n"
        out.append(q)
        ptrs = "; ".join(p.get("text", "") for p in n.get("prelims_pointers") or [])
        out.append(f"<details><summary>Source note</summary>\n\n**Why in news:** {n['why_in_news']}\n\n"
                   f"**Key facts:** {n['fact_box']}\n\n**Pointers:** {ptrs}\n</details>\n")
    return "\n".join(out)


if __name__ == "__main__":
    rows = []
    for f in sorted(glob.glob(f"{sys.argv[1]}/**/*.jsonl", recursive=True)):
        rows += [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    open(sys.argv[2], "w", encoding="utf-8").write(render(rows) if rows else "# Study kit preview\n\nNo output.\n")
    print(f"{len(rows)} kits rendered")
