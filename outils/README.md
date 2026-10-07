# Tools of the collation

Each script is standalone and declares its dependencies inline (PEP 723), so
`uv run outils/<name>.py` installs what it needs and runs it. Paths inside them
are absolute for this machine: on a clone they must be pointed at the clone.

## Cutting the plates

| | |
|---|---|
| `recadrer_lignes.py` | re-cuts one plate so its edges fall between lines of writing, never inside one. Matches the former plate on its page, projects the ink on the y axis, widens by one whole line on each side and places the edges at the emptiest row. `recadrer_lignes.py <plate.webp> <page.webp> <out.png>` |
| `passe_lignes.py` | the same over every plate of the report, with two guards: the frame is capped at six lines, which makes the pass idempotent, and a match below 0.50 is never used. Writes a JSON report. |
| `pas_ligne.py` | for dense hands where the bands of ink merge and the line counter returns far too few lines. Measures the line pitch **by the spectrum** of the ink profile, never by autocorrelation, which decays near zero and always returns the smallest lag allowed. |
| `flou.py` | places a plate whose rendering is far above its page's resolution: both are brought to a common small width and blurred, because thin strokes alias when reduced and destroy the correlation. Searches scales from 0.5 up, since below that the normalised correlation always prefers a small template. |
| `faibles.py` | the hard cases: grey level instead of Otsu for the photocopy, and a rotation search for notes written aslant in a margin. |
| `noun.py` | rebuilds the pages of ن from the source PDF and re-cuts their plates. Its plates were cut in the PDF, while the published pages were trimmed to the written block, so a match that scores 0.9 on the source collapses to 0.2 on them. |

## Reading and checking

| | |
|---|---|
| `lire_pages.py` | reads a list of Shamela pages in one pass, straight from the local Lucene index, instead of one call per page. |
| `sigles.py` | wraps the manuscript sigla in `<b class="sig">` so an Arabic reader cannot mistake them for letters of the text. |
| `web/deborde.py` | checks that no figure runs past the text, at seven window widths, **with classic scrollbars forced**: headless Chromium draws overlay scrollbars and hides an overflow every real browser shows. |
| `web/larg.py` | measures how large each plate is actually drawn, in multiples of the source. Below one, the plate shows less than the manuscript holds. |
| `web/enligne.py` | loads the published site from its real address and opens a plate in the viewer, to prove the whole chain. |

## The journal

`org2html.py` builds `images-apport-manuscrits/00-index.html` from its `.org`
source. On this machine the journal is rebuilt with
`uv run --quiet python ../../../../outils/org2html.py 00-index.org`; on a clone
the converter is here, so the path becomes `../outils/org2html.py`.

## What these tools learned, and the report keeps

- A plate cut at the edge of the word proves nothing: frames take whole lines,
  one more on each side, and the width opens to the whole text block.
- A match that scores low is not a weak answer, it is a wrong place. Nothing is
  ever installed on a score alone: the old plate and the new one go side by
  side and the new one must contain the old.
- Two near-identical passages on one page defeat both the score and the eye.
  Read the words that differ.
- Never render above the source. Enlarge once, then raise the L channel of
  CIELAB only, so hue is untouched.
