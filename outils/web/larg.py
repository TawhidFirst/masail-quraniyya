"""Measure how large a plate is actually drawn, in multiples of the source.

Notes
-----
A plate is cut from the page at the page's own resolution and then enlarged
once to a common width, so the only figure that matters to a reader is the
width at which the browser draws it divided by the width the cut had on the
leaf. Below one, the plate shows less than the manuscript holds.
"""
import functools, http.server, json, socketserver, threading
from playwright.sync_api import sync_playwright

ROOT = ("/home/az/Documents/github/personal/shamela/ibn-qayyim-mafqud/"
        "manuscrits/ms-or-oct-3968-tafsir-ibn-abd-al-wahhab/tahqiq")
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
port = srv.server_address[1]
natif = {x["planche"]: x["natif"][0]
         for x in json.load(open("/home/az/.claude/jobs/2bcaa573/tmp/passe/rapport.json"))
         if "natif" in x}

with sync_playwright() as p:
    b = p.chromium.launch()
    for larg in (1440, 390):
        pg = b.new_page(viewport={"width": larg, "height": 900})
        errs, bad = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("response", lambda r: r.status >= 400 and bad.append(f"{r.status} {r.url}"))
        pg.goto(f"http://127.0.0.1:{port}/00-apports-ar.html",
                wait_until="load")
        pg.wait_for_timeout(900)
        # les planches sont en chargement differe : tant qu elles ne sont pas
        # chargees elles n ont pas de dimension propre. On mesure donc la largeur
        # que la mise en page donne a la figure, qui est celle a laquelle la
        # planche sera tracee puisque sa largeur propre, 2600 px, lui est superieure.
        d = pg.eval_on_selector_all(
            "figure",
            "fs => fs.map(f => ({src: (f.querySelector('img')||{}).getAttribute "
            "? f.querySelector('img').getAttribute('src') : '', "
            "w: f.getBoundingClientRect().width}))")
        over = pg.evaluate("document.documentElement.scrollWidth > "
                           "document.documentElement.clientWidth")
        rap = []
        for x in d:
            n = x["src"].split("/")[-1].split("?")[0]
            if n in natif and x["w"]:
                rap.append(x["w"] / natif[n])
        rap.sort()
        print("fenetre %4d px : %d planches, grossissement median %.2f, "
              "min %.2f, max %.2f, sous 1x : %d  | debordement %s  erreurs %s  4xx %s"
              % (larg, len(rap), rap[len(rap)//2], rap[0], rap[-1],
                 sum(1 for v in rap if v < 1), over, errs, bad[:3]))
        pg.close()
    b.close()
srv.shutdown()
