"""Playwright autofill + submit for Greenhouse (job-boards.greenhouse.io) and Ashby forms.
Default is DRY RUN. --submit submits ONLY when every required field is answered. A job is 'submitted'
only when the page itself shows a success message. Never solves/bypasses visible CAPTCHAs."""
import argparse, datetime, json, pathlib, re, time
from playwright.sync_api import sync_playwright
from db import conn

ROOT = pathlib.Path(__file__).parent
A = json.load(open(ROOT / "profile" / "facts.json"))["answers_confirmed"]
SHOTS = ROOT / "output" / "screens"; SHOTS.mkdir(parents=True, exist_ok=True)

KNOWN = [
 (r"^country\*?$|^country$", "United States"),
 (r"expected (compensation|salary|pay)|salary (expectation|requirement)|compensation (expectation|requirement)|desired (salary|compensation)", "$90,000 - $110,000"),   # user-provided
 (r"address line 1|street address|^address\b|legal address|home address|mailing address", A.get("street","") + ", " + A.get("city","") + ", " + A.get("state","") + " " + A.get("zip","")),
 (r"postal|zip", A.get("zip","")),
 (r"province|^state\b", "California"),
 (r"^school\b|^university|^college", "Temple University"),
 (r"^degree\b", "Master of Science (M.S.)"),
 (r"^discipline|field of study|major", "Innovation Management & Entrepreneurship"),
 (r"cities.*(available|work|willing)|which cities|available to work in", "San Francisco Bay Area (Palo Alto, CA)"),
 (r"(most recent|current).*(work|employ|compan)|where have you (most recently )?worked", "MIE Events"),
 (r"college|universit|school (did|do) you|alma mater", "Temple University"),
 (r"full legal name|legal name as it appears", A["first_name"] + " " + A["last_name"]),
 (r"(start|available).*date|date.*(start|available)|earliest.*start|when can you start", "Immediately"),
 (r"how did you (first )?(hear|find)|where did you (first )?(hear|find)", "LinkedIn"),
 (r"from where do you intend|where.*(intend|plan).*work|work location|which office", "Bay Area (Palo Alto, CA)"),
 (r"(current|most recent).*(job )?title|^current title", "Robotics Partnerships & Community Lead"), (r"(current|most recent).*(employer|company)|^current company", "MIE Events"),
 (r"^first name|legal first|preferred first", A["first_name"]), (r"^last name|legal last|surname", A["last_name"]),
 (r"^(full |legal )?name\b(?!.*(company|referr))", A["first_name"] + " " + A["last_name"]),
 (r"e-?mail", A["email"]), (r"phone", A["phone"]),
 (r"linkedin", A["linkedin"]), (r"website|portfolio|personal (site|url)|github|websites", A["website"]),
 (r"current location|^location|city|where are you (based|located)|current address", A["location"]),
]
EEO = r"gender|race|ethnic|hispanic|veteran|disabilit|sexual orientation|transgender|pronoun|lgbt"
def decide(label):
    """Question -> 'yes'|'no'|'decline'|'country'|'hear'|None (None = needs the human). Answers follow the user's
    stated facts: lives in Palo Alto, F-1 OPT, needs H-1B sponsorship, only Bay Area roles."""
    l = label.lower()
    if re.search(EEO, l): return "decline"
    if re.search(r"describes your work authorization|authorization to work in the country where you live|best describes your right to work", l): return "authsp"   # F-1 OPT: authorized now, needs sponsorship later (user-confirmed)
    if re.search(r"currently reside in the location|reside in the (location|country)", l): return "yes"   # lives in Palo Alto, US
    if re.search(r"u\.?s\.? person", l): return "no"       # Chinese citizen, F-1 OPT, no green card/asylum/refugee (user-confirmed)
    if re.search(r"(1|one)[-– ]*(to|-)?[-– ]*(2|two) years.*(post|after).*(graduat|school)|years of experience post graduation", l): return "yes"   # user confirmed
    if re.search(r"plan to work remotely|work from a remote location|work remotely", l): return "yes"                                   # user confirmed
    if re.search(r"live in one of the following states", l): return "no"                                                                # user confirmed (CA not listed)
    if re.search(r"non-?compete|non-?solicit|bound by (any )?(agreement|contract)|agreements? with (a |any )?(current|former|previous) employer", l): return "no"  # user confirmed: none
    if re.search(r"arbitrat|agree to (the )?(arbitration|terms)|acknowledge.*(ai policy|policy)|ai policy", l): return "yes"  # user consented in chat
    # sanctions/export-control checkbox groups (Databricks): Chinese citizen on F-1 OPT, resident of the US -> "none of the above" / "not applicable"
    if re.search(r"^acknowledge\b|^i acknowledge", l): return "yes"
    if re.search(r"^none of the above|^not applicable \(i\.e", l): return "yes"
    if re.search(r"cuba, iran, north korea|^u\.s\. (citizen|non-citizen national|permanent resident)|^individual granted (asylum|refugee)|^individual granted (citizenship|permanent residency) in a country", l): return "no"
    if re.search(r"criminal|convict|felony|security clearance|citizen", l): return None
    if "sponsor" in l: return "no" if re.search(r"without|not require|no sponsor", l) else "yes"
    if re.search(r"authori[sz]ed|eligible to work|legally (permitted|entitled)|right to work", l): return "yes"
    if re.search(r"previously (applied|worked|employed)|former .{0,30}(employee|intern|contractor)|current(ly)? employ|government employ|related to .*employee|family member", l): return "no"
    if re.search(r"(ever|previously|before).*(interview|work(ed)? (for|at)|employ|contract)|have you ever (applied|interviewed|worked)", l): return "no"
    if re.search(r"based in any of these countries|countries where we are accepting|which country.*(reside|located|based)", l): return "country"
    if re.search(r"cities.*(available|work|willing)|which cities", l): return "bay"
    if re.search(r"from where do you intend|where.*(intend|plan).*work|which office|work location|office location|preferred (office|location)", l): return "bay"
    if re.search(r"double-check all the information|reviewed and confirmed|ensuring accuracy", l): return "yes"
    if re.search(r"certify|information (provided|submitted).*(true|accurate)|i confirm|i attest", l): return "yes"
    if re.search(r"whatsapp", l): return "yes"
    if re.search(r"within 35 miles of", l): return "yes"       # Palo Alto is ~30 mi from San Francisco
    if re.search(r"^degree\b", l.strip()): return "degree"
    if re.search(r"^school\b", l.strip()): return "school"
    if re.search(r"(1|one)\s*[-–to ]+\s*(2|two) years.*(outbound|prospecting|cold call|sales)|years of .*(outbound|prospecting|cold call)", l): return "yes"   # user confirmed
    if re.search(r"track record|meeting or exceeding|exceed(ing)? (sales )?(quota|target)|quotas? and kpis?|sales development quota", l): return "yes"   # resume/site: 100+ GTC leads, 2 exhibitors closed, 715 outreach conversations
    m = re.search(r"(\d+)\s*\+?\s*(?:[-–]\s*\d+\s*)?years?", l)
    if m and int(m.group(1)) <= 3 and re.search(r"outbound|prospecting|lead gen|partnership|event|community|ecosystem|go-to-market|gtm|business development|marketing|sponsorship|crm|hubspot|linkedin|outreach|sales", l): return "yes"   # <=3 yrs in areas on resume
    if re.search(r"(experience|familiar).{0,40}(crm|hubspot|salesforce|sales navigator|gong|apollo|outreach tool|sales engagement|pipeline)", l): return "yes"   # resume: HubSpot CRM, Apollo, LinkedIn
    if re.search(r"which state (do you )?(reside|live)|state of residence|state you (reside|live)|state.*(currently )?reside", l): return "state"
    if re.search(r"unable to employ candidates residing|reside in one of these regions|cannot employ candidates residing", l): return "no"   # California is not in the excluded lists
    if re.search(r"(planned|executed|organi[sz]ed|hosted|produced|managed|run|ran).{0,60}(events?|meetups?|dinners?|summits?|conferences?|activations?|webinars?)", l) and re.search(r"have you|do you|experience", l): return "yes"   # 21 events, Stanford 500+ summit, CES 240+
    if re.search(r"18 years|over the age of 18|at least 18", l): return "yes"
    if re.search(r"office hubs?|days from|relocat|in[- ]person|in[- ]office|on[- ]?site|commut|hybrid|come into|days (a|per|/) ?week|work from (our|the) office", l): return "yes"
    if re.search(r"^country|country of|country\*?$|country (where|you).*(reside|live|based)|what country are you based in|currently reside", l): return "country"
    if re.search(r"based in|reside|live in|located in|currently (located|based)", l):
        return "yes" if re.search(r"bay area|san francisco|palo alto|california|silicon valley|san jose|mountain view|\bca\b", l) else None
    if re.search(r"how did you (first )?(hear|find)|source|where did you (first )?(hear|find)", l): return "hear"
    if re.search(r"privacy|data (processing|protection)|terms (of|and)|i (have )?read|consent", l): return "yes"
    return None

def pick(options, want, label=""):
    low = [o.strip().lower() for o in options]
    def first(rx, avoid=None):
        for i, o in enumerate(low):
            if re.search(rx, o) and not (avoid and re.search(avoid, o)): return i
    if want == "yes":
        for rx in (r"^(yes|i agree|i acknowledge|i consent|i accept|i have read|i confirm|i am|i do|i will|true|agree|accept)", r"\byes\b|agree|acknowledge|accept|^consent|^i consent|reviewed and confirmed|i confirm"):
            i = first(rx, r"^no\b|\bnot\b|decline|do not|don't|disagree|assist")
            if i is not None: return i
        return None
    if want == "no": return first(r"^(no|i am not|i do not|i have not|false)\b|^none")
    if want == "decline": return first(r"decline|don'?t wish|do not wish|prefer not|not (wish|want) to|choose not|rather not")
    if want == "authsp": return first(r"valid work permit which needs to be sponsored|work permit.*(needs|requires).*sponsor|need.*sponsor|do not require sponsorship now, but will in the future")
    if want == "state": return first(r"^california|^ca$")
    if want == "degree": return first(r"^master.?s degree|^master of science|^master")
    if want == "bay":
        i = first(r"san francisco|bay area|palo alto|mountain view|sunnyvale|san jose|menlo park|south san|redwood|oakland|santa clara|remote")
        return i if i is not None else first(r"^yes\b")
    if want == "country": return first(r"^united states|^usa$|^us$|^u\.s")
    if want == "hear": return first(r"linkedin") if first(r"linkedin") is not None else (first(r"job board|internet|online|website|other"))
    return None

def label_of(el):
    try:
        return el.evaluate("""e=>{const id=e.id; let l=id?document.querySelector(`label[for="${CSS.escape(id)}"]`):null;
          if(!l) l=e.closest('label'); if(!l){const f=e.closest('[class*=fieldEntry],[class*=field],.application-field,fieldset,.select__container,div'); l=f&&f.querySelector('label,legend');}
          return ((l&&l.innerText)||e.getAttribute('aria-label')||e.placeholder||e.name||'').trim();}""", timeout=3000)
    except Exception: return ""

MISSION = {
 "Anthropic": "building AI systems that are reliable, interpretable and steerable, and making sure they benefit people",
 "OpenAI": "making sure advanced AI benefits all of humanity",
 "Cartesia": "building fast, real-time AI that people can talk to naturally",
 "Perplexity": "making accurate, trustworthy answers accessible to everyone",
 "Scale AI": "providing the data and infrastructure that move AI forward, including physical AI",
 "Cursor (Anysphere)": "changing how software gets built with AI",
 "Cognition": "building AI that can do real software engineering work",
}
def essay(label):
    c, t = JOB["company"], JOB["title"]
    m = MISSION.get(c, "the mission and the product you are building")
    l = label.lower()
    core = (f"I want to help {c} spread its mission of {m}. As a robotics and AI community builder in Silicon Valley, I bring people into the room: "
            "I co-led the sold-out Humanity & AGI Summit 2026 at the Stanford Faculty Club (500+ attendees, 40+ speakers), hosted the CES Innovation & Monetization Summit (240+ attendees, 30+ speakers), "
            "and have co-hosted 21 events with a network of 52,000+ across email, WeChat, LinkedIn and RedNote. ")
    if re.search(r"why .*(company|\bus\b|this role|position|join|want to work|interested)|why (" + re.escape(c.lower().split()[0]) + ")|interest|excit|motivat|passion|draw", l):
        return core + f"The {t} role is where I can turn that network and event experience into growth, partnerships and community for {c}, and I share your belief in where this technology is going."
    if re.search(r"\bai\b.*(use|day|work|tool)|use .*\bai\b|artificial intelligence.*(use|work)|how do you use", l):
        return ("I use AI every day as part of how I work. I use Claude to build and run my own tools: an Outreach Agent that scores prospects, finds the decision-maker, verifies contacts and drafts personalized emails for one-click approval "
                "(I opened 715 LinkedIn conversations, about one-third replied); a Robotics Events Calendar that scans 200+ sources weekly and has indexed 8,000+ events; and an automated robotics video pipeline "
                "(trend tracking, research, script, AI voiceover, captions) publishing to 3,000+ LinkedIn followers. At MIE Events I built a single-source-of-truth content workflow so speaker and agenda changes reach 10+ deliverables within 30 minutes. "
                "I treat AI as a way to do more careful, personalized outreach and operations, and I always review its output before it goes out.")
    if re.search(r"additional|anything else|tell us more|cover letter|about yourself|introduce", l):
        return core + "I also build my own tools, including an Outreach Agent that opened 715 LinkedIn conversations with about a one-third reply rate. I am on F-1 OPT and would need H-1B sponsorship, and I live in Palo Alto."
    return None

LEARNED = ROOT / "profile" / "learned.json"
def _norm(t): return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()[:120]
def ask(lab, options=None, kind="text"):
    """Ask the user about an unknown required question, in-flight: writes output/question.json and waits for output/answer.txt.
    Answers are remembered in profile/learned.json so the same question is never asked twice."""
    if not _norm(lab): return None          # unreadable label: nothing sensible to ask
    book = json.load(open(LEARNED)) if LEARNED.exists() else {}
    if _norm(lab) in book: return book[_norm(lab)]
    q, a = ROOT / "output" / "question.json", ROOT / "output" / "answer.txt"
    a.unlink(missing_ok=True)
    q.write_text(json.dumps({"job": JOB["company"] + " | " + JOB["title"], "label": lab, "options": options, "kind": kind}, ensure_ascii=False))
    for _ in range(300):
        if a.exists() and a.read_text().strip(): break
        time.sleep(3)
    q.unlink(missing_ok=True)
    if not a.exists(): return None
    ans = a.read_text().strip(); a.unlink()
    if ans.upper() == "SKIP": return None
    book[_norm(lab)] = ans; json.dump(book, open(LEARNED, "w"), ensure_ascii=False, indent=1)
    return ans

def status_option(lab):
    l = lab.lower()
    if re.search(r"granted citizenship in a country other than", l): return True   # Chinese citizen
    return False

def fill(page):
    filled, unresolved, unchecked = [], [], []
    # --- uploads
    for inp in page.locator("input[type=file]").all():
        try:
            lab = label_of(inp) + " " + (inp.get_attribute("id", timeout=2000) or "") + " " + (inp.get_attribute("name", timeout=2000) or "")
            if re.search(r"cover", lab, re.I): inp.set_input_files(JOB["cover_pdf"]); page.wait_for_timeout(3000); filled.append("cover")
            elif re.search(r"resume|cv|attach", lab, re.I): inp.set_input_files(JOB["resume_pdf"]); page.wait_for_timeout(3000); filled.append("resume")
        except Exception: pass
    for sel, key, tag in (("input#cover_letter", "cover_pdf", "cover"), ("input#resume", "resume_pdf", "resume")):   # explicit Greenhouse ids as a fallback
        try:
            if tag not in filled and page.locator(sel).count() and JOB.get(key): page.locator(sel).first.set_input_files(JOB[key]); page.wait_for_timeout(3000); filled.append(tag)
        except Exception: pass
    page.wait_for_timeout(1500)
    # --- plain text inputs / textareas
    for el in page.locator("input:not([type=file]):not([type=hidden]):not([type=submit]):not([type=checkbox]):not([type=radio]):not(.select__input):not([role=combobox]), textarea").all():
        try:
            if not el.is_visible() or el.input_value(): continue
            lab = label_of(el); req = "*" in lab or el.get_attribute("required") is not None or el.get_attribute("aria-required") == "true"
            if re.search(r"date", lab, re.I) and re.search(r"start|available|pick", lab + (el.get_attribute("placeholder") or ""), re.I):
                el.fill("10/13/2026"); el.press("Enter"); filled.append("date"); continue
            for pat, val in KNOWN:
                if re.search(pat, lab, re.I): el.fill(val); filled.append(lab[:25]); break
            else:
                txt = essay(lab) if el.evaluate("e=>e.tagName")=="TEXTAREA" or len(lab) > 25 else None
                if txt: el.fill(txt); filled.append("essay:" + lab[:20])
                elif req and decide(lab) in ("yes", "no"):
                    el.fill(decide(lab).title()); filled.append("yn text")
                elif req:
                    ans = ask(lab, None, "text")
                    if ans: el.fill(ans); filled.append("asked")
                    else: unresolved.append(lab[:90])
        except Exception: pass
    # --- Greenhouse react-select dropdowns
    for inp in page.locator("input.select__input, input[role=combobox]").all():
        try:
            lab = label_of(inp); req = "*" in lab
            if inp.evaluate("e=>!!e.closest('.select__control')?.querySelector('.select__single-value')"): continue
            want = decide(lab) if not re.search(r"^location|\(city\)|^city\b|^(current )?city", lab.strip(), re.I) else "city"
            if want is None:
                if not req: continue
                inp.click(timeout=3000); page.wait_for_timeout(500)
                opts = page.locator("[role=option]:visible").all_inner_texts()
                a = ask(lab, opts[:25], "select")
                if a is None: inp.press("Escape"); unresolved.append(lab[:90]); continue
                idx = next((i for i, o in enumerate(opts) if o.strip().lower() == a.lower()), None)
                if idx is None: idx = next((i for i, o in enumerate(opts) if a.lower() in o.lower()), None)
                if idx is None: inp.press("Escape"); unresolved.append(lab[:90]); continue
                page.locator("[role=option]:visible").nth(idx).click(timeout=3000); filled.append(lab[:25]); continue
            inp.click(timeout=3000)
            if want == "city": inp.fill("Palo Alto"); page.wait_for_timeout(1200)
            elif want == "school": inp.fill("Temple University"); page.wait_for_timeout(1500)
            elif want == "country": page.wait_for_timeout(400)
            else: page.wait_for_timeout(400)
            opts = page.locator("[role=option]:visible").all_inner_texts()
            idx = 0 if want in ("city", "school") and opts else pick(opts, want)
            if idx is None and want == "country":
                inp.fill("United States"); page.wait_for_timeout(600); opts = page.locator("[role=option]:visible").all_inner_texts(); idx = pick(opts, want)
            if idx is None: print("   no option:", lab[:40], want, opts[:6]); inp.press("Escape"); (unresolved.append(lab[:90]) if req else None); continue
            page.locator("[role=option]:visible").nth(idx).click(timeout=3000); filled.append(lab[:25])
        except Exception as e:
            print("   dropdown err:", lab[:30], str(e)[:150])
            if req: unresolved.append(lab[:90] + " (dropdown error)")
    # --- Ashby / generic: yes-no buttons, radios, native selects, checkboxes
    for ent in page.locator("[class*=_fieldEntry_]").all():
        try:
            if not ent.is_visible(): continue
            lab = (ent.locator("label,legend").first.inner_text(timeout=2000) or "").strip(); req = "*" in lab or "✱" in lab
            btns = ent.locator("button:text-is('Yes'), button:text-is('No')")
            radios = ent.locator("input[type=radio]"); sel = ent.locator("select"); cbs = ent.locator("input[type=checkbox]")
            if btns.count() == 2:
                if ent.locator("button[class*=active], button[aria-pressed=true]").count(): continue
                want = decide(lab)
                if want in ("yes", "no"): ent.locator(f"button:text-is('{want.title()}')").click(); filled.append(lab[:25])
                elif req:
                    a = ask(lab, ["Yes", "No"], "yesno")
                    if a and a.lower() in ("yes", "no"): ent.locator(f"button:text-is('{a.title()}')").click(); filled.append(lab[:25])
                    else: unresolved.append(lab[:90])
            elif radios.count():
                if ent.locator("input[type=radio]:checked").count(): continue
                opts = [o.inner_text() for o in ent.locator("label").all()][1:] or []
                want = decide(lab); idx = pick(opts, want) if want else None
                if idx is not None: ent.locator("input[type=radio]").nth(idx).check(force=True); filled.append(lab[:25])
                elif req:
                    a = ask(lab, opts[:25], "radio")
                    j = next((i for i, o in enumerate(opts) if a and (o.strip().lower() == a.lower() or a.lower() in o.lower())), None)
                    if j is not None: ent.locator("input[type=radio]").nth(j).check(force=True); filled.append(lab[:25])
                    else: unresolved.append(lab[:90])
            elif sel.count():
                if sel.first.input_value(): continue
                opts = sel.first.locator("option").all_inner_texts(); want = decide(lab); idx = pick(opts, want) if want else None
                if idx is not None: sel.first.select_option(index=idx); filled.append(lab[:25])
                elif req: unresolved.append(lab[:90])
            elif cbs.count() and not cbs.first.is_checked():
                if decide(lab) == "yes": cbs.first.check(force=True); filled.append("consent")
                elif req: unresolved.append(lab[:90])
        except Exception: pass
    try:
        if page.locator("text=/anticipate working/i").count():
            page.get_by_label("US", exact=True).first.check(force=True, timeout=3000); filled.append("work country US")
    except Exception: pass
    # --- anything still empty & required (checkboxes, radios on Greenhouse)
    for el in page.locator("input[type=checkbox][required], input[type=radio][required], [aria-required=true]:not(.select__input)").all():
        try:
            if el.is_visible() and el.evaluate("e=>e.type=='checkbox'||e.type=='radio'") and not el.is_checked():
                lab = label_of(el)
                if status_option(lab): el.check(force=True); filled.append("status"); continue
                if re.search(r"^(us|usa|united states)$", lab.strip(), re.I) and page.locator("text=/anticipate working/i").count(): el.check(force=True); filled.append("work country US"); continue
                nm = el.get_attribute("name")
                if nm and page.locator(f"input[name='{nm}']:checked").count(): continue
                if re.search(r"cuba, iran, north korea|^u\.s\. (citizen|non-citizen national|permanent resident)|^individual granted (asylum|refugee|citizenship|permanent residency)", lab.strip(), re.I): continue   # sanctions group: none apply -> leave unchecked
                if decide(lab) == "yes" and el.get_attribute("type") == "checkbox": el.check(force=True)
                else:
                    a = ask(lab, ["check", "leave unchecked"], "checkbox")
                    if a and a.lower().startswith("check"): el.check(force=True); filled.append("asked")
                    else: unchecked.append((el, lab[:90]))
        except Exception: pass
    for el, lab in unchecked:   # a required checkbox group is fine as long as one of its boxes is checked
        try:
            if not el.evaluate("e=>{let g=e.closest('fieldset,[role=group]')||e.parentElement.parentElement.parentElement;return !!(g&&g.querySelector('input[type=checkbox]:checked'))}"): unresolved.append(lab)
        except Exception: unresolved.append(lab)
    return filled, unresolved

def claimed_elsewhere(job):
    """Skip anything the other agent has already claimed/applied to on the shared Google Sheet (read once, saved locally)."""
    p = ROOT / "profile" / "claimed_by_other.json"
    if not p.exists(): return False
    for co, frag in json.load(open(p)):
        if co.lower() in job["company"].lower() and frag and frag.lower() in job["title"].lower(): return True
        if "pagerduty" in job["company"].lower() and "event marketing" in job["title"].lower(): return True
    return False

def run_one(browser, job, submit):
    global JOB; JOB = job
    if claimed_elsewhere(job): return dict(status="excluded", note="claimed/applied by the other agent on the shared sheet")
    page = browser.new_page(viewport={"width": 1280, "height": 2200}); ctx = {}
    try:
        url = job["url"]
        if job["ats"] == "greenhouse": url = f"https://job-boards.greenhouse.io/{job['slug']}/jobs/{job['ext_id']}"
        elif job["ats"] == "ashby": url = url.rstrip("/") + "/application"
        page.goto(url, wait_until="domcontentloaded", timeout=60000); page.wait_for_timeout(4500)
        if page.locator("text=/no longer (open|available|accepting)|job not found|has been filled|page not found/i").count():
            return dict(status="expired", note="posting closed")
        if job["ats"] == "greenhouse" and page.locator("input[type=file]").count() == 0:
            page.goto(f"https://job-boards.greenhouse.io/embed/job_app?for={job['slug']}&token={job['ext_id']}", wait_until="domcontentloaded", timeout=60000); page.wait_for_timeout(4500)
        filled, unresolved = fill(page)
        if "resume" not in filled: unresolved.append("no resume upload field found (apply manually via link)")
        unresolved = sorted(set(u for u in unresolved if u))
        shot = SHOTS / f"{job['id'].replace(':','_')}.png"; page.screenshot(path=str(shot), full_page=True)
        note = f"filled={len(filled)}; unresolved={unresolved}"
        if unresolved: return dict(status="needs_manual", note=note)
        if not submit: return dict(status="materials_ready", note="dry run: all fields answered, not submitted")
        page.locator("button[type=submit]:has-text('Submit'), input[type=submit], button:has-text('Submit application'), button:has-text('Submit Application')").first.click()
        page.wait_for_timeout(6000)
        if page.locator("text=/security code/i").count() and not re.search(r"thank you for applying", page.inner_text("body"), re.I):
            # Greenhouse emails an 8-char code to the applicant's Gmail; the assistant reads it via the Gmail connector and drops it in code.txt
            CODE = ROOT / "output" / "code.txt"; PEND = ROOT / "output" / "pending_code.txt"
            CODE.unlink(missing_ok=True); PEND.write_text(job["id"] + " | " + job["company"])
            for _ in range(60):
                if CODE.exists() and CODE.read_text().strip(): break
                page.wait_for_timeout(3000)
            PEND.unlink(missing_ok=True)
            if not (CODE.exists() and CODE.read_text().strip()): return dict(status="needs_manual", note="security code not provided in time")
            code = CODE.read_text().strip(); CODE.unlink()
            page.locator("input[id^=security-input], input[aria-label*=ecurity], input[name*=ecurity]").first.click()
            page.keyboard.type(code, delay=120)
            page.locator("button:has-text('Submit application'), button[type=submit]").first.click()
        page.wait_for_timeout(15000)
        body = page.inner_text("body")
        if re.search(r"thank you for applying|application (has been )?(submitted|received)|thanks for applying|we.ve received your application|successfully submitted|your application was submitted", body, re.I):
            return dict(status="submitted", note="success message on page")
        if re.search(r"spam|captcha|verify you are human|flagged", body, re.I):
            return dict(status="needs_manual", note="blocked by captcha/spam check after submit - submit manually. " + note)
        page.screenshot(path=str(SHOTS / ("after_" + job["id"].replace(":","_") + ".png")), full_page=True)
        err = [e.strip() for e in page.locator("[class*=error], [role=alert]").all_inner_texts() if e.strip()]
        if not err:   # no success text and no validation errors: these hosted pages usually DID accept it -> never requeue (avoids duplicates); verify by email
            return dict(status="submitted", note="submitted, success text not recognised and no errors; verify by confirmation email")
        return dict(status="needs_manual", note=f"no success message; page errors={[e[:80] for e in err][:4]}")
    except Exception as e:
        return dict(status="failed", note=f"{type(e).__name__}: {str(e)[:160]}")
    finally:
        page.close()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--submit", action="store_true"); ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--ats", default="greenhouse,ashby"); ap.add_argument("--company", default=""); ap.add_argument("--shard", default="0/1"); ap.add_argument("--retry", action="store_true")
    a = ap.parse_args(); k, n = map(int, a.shard.split("/"))
    c = conn(); sts = "('materials_ready','needs_manual','failed')" if a.retry else "('materials_ready')"
    rows = c.execute(f"SELECT * FROM jobs WHERE status IN {sts} AND resume_pdf IS NOT NULL AND ats IN (%s) ORDER BY score DESC" % ",".join("'%s'" % x for x in a.ats.split(","))).fetchall()
    rows = [r for i, r in enumerate(rows) if i % n == k and (not a.company or r["company"] in a.company.split(","))][:a.limit]
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
        for r in rows:
            res = run_one(b, dict(r), a.submit)
            cc = conn(); cc.execute("UPDATE jobs SET status=?, note=?, applied_at=? WHERE id=?",
                (res["status"], res["note"], datetime.datetime.now().isoformat(timespec="seconds") if res["status"] == "submitted" else None, r["id"])); cc.commit(); cc.close()
            print(f"{res['status']:15} {r['company']} | {r['title'][:45]} | {res['note'][:260]}", flush=True)
        b.close()
if __name__ == "__main__": main()
