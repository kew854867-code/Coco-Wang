import csv
from db import conn
c = conn(); rows = c.execute("SELECT * FROM jobs WHERE status!='expired' AND tier!='skip' ORDER BY (tier='priority') DESC, score DESC").fetchall()
cols = ["tier","score","company","title","location","sponsor_signal","status","url","pros","gaps","verify","resume_pdf","cover_pdf","applied_at","note","first_seen"]
with open("data/applications.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(cols); [w.writerow([r[k] for k in cols]) for r in rows]
print(len(rows), "rows -> data/applications.csv")
for s in ("pending","materials_ready","submitted","needs_manual","failed"):
    print(s, c.execute("select count(*) from jobs where status=? and tier!='skip'", (s,)).fetchone()[0])
