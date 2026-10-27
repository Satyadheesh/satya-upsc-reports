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
CREATE INDEX IF NOT EXISTS idx_kit_trans_status ON upsc_kit(translated_hi, status, prompt_version);

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

-- Instagram carousel posts (one row per post, so a rerun never double-posts).
CREATE TABLE IF NOT EXISTS ig_posts (
  key        TEXT PRIMARY KEY,   -- e.g. ig:daily:2026-10-03:en
  media_id   TEXT,
  posted_at  INTEGER NOT NULL
);

-- Instagram long-lived token, refreshed by the poster (valid 60 days; refreshed weekly). Seeded from the IG_TOKEN secret.
CREATE TABLE IF NOT EXISTS ig_auth (
  k            TEXT PRIMARY KEY,
  token        TEXT NOT NULL,
  refreshed_at INTEGER NOT NULL
);

-- SSC CGL Study Kit: rapid-fire active-recall flashcards generated per note (Gemma 4 12B).
CREATE TABLE IF NOT EXISTS ssc_kit (
  article_id      INTEGER PRIMARY KEY,
  status          TEXT NOT NULL CHECK (status IN ('done','failed')),
  attempts        INTEGER NOT NULL DEFAULT 1,
  question_en     TEXT,
  answer_en       TEXT,
  key_fact_en     TEXT,
  static_gk_en    TEXT,
  question_hi     TEXT,
  answer_hi       TEXT,
  key_fact_hi     TEXT,
  static_gk_hi    TEXT,
  note_updated_at INTEGER,
  model           TEXT,
  prompt_version  TEXT,
  error           TEXT,
  created_at      INTEGER NOT NULL,
  updated_at      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ssc_kit_status ON ssc_kit(status, attempts);

-- SSC CGL current affairs, judged from the raw news (sscca/): one row per article looked at.
-- status: card (gate passed + valid card), skip (not SSC material / duplicate story), failed (retry later).
CREATE TABLE IF NOT EXISTS ssc_ca (
  article_id      INTEGER PRIMARY KEY,
  published_at    INTEGER NOT NULL,
  cluster_id      TEXT,
  status          TEXT NOT NULL CHECK (status IN ('card','skip','failed')),
  attempts        INTEGER NOT NULL DEFAULT 1,
  topic           TEXT,
  importance      INTEGER,
  scope           TEXT,
  fact            TEXT,
  title           TEXT,
  question        TEXT,
  answer          TEXT,
  key_fact        TEXT,
  static_gk       TEXT,
  reason          TEXT,
  model           TEXT,
  prompt_version  TEXT,
  created_at      INTEGER NOT NULL,
  updated_at      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ssc_ca_pub ON ssc_ca(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_ssc_ca_status ON ssc_ca(status, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_ssc_ca_cluster ON ssc_ca(cluster_id);

-- Top-news alerts, shadow mode (alerts/pick.py, 17 Oct 2026): every story the picker scored, what the AI editor said,
-- and the decision (picked / blocked:<why> / rejected / scored). Picks go to the admin Telegram chat only.
CREATE TABLE IF NOT EXISTS alert_candidates (
  story_key   TEXT PRIMARY KEY,
  article_id  INTEGER NOT NULL,
  first_seen  INTEGER NOT NULL,
  score       REAL NOT NULL,
  signals     TEXT,
  judged_at   INTEGER,
  notify      INTEGER,
  importance  INTEGER,
  why         TEXT,
  line_en     TEXT,
  line_hi     TEXT,
  decision    TEXT,
  decided_at  INTEGER,
  admin_msg   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_alert_decided ON alert_candidates(decided_at);

-- Viral reels candidates across all topics, judged by Gemma 4 12B (tools/reel_scorer.py)
CREATE TABLE IF NOT EXISTS reel_candidates (
  article_id      INTEGER PRIMARY KEY,
  published_at    INTEGER NOT NULL,
  topic           TEXT,
  viral_score     INTEGER NOT NULL,
  hook_angle      TEXT,
  wow_fact        TEXT,
  why             TEXT,
  model           TEXT,
  created_at      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reel_candidates_score ON reel_candidates(viral_score DESC, published_at DESC);

-- Dispatched viral reels (one row per dispatched article, ensures no duplicate reels)
CREATE TABLE IF NOT EXISTS reel_posts (
  article_id    INTEGER PRIMARY KEY,
  title         TEXT,
  topic         TEXT,
  viral_score   INTEGER NOT NULL,
  hook_angle    TEXT,
  dispatched_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reel_posts_time ON reel_posts(dispatched_at DESC);
