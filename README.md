# The manuscripts' contributions to the Qurʾanic *masāʾil* of Muḥammad b. ʿAbd al-Wahhāb

A critical report on the places where the manuscripts differ from the printed
editions, in two parallel versions, French and Arabic, each illustrated with the
leaf it rests on.

## The site

| | |
|---|---|
| `00-apports-qui-changent-le-sens.html` | French version |
| `00-apports-ar.html` | Arabic version |

Both are self-contained: a reader needs no server and no network. Every reading
links to the page of the manuscript that carries it, which opens in a viewer
over the report (OpenSeadragon 5.0.1, vendored, no CDN), and every printed
reading links to its page on Shamela.

- `images-apport-manuscrits/*.webp` — 246 plates, cut from the leaves
- `pages-manuscrits/*.webp` — 182 manuscript pages at their own resolution
- `openseadragon.min.js` — the viewer, 271 KB

## The witnesses

| siglum | shelfmark |
|---|---|
| ب | Berlin, Ms. or. oct. 3968 |
| ك | Riyadh, KSU 2351 |
| ر | Riyadh, KFNL 472/86 |
| ض | Riyadh, KFNL 516/86 |
| ز | Riyadh, KFNL 673/86 |
| ش | Riyadh, KFNL 1014/86 |
| ن | private library, `كتاب رقم ١` |
| ط | printed, Shamela 11099 |
| د | printed, Shamela 3055 |

## What is not here

The plate originals before conversion (1371 PNG files, 2.1 GB) and the source
PDFs are not committed: three of the PDFs are above GitHub's 100 MiB per-file
limit, and the site never serves either. The working journal is kept as its
`.org` source, `images-apport-manuscrits/00-index.org`; its generated HTML is
not committed because its illustrations are the PNG files.

## Rebuilding

The journal is regenerated with the repository's own converter:

    uv run --quiet python ../../../../outils/org2html.py 00-index.org
