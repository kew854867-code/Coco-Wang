"""Generate tailored resume + cover letter PDFs for priority jobs; verify they open and contain the facts."""
import json, pathlib, re, sys
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, ListFlowable, ListItem
from xml.sax.saxutils import escape as esc
import pdfplumber
from db import conn
from customize import hook

ROOT = pathlib.Path(__file__).parent
F = json.load(open(ROOT / "profile" / "facts.json"))
OUT = ROOT / "output"; OUT.mkdir(exist_ok=True)
base = ParagraphStyle("b", fontName="Helvetica", fontSize=9.0, leading=11.3)
H = ParagraphStyle("h", parent=base, fontName="Helvetica-Bold", fontSize=10.5, spaceBefore=5, spaceAfter=1, textColor=colors.HexColor("#1F3A5F"))
def slug(s): return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:40]

def resume_pdf(path, company, title):
    sentence, _ = hook(company, title)
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=.65*inch, rightMargin=.65*inch, topMargin=.4*inch, bottomMargin=.35*inch,
                            title=f"{F['name']} - Resume", author=F["name"])
    s = []
    s.append(Paragraph(f"<b>{F['name']}</b>", ParagraphStyle("n", parent=base, fontSize=19, leading=22, alignment=1)))
    s.append(Paragraph(f"{F['location']} | {F['phone']} | {F['email']} | <link href='{F['linkedin']}' color='blue'>LinkedIn</link> | <link href='{F['website']}' color='blue'>Personal Website</link>",
                       ParagraphStyle("c", parent=base, alignment=1)))
    def head(t): s.extend([Paragraph(t, H), HRFlowable(width="100%", thickness=.6, color=colors.HexColor("#1F3A5F"), spaceAfter=3)])
    head("SUMMARY"); s.append(Paragraph(esc(F["summary_base"]) + " " + esc(sentence), base))
    head("EXPERIENCE")
    for e in F["experience"]:
        t = Table([[Paragraph(f"<b>{esc(e['org'])}</b>", base), Paragraph(esc(e["dates"]), ParagraphStyle("r", parent=base, alignment=2))]], colWidths=[5.2*inch, 1.99*inch])
        t.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
        s.append(t); s.append(Paragraph(f"<i>{esc(e['title'])}</i>", base))
        s.append(ListFlowable([ListItem(Paragraph(esc(b), base), leftIndent=12) for b in e["bullets"]], bulletType="bullet", start="•", leftIndent=12, bulletFontSize=8))
    head("ROBOTICS COMMUNITY TOOLS I BUILT")
    s.append(ListFlowable([ListItem(Paragraph(f"<b>{esc(a)}</b> {esc(b)}", base), leftIndent=12) for a, b in F["tools_built"]], bulletType="bullet", start="•", leftIndent=12, bulletFontSize=8))
    head("SKILLS")
    for a, b in F["skills"]: s.append(Paragraph(f"<b>{esc(a)}:</b> {esc(b)}", base))
    head("EDUCATION")
    for a, d, c in F["education"]:
        t = Table([[Paragraph(f"<b>{esc(a)}</b> — {esc(c)}", base), Paragraph(esc(d), ParagraphStyle("r", parent=base, alignment=2))]], colWidths=[5.6*inch, 1.59*inch])
        t.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),1),("BOTTOMPADDING",(0,0),(-1,-1),1)])); s.append(t)
    doc.build(s)

def cover_pdf(path, company, title):
    _, line = hook(company, title)
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=1*inch, rightMargin=1*inch, topMargin=.9*inch, bottomMargin=.8*inch, title=f"{F['name']} - Cover Letter", author=F["name"])
    b = ParagraphStyle("cb", parent=base, fontSize=10.5, leading=15, spaceAfter=9)
    s = [Paragraph(f"<b>{F['name']}</b><br/>{F['location']} | {F['phone']} | {F['email']}", b), Spacer(1, 6),
         Paragraph(f"Dear {esc(company)} Hiring Team,", b),
         Paragraph(f"I am applying for the <b>{esc(title)}</b> role at {esc(company)}. I am a Silicon Valley robotics and AI community builder who produces events that fill rooms and move deals, and I would like to bring that to your team.", b),
         Paragraph("Most recently I co-led the Humanity &amp; AGI Summit 2026 at the Stanford Faculty Club (sold out): 500+ attendees, 40+ speakers, and 40+ university and Silicon Valley community partners. I recruited speakers and secured sponsors and co-hosts including Tencent and AgiBot through executive outreach. Before that, as Co-Founder of Rwawa Inc., I hosted the CES Innovation &amp; Monetization Summit in Las Vegas with 240+ paying attendees, 30+ speakers and Faraday Future as title sponsor, and co-hosted 21 events across robotics, AI and emerging tech.", b),
         Paragraph("I also build my own tools: an Outreach Agent that scored prospects and drafted personalized emails, helping me open 715 LinkedIn conversations with about a one-third reply rate, and a Robotics Events Calendar indexing 8,000+ events from 200+ sources. At MIE Events I cleaned and segmented a 182K-record database for targeted outreach that drove 200+ attendees and closed 2 new exhibitors.", b),
         Paragraph(esc(line), b),
         Paragraph("Thank you for your time and consideration. I would welcome the chance to talk.", b),
         Paragraph("Sincerely,<br/>Ke Wang", b)]
    doc.build(s)

def verify(p):
    with pdfplumber.open(p) as pdf:
        text = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
        return len(pdf.pages), text

def main(tiers=("priority",), limit=None):
    c = conn()
    rows = c.execute(f"SELECT * FROM jobs WHERE tier IN ({','.join('?'*len(tiers))}) AND status IN ('pending','materials_ready') ORDER BY score DESC", tiers).fetchall()
    for r in rows[:limit]:
        d = OUT / f"{slug(r['company'])}__{slug(r['title'])}__{r['ext_id'][:8]}"; d.mkdir(exist_ok=True)
        rp, cp = d / "Ke_Wang_Resume.pdf", d / "Ke_Wang_Cover_Letter.pdf"
        resume_pdf(rp, r["company"], r["title"]); cover_pdf(cp, r["company"], r["title"])
        n, t = verify(rp); n2, t2 = verify(cp)
        ok = n == 1 and all(k in t for k in ["182K", "Stanford", "715 outreach", "KE WANG"]) and r["company"] in t2
        c.execute("UPDATE jobs SET resume_pdf=?, cover_pdf=?, status=?, note=? WHERE id=?", (str(rp), str(cp), "materials_ready" if ok else "failed", f"resume pages={n}" if ok else "PDF verification failed", r["id"]))
        print(("OK " if ok else "BAD"), r["company"], "|", r["title"], f"(resume {n}p)")
    c.commit()
if __name__ == "__main__": main(tuple(sys.argv[1].split(",")) if len(sys.argv) > 1 else ("priority",))
