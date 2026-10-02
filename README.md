# satya-upsc-reports

Everything behind SatyaDheesh's UPSC study material that is built *from* the UPSC notes
(the notes themselves come from `satya-upsc-service`).

| Part | What it does | Status |
|---|---|---|
| `kit/` — Study Kit | Per note: short headline, "why it matters", In-brief line, cleaned facts, one MCQ. Gemma 4 12B on 5 runners. Table `upsc_kit` in the UPSC DB. | building |
| `reports/` — Report builder | Brief + Detailed PDFs (daily / weekly / monthly, English + Hindi), rendered from this repo's templates, stored in `upsc_reports` for the site to serve. | next |

## Secrets (Settings → Secrets → Actions)
`SATYA_UPSC_DB_URL`, `SATYA_UPSC_DB_TOKEN`, `SATYA_DB_URL`, `SATYA_DB_TOKEN` — same values as in satya-upsc-service.
The main DB is only read (article titles).

## Study kit
- `kit/setup_shards.py` picks notes that need a kit (new, changed since their kit, or failed < 3 times) and splits them over 5 runners.
  Normal runs scan the last 3 days; a full 30-day scan runs until the backfill is done and then nightly.
- `kit/run.py` makes the kits. Every output goes through `kit/validate.py`: numbers must be in the note, answers and
  true statements must be supported by the note, 4 distinct options. The answer key is never written by the model —
  single-answer options are shuffled by us, statement options ("1 and 2 only") are built from the model's true/false flags.
- Preview: run the workflow with `preview = 20`; results land on the `previews` branch (`kit/README.md`), nothing is written to the DB.

Tests: `python -m unittest discover -s tests -t .`
