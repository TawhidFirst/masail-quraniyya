"""Mark the manuscript sigla so they cannot be read as letters of the text.

Notes
-----
A siglum in this edition is a single Arabic letter from the set
`ب ك ر ض ن ط د ز ش ع غ ث ح س ق`. Set in running Arabic prose it is
indistinguishable from a letter belonging to the text, which is why it is
wrapped here in `b.sig` and set in bold.

Two occurrences must not be marked:

1. In the Arabic version `ق` also abbreviates `ورقة` (folio), as in `ق ٣٦ظ`.
   The abbreviation is always followed by a number, the siglum never is.
2. `<em class="f">ن</em>` is the nun added above the line in ض, that is a
   letter of the manuscript seen as a drawing, not a witness.

In the Arabic version the waw of coordination is written against the siglum
(`ض ون` for "ض and ن"), which hides 140 sigla from a naive word boundary.
The waw is matched and left outside the wrapper.
"""
import re
import pathlib

AR = r'ؠ-ٰٟ-ۿ'
SIG = 'بكرضنطدزشعغثحسق'
MOTIF = re.compile(rf'(?<![{AR}])(و?)([{SIG}])(?![{AR}])')
REGLE = ('.sig{font-weight:700;font-style:normal;'
         'font-family:Amiri,"Scheherazade New",serif;direction:rtl;unicode-bidi:isolate}')
TOTAL = 1451
FICHIERS = ['00-apports-qui-changent-le-sens.html', '00-apports-ar.html']


def marque(corps: str, compteur: list[int]) -> str:
    """Wrap every siglum of a body's text nodes, skipping the two exceptions."""
    bouts = re.split(r'(<[^>]+>)', corps)
    for k, b in enumerate(bouts):
        if b.startswith('<') or not re.search(rf'[{SIG}]', b):
            continue
        bal = next((bouts[j] for j in range(k - 1, -1, -1) if bouts[j].startswith('<')), '')
        if bal == '<em class="f">' and re.fullmatch(rf'\s*[{AR}]\s*', b):
            continue
        def rep(m, texte=b):
            if m.group(2) == 'ق' and re.match(r'\s*[٠-٩]', texte[m.end():]):
                return m.group(0)
            compteur[0] += 1
            return f'{m.group(1)}<b class="sig">{m.group(2)}</b>'
        bouts[k] = MOTIF.sub(rep, b)
    return ''.join(bouts)


for f in FICHIERS:
    p = pathlib.Path(f)
    s = p.read_text(encoding='utf-8')
    tete, corps = s.split('</head>', 1)
    assert '.sig{' not in tete
    tete = re.sub(r'(\.ar\{[^}]*\}\n)', r'\1' + REGLE + '\n', tete, count=1)
    assert '.sig{' in tete

    c = [0]
    s2 = tete + '</head>' + marque(corps, c)
    assert c[0] == TOTAL, c[0]
    assert s2.count('<b class="sig">') == TOTAL == s2.count('</b>')
    assert len(re.findall(r'<h3 id=', s2)) == 78 and len(re.findall(r'<img', s2)) == 246
    assert len(re.findall(r'<figcaption', s2)) == 246 and s2.count('shamela.ws') == 165
    assert s2.count('<a ') == s.count('<a ') and s2.count('<tr') == s.count('<tr')
    assert s2.count('<em') == s.count('<em') and s2.count('class="k"') == 215
    assert '<b class="sig">' not in s2.split('</head>')[0]
    assert not re.search(r'[—–]', s2)
    # reversibility: stripping the wrapper and the rule gives the source back
    assert re.sub(r'<b class="sig">|</b>', '', s2).replace(REGLE + '\n', '') == s
    p.write_text(s2, encoding='utf-8')
    print(f'{f} : {c[0]} sigles balises')
