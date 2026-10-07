# /// script
# dependencies = ["pillow", "numpy", "opencv-python-headless"]
# ///
"""Place a plate on its page by matching at reduced resolution, then widen it.

Notes
-----
Correlating a plate rendered at three times the page's width against the page
means reducing the template heavily, and thin strokes alias when reduced, which
destroys the correlation. Both images are therefore brought to a common small
width and blurred before matching, so what is compared is the mass of the words
and not the grain. The scale is searched only from 0.5 upward: below that the
normalised correlation always prefers a small template, and the peak it returns
is an artefact rather than a position.
"""
import json
import pathlib
import sys

import cv2
import numpy as np
from PIL import Image

BASE = pathlib.Path("/home/az/Documents/github/personal/shamela/ibn-qayyim-mafqud/"
                    "manuscrits/ms-or-oct-3968-tafsir-ibn-abd-al-wahhab/tahqiq")
SORTIE = pathlib.Path("/home/az/.claude/jobs/2bcaa573/tmp/flou")
SORTIE.mkdir(exist_ok=True)
LARGEUR, LP = 2600, 700


def flou(a, larg):
    a = cv2.resize(a, (larg, max(1, round(larg * a.shape[0] / a.shape[1]))),
                   interpolation=cv2.INTER_AREA)
    return cv2.GaussianBlur(a, (0, 0), 1.5)


def rehausse(a):
    lab = cv2.cvtColor(a, cv2.COLOR_RGB2LAB)
    lab[:, :, 0] = cv2.createCLAHE(2.0, (8, 8)).apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


def pas(prof, hmin=12, hmax=200):
    p = prof - prof.mean()
    n = len(p)
    sp = np.abs(np.fft.rfft(p * np.hanning(n))) ** 2
    k = np.arange(len(sp))
    per = np.where(k > 0, n / np.maximum(k, 1), 0.0)
    bon = (per >= hmin) & (per <= hmax)
    return int(round(per[bon][int(np.argmax(sp[bon]))])) if bon.any() else 40


carte = json.load(open("/home/az/.claude/jobs/2bcaa573/tmp/carte.json"))
for nom in sys.argv[1:]:
    pgc = np.array(Image.open(BASE / "pages-manuscrits" / carte[nom]).convert("RGB"))
    pg0 = cv2.cvtColor(pgc, cv2.COLOR_RGB2GRAY)
    pl0 = np.array(Image.open(BASE / "images-apport-manuscrits" / nom).convert("L"))
    pg = flou(pg0, LP)
    best = None
    for s in np.arange(0.50, 1.001, 0.01):
        t = flou(pl0, int(LP * s))
        if t.shape[0] >= pg.shape[0] or t.shape[1] >= pg.shape[1]:
            continue
        _, mx, _, loc = cv2.minMaxLoc(cv2.matchTemplate(pg, t, cv2.TM_CCOEFF_NORMED))
        if best is None or mx > best[0]:
            best = (mx, loc[0], loc[1], t.shape[1], t.shape[0])
    sc, x, y, w, h = best
    k = pg0.shape[1] / LP
    x, y, w, h = (int(v * k) for v in (x, y, w, h))
    H, W = pg0.shape
    _, pgb = cv2.threshold(cv2.GaussianBlur(pg0, (3, 3), 0), 0, 255,
                           cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    prof = (pgb == 0).sum(axis=1).astype(float)
    p = pas(prof, 12, max(14, H // 8))

    def creux(c, d_):
        a_, b_ = max(0, c - d_), min(H, c + d_ + 1)
        return a_ + int(np.argmin(prof[a_:b_])) if b_ > a_ + 1 else c

    y0 = creux(max(0, y - int(1.35 * p)), p // 3)
    y1 = creux(min(H, y + h + int(1.35 * p)), p // 3)
    col = (pgb == 0).sum(axis=0)
    enc = np.nonzero(col > np.percentile(col, 95) * 0.06)[0]
    gx0, gx1 = (int(enc.min()), int(enc.max())) if len(enc) else (0, W)
    x0 = max(0, min(x, gx0) - int(W * 0.012))
    x1 = min(W, max(x + w, gx1) + int(W * 0.012))
    cut = pgc[y0:y1, x0:x1]
    im = cv2.resize(cut, (LARGEUR, max(1, round(LARGEUR * cut.shape[0] / cut.shape[1]))),
                    interpolation=cv2.INTER_LANCZOS4)
    Image.fromarray(rehausse(im)).save(SORTIE / nom, "WEBP", quality=82, method=6)
    print("%-50s score %.3f  pas %3d  cadre %dx%d  (%d%% de la page)"
          % (nom[:50], sc, p, cut.shape[1], cut.shape[0], 100 * (y1 - y0) // H), flush=True)
