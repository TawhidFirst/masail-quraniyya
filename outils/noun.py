# /// script
# dependencies = ["pymupdf", "pillow", "numpy", "opencv-python-headless"]
# ///
"""Rebuild the pages of ن from their source, then re-cut the plates on them.

Notes
-----
The plates of ن were cut in the source PDF, whereas the published pages were
trimmed to the written block, which both loses the marginal notes and makes
the plates impossible to locate on them: a match that scores 0.9 on the source
collapses to 0.2 on the published page. Each published page is therefore first
placed on the source, by matching it against the halves of the plausible
openings, and then rewritten whole from the half it belongs to, margins
included. The plates are then re-cut on that page like every other, the frame
being widened by one measured line pitch on each side.

The page to view rule of this witness changes partway through the volume, so
both forms are tried, with a view either side, and the one that matches is
kept rather than the one that was calculated.
"""
import json
import pathlib

import cv2
import numpy as np
import pymupdf
from PIL import Image

PDF = ("/home/az/Téléchargements/"
       "استنباطات من القران الكريم لشيخ الاسلام محمد بن عبدالوهاب.pdf")
BASE = pathlib.Path("/home/az/Documents/github/personal/shamela/ibn-qayyim-mafqud/"
                    "manuscrits/ms-or-oct-3968-tafsir-ibn-abd-al-wahhab/tahqiq")
SORTIE = pathlib.Path("/home/az/.claude/jobs/2bcaa573/tmp/noun")
(SORTIE / "pages").mkdir(parents=True, exist_ok=True)
(SORTIE / "planches").mkdir(parents=True, exist_ok=True)
LARGEUR = 2600

doc = pymupdf.open(PDF)
_cache = {}


def ouverture(v):
    if v not in _cache:
        px = doc[v - 1].get_pixmap(dpi=310)
        a = np.frombuffer(px.samples, dtype=np.uint8).reshape(px.height, px.width, px.n)
        _cache.clear()
        _cache[v] = a[:, :, :3].copy()
    return _cache[v]


def moitie(v, cote):
    a = ouverture(v)
    W = a.shape[1]
    return a[:, W // 2:].copy() if cote == "D" else a[:, :W // 2].copy()


def apparie(page, tpl, lo=0.15, hi=1.0, pas_=0.01):
    g = cv2.cvtColor(page, cv2.COLOR_RGB2GRAY) if page.ndim == 3 else page
    t0 = cv2.cvtColor(tpl, cv2.COLOR_RGB2GRAY) if tpl.ndim == 3 else tpl
    out = (-2.0, 0, 0, 0, 0)
    for s in np.arange(lo, hi + 1e-9, pas_):
        w = int(g.shape[1] * s)
        h = max(1, int(round(w * t0.shape[0] / t0.shape[1])))
        if w < 40 or h < 10 or w >= g.shape[1] or h >= g.shape[0]:
            continue
        t = cv2.resize(t0, (w, h), interpolation=cv2.INTER_AREA)
        _, mx, _, loc = cv2.minMaxLoc(cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED))
        if mx > out[0]:
            out = (mx, loc[0], loc[1], w, h)
    return out


def pas_ligne(prof, hmin=18, hmax=200):
    p = prof - prof.mean()
    n = len(p)
    sp = np.abs(np.fft.rfft(p * np.hanning(n))) ** 2
    k = np.arange(len(sp))
    per = np.where(k > 0, n / np.maximum(k, 1), 0.0)
    bon = (per >= hmin) & (per <= hmax)
    return int(round(per[bon][int(np.argmax(sp[bon]))])) if bon.any() else 40


def rehausse(a):
    lab = cv2.cvtColor(a, cv2.COLOR_RGB2LAB)
    lab[:, :, 0] = cv2.createCLAHE(2.0, (8, 8)).apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


carte = json.load(open("/home/az/.claude/jobs/2bcaa573/tmp/carte.json"))
pages = sorted({v for v in carte.values() if v and v.startswith("N-")})
rapport = []

for nom_page in pages:
    pub = np.array(Image.open(BASE / "pages-manuscrits" / nom_page).convert("RGB"))
    tige = nom_page[2:-5]
    if tige.startswith("vue"):
        cands = [(int(tige[3:]), c) for c in "DG"]
    else:
        p = int(tige[1:])
        cote = "D" if p % 2 == 0 else "G"
        base = (p + 2) // 2 if p % 2 == 0 else (p + 1) // 2
        tard = (p + 4) // 2 if p % 2 == 0 else (p + 3) // 2
        cands = [(v, cote) for v in sorted({base, base - 1, base + 1, tard, tard + 1})
                 if 1 <= v <= doc.page_count]
    best = None
    for v, c in cands:
        src = moitie(v, c)
        sc = apparie(src, pub, 0.5, 1.0, 0.02)[0]
        if best is None or sc > best[0]:
            best = (sc, v, c)
    sc, v, c = best
    src = moitie(v, c)
    Image.fromarray(rehausse(src)).save(BASE / "pages-manuscrits" / nom_page,
                                        "WEBP", quality=82, method=6)
    ligne = {"page": nom_page, "vue": v, "cote": c, "score_page": round(float(sc), 3),
             "taille": [int(src.shape[1]), int(src.shape[0])], "planches": []}

    pgb = cv2.cvtColor(src, cv2.COLOR_RGB2GRAY)
    _, pgb = cv2.threshold(cv2.GaussianBlur(pgb, (3, 3), 0), 0, 255,
                           cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    prof = (pgb == 0).sum(axis=1).astype(float)
    pitch = pas_ligne(prof, 18, min(200, src.shape[0] // 8))
    H, W = src.shape[:2]

    def creux(ctr, demi):
        a_, b_ = max(0, ctr - demi), min(H, ctr + demi + 1)
        return a_ + int(np.argmin(prof[a_:b_])) if b_ > a_ + 1 else ctr

    for nom in sorted(k for k, vv in carte.items() if vv == nom_page):
        pl = np.array(Image.open(BASE / "images-apport-manuscrits" / nom).convert("RGB"))
        s2, x, y, w, h = apparie(src, pl)
        if s2 < 0.45:
            ligne["planches"].append({"planche": nom, "score": round(float(s2), 3),
                                      "etat": "faible"})
            continue
        y0 = creux(max(0, y - int(1.35 * pitch)), pitch // 3)
        y1 = creux(min(H, y + h + int(1.35 * pitch)), pitch // 3)
        col = (pgb == 0).sum(axis=0)
        enc = np.nonzero(col > np.percentile(col, 95) * 0.06)[0]
        gx0, gx1 = (int(enc.min()), int(enc.max())) if len(enc) else (0, W)
        x0 = max(0, min(x, gx0) - int(W * 0.012))
        x1 = min(W, max(x + w, gx1) + int(W * 0.012))
        cut = src[y0:y1, x0:x1]
        im = cv2.resize(cut, (LARGEUR, max(1, round(LARGEUR * cut.shape[0] / cut.shape[1]))),
                        interpolation=cv2.INTER_LANCZOS4)
        Image.fromarray(rehausse(im)).save(SORTIE / "planches" / nom, "WEBP",
                                           quality=82, method=6)
        ligne["planches"].append({"planche": nom, "score": round(float(s2), 3),
                                  "etat": "pose", "natif": [int(cut.shape[1]), int(cut.shape[0])]})
    rapport.append(ligne)
    print(json.dumps(ligne, ensure_ascii=False), flush=True)

json.dump(rapport, open(SORTIE / "rapport.json", "w"), ensure_ascii=False, indent=1)
print("fini")
