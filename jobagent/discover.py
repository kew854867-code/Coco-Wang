"""Fetch live postings from Greenhouse / Lever / Ashby public APIs, filter, score, store."""
import re, html, json, datetime, requests, concurrent.futures as cf
from companies import COMPANIES
from db import conn

UA = {"User-Agent": "Mozilla/5.0 personal-job-search"}
def strip(h): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(h or ""))).strip()

def fetch(ats, slug, name):
    out = []
    try:
        if ats == "greenhouse":
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", headers=UA, timeout=60).json()
            for j in r["jobs"]:
                out.append(dict(ext_id=str(j["id"]), title=j["title"], location=(j.get("location") or {}).get("name", ""),
                    url=j["absolute_url"], jd=strip(j.get("content")), posted=j.get("updated_at", "")))
        elif ats == "lever":
            r = requests.get(f"https://api.lever.co/v0/postings/{slug}?mode=json", headers=UA, timeout=60).json()
            for j in r:
                c = j.get("categories") or {}
                loc = c.get("location") or ""
                if c.get("allLocations"): loc = "; ".join(c["allLocations"])
                out.append(dict(ext_id=j["id"], title=j["text"], location=loc, url=j["hostedUrl"],
                    jd=j.get("descriptionPlain", "") + " " + " ".join(l.get("text","")+" "+strip(l.get("content")) for l in j.get("lists", [])),
                    posted=datetime.datetime.fromtimestamp(j["createdAt"]/1000).isoformat() if j.get("createdAt") else ""))
        elif ats == "ashby":
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", headers=UA, timeout=90).json()
            for j in r["jobs"]:
                if j.get("isListed") is False: continue
                loc = j.get("location") or ""
                for s in j.get("secondaryLocations") or []: loc += "; " + (s.get("location") or "")
                if j.get("isRemote") and "remote" not in loc.lower(): loc += " (Remote)"
                out.append(dict(ext_id=j["id"], title=j["title"], location=loc, url=j["jobUrl"],
                    jd=j.get("descriptionPlain") or strip(j.get("descriptionHtml")), posted=j.get("publishedAt", "")))
    except Exception as e:
        print(f"  ! {name}: {e}")
    return out

# ---------- filtering & scoring ----------
INCLUDE = r"community|event|partnership|business development|biz dev|ecosystem|developer relations|devrel|developer advocate|developer marketing|developer experience|growth|founder|startup|alliances|program manager|programs|field marketing|brand|communications|strategic|bd\b|go-to-market|gtm|operations associate"
EXCLUDE = r"software engineer|machine learning engineer|research (scientist|engineer)|data scientist|account executive|sales development|recruit|talent|legal|counsel|accountant|finance|payroll|tax\b|security engineer|mechanical|electrical|firmware|hardware|supply chain|procurement|technician|designer|product manager|solutions? (engineer|architect)|customer success|support|attorney|compliance|physician|nurse|\bintern\b|facilities|it (support|engineer)|sdet|devops|sre\b|manufacturing|quality|analyst|architect|applied ai|sales leader|billing|data engineer|operations engineer|machine learning|engineer(?!ing)|revenue operations|order management|partner \\d+|channel|technical program|technical producer|founders' office|product strategy|commercial operations|workplace services|internal communications|npi|content marketing|contractor|part time"
SENIOR = r"senior director|vice president|\bvp\b|head of|chief|principal|\bstaff\b|director|group manager"
US = r"united states|\busa?\b|, ca\b|california|san francisco|bay area|palo alto|mountain view|sunnyvale|san jose|redwood|menlo|oakland|seattle|new york|boston|austin|los angeles|remote|\b[A-Z]{2}\b(?:, US)?"
NO_SPONSOR = r"(not|unable to|cannot|can't|won't|do not|does not|will not)[^.]{0,40}(sponsor|sponsorship)|without (the need for )?(visa )?sponsorship|must be (a )?(u\.?s\.? citizen|authorized to work)[^.]{0,60}(without|no)|us citizen(ship)? (is )?required|u\.s\. citizens? only|itar|security clearance"
SPONSOR_YES = r"(provide|offer|support|available)[^.]{0,40}(visa )?sponsorship|sponsor(s|ship)? (is )?available|visa sponsorship (is )?(available|provided)|will sponsor|h-?1b"
BAY = r"san francisco|bay area|palo alto|mountain view|sunnyvale|san jose|redwood city|menlo park|oakland|santa clara|fremont|south san|cupertino|berkeley|los altos|milpitas|hayward|burlingame|san mateo"

def is_us(loc):
    l = loc or ""
    low = l.lower()
    if re.search(r"united states|\busa\b|\bus\b|u\.s\.|remote - us|us-remote", low): return True
    if re.search(BAY, low): return True
    if re.search(r"(seattle|new york|boston|austin|los angeles|chicago|denver|atlanta|washington|las vegas|miami|pittsburgh|portland|, (ca|wa|ny|ma|tx|co|il|ga|fl|dc|va|pa|nv|or|nj)\b)", low): return True
    return False

def evaluate(job, domain):
    t, jd, loc = job["title"], job["jd"], job["location"]
    tl, jl = t.lower(), jd.lower()
    if not re.search(INCLUDE, tl) or re.search(EXCLUDE, tl): return None
    if not re.search(BAY, loc.lower()): return None  # Bay Area only (user lives in Palo Alto)
    score, pros, gaps, verify = 0, [], [], []
    # title fit
    core = r"community|events?\b|partnership|business development|ecosystem|developer relations|devrel|developer advocate|founder|startup|alliances"
    if re.search(core, tl): score += 40; pros.append("Title matches target function (" + re.search(core, tl).group(0) + ")")
    else: score += 20; verify.append("Title only loosely matches targets; read JD")
    if re.search(r"community", tl) and re.search(r"event", tl): score += 15
    # seniority / experience
    if re.search(r"\bsenior\b|\bsr\.?\b|\blead\b|manager of", tl): score -= 8; gaps.append("Senior/lead wording in title - stretch")
    if re.search(SENIOR, tl): score -= 25; gaps.append("Senior-level title; resume is ~1.5 yrs of full-time-equivalent experience")
    yrs = [int(x) for x in re.findall(r"(\d{1,2})\+?\s*(?:-\s*\d+\s*)?years", jl)]
    if yrs:
        m = max(yrs[:6]) if yrs else 0
        if m >= 7: score -= 20; gaps.append(f"JD asks for {m}+ years")
        elif m >= 5: score -= 10; gaps.append(f"JD asks for {m}+ years")
        elif m <= 3: score += 5
    # domain
    d = {"robotics": 20, "ai": 12, "ecosystem": 15, "tech": 4}[domain]; score += d
    if domain in ("robotics", "ai"): pros.append(f"{domain.upper()} company - matches robotics/AI community background")
    if domain == "ecosystem": pros.append("Startup-ecosystem organisation - matches founder/program work")
    kw = sum(1 for k in ["robot", "embodied", "humanoid", "physical ai", "conference", "speaker", "sponsor", "founder", "startup", "luma", "hubspot", "crm", "executive", "outreach", "summit", "community"] if k in jl)
    score += min(kw * 2, 14)
    # location
    if re.search(BAY, loc.lower()): score += 10; pros.append("Bay Area location")
    elif "remote" in loc.lower(): score += 3; verify.append("Remote - confirm eligible states")
    else: score += 4
    if re.search(r"hybrid|on-?site|in-office", jl): verify.append("Check in-office expectations")
    # sponsorship
    spons = "unknown"
    if re.search(NO_SPONSOR, jl): spons = "NO"; score -= 60; gaps.append("JD indicates no visa sponsorship / citizenship requirement")
    elif re.search(SPONSOR_YES, jl): spons = "YES"; score += 12; pros.append("JD mentions visa sponsorship")
    else: verify.append("Sponsorship not stated - ask recruiter / check company history")
    verify.append("Work authorization question must be answered by you")
    tier = "priority" if score >= 62 and spons != "NO" else "consider" if score >= 36 and spons != "NO" else "skip"
    return dict(score=score, tier=tier, pros="; ".join(pros), gaps="; ".join(gaps) or "None obvious", verify="; ".join(verify), sponsor_signal=spons)

def main():
    c = conn(); now = datetime.datetime.now().isoformat(timespec="seconds")
    total = kept = new = 0
    with cf.ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda x: (x, fetch(x[0], x[1], x[2])), COMPANIES))
    for (ats, slug, name, domain), jobs in results:
        total += len(jobs)
        for j in jobs:
            ev = evaluate(j, domain)
            if not ev: continue
            kept += 1
            jid = f"{ats}:{slug}:{j['ext_id']}"
            ex_ = c.execute("SELECT 1 FROM jobs WHERE id=?", (jid,)).fetchone()
            if ex_:
                c.execute("UPDATE jobs SET score=?,tier=?,pros=?,gaps=?,verify=?,sponsor_signal=? WHERE id=?",
                          (ev["score"], ev["tier"], ev["pros"], ev["gaps"], ev["verify"], ev["sponsor_signal"], jid)); continue
            try:
                c.execute("""INSERT INTO jobs(id,ats,company,slug,ext_id,title,location,url,jd_text,posted,first_seen,score,tier,pros,gaps,verify,sponsor_signal)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (jid, ats, name, slug, j["ext_id"], j["title"], j["location"], j["url"], j["jd"], j["posted"], now,
                     ev["score"], ev["tier"], ev["pros"], ev["gaps"], ev["verify"], ev["sponsor_signal"])); new += 1
            except Exception: pass  # duplicate (company,title,location)
    # drop postings that vanished from live feeds (expired) if not yet applied
    live = {f"{a}:{s}:{j['ext_id']}" for (a, s, n, d), js in results for j in js}
    gone = [r["id"] for r in c.execute("SELECT id FROM jobs WHERE status IN ('pending','materials_ready')") if r["id"] not in live]
    for g in gone: c.execute("UPDATE jobs SET status='expired' WHERE id=?", (g,))
    c.commit()
    print(f"Fetched {total} live postings from {len(COMPANIES)} companies; {kept} matched function+US filter; {new} new; {len(gone)} expired")
    for t in ("priority", "consider", "skip"):
        print(t, c.execute("SELECT COUNT(*) FROM jobs WHERE tier=? AND status!='expired'", (t,)).fetchone()[0])

if __name__ == "__main__": main()
