# ما تُفيدُه المخطوطاتُ ممَّا يتغيَّر به المعنى

A critical report, in Arabic, on the places where the manuscripts of the
Qurʾanic *masāʾil* of Muḥammad b. ʿAbd al-Wahhāb differ from the two printed
editions, each place illustrated with the leaf it rests on.

Published at **https://tawhidfirst.github.io/masail-quraniyya/**

## What is in this branch

| | |
|---|---|
| `00-apports-ar.html` | the report, self-contained |
| `index.html` | sends the reader to it |
| `images-apport-manuscrits/*.webp` | 232 plates cut from the leaves |
| `pages-manuscrits/*.webp` | 176 manuscript pages at their own resolution |
| `openseadragon.min.js` | the viewer, 271 KB, vendored, no CDN |

The report needs no server and no network of its own. Every manuscript reading
links to the page that carries it, which opens in a viewer over the report, and
every printed reading links to its page on Shamela.

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

## What is not in this branch

The French version of the report, the working units of the edition, the working
journal, the plate originals before conversion (2.1 GB of PNG) and the source
PDFs. They are kept outside git: three of the PDFs are above GitHub's 100 MiB
per-file limit, and none of this is served.

Eleven `.webp` are present on disk but excluded by name: the plates of an entry
withdrawn during the collation, and one folio shown to be misnumbered.
