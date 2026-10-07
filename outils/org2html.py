#!/usr/bin/env python3
"""Render an Org transcription file as a readable bilingual HTML page.

Built for manuscript transcriptions that mix a European scholarly apparatus
with Arabic text. Arabic runs are detected automatically and rendered
right-to-left; everything else stays left-to-right.

Usage
-----
    python org2html.py FILE.org [-o OUT.html] [--open]
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import unicodedata
from pathlib import Path

ARABIC_RANGES: tuple[tuple[int, int], ...] = (
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
)

RTL_THRESHOLD = 0.25


def arabic_ratio(text: str) -> float:
    """Share of letters in `text` that belong to the Arabic script.

    Parameters
    ----------
    text : str
        Any string, possibly mixing scripts.

    Returns
    -------
    float
        Ratio in [0, 1]. Returns 0.0 when `text` holds no letters.

    Notes
    -----
    Only characters of Unicode general category L* are counted, so digits,
    punctuation and the editorial brackets used in transcriptions do not
    skew the result. A line such as ``[...] قال الشيخ [...]`` is therefore
    scored on its four Arabic letters alone.
    """
    letters = [c for c in text if unicodedata.category(c).startswith("L")]
    if not letters:
        return 0.0
    arabic = sum(
        1
        for c in letters
        if any(lo <= ord(c) <= hi for lo, hi in ARABIC_RANGES)
    )
    return arabic / len(letters)


def is_rtl(text: str) -> bool:
    """Whether `text` should be laid out right-to-left."""
    return arabic_ratio(text) >= RTL_THRESHOLD


def _code_span(m: re.Match[str]) -> str:
    """Wrap ``=verbatim=`` and ``~code~`` content, in the right script.

    Parameters
    ----------
    m : re.Match
        Match whose first group is the marked-up content.

    Returns
    -------
    str
        A ``<code>`` element, carrying ``class="ar" dir="rtl"`` when the
        content is Arabic.

    Notes
    -----
    Arabic quoted inside a Latin sentence is the normal case in these files:
    a word of the manuscript, a variant, a rubric. Left in the monospace face
    that suits code, it loses its ligatures and becomes hard to read, which
    defeats the point of quoting a reading at all. Such a span is therefore
    set in the same Naskh face as the edited text, with no frame, so that it
    reads as a quotation and not as an identifier.
    """
    body = m.group(1)
    if is_rtl(body):
        return f'<code class="ar" dir="rtl">{body}</code>'
    return f"<code>{body}</code>"


def inline(text: str) -> str:
    """Convert Org inline markup to HTML, escaping everything else.

    Handles ``=verbatim=``, ``~code~``, ``*bold*``, ``/italic/`` and bare
    URLs. Editorial marks are wrapped in spans so the stylesheet can grey
    them out: ``[...]`` for an undeciphered passage, ``[word ?]`` for an
    uncertain reading, ``[[text]]`` for an editorial restitution.

    Org links are honoured as well: ``[[file:plate.png]]`` becomes an inline
    image, ``[[file:unit.txt][01]]`` a link. They are converted before the
    editorial ``[[...]]`` mark, which would otherwise swallow them.
    """
    out = html.escape(text)
    out = re.sub(r"=([^=\n]+)=", _code_span, out)
    out = re.sub(r"~([^~\n]+)~", _code_span, out)
    out = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w/])/([^/\n]+)/(?![\w/])", r"<em>\1</em>", out)
    # Org links to an external URL, before the bare-URL autolink that would
    # otherwise swallow the URL and leave the label stranded.
    out = re.sub(
        r"\[\[(https?://[^\]]+?)\]\[([^\]]+?)\]\]",
        r'<a href="\1" target="_blank" rel="noopener">\2</a>',
        out,
    )
    out = re.sub(
        r"(?<![\"=])(https?://[^\s<]+)", r'<a href="\1" target="_blank">\1</a>', out
    )
    # Org links, before the editorial [[...]] mark that would swallow them
    out = re.sub(
        r"\[\[file:([^\]]+?\.(?:png|jpg|jpeg|webp|gif))\]\]",
        r'<img class="plate" src="\1" alt="">',
        out,
    )
    out = re.sub(r"\[\[file:([^\]]+?)\]\[([^\]]+?)\]\]", r'<a href="\1">\2</a>', out)
    out = re.sub(r"\[\[file:([^\]]+?)\]\]", r'<a href="\1">\1</a>', out)
    # editorial marks, longest pattern first
    out = re.sub(r"\[\[([^\]]+)\]\]", r'<span class="restit">[\1]</span>', out)
    out = out.replace("[...]", '<span class="lacuna">[…]</span>')
    out = re.sub(r"\[([^\[\]]*\?)\]", r'<span class="doubt">[\1]</span>', out)
    return out


def _flush_table(rows: list[str], parts: list[str]) -> None:
    """Emit a buffered Org table as an HTML table."""
    if not rows:
        return
    cells = [
        [c.strip() for c in r.strip().strip("|").split("|")]
        for r in rows
        if not re.match(r"^\s*\|[-+]+\|?\s*$", r)
    ]
    if not cells:
        rows.clear()
        return
    head, body = cells[0], cells[1:]
    parts.append("<table>")
    parts.append(
        "<thead><tr>"
        + "".join(f"<th{_dir(c)}>{inline(c)}</th>" for c in head)
        + "</tr></thead>"
    )
    parts.append("<tbody>")
    for row in body:
        parts.append(
            "<tr>"
            + "".join(f"<td{_dir(c)}>{inline(c)}</td>" for c in row)
            + "</tr>"
        )
    parts.append("</tbody></table>")
    rows.clear()


def _dir(text: str) -> str:
    """Return a ``dir`` attribute when `text` is Arabic, else an empty string."""
    return ' dir="rtl" class="ar"' if is_rtl(text) else ""


def org_to_html(src: Path) -> str:
    """Convert an Org transcription file to a standalone HTML document.

    Parameters
    ----------
    src : Path
        Org file. Recognised constructs: ``#+TITLE:``, headings (``*``),
        tables, ``#+begin_quote`` blocks, ``:PROPERTIES:`` drawers, plain
        lists and paragraphs.

    Returns
    -------
    str
        A complete HTML document, styled, with no external dependency
        beyond a Google Fonts stylesheet for the Arabic face.

    Notes
    -----
    Quote blocks are the transcription proper. Each is tested with
    `is_rtl` and, when Arabic, rendered right-to-left at a larger size with
    generous line height, since manuscript transcriptions are read slowly
    and compared against an image.
    """
    lines = src.read_text(encoding="utf-8").splitlines()
    title = src.stem
    head_lines: list[tuple[str, str]] = []
    parts: list[str] = []
    table_buf: list[str] = []
    quote_buf: list[str] | None = None
    para_buf: list[str] = []
    in_drawer = False

    def flush_para() -> None:
        if not para_buf:
            return
        text = " ".join(para_buf)
        parts.append(f"<p{_dir(text)}>{inline(text)}</p>")
        para_buf.clear()

    for raw in lines:
        line = raw.rstrip()

        if quote_buf is not None:
            if line.strip().lower() == "#+end_quote":
                body = "\n".join(quote_buf)
                cls = "quote ar" if is_rtl(body) else "quote"
                d = ' dir="rtl"' if is_rtl(body) else ""
                inner = "<br>\n".join(
                    inline(x) if x.strip() else "&nbsp;" for x in quote_buf
                )
                parts.append(f'<blockquote class="{cls}"{d}>{inner}</blockquote>')
                quote_buf = None
            else:
                quote_buf.append(line)
            continue

        if line.strip().lower() == "#+begin_quote":
            flush_para()
            _flush_table(table_buf, parts)
            quote_buf = []
            continue

        if line.strip() == ":PROPERTIES:":
            in_drawer = True
            flush_para()
            parts.append('<dl class="props">')
            continue
        if line.strip() == ":END:":
            in_drawer = False
            parts.append("</dl>")
            continue
        if in_drawer:
            m = re.match(r"^\s*:([^:]+):\s*(.*)$", line)
            if m:
                k, v = m.group(1), m.group(2)
                parts.append(
                    f"<dt>{inline(k)}</dt><dd{_dir(v)}>{inline(v)}</dd>"
                )
            continue

        if m := re.match(r"^#\+TITLE:\s*(.+)$", line, re.I):
            title = m.group(1).strip()
            continue
        if m := re.match(r"^#\+(SUBTITLE|SIGLES):\s*(.+)$", line, re.I):
            head_lines.append((m.group(1).lower(), m.group(2).strip()))
            continue
        if line.startswith("#+"):
            continue

        if line.startswith("|"):
            flush_para()
            table_buf.append(line)
            continue
        _flush_table(table_buf, parts)

        if m := re.match(r"^(\*+)\s+(.*)$", line):
            flush_para()
            level = min(len(m.group(1)), 5) + 1
            text = m.group(2)
            parts.append(f"<h{level}{_dir(text)}>{inline(text)}</h{level}>")
            continue

        if m := re.match(r"^\s*[-+]\s+(.*)$", line):
            flush_para()
            text = m.group(1)
            parts.append(f'<p class="li"{_dir(text)}>{inline(text)}</p>')
            continue

        if not line.strip():
            flush_para()
            continue

        para_buf.append(line.strip())

    flush_para()
    _flush_table(table_buf, parts)

    head = ""
    if head_lines:
        rows = "".join(
            f'<p class="{k}"{_dir(v)}>{inline(v)}</p>' for k, v in head_lines
        )
        head = f'<div class="unithead">{rows}</div>'

    return _PAGE.format(title=html.escape(title), body=head + "\n".join(parts))


_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
<style>
:root {{
  --ink: #1b1a17; --dim: #6b675f; --faint: #a8a298;
  --bg: #faf8f4; --panel: #fff; --rule: #e2ddd3; --mark: #8a6d3b;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --ink: #e8e4dc; --dim: #a09a90; --faint: #6e6860;
    --bg: #16150f; --panel: #1d1c16; --rule: #302e26; --mark: #c9a45f;
  }}
}}
:root[data-theme="dark"] {{
  --ink: #e8e4dc; --dim: #a09a90; --faint: #6e6860;
  --bg: #16150f; --panel: #1d1c16; --rule: #302e26; --mark: #c9a45f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 3rem 16px 6rem; background: var(--bg); color: var(--ink);
  font-family: "Source Serif 4", Georgia, serif; font-size: 17px; line-height: 1.65;
}}
main {{ max-width: 46rem; margin: 0 auto; }}
h1 {{ font-size: 1.9rem; line-height: 1.2; margin: 0 0 2rem; }}
h2 {{ font-size: 1.35rem; margin: 2.6rem 0 .8rem; padding-bottom: .35rem;
     border-bottom: 1px solid var(--rule); }}
h3 {{ font-size: 1.12rem; margin: 2rem 0 .6rem; }}
h4, h5, h6 {{ font-size: 1rem; margin: 1.5rem 0 .5rem; color: var(--dim); }}
p {{ margin: 0 0 .9rem; }}
p.li {{ padding-left: 1.1rem; text-indent: -1.1rem; margin-bottom: .35rem; }}
p.li[dir="rtl"] {{ padding: 0 1.1rem 0 0; text-indent: -1.1rem; }}
code.ar {{ font-family: Amiri, "Scheherazade New", serif;
        font-size: 1.22em; line-height: 1.2; background: none; border: none;
        padding: 0 .12em; vertical-align: -.06em; }}
code {{ font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
        font-size: .88em; background: var(--panel); border: 1px solid var(--rule);
        border-radius: 3px; padding: .06em .3em; }}
a {{ color: var(--mark); }}
.ar, [dir="rtl"] {{ font-family: "Amiri", "Scheherazade New", serif; }}
blockquote.quote {{
  margin: 1.2rem 0 1.6rem; padding: 1.1rem 1.3rem; background: var(--panel);
  border: 1px solid var(--rule); border-radius: 4px;
}}
blockquote.quote.ar {{ font-size: 1.42rem; line-height: 2.5; text-align: right; }}
blockquote.quote.ar code {{ font-size: .62em; }}
.lacuna {{ color: var(--faint); }}
.doubt {{ color: var(--mark); }}
.restit {{ color: var(--dim); font-style: italic; }}
img.plate {{ display: block; max-width: 100%; height: auto; margin: 1.1rem auto;
             border: 1px solid var(--rule); border-radius: 3px;
             background: var(--panel); }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 1.6rem;
         font-size: .94rem; }}
th, td {{ border: 1px solid var(--rule); padding: .4rem .6rem;
          text-align: left; vertical-align: top; }}
th {{ background: var(--panel); font-weight: 600; }}
td[dir="rtl"], th[dir="rtl"] {{ text-align: right; font-size: 1.12rem; }}
dl.props {{ margin: 0 0 1.2rem; padding: .7rem 1rem; background: var(--panel);
            border: 1px solid var(--rule); border-radius: 4px; font-size: .9rem; }}
dl.props dt {{ float: left; clear: left; width: 8rem; color: var(--dim); }}
dl.props dd {{ margin: 0 0 .2rem 8.5rem; }}
@media (max-width: 34rem) {{
  body {{ padding-top: 1.5rem; font-size: 16px; }}
  blockquote.quote.ar {{ font-size: 1.25rem; line-height: 2.2; }}
  dl.props dt {{ float: none; width: auto; }}
  dl.props dd {{ margin-left: 0; }}
}}
.unithead {{ margin:-.6rem 0 1.6rem; padding:.7rem .9rem; border:1px solid #d9d4c9; border-radius:4px; background:#fbfaf7 }}
.unithead p {{ margin:.2rem 0; font-size:.95rem; line-height:1.9 }}
.unithead .sigles {{ font-size:.88rem; color:#5d5a52 }}
</style>
</head>
<body>
<main>
<h1>{title}</h1>
{body}
</main>
</body>
</html>
"""


def main() -> None:
    """Command-line entry point."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", type=Path, help="Org transcription file")
    ap.add_argument("-o", "--out", type=Path, help="output HTML (default: alongside)")
    ap.add_argument("--open", action="store_true", help="open in the browser")
    args = ap.parse_args()

    out = args.out or args.src.with_suffix(".html")
    out.write_text(org_to_html(args.src), encoding="utf-8")
    print(f"{out}  ({out.stat().st_size} bytes)")
    if args.open:
        subprocess.Popen(
            ["xdg-open", str(out)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


if __name__ == "__main__":
    main()
