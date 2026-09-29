"""Geometry checks for a diagram nobody can look at.

A malformed or overlapping SVG renders as a mess and AppTest will not notice,
so these are the only automated eyes on it: boxes must not overlap, wires must
not cross boxes, labels must not land on boxes, and text must fit its box.
"""
import os, shutil, sys, re, xml.etree.ElementTree as ET
# Drop stale bytecode first. A same-length edit (C1X -> C2X) in the same second
# leaves mtime AND size unchanged, so Python reuses the cached .pyc and this
# script silently validates the PREVIOUS version of the diagram.
shutil.rmtree(os.path.join("app", "__pycache__"), ignore_errors=True)
sys.path.insert(0, "app")
import architecture as A

NS = "{http://www.w3.org/2000/svg}"
DIAGRAMS = {
    "architecture": lambda: A.diagram(
        {"trials": 12404, "criteria": 268912, "vector_rows": 25815552, "countries": 114},
        {"papers": 3796, "links": 4627}, {"native_ms": 328, "lake_ms": 487, "delta_ms": 159}),
    "four_shapes": lambda: A.four_shapes(34.4, 35.7),
    "before_after": lambda: A.before_after(),
}
which = sys.argv[1] if len(sys.argv) > 1 else "architecture"
print("=== %s ===" % which)
svg = DIAGRAMS[which]()
root = ET.fromstring(svg)
fail = 0

boxes = [(float(r.get('x')), float(r.get('y')), float(r.get('width')), float(r.get('height')))
         for r in root.iter(NS + 'rect')
         if r.get('stroke-dasharray') is None and float(r.get('width', 0)) > 150
         and float(r.get('height', 0)) > 60]

def rects_hit(a, b):
    return a[0] < b[0]+b[2] and b[0] < a[0]+a[2] and a[1] < b[1]+b[3] and b[1] < a[1]+a[3]

ov = [(a, b) for i, a in enumerate(boxes) for b in boxes[i+1:] if rects_hit(a, b)]
print(f"content boxes            : {len(boxes)}")
print(f"overlapping boxes        : {len(ov)}")
for a, b in ov[:4]: print("   ", a, b); fail = 1
if ov: fail = 1

def seg_hits(p1, p2, bx):
    x, y, w, h = bx[0]+1, bx[1]+1, bx[2]-2, bx[3]-2
    (x1, y1), (x2, y2) = p1, p2
    if y1 == y2: return y < y1 < y+h and max(x1, x2) > x and min(x1, x2) < x+w
    if x1 == x2: return x < x1 < x+w and max(y1, y2) > y and min(y1, y2) < y+h
    return False

bad = []
for path in root.iter(NS + 'path'):
    d = path.get('d', '')
    if not d.startswith('M') or 'z' in d: continue
    pts = [tuple(map(float, q.split(','))) for q in re.findall(r'-?\d+\.?\d*,-?\d+\.?\d*', d)]
    for s_, e_ in zip(pts, pts[1:]):
        for bx in boxes:
            if seg_hits(s_, e_, bx): bad.append((s_, e_, bx))
print(f"wires crossing a box     : {len(bad)}")
for b in bad[:4]: print("   ", b)
if bad: fail = 1

chips = [(float(r.get('x')), float(r.get('y')), float(r.get('width')), float(r.get('height')))
         for r in root.iter(NS + 'rect') if float(r.get('height', 0)) == 20 and r.get('rx') == '10']
clash = [(c, bx) for c in chips for bx in boxes if rects_hit(c, bx)]
print(f"label chips on a box     : {len(clash)}")
for c in clash[:4]: print("   ", c)
if clash: fail = 1

# A chip must not sit ON its own wire. A 92px label in a 98px gutter hid the
# arrow end to end and the two boxes read as unconnected -- checking chips
# against BOXES only, as this did at first, never sees it.
covered = []
for path in root.iter(NS + 'path'):
    d = path.get('d', '')
    if not d.startswith('M') or 'z' in d: continue
    pts = [tuple(map(float, q.split(','))) for q in re.findall(r'-?\d+\.?\d*,-?\d+\.?\d*', d)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if y1 != y2: continue                      # vertical legs may carry a chip
        seg = (min(x1, x2), y1 - 1, abs(x2 - x1), 2)
        for c in chips:
            if rects_hit(c, seg):
                vis = abs(x2 - x1) - c[2]
                if vis < 18:                        # less than 18px of arrow left
                    covered.append((round(abs(x2-x1)), round(c[2]), round(vis)))
print(f"arrows hidden by a label : {len(covered)}  (gutter, chip, visible px)")
for c in covered[:4]: print("   ", c)
if covered: fail = 1

# A chip must not land on TEXT either. Checking chips against boxes and wires
# missed a label sitting squarely on a lane caption, because a caption is bare
# text in a band, not a box.
# Calibrated against the rendered fonts, not guessed: a 13.5px Figtree title
# fits ~29 characters in a 288px card (266px usable) -> 0.68 x font-size per
# character; JetBrains Mono at 9.6px fits ~43 -> 0.645. The previous 0.52/0.60
# were optimistic and would pass strings that actually overflow.
ADV_SANS, ADV_MONO = 0.68, 0.645
def text_bbox(t):
    fs = float(t.get('font-size', 12))
    mono = 'JetBrains' in (t.get('font-family') or '')
    w = len(t.text or '') * fs * (ADV_MONO if mono else ADV_SANS)
    if t.get('text-anchor') == 'middle':
        return (float(t.get('x')) - w/2, float(t.get('y')) - fs*0.8, w, fs*1.15)
    return (float(t.get('x')), float(t.get('y')) - fs*0.8, w, fs*1.15)

chip_texts = {id(x) for x in root.iter(NS + 'text') if x.get('text-anchor') == 'middle'}
on_text = []
for t in root.iter(NS + 'text'):
    if id(t) in chip_texts: continue          # a chip's own label
    bb = text_bbox(t)
    for c in chips:
        if rects_hit(c, bb):
            on_text.append(((t.text or '')[:38], round(c[0]), round(c[1])))
print(f"label chips on text      : {len(on_text)}")
for o in on_text[:4]: print("   ", o)
if on_text: fail = 1

# Two wires sharing a lane draw on top of each other and read as one line.
# The validator did not see this: route 1's long drop and route 2's merge bus
# both defaulted to the middle of the same gutter.
segs = []
for path in root.iter(NS + 'path'):
    d = path.get('d', '')
    if not d.startswith('M') or 'z' in d: continue
    pts = [tuple(map(float, q.split(','))) for q in re.findall(r'-?\d+\.?\d*,-?\d+\.?\d*', d)]
    segs += list(zip(pts, pts[1:]))
def overlap1d(a1, a2, b1, b2):
    return min(max(a1, a2), max(b1, b2)) - max(min(a1, a2), min(b1, b2))
collide = []
for i, (p1, p2) in enumerate(segs):
    for p3, p4 in segs[i+1:]:
        if p1[0] == p2[0] and p3[0] == p4[0] and abs(p1[0] - p3[0]) < 6:      # both vertical, same lane
            if overlap1d(p1[1], p2[1], p3[1], p4[1]) > 8:
                collide.append(("vertical", round(p1[0]), round(p1[1]), round(p3[1])))
        if p1[1] == p2[1] and p3[1] == p4[1] and abs(p1[1] - p3[1]) < 6:      # both horizontal, same row
            if overlap1d(p1[0], p2[0], p3[0], p4[0]) > 8:
                collide.append(("horizontal", round(p1[1]), round(p1[0]), round(p3[0])))
print(f"wires drawn over wires   : {len(collide)}")
for c in collide[:4]: print("   ", c)
if collide: fail = 1

# text must fit inside its own box (rough advance widths per font size)
overflow = []
for t in root.iter(NS + 'text'):
    if t.get('text-anchor') == 'middle': continue
    tx, ty = float(t.get('x')), float(t.get('y'))
    fs = float(t.get('font-size', 12))
    mono = 'JetBrains' in (t.get('font-family') or '')
    w = len(t.text or '') * fs * (ADV_MONO if mono else ADV_SANS)
    for bx in boxes:
        if bx[0] <= tx <= bx[0]+bx[2] and bx[1] <= ty <= bx[1]+bx[3]:
            if tx + w > bx[0] + bx[2] - 6:
                overflow.append((t.text[:40], round(tx+w-bx[0]-bx[2])))
            break
print(f"text overflowing its box : {len(overflow)}")
for o in overflow[:6]: print("   ", o)
if overflow: fail = 1

VW, VH = (float(v) for v in root.get('viewBox').split()[2:])
out = [(float(r.get('x', 0)) + float(r.get('width', 0)), float(r.get('y', 0)) + float(r.get('height', 0)))
       for r in root.iter(NS + 'rect')]
over = [o for o in out if o[0] > VW or o[1] > VH]
print(f"canvas overflow          : {over}")
if over: fail = 1
print("RESULT:", "FAIL" if fail else "clean")
sys.exit(fail)
