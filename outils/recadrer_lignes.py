# /// script
# dependencies = ["pillow", "numpy", "opencv-python-headless"]
# ///
"""Re-cut a plate so its top and bottom edges fall between lines, never inside one.

Usage: recadrer_lignes.py <planche.webp> <page.webp> <sortie.png> [marge_x]

Notes
-----
Aiming by eye has failed repeatedly on these pages. The frame is therefore
found in two steps. The former plate is matched on its page to recover where
it was cut, which fixes the horizontal span the caption assumes. Then the ink
of the page is projected on the y axis: a line of writing is a band of ink
between two clear bands, and the top and bottom edges are moved out to the
nearest clear bands, so no line is ever severed.

The page is already published at the resolution its source holds, and the cut
is enlarged once, so nothing is rendered above the native.
"""
import pathlib
import sys

import cv2
import numpy as np
from PIL import Image



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
        r = cv2.matchTemplate(page_bin, t, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(r)
        if mx > out[0]:
            out = (mx, loc[0], loc[1], w, h)
    return out


Image.MAX_IMAGE_PIXELS = None
LARGEUR = 2600


def _bandes_a(prof: np.ndarray, seuil: float) -> list[tuple[int, int]]:
    out, dedans = [], False
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


def bandes(page_bin: np.ndarray) -> list[tuple[int, int]]:
    """Return the (top, bottom) of every line of writing on the page.

    Ascenders and descenders keep ink in the gap between two lines, so a low
    threshold merges the whole block into one band and a high one shreds it.
    Several are tried and the one yielding the most bands of plausible height
    is kept, a band being plausible when it is taller than eight pixels and
    shorter than a seventh of the page.
    """
    prof = (page_bin == 0).sum(axis=1) / page_bin.shape[1]
    haut = float(np.percentile(prof, 95))
    H = len(prof)
    best = []
    for part in np.arange(0.08, 0.61, 0.03):
        b = _fondre([t for t in _bandes_a(prof, haut * part)
                     if 4 <= t[1] - t[0] <= H / 7])
        if len(b) > len(best):
            best = b
    return best


def _fondre(b: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge bands separated by less than a third of the median height.

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

planche, page, sortie = sys.argv[1], sys.argv[2], sys.argv[3]
marge = float(sys.argv[4]) if len(sys.argv) > 4 else 0.012

pl = np.array(Image.open(planche).convert("RGB"))
pg = np.array(Image.open(page).convert("RGB"))
H, W = pg.shape[:2]
sc, x, y, w, h = best_match(binarise(pg), binarise(pl), np.arange(0.20, 1.001, 0.01))
print(f"  appariement  score {sc:.3f}  boite x {x}-{x+w}  y {y}-{y+h}  sur {W}x{H}")

b = bandes(binarise(pg))
print(f"  {len(b)} lignes detectees sur la page")
dedans = [i for i, (d, f) in enumerate(b) if f > y + 4 and d < y + h - 4]
if not dedans:
    sys.exit("aucune ligne dans la boite, cadrage a revoir")
# On prend PLUS plutot que MOINS : une ligne entiere de plus de chaque cote.
# Un moignon de ligne se lit comme un defaut, une ligne de contexte ne nuit pas,
# et cela met le bord loin de l ecriture qui nous interesse.
i0 = max(0, min(dedans) - 1)
i1 = min(len(b) - 1, max(dedans) + 1)
haut, bas = b[i0][0], b[i1][1]
print(f"  lignes touchees : {len(dedans)}, elargies a {i1 - i0 + 1}, "
      f"de y {haut} a {bas}")

# un peu d air, et la largeur du bloc de texte plutot que celle de la planche
col = (binarise(pg) == 0).sum(axis=0)
enc = np.nonzero(col > np.percentile(col, 95) * 0.06)[0]
gx0, gx1 = int(enc.min()), int(enc.max())
x0 = max(0, min(x, gx0) - int(W * marge))
x1 = min(W, max(x + w, gx1) + int(W * marge))
# Les bords vont au MILIEU du blanc qui separe des lignes voisines. Une bande
# d encre exclut les hampes et les queues, donc une marge proportionnelle la
# rogne encore ; le milieu du blanc, lui, ne coupe jamais une ligne.
med = sorted(f - d for d, f in b)[len(b) // 2] if b else 20
av = [t for t in b if t[1] <= haut]
ap = [t for t in b if t[0] >= bas]
# Le bord se pose la ou il y a LE MOINS d encre entre deux lignes. Le milieu du
# blanc rogne nos queues, et le bord de la bande voisine laisse paraitre ses
# hampes ; le minimum du profil est le seul point qui ne prenne ni l un ni
# l autre.
prof_y = (binarise(pg) == 0).sum(axis=1).astype(float)


def creux(a: int, b: int) -> int:
    """Return the emptiest row between two lines."""
    if b <= a + 1:
        return (a + b) // 2
    return a + int(np.argmin(prof_y[a:b]))


y0 = max(0, creux(max(t[1] for t in av), haut) if av else haut - int(med * 0.7))
y1 = min(H, creux(bas, min(t[0] for t in ap)) if ap else bas + int(med * 0.7))

cut = pg[y0:y1, x0:x1]
im = Image.fromarray(cut)
im = im.resize((LARGEUR, max(1, round(LARGEUR * im.height / im.width))), Image.LANCZOS)
im.save(sortie)
print(f"  -> {sortie}  natif {cut.shape[1]}x{cut.shape[0]} -> {im.size}")
