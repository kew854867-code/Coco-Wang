import sqlite3, pathlib
DB = pathlib.Path(__file__).parent / "data" / "jobs.db"
def conn():
    DB.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS jobs(
      id TEXT PRIMARY KEY, ats TEXT, company TEXT, slug TEXT, ext_id TEXT, title TEXT, location TEXT,
      url TEXT, jd_text TEXT, posted TEXT, first_seen TEXT,
      score INTEGER, tier TEXT, pros TEXT, gaps TEXT, verify TEXT, sponsor_signal TEXT,
      status TEXT DEFAULT 'pending', resume_pdf TEXT, cover_pdf TEXT, applied_at TEXT, note TEXT);
    CREATE UNIQUE INDEX IF NOT EXISTS u_dedupe ON jobs(company, title, location);
    """)
    return c
