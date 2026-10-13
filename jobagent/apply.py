"""Browser automation for Greenhouse (job-boards.greenhouse.io) and Ashby application forms.
Default = DRY RUN: fills confirmed fields, uploads PDFs, screenshots, lists blockers, does NOT submit.
Use --submit to actually submit; only happens if every required field is answered, no captcha, and
only success text on the page (not the click) marks the job 'submitted'."""
import argparse, datetime, json, pathlib, re, sys
from playwright.sync_api import sync_playwright
from db import conn

ROOT = pathlib.Path(__file__).parent
A = json.load(open(ROOT / "profile" / "facts.json"))["answers_confirmed"]
SHOTS = ROOT / "output" / "screens"; SHOTS.mkdir(parents=True, exist_ok=True)

# label regex -> confirmed answer. Anything not matched stays blank and blocks submission.
KNOWN = [
 (r"^first name|legal first", A["first_name"]), (r"^last name|legal last|surname", A["last_name"]),
 (r"^(full )?name\b(?!.*(company|referr))", A["first_name"] + " " + A["last_name"]),
 (r"e-?mail", A["email"]), (r"phone", A["phone"]),
 (r"linkedin", A["linkedin"]), (r"website|portfolio|personal (site|url)|github", A["website"]),
 (r"^(current )?location|city", A["location"]),
]
SENSITIVE = r"authori[sz]|sponsor|visa|citizen|legal(ly)?|veteran|disabilit|gender|race|ethnic|hispanic|pronoun|sexual|criminal|convict|relocat|salary|compensation|notice|signature|background check|agree|consent|referr|how did you hear|start date|clearance|export"

def find_label(page, el):
    return page.evaluate("""e=>{ const id=e.id; let l=id?document.querySelector(`label[for="${CSS.escape(id)}"]`):null;
        if(!l) l=e.closest('label'); if(!l){const f=e.closest('[class*=field],[class*=Field],.application-field,fieldset,div'); l=f&&f.querySelector('label,legend');}
        return ((l&&l.innerText)||e.getAttribute('aria-label')||e.placeholder||e.name||'').trim(); }""", el.element_handle())

def run_one(browser, job, submit):
    result = dict(status="needs_manual", note="")
    page = browser.new_page(viewport={"width": 1280, "height": 2000})
    try:
        url = job["url"]
        if job["ats"] == "greenhouse":
            url = f"https://job-boards.greenhouse.io/{job['slug']}/jobs/{job['ext_id']}"
        elif job["ats"] == "ashby":
            url = url.rstrip("/") + "/application"
        page.goto(url, wait_until="networkidle", timeout=60000)
        if page.locator("text=/no longer (open|available|accepting)|job not found|position has been filled/i").count():
            return dict(status="expired", note="posting closed")
        if job["ats"] == "greenhouse" and page.locator("#application-form, form").count() == 0:
            page.locator("text=/apply/i").first.click(timeout=5000)
        unresolved, filled = [], []
        # file uploads
        for inp in page.locator("input[type=file]").all():
            lab = (find_label(page, inp) or "") + " " + (inp.get_attribute("id") or "") + " " + (inp.get_attribute("name") or "")
            try:
                if re.search(r"cover", lab, re.I): inp.set_input_files(job["cover_pdf"]); filled.append("cover letter PDF")
                elif re.search(r"resume|cv|attach", lab, re.I): inp.set_input_files(job["resume_pdf"]); filled.append("resume PDF")
            except Exception as e: unresolved.append(f"upload failed: {lab.strip()[:40]} ({e})")
        # text fields
        for el in page.locator("input:not([type=file]):not([type=hidden]):not([type=submit]):not([type=checkbox]):not([type=radio]), textarea").all():
            try:
                if not el.is_visible(): continue
                label = find_label(page, el); req = bool(el.get_attribute("required") or el.get_attribute("aria-required") == "true" or "*" in label)
                if el.input_value(): continue
                if el.get_attribute("role") == "combobox" or el.get_attribute("aria-haspopup"):
                    if req: unresolved.append(label[:80])
                    continue
                if re.search(SENSITIVE, label, re.I):
                    if req: unresolved.append(label[:80])
                    continue
                for pat, val in KNOWN:
                    if re.search(pat, label, re.I):
                        el.fill(val); filled.append(label[:30]); break
                else:
                    if req: unresolved.append(label[:80])
            except Exception: pass
        # selects / checkboxes / radios that are required
        for el in page.locator("select, input[type=checkbox], input[type=radio]").all():
            try:
                if not el.is_visible(): continue
                label = find_label(page, el)
                if (el.get_attribute("required") or el.get_attribute("aria-required") == "true") and not (el.input_value() if el.evaluate("e=>e.tagName")=="SELECT" else el.is_checked()):
                    unresolved.append(label[:80])
            except Exception: pass
        captcha = page.locator("iframe[src*=recaptcha], iframe[src*=hcaptcha], .g-recaptcha, [data-sitekey]").count() > 0
        shot = SHOTS / f"{job['id'].replace(':','_')}.png"; page.screenshot(path=str(shot), full_page=True)
        unresolved = sorted(set(u for u in unresolved if u))
        result["note"] = f"filled={sorted(set(filled))}; unresolved={unresolved}; captcha={captcha}; screenshot={shot.name}"
        if not any('resume' in f for f in filled):
            unresolved.append('no application form/resume upload found on page (apply manually via link)')
        if unresolved or captcha or not submit:
            result["status"] = "needs_manual" if (unresolved or captcha) else "materials_ready"
            if not submit and not unresolved and not captcha: result["note"] += " (dry run: ready, not submitted)"
            return result
        page.locator("button[type=submit], input[type=submit], button:has-text('Submit')").first.click()
        page.wait_for_timeout(6000)
        body = page.inner_text("body")
        if re.search(r"thank you for applying|application (has been )?(submitted|received)|thanks for applying|we.ve received your application|successfully submitted", body, re.I):
            result.update(status="submitted", note="success message detected on page")
        else:
            result.update(status="needs_manual", note="clicked submit but no success message; verify manually. " + result["note"])
        return result
    except Exception as e:
        return dict(status="failed", note=f"{type(e).__name__}: {str(e)[:200]}")
    finally:
        page.close()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--submit", action="store_true"); ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--ats", default="greenhouse,ashby"); a = ap.parse_args()
    c = conn()
    rows = c.execute("SELECT * FROM jobs WHERE status IN ('materials_ready','needs_manual') AND resume_pdf IS NOT NULL AND ats IN (%s) ORDER BY score DESC" % ",".join("'%s'" % x for x in a.ats.split(",")))
    rows = rows.fetchall()[:a.limit]
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium" if pathlib.Path("/opt/pw-browsers/chromium").exists() else None, args=["--no-sandbox"])
        for r in rows:
            res = run_one(b, dict(r), a.submit)
            c.execute("UPDATE jobs SET status=?, note=?, applied_at=? WHERE id=?",
                      (res["status"], res["note"], datetime.datetime.now().isoformat(timespec="seconds") if res["status"] == "submitted" else None, r["id"]))
            c.commit(); print(f"{res['status']:15} {r['company']} | {r['title'][:45]} | {res['note'][:250]}")
        b.close()
if __name__ == "__main__": main()
