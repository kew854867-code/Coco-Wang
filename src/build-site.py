# -*- coding: utf-8 -*-
"""Main.dc.html -> a standalone index.html for GitHub Pages."""
import io, re, os, shutil, sys

SRC = "Main.dc.html"
OUT = "site"
DESC = ("Coco Wang — Robotics Partnerships & Community Lead at MIE Events. "
        "I build robotics ecosystems and AI agents that help robotics companies "
        "go to market 10x faster.")
URL = "https://kew854867-code.github.io/Coco-Wang/"

s = io.open(SRC, encoding="utf-8").read()

helmet = s[s.index("<helmet>") + len("<helmet>"): s.index("</helmet>")]
body = s[s.index("</helmet>") + len("</helmet>"): s.index("</x-dc>")]
body = body.replace("{{accent}}", "#2F5BFF")
helmet = helmet.replace("{{accent}}", "#2F5BFF")
# assets sit in img/v4/ next to index.html
body = re.sub(r'(<img[^>]*\bsrc=")(?!https?:|data:|img/)', r'\1img/v4/', body)

og = "img/v4/portrait.jpg"
page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Coco Wang — Robotics Ecosystems &amp; AI Agents</title>
<meta name="description" content="{DESC}">
<link rel="canonical" href="{URL}">
<meta property="og:type" content="website">
<meta property="og:url" content="{URL}">
<meta property="og:title" content="Coco Wang — Robotics Ecosystems &amp; AI Agents">
<meta property="og:description" content="{DESC}">
<meta property="og:image" content="{URL}{og}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🤖</text></svg>">
{helmet.strip()}
</head>
<body>
{body.strip()}
</body>
</html>
"""

if os.path.isdir(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT + "/img/v4", exist_ok=True)
io.open(OUT + "/index.html", "w", encoding="utf-8").write(page)
io.open(OUT + "/.nojekyll", "w").write("")

used = set(re.findall(r'src="img/v4/([^"]+)"', page))
for f in sorted(used):
    shutil.copy2("img/v4/" + f, OUT + "/img/v4/" + f)

total = sum(os.path.getsize(os.path.join(r, f))
            for r, _, fs in os.walk(OUT) for f in fs)
print("index.html %.0f KB | %d images | total %.1f MB"
      % (os.path.getsize(OUT + "/index.html") / 1024, len(used), total / 1e6))
