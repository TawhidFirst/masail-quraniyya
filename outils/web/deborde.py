"""Check that no figure runs past the text, with a classic scrollbar forced.

Notes
-----
Headless Chromium draws overlay scrollbars, so `100vw` and the usable width
coincide and an overflow that every real browser shows stays invisible. The
browser is therefore started with classic scrollbars, and the check is made
on two counts: the page must not scroll sideways, and no figure may be wider
than the body's content box or stick out of it on either side.
"""
import functools, http.server, socketserver, threading
from playwright.sync_api import sync_playwright

ROOT = ("/home/az/Documents/github/personal/shamela/ibn-qayyim-mafqud/"
        "manuscrits/ms-or-oct-3968-tafsir-ibn-abd-al-wahhab/tahqiq")
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
port = srv.server_address[1]

MESURE = """() => {
  const b = document.body.getBoundingClientRect();
  const cs = getComputedStyle(document.body);
  const g0 = b.left + parseFloat(cs.paddingLeft);
  const g1 = b.right - parseFloat(cs.paddingRight);
  let pire = 0, n = 0, large = 0;
  document.querySelectorAll('figure').forEach(f => {
    const r = f.getBoundingClientRect();
    if (!r.width) return;
    n++; large = Math.max(large, r.width);
    pire = Math.max(pire, g0 - r.left, r.right - g1);
  });
  return {n, pire: Math.round(pire), large: Math.round(large),
          sb: window.innerWidth - document.documentElement.clientWidth,
          scroll: document.documentElement.scrollWidth
                  - document.documentElement.clientWidth};
}"""

with sync_playwright() as p:
    b = p.chromium.launch(args=["--disable-features=OverlayScrollbar",
                                "--hide-scrollbars=false"])
    for f in ("00-apports-qui-changent-le-sens.html", "00-apports-ar.html"):
        for larg in (1920, 1440, 1280, 1024, 860, 700, 390):
            pg = b.new_page(viewport={"width": larg, "height": 900})
            pg.goto(f"http://127.0.0.1:{port}/{f}", wait_until="load")
            pg.wait_for_timeout(500)
            m = pg.evaluate(MESURE)
            etat = "OK " if m["pire"] <= 1 and m["scroll"] <= 0 else "DEBORDE"
            print("%-8s %4d px : %s  figures %3d, la plus large %4d, "
                  "depassement %3d px, barre %2d, scroll lateral %d"
                  % (f[11:17], larg, etat, m["n"], m["large"], m["pire"],
                     m["sb"], m["scroll"]))
            pg.close()
    b.close()
srv.shutdown()
