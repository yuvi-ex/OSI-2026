#!/usr/bin/env python3
"""Markdown -> a shareable PDF, styled like the demo.

    .work/lakeenv/bin/python bin/md2pdf.py <file.md> [out.pdf]

Markdown is rendered to HTML and printed by headless Chrome. Print rules are what
matter here, not screen rules: a table must not split across a page, a heading
must not strand at the foot of one, and a long SQL line must WRAP rather than be
clipped -- a citation you cannot read in full is not a citation.
"""
import os, subprocess, sys
import markdown

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
@page { size: A4; margin: 17mm 15mm 18mm 15mm; }
:root{ --ink:#112235; --muted:#5d6e84; --faint:#8294a8; --teal:#0f766e;
       --amber:#c57d1f; --line:#dfe4ea; --soft:#f6f8fa; }
*{ box-sizing:border-box; }
body{ font-family:"IBM Plex Sans","Helvetica Neue",Arial,sans-serif;
      font-size:9.6pt; line-height:1.55; color:var(--ink); margin:0; }
h1,h2,h3,h4{ font-family:"Space Grotesk","IBM Plex Sans",sans-serif;
      letter-spacing:-.02em; break-after:avoid-page; page-break-after:avoid; }
body > h1:first-of-type{ font-size:20pt; line-height:1.18; margin:0 0 6pt;
      padding-bottom:10pt; border-bottom:3px solid var(--teal); }
h1{ font-size:14.5pt; margin:22pt 0 8pt; padding:7pt 0 0;
    border-top:1px solid var(--line); color:var(--teal); }
h2{ font-size:11.5pt; margin:15pt 0 5pt; color:var(--teal); }
h3{ font-size:10pt; margin:11pt 0 4pt; color:var(--muted);
    text-transform:uppercase; letter-spacing:.07em; }
p{ margin:0 0 7pt; }
/* a paragraph that is only bold text acts as a heading -- keep it with what follows */
p:has(> strong:only-child){ break-after:avoid-page; page-break-after:avoid; margin-bottom:4pt; }
p > em:only-child{ color:var(--muted); }
em{ color:var(--muted); }
hr{ border:0; border-top:1px solid var(--line); margin:14pt 0; }
a{ color:var(--teal); text-decoration:none; }
code{ font-family:"JetBrains Mono","SF Mono",Menlo,monospace; font-size:8.4pt;
      background:rgba(15,118,110,.08); color:#0b5b54; padding:.5pt 3pt; border-radius:3px; }
/* SQL citations must wrap, never clip. overflow:hidden would silently cut them. */
pre{ background:var(--soft); border:1px solid var(--line); border-left:3px solid var(--teal);
     border-radius:5px; padding:8pt 10pt; margin:6pt 0 10pt;
     white-space:pre-wrap; word-break:break-word; overflow-wrap:anywhere;
     break-inside:avoid; page-break-inside:avoid; }
pre code{ background:none; color:var(--ink); font-size:7.9pt; line-height:1.45; padding:0;
     white-space:pre-wrap; }
blockquote{ margin:8pt 0; padding:7pt 11pt; background:#fff8ec;
     border-left:3px solid var(--amber); border-radius:0 5px 5px 0; }
blockquote p{ margin:0; }
table{ width:100%; border-collapse:collapse; margin:8pt 0 11pt; font-size:8.6pt;
       break-inside:avoid; page-break-inside:avoid; table-layout:fixed; }
th{ text-align:left; font-size:7.4pt; text-transform:uppercase; letter-spacing:.07em;
    color:var(--muted); border-bottom:1.5px solid var(--ink); padding:5pt 6pt; font-weight:700; }
td{ padding:5pt 6pt; border-bottom:1px solid var(--line); vertical-align:top;
    overflow-wrap:anywhere; }
tr:nth-child(even) td{ background:#fafbfc; }
ul,ol{ margin:0 0 8pt; padding-left:16pt; }
li{ margin-bottom:3pt; }
.foot{ margin-top:20pt; padding-top:8pt; border-top:1px solid var(--line);
       font-size:7.6pt; color:var(--faint); }
"""


def convert(src, out=None):
    src = os.path.abspath(src)
    out = os.path.abspath(out or os.path.splitext(src)[0] + ".pdf")
    body = markdown.markdown(open(src, encoding="utf8").read(),
                             extensions=["tables", "fenced_code", "sane_lists", "attr_list"])
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
<style>{CSS}</style></head><body>{body}
<div class="foot">Generated from ClinicalTrials.gov and PubMed data held in Exasol.
Every figure is the output of the statement printed beneath it.</div></body></html>"""
    html_path = "/tmp/_md2pdf.html"
    open(html_path, "w", encoding="utf8").write(page)
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=12000", f"--print-to-pdf={out}",
                    "file://" + html_path], capture_output=True, timeout=180)
    if not os.path.exists(out):
        raise SystemExit("Chrome produced no PDF")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    p = convert(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print("wrote %s (%.1f KB)" % (p, os.path.getsize(p) / 1024))
