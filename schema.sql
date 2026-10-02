-- satya-upsc-reports: tables this repo owns in the UPSC DB. Applied by migrate.py (idempotent).

-- Study kit: exam extras generated per UPSC note (upsc_articles.article_id).
CREATE TABLE IF NOT EXISTS upsc_kit (
  article_id      INTEGER PRIMARY KEY,
  status          TEXT NOT NULL CHECK (status IN ('done','failed')),
  attempts        INTEGER NOT NULL DEFAULT 1,
  short_title     TEXT,             -- <= 80 chars, for cards and lists
  takeaway        TEXT,             -- "why it matters" line, <= 150 chars
  brief_lead      TEXT,             -- In-brief one-liner: bold lead ...
  brief_text      TEXT,             -- ... and the rest of the line
  facts           TEXT,             -- JSON [{"label","text"}] merged, de-duplicated facts
  mcq             TEXT,             -- JSON {"type","question","statements","options","answer","explanation"}
  note_updated_at INTEGER,          -- upsc_articles.updated_at the kit was made from (re-made when the note changes)
  model           TEXT,
  prompt_version  TEXT,
  error           TEXT,
  created_at      INTEGER NOT NULL,
  updated_at      INTEGER NOT NULL,
  translated_hi   INTEGER DEFAULT 0 -- for the Hindi service, later
);
CREATE INDEX IF NOT EXISTS idx_kit_status ON upsc_kit(status, attempts);

CREATE TABLE IF NOT EXISTS kit_meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);

-- Telegram channel posts (one row per post part, so a rerun never double-posts).
CREATE TABLE IF NOT EXISTS telegram_posts (
  key        TEXT PRIMARY KEY,   -- e.g. daily:2026-10-01:en, daily:2026-10-01:hi, daily:2026-10-01:quiz
  chat       TEXT NOT NULL,
  message_id INTEGER,
  posted_at  INTEGER NOT NULL
);
