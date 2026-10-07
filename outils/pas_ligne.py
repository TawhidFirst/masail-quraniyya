# /// script
# dependencies = ["pillow", "numpy", "opencv-python-headless"]
# ///
"""Widen a plate by one line pitch on each side, the pitch being measured.

Notes
-----
On a densely written page the bands of ink merge, so counting bands returns
far too few lines and "one line more on each side" swallows the page. Here
the pitch is measured instead, by autocorrelation of the ink profile: the
profile of a page of writing is quasi periodic, and the first clear peak of
its autocorrelation beyond a few pixels is the distance from one line to the
next. The frame is then the matched box extended by one pitch each way, the
edge being placed at the emptiest row inside a narrow window so it still
falls between two lines rather than through one.
"""
import json
import sys
import pathlib

import cv2
import numpy as np
from PIL import Image

BASE = pathlib.Path("/home/az/Documents/github/personal/shamela/ibn-qayyim-mafqud/"
                    "manuscrits/ms-or-oct-3968-tafsir-ibn-abd-al-wahhab/tahqiq")
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

def rehausse(a):
    lab = cv2.cvtColor(a, cv2.COLOR_RGB2LAB)
    lab[:, :, 0] = cv2.createCLAHE(2.0, (8, 8)).apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

LARGEUR = 2600


def pas(prof: np.ndarray, hmin=18, hmax=160) -> int:
    """Return the distance from one line of writing to the next, in pixels.

    The autocorrelation decays monotonically near zero, so its plain maximum
    always falls on the shortest lag allowed. The profile is taken to the
    frequency domain instead, and the period kept is the one carrying the most
    power within the plausible range for a line of writing.
    """
    p = prof - prof.mean()
    n = len(p)
    sp = np.abs(np.fft.rfft(p * np.hanning(n))) ** 2
    k = np.arange(len(sp))
    with np.errstate(divide="ignore"):
        per = np.where(k > 0, n / np.maximum(k, 1), 0.0)
    bon = (per >= hmin) & (per <= hmax)
    if not bon.any():
        return 30
    return int(round(per[bon][int(np.argmax(sp[bon]))]))


carte = json.load(open("/home/az/.claude/jobs/2bcaa573/tmp/carte.json"))
sortie = pathlib.Path("/home/az/.claude/jobs/2bcaa573/tmp/pas")
sortie.mkdir(exist_ok=True)

for nom in sys.argv[1:]:
    page = carte[nom]
    pg = np.array(Image.open(BASE / "pages-manuscrits" / page).convert("RGB"))
    pl = np.array(Image.open(BASE / "images-apport-manuscrits" / nom).convert("RGB"))
    pgb = binarise(pg)
    H, W = pg.shape[:2]
    sc, x, y, w, h = best_match(pgb, binarise(pl), np.arange(0.20, 1.001, 0.01))
    prof = (pgb == 0).sum(axis=1).astype(float)
    pitch = pas(prof, 12, min(200, H // 6))

    def creux(centre, demi):
        a, b = max(0, centre - demi), min(H, centre + demi + 1)
        return a + int(np.argmin(prof[a:b])) if b > a + 1 else centre

    y0 = creux(max(0, y - int(1.35 * pitch)), pitch // 3)
    y1 = creux(min(H, y + h + int(1.35 * pitch)), pitch // 3)
    col = (pgb == 0).sum(axis=0)
    enc = np.nonzero(col > np.percentile(col, 95) * 0.06)[0]
    gx0, gx1 = (int(enc.min()), int(enc.max())) if len(enc) else (0, W)
    x0 = max(0, min(x, gx0) - int(W * 0.012))
    x1 = min(W, max(x + w, gx1) + int(W * 0.012))
    cut = pg[y0:y1, x0:x1]
    im = cv2.resize(cut, (LARGEUR, max(1, round(LARGEUR * cut.shape[0] / cut.shape[1]))),
                    interpolation=cv2.INTER_LANCZOS4)
    Image.fromarray(rehausse(im)).save(sortie / nom, "WEBP", quality=82, method=6)
    print("%-50s score %.3f  pas %3d  boite y %d-%d -> %d-%d  (%d%% de la page)"
          % (nom[:50], sc, pitch, y, y + h, y0, y1, 100 * (y1 - y0) // H), flush=True)
