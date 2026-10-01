# Coco Wang

Personal site — robotics ecosystems, AI agents, and North America go-to-market.

**Live:** https://kew854867-code.github.io/Coco-Wang/

## Layout

- `index.html` — the site, fully static (no build step needed to serve it)
- `img/v4/` — every image the page uses
- `src/` — the source artboards (`Main.dc.html`, `Mobile.dc.html`, `canvas.json`)
  and `build-site.py`, which regenerates `index.html` from `Main.dc.html`

## Rebuild

Edit `src/Main.dc.html`, then from the repo root:

```
python3 src/build-site.py
```

It writes a fresh `site/` folder; copy `site/index.html` and `site/img/` up to the
repo root and commit.
