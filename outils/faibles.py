# /// script
# dependencies = ["pillow", "numpy", "opencv-python-headless"]
# ///
"""Re-cut the plates whose match on the binarised page was too weak to trust.

Notes
-----
Two families fail the ordinary pass. On ن, a black and white photocopy, Otsu
turns grain into ink and the binary correlation collapses to about 0.2; the
match is therefore run on the grey level, blurred and locally normalised, which
ignores the grain while keeping the shape of the words. And a note written
aslant in a margin cannot be found by a translation-only search, so the leaf is
turned through a range of angles and the best response over all of them is
kept, the cut being taken from the leaf turned by that same angle.

The frame is widened by one measured line pitch on each side, as elsewhere,
and the result is never rendered above the page's own resolution more than
the single enlargement to the common width.
"""
import json
import pathlib
import sys

import cv2
import numpy as np
from PIL import Image

BASE = pathlib.Path("/home/az/Documents/github/personal/shamela/ibn-qayyim-mafqud/"
                    "manuscrits/ms-or-oct-3968-tafsir-ibn-abd-al-wahhab/tahqiq")
SORTIE = pathlib.Path("/home/az/.claude/jobs/2bcaa573/tmp/faibles")
SORTIE.mkdir(exist_ok=True)
LARGEUR = 2600


def gris(a):
    """Grey level, blurred and locally normalised, grain removed."""
    g = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY) if a.ndim == 3 else a
    g = cv2.GaussianBlur(g, (5, 5), 0).astype(np.float32)
    fond = cv2.GaussianBlur(g, (0, 0), 25)
    d = g - fond
    return cv2.normalize(d, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)


def tourne(a, ang):
    h, w = a.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    m[0, 2] += nw / 2 - w / 2
    m[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(a, m, (nw, nh), flags=cv2.INTER_LANCZOS4,
                          borderMode=cv2.BORDER_REPLICATE)


def apparie(pageg, tplg, echelles):
    ph, pw = pageg.shape
    th, tw = tplg.shape
    out = (-2.0, 0, 0, 0, 0)
    for s in echelles:
        w = int(pw * s)
        h = max(1, int(round(w * th / tw)))
        if w < 24 or h < 8 or w > pw or h > ph:
            continue
        t = cv2.resize(tplg, (w, h), interpolation=cv2.INTER_AREA)
        _, mx, _, loc = cv2.minMaxLoc(cv2.matchTemplate(pageg, t, cv2.TM_CCOEFF_NORMED))
        if mx > out[0]:
            out = (mx, loc[0], loc[1], w, h)
    return out


def pas(prof, hmin=18, hmax=160):
    """Period carrying the most power in the range of a line of writing."""
    p = prof - prof.mean()
    n = len(p)
    sp = np.abs(np.fft.rfft(p * np.hanning(n))) ** 2
    k = np.arange(len(sp))
    per = np.where(k > 0, n / np.maximum(k, 1), 0.0)
    bon = (per >= hmin) & (per <= hmax)
    return int(round(per[bon][int(np.argmax(sp[bon]))])) if bon.any() else 30


def rehausse(a):
    lab = cv2.cvtColor(a, cv2.COLOR_RGB2LAB)
    lab[:, :, 0] = cv2.createCLAHE(2.0, (8, 8)).apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


carte = json.load(open("/home/az/.claude/jobs/2bcaa573/tmp/carte.json"))
BIAIS = {"NH1", "NH2", "NH4", "NI5", "GV2", "ED1", "KD8"}   # notes en biais
rapport = []
for nom in sys.argv[1:]:
    page = carte[nom]
    pg = np.array(Image.open(BASE / "pages-manuscrits" / page).convert("RGB"))
    pl = np.array(Image.open(BASE / "images-apport-manuscrits" / nom).convert("RGB"))
    tplg = gris(pl)
    code = nom.split("-")[0]
    angles = np.arange(-40, 40.1, 2.5) if code in BIAIS else [0.0]
    best = None
    for ang in angles:
        pgt = tourne(pg, ang) if ang else pg
        r = apparie(gris(pgt), tplg, np.arange(0.20, 1.001, 0.02))
        if best is None or r[0] > best[0][0]:
            best = (r, float(ang), pgt)
    (sc, x, y, w, h), ang, pgt = best
    H, W = pgt.shape[:2]
    pgb = cv2.cvtColor(pgt, cv2.COLOR_RGB2GRAY)
    _, pgb = cv2.threshold(cv2.GaussianBlur(pgb, (3, 3), 0), 0, 255,
                           cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    prof = (pgb == 0).sum(axis=1).astype(float)
    p = pas(prof, 18, min(160, H // 8))

    def creux(c, demi):
        a_, b_ = max(0, c - demi), min(H, c + demi + 1)
        return a_ + int(np.argmin(prof[a_:b_])) if b_ > a_ + 1 else c

    y0 = creux(max(0, y - int(1.35 * p)), p // 3)
    y1 = creux(min(H, y + h + int(1.35 * p)), p // 3)
    x0, x1 = max(0, x - int(W * 0.02)), min(W, x + w + int(W * 0.02))
    cut = pgt[y0:y1, x0:x1]
    im = cv2.resize(cut, (LARGEUR, max(1, round(LARGEUR * cut.shape[0] / cut.shape[1]))),
                    interpolation=cv2.INTER_LANCZOS4)
    Image.fromarray(rehausse(im)).save(SORTIE / nom, "WEBP", quality=82, method=6)
    rapport.append({"planche": nom, "score": round(float(sc), 3), "angle": ang,
                    "pas": p, "natif": [int(cut.shape[1]), int(cut.shape[0])]})
    print("%-50s score %.3f  angle %5.1f  pas %3d  natif %dx%d"
          % (nom[:50], sc, ang, p, cut.shape[1], cut.shape[0]), flush=True)
json.dump(rapport, open(SORTIE / "rapport.json", "w"), ensure_ascii=False, indent=1)
