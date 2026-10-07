# /// script
# dependencies = ["pillow", "numpy", "opencv-python-headless"]
# ///
"""Re-cut every plate of the report so no line of writing is severed.

Usage: passe_lignes.py <carte.json> <sortie/> [--poser]

Notes
-----
The frame of each plate is recovered by matching it on its own page, then
widened to whole lines: the ink of the page is projected on the y axis, a
line of writing being a band of ink between two clear bands, and the edges
are moved out to the emptiest row between two lines. One whole extra line is
taken on each side, on the principle that a stump of a line reads as a fault
whereas a line of context never hurts.

Two guards keep the pass from drifting. A plate already widened would gain
another line at each run, so the frame is capped at six whole lines, which
makes the pass idempotent on anything already opened up. And a frame is only
kept when the match is sound: on ن, a black and white photocopy, Otsu gives
scores around 0.2 and the result cannot be trusted.

Nothing is rendered above the page's own resolution more than once: the cut
is enlarged a single time to a common width, and only the L channel of
CIELAB is raised, so hue is untouched.
"""
import json
import pathlib
import sys

import cv2
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
LARGEUR = 2600
MAX_LIGNES = 6
SEUIL_SCORE = 0.50

BASE = pathlib.Path("/home/az/Documents/github/personal/shamela/ibn-qayyim-mafqud/"
                    "manuscrits/ms-or-oct-3968-tafsir-ibn-abd-al-wahhab/tahqiq")
PLANCHES = BASE / "images-apport-manuscrits"
PAGES = BASE / "pages-manuscrits"


def binarise(a: np.ndarray) -> np.ndarray:
    """Return a 0/255 single channel image, ink dark on light ground."""
    if a.ndim == 3:
        a = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    a = cv2.GaussianBlur(a, (3, 3), 0)
    _, b = cv2.threshold(a, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return b


def best_match(page_bin, tpl_bin, scales):
    """Best (score, x0, y0, w, h) of the template over a range of widths."""
    ph, pw = page_bin.shape
    th, tw = tpl_bin.shape
    out = (-2.0, 0, 0, 0, 0)
    for s in scales:
        w = int(pw * s)
        h = max(1, int(round(w * th / tw)))
        if w < 24 or h < 8 or w > pw or h > ph:
            continue
        t = cv2.resize(tpl_bin, (w, h), interpolation=cv2.INTER_AREA)
        _, mx, _, loc = cv2.minMaxLoc(cv2.matchTemplate(page_bin, t, cv2.TM_CCOEFF_NORMED))
        if mx > out[0]:
            out = (mx, loc[0], loc[1], w, h)
    return out


def _bandes_a(prof, seuil):
    out, dedans, d = [], False, 0
    for y, v in enumerate(prof):
        if v > seuil and not dedans:
            dedans, d = True, y
        elif v <= seuil and dedans:
            dedans = False
            if y - d >= 4:
                out.append((d, y))
    if dedans:
        out.append((d, len(prof)))
    return out


def _fondre(b):
    """Merge bands closer than a third of the median height.

    A high threshold cuts a line in two at the waist, the upper strokes on one
    side and the body on the other, which would let an edge fall inside the
    writing. Two bands closer than a third of a line are one line.
    """
    if len(b) < 2:
        return b
    med = sorted(f - d for d, f in b)[len(b) // 2]
    out = [list(b[0])]
    for d, f in b[1:]:
        if d - out[-1][1] < med / 3:
            out[-1][1] = f
        else:
            out.append([d, f])
    return [tuple(t) for t in out if t[1] - t[0] >= 8]


def bandes(page_bin):
    """Return the (top, bottom) of every line of writing on the page."""
    prof = (page_bin == 0).sum(axis=1) / page_bin.shape[1]
    haut = float(np.percentile(prof, 95))
    H = len(prof)
    best = []
    for part in np.arange(0.08, 0.61, 0.03):
        b = _fondre([t for t in _bandes_a(prof, haut * part) if 4 <= t[1] - t[0] <= H / 7])
        if len(b) > len(best):
            best = b
    return best


def rehausse(a):
    lab = cv2.cvtColor(a, cv2.COLOR_RGB2LAB)
    lab[:, :, 0] = cv2.createCLAHE(2.0, (8, 8)).apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


carte = json.load(open(sys.argv[1]))
sortie = pathlib.Path(sys.argv[2])
sortie.mkdir(parents=True, exist_ok=True)
poser = "--poser" in sys.argv

cache_page = {}
rapport = []
for nom in sorted(carte):
    page = carte[nom]
    ligne = {"planche": nom, "page": page}
    if not page or not (PAGES / page).exists() or not (PLANCHES / nom).exists():
        ligne["etat"] = "sans page"
        rapport.append(ligne)
        print(json.dumps(ligne, ensure_ascii=False), flush=True)
        continue
    if page not in cache_page:
        pg = np.array(Image.open(PAGES / page).convert("RGB"))
        cache_page.clear()
        cache_page[page] = (pg, binarise(pg), bandes(binarise(pg)))
    pg, pgb, b = cache_page[page]
    H, W = pg.shape[:2]
    pl = np.array(Image.open(PLANCHES / nom).convert("RGB"))
    sc, x, y, w, h = best_match(pgb, binarise(pl), np.arange(0.20, 1.001, 0.01))
    ligne |= {"score": round(float(sc), 3), "boite": [x, y, w, h], "lignes_page": len(b)}
    if sc < SEUIL_SCORE:
        ligne["etat"] = "appariement faible"
        rapport.append(ligne); print(json.dumps(ligne, ensure_ascii=False), flush=True); continue
    dedans = [i for i, (d, f) in enumerate(b) if f > y + 4 and d < y + h - 4]
    if not dedans:
        ligne["etat"] = "aucune ligne dans la boite"
        rapport.append(ligne); print(json.dumps(ligne, ensure_ascii=False), flush=True); continue
    i0, i1 = max(0, min(dedans) - 1), min(len(b) - 1, max(dedans) + 1)
    while i1 - i0 + 1 > MAX_LIGNES:          # cap, so the pass does not drift
        if i1 > max(dedans):
            i1 -= 1
        elif i0 < min(dedans):
            i0 += 1
        else:
            break
    haut_y, bas_y = b[i0][0], b[i1][1]
    prof_y = (pgb == 0).sum(axis=1).astype(float)

    def creux(a_, b_):
        return (a_ + b_) // 2 if b_ <= a_ + 1 else a_ + int(np.argmin(prof_y[a_:b_]))

    med = sorted(f - d for d, f in b)[len(b) // 2]
    av = [t for t in b if t[1] <= haut_y]
    ap = [t for t in b if t[0] >= bas_y]
    y0 = max(0, creux(max(t[1] for t in av), haut_y) if av else haut_y - int(med * 0.7))
    y1 = min(H, creux(bas_y, min(t[0] for t in ap)) if ap else bas_y + int(med * 0.7))
    col = (pgb == 0).sum(axis=0)
    enc = np.nonzero(col > np.percentile(col, 95) * 0.06)[0]
    gx0, gx1 = (int(enc.min()), int(enc.max())) if len(enc) else (0, W)
    x0 = max(0, min(x, gx0) - int(W * 0.012))
    x1 = min(W, max(x + w, gx1) + int(W * 0.012))

    cut = pg[y0:y1, x0:x1]
    if cut.size == 0:
        ligne["etat"] = "coupe vide"
        rapport.append(ligne); print(json.dumps(ligne, ensure_ascii=False), flush=True); continue
    gain = (y1 - y0) / max(1, h)
    im = cv2.resize(cut, (LARGEUR, max(1, round(LARGEUR * cut.shape[0] / cut.shape[1]))),
                    interpolation=cv2.INTER_LANCZOS4)
    im = Image.fromarray(rehausse(im))
    anc = Image.open(PLANCHES / nom)
    ligne |= {"etat": "pose" if poser else "essai",
              "lignes_cadre": i1 - i0 + 1, "gain_hauteur": round(float(gain), 2),
              "natif": [int(cut.shape[1]), int(cut.shape[0])],
              "avant": list(anc.size), "apres": list(im.size)}
    cible = (PLANCHES / nom) if poser else (sortie / nom)
    im.save(cible, "WEBP", quality=82, method=6)
    arr = np.asarray(Image.open(cible).convert("RGB"), dtype=np.int16)
    ligne["sat"] = round(float((arr.max(axis=2) - arr.min(axis=2)).mean()), 1)
    rapport.append(ligne)
    print(json.dumps(ligne, ensure_ascii=False), flush=True)

json.dump(rapport, open(sortie / "rapport.json", "w"), ensure_ascii=False, indent=1)
print("fini", len(rapport))
