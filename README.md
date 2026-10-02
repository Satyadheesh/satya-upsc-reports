# satya-upsc-reports

Everything behind SatyaDheesh's UPSC study material that is built *from* the UPSC notes
(the notes themselves come from `satya-upsc-service`).

| Part | What it does | Status |
|---|---|---|
| `kit/` — Study Kit | Per note: short headline, "why it matters", In-brief line, cleaned facts, one MCQ. Gemma 4 12B on 5 runners. Table `upsc_kit` in the UPSC DB. | building |
| `tg/` — Telegram channel | Daily report at 05:00 IST (yesterday's), weekly on Sunday 07:00 IST: English PDF, Hindi PDF (when ready), quiz polls from the study kit. | built |
| `reports/` — Report builder | Brief + Detailed PDFs (daily / weekly / monthly, English + Hindi), rendered from this repo's templates, stored in `upsc_reports` for the site to serve. | next |

## Secrets (Settings → Secrets → Actions)
| Secret | Copy from | Used for |
|---|---|---|
| `SATYA_UPSC_DB_URL`, `SATYA_UPSC_DB_TOKEN` | satya-upsc-service | notes in; kits and PDFs out |
| `SATYA_DB_URL`, `SATYA_DB_TOKEN` | satya-upsc-service | article titles and sources (read only) |
| `SATYA_TRANSLATION_DB_URL`, `SATYA_TRANSLATION_DB_TOKEN` | SatyaDheesh-Hindi/Hindi | Hindi headlines and notes for Hindi reports (read only) |
| `TELEGRAM_BOT_TOKEN` | @BotFather | posting to the channel (bot must be a channel admin with "Post messages") |
| `TELEGRAM_CHAT_ID` | your channel | `@channelusername` or the numeric id (-100…) |
| `TELEGRAM_TEST_CHAT_ID` (optional) | a private test channel | `mode = test` runs post here instead |
| `REVALIDATE_SECRET` | SatyaDheesh-Hindi/Hindi (same as the site's) | refresh the site's report pages after new PDFs |

## Study kit
- `kit/setup_shards.py` picks notes that need a kit (new, changed since their kit, or failed < 3 times) and splits them over 5 runners.
  Normal runs scan the last 3 days; a full 30-day scan runs until the backfill is done and then nightly.
- `kit/run.py` makes the kits. Every output goes through `kit/validate.py`: numbers must be in the note, answers and
  true statements must be supported by the note, 4 distinct options. The answer key is never written by the model —
  single-answer options are shuffled by us, statement options ("1 and 2 only") are built from the model's true/false flags.
- Preview: run the workflow with `preview = 20`; results land on the `previews` branch (`kit/README.md`), nothing is written to the DB.

Tests: `python -m unittest discover -s tests -t .`

## Telegram
`.github/workflows/telegram.yml` starts each post ~40 min early (and once more ~10 min early as a backup) because GitHub's
scheduler is often late; `tg/post.py` waits for the report, then for the exact minute (05:00 / 07:00 IST), then posts.
Every part is recorded in `telegram_posts`, so the backup start or a rerun never posts twice.
Manual runs: `mode = dry-run` prints the captions and polls; `test` posts to the test channel; `now` posts to the channel immediately.
