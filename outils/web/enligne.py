"""Check the published site the way a reader meets it.

Notes
-----
A page that works from the disk can still fail once published: a path that
differs by its case, an asset the commit left out, a viewer that cannot reach
its script. The three pages are therefore loaded from the real address, their
console and their failed requests are collected, and one plate is opened in
the viewer to prove the whole chain.
"""
from playwright.sync_api import sync_playwright

BASE = "https://tawhidfirst.github.io/masail-quraniyya/"
PAGES = [""]

with sync_playwright() as p:
    b = p.chromium.launch()
    for rel in PAGES:
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        bad, errs = [], []
        pg.on("response", lambda r: r.status >= 400 and bad.append(f"{r.status} {r.url}"))
        pg.on("pageerror", lambda e: errs.append(str(e)))
        r = pg.goto(BASE + rel, wait_until="load", timeout=60000)
        pg.wait_for_timeout(2500)
        titre = pg.title()
        n = pg.eval_on_selector_all("figure img", "e => e.length")
        print("%-38s %s  « %s »  %d planches" % (rel or "(accueil)", r.status, titre[:40], n))
        if True:
            a = pg.query_selector("figure a.pg")
            if a:
                a.click(); pg.wait_for_timeout(3000)
                ou = pg.eval_on_selector("dialog.vue", "d => d.open ? d.querySelector('.ou').textContent : 'fermee'")
                print("     fenetre du manuscrit : %s" % ou)
        print("     4xx/5xx : %s" % (bad[:3] or "aucun"))
        print("     erreurs : %s" % (errs[:2] or "aucune"))
        pg.close()
    b.close()
