"""The architecture, drawn.

Two bands, because the most important architectural fact about this system is
WHEN each thing happens: everything expensive runs once, offline, and a question
at the booth touches only the bottom band.

DRAWING RULES, learned by getting them wrong:
  * Every connector is orthogonal -- out of a box edge, along a gutter, into the
    next box edge. Diagonals read as noise once there are more than three.
  * Columns are separated by wide gutters and connectors live IN the gutters, so
    a line never crosses a box.
  * Every label sits on an opaque chip, so it is legible wherever it lands.
  * No long dashed lines across the whole picture. Where the bottom band needs
    something from the top band, it says so in words inside the box.
  * Each lane is one left-to-right chain, which is also the sentence you say.

Inline SVG rather than an image, because the numbers in it are live and a picture
file would drift away from the system it describes.
"""

# Exasol brand. THE RULE: #00B2FF is a fill, never text -- 2.38:1 on white.
# Every coloured word below uses an -ink variant.
INK, MUTED, FAINT = "#081226", "#4A5464", "#66748A"
TEAL, AMBER = "#12796A", "#9A6206"          # the -ink variants, for text
TEAL_FILL, BLUE_FILL = "#1FA08B", "#00B2FF"  # fills only
LINE, WIRE = "#D5DCE6", "#8E9BAD"
SANS = "Figtree, system-ui, sans-serif"
HEAD = "Figtree, system-ui, sans-serif"
MONO = "JetBrains Mono, ui-monospace, monospace"


class Box:
    def __init__(self, x, y, w, h, title, lines, accent=TEAL, fill="#ffffff", note=""):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.title, self.lines, self.accent, self.fill, self.note = title, lines, accent, fill, note

    # anchors -- t is a 0..1 position along the edge
    def right(self, t=0.5):  return (self.x + self.w, self.y + self.h * t)
    def left(self, t=0.5):   return (self.x, self.y + self.h * t)
    def bottom(self, t=0.5): return (self.x + self.w * t, self.y + self.h)
    def top(self, t=0.5):    return (self.x + self.w * t, self.y)

    def svg(self):
        out = [f'<rect x="{self.x}" y="{self.y}" width="{self.w}" height="{self.h}" rx="12" '
               f'fill="{self.fill}" stroke="{LINE}" stroke-width="1.2"/>',
               f'<rect x="{self.x}" y="{self.y}" width="5" height="{self.h}" rx="2.5" fill="{self.accent}"/>',
               f'<text x="{self.x+16}" y="{self.y+25}" font-family="{HEAD}" font-size="14.5" '
               f'font-weight="700" fill="{INK}">{self.title}</text>']
        ty = self.y + 45
        for ln in self.lines:
            mono = ln.startswith("`")
            out.append(f'<text x="{self.x+16}" y="{ty}" font-family="{MONO if mono else SANS}" '
                       f'font-size="{11 if mono else 12}" fill="{MUTED}">{ln.strip("`")}</text>')
            ty += 16
        if self.note:
            out.append(f'<text x="{self.x+16}" y="{self.y+self.h-11}" font-family="{SANS}" '
                       f'font-size="11" font-style="italic" fill="{self.accent}">{self.note}</text>')
        return "".join(out)


def _chip(x, y, text, colour=MUTED):
    """A label on an opaque plate. Nothing behind it can make it unreadable."""
    w = len(text) * 6.0 + 14
    return (f'<rect x="{x-w/2:.1f}" y="{y-10}" width="{w:.1f}" height="20" rx="10" '
            f'fill="#ffffff" stroke="{LINE}" stroke-width="1"/>'
            f'<text x="{x}" y="{y+4}" text-anchor="middle" font-family="{MONO}" '
            f'font-size="10.5" fill="{colour}">{text}</text>')


def _wire(pts, label="", lp=None, colour=WIRE, dash=False):
    """An orthogonal polyline through explicit points, arrowhead at the end.

    `lp` is where the label goes, and the CALLER works it out, because only the
    caller knows which part of the path is in a gutter. Guessing here is what put
    twelve labels on top of boxes.
    """
    d = "M" + " L".join(f"{x},{y}" for x, y in pts)
    s = [f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="1.8" '
         f'stroke-linejoin="round" marker-end="url(#ah)"'
         + (' stroke-dasharray="6 5"' if dash else "") + "/>"]
    if label and lp:
        s.append(_chip(lp[0], lp[1], label, colour))
    return "".join(s)


def _hop(a, b, midx, label="", colour=WIRE, dash=False):
    """Box edge -> gutter -> box edge, always orthogonal.

    Straight run: the label goes at its midpoint, which is inside the gutter.
    Elbow: the label goes on the VERTICAL leg, which also lives in the gutter --
    the two horizontal stubs are only half a gutter long and far too short to
    hold a chip without it spilling onto a box.
    """
    (x1, y1), (x2, y2) = a, b
    if y1 == y2:
        return _wire([(x1, y1), (x2, y2)], label, ((x1 + x2) / 2, y1 - 14), colour, dash)
    pts = [(x1, y1), (midx, y1), (midx, y2), (x2, y2)]
    return _wire(pts, label, (midx, (y1 + y2) / 2), colour, dash)


def _drop(a, b, label=""):
    """Straight down from one box's bottom into the next box's top."""
    (x1, y1), (x2, y2) = a, b
    return _wire([(x1, y1), (x2, y2)], label, (x1, (y1 + y2) / 2))


def _lane(x, y, tag, sentence):
    return (f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="10.5" font-weight="700" '
            f'letter-spacing="1.6" fill="{FAINT}">{tag}</text>'
            f'<text x="{x+88}" y="{y}" font-family="{SANS}" font-size="12.5" '
            f'font-style="italic" fill="{MUTED}">{sentence}</text>')


def _bus(src, targets, busx, label=""):
    """One trunk out, one vertical bus, one branch per target.

    Three separate elbows leave stubs of ~28px, which cannot hold a label and
    read as clutter. A bus is one line, one label, and the branch points make
    the fan-out explicit.
    """
    ys = [t[1] for t in targets]
    out = [f'<path d="M{src[0]},{src[1]} L{busx},{src[1]}" fill="none" stroke="{WIRE}" '
           f'stroke-width="1.8"/>',
           f'<path d="M{busx},{min(ys + [src[1]])} L{busx},{max(ys + [src[1]])}" fill="none" '
           f'stroke="{WIRE}" stroke-width="1.8"/>']
    for tx, ty in targets:
        out.append(f'<path d="M{busx},{ty} L{tx},{ty}" fill="none" stroke="{WIRE}" '
                   f'stroke-width="1.8" marker-end="url(#ah)"/>')
        out.append(f'<circle cx="{busx}" cy="{ty}" r="3" fill="{WIRE}"/>')
    if label:
        out.append(_chip((src[0] + busx) / 2, src[1] - 14, label))
    return "".join(out)


def _merge(sources, target, busx, label=""):
    """The mirror image: several boxes into one."""
    ys = [s_[1] for s_ in sources]
    out = [f'<path d="M{busx},{min(ys + [target[1]])} L{busx},{max(ys + [target[1]])}" '
           f'fill="none" stroke="{WIRE}" stroke-width="1.8"/>']
    for sx, sy in sources:
        out.append(f'<path d="M{sx},{sy} L{busx},{sy}" fill="none" stroke="{WIRE}" stroke-width="1.8"/>')
        out.append(f'<circle cx="{busx}" cy="{sy}" r="3" fill="{WIRE}"/>')
    out.append(f'<path d="M{busx},{target[1]} L{target[0]},{target[1]}" fill="none" '
               f'stroke="{WIRE}" stroke-width="1.8" marker-end="url(#ah)"/>')
    if label:
        out.append(_chip((busx + target[0]) / 2, target[1] - 14, label))
    return "".join(out)


def _band(x, y, w, h, label, sub, fill):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{fill}" '
            f'stroke="{LINE}" stroke-dasharray="4 6"/>'
            f'<text x="{x+22}" y="{y+28}" font-family="{MONO}" font-size="12" '
            f'font-weight="700" letter-spacing="2.5" fill="{MUTED}">{label}</text>'
            f'<text x="{x+22}" y="{y+47}" font-family="{SANS}" font-size="12.5" fill="{FAINT}">{sub}</text>')


# three columns, wide gutters, used by both bands
# Columns and gutters are sized so the WIDEST label still fits in the gutter:
# a chip is len*6+14 wide, so a 110px gutter holds 16 characters.
C1X, C1W = 44, 286
C2X, C2W = 440, 312
C3X, C3W = 850, 334
G1 = (C1X + C1W + C2X) / 2          # 385, inside the 110px gutter
G2 = (C2X + C2W + C3X) / 2          # 795, likewise


def diagram(t, lake, cost):
    tr, cr, vr = f'{t["trials"]:,}', f'{t["criteria"]:,}', f'{t["vector_rows"]:,}'
    pp, lk = f'{lake["papers"]:,}', f'{lake["links"]:,}'
    p = ['<svg viewBox="0 0 1240 1210" width="100%" role="img" '
         'aria-label="Architecture. Top half, build time: three chains that run once before the demo - the registry becomes tables, the free text becomes vectors, and the literature is written to object storage. Bottom half, query time: three routes into one engine - an agent writing its own SQL over MCP, the app\u2019s fixed retrieval statement, and a counting question that joins the lakehouse." '
         'xmlns="http://www.w3.org/2000/svg">',
         f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" '
         f'markerHeight="6.5" orient="auto-start-reverse">'
         f'<path d="M0,0 L10,5 L0,10 z" fill="{WIRE}"/></marker></defs>']

    # ============================================================ BUILD TIME
    p.append(_band(16, 16, 1208, 500, "BUILD TIME",
                   "Runs once, offline, before the booth opens. None of this happens during a demo.",
                   "rgba(15,118,110,0.04)"))

    # Three INDEPENDENT chains. They are lettered, not numbered 1..8, because a
    # single run of numbers invites the reader to look for a step between the
    # lanes -- and there isn't one.
    p.append(_lane(C1X, 82, "LANE A", "the registry becomes tables"))
    src = Box(C1X, 94, C1W, 106, "A1 · ClinicalTrials.gov", [
        "API v2, oncology, 2015+",
        f"{tr} trials",
        "`snapshot committed to git`",
    ], TEAL, note="no venue network at demo time")
    shred = Box(C2X, 94, C2W, 106, "A2 · Shred &amp; derive", [
        f"`ingest/shred.py` → {cr} criteria",
        "INCLUSION / EXCLUSION recovered",
        "endpoint → 18 categories",
        "country → 7 regions",
    ], TEAL)
    exa = Box(C3X, 94, C3W, 106, "A3 · Exasol, native tables", [
        "`IMPORT FROM LOCAL CSV FILE`",
        f"TRIALS {tr} · ELIG_CHUNKS {cr}",
        "+ semantic layer views",
    ], TEAL)

    p.append(_lane(C1X, 240, "LANE B", "the text becomes arithmetic"))
    embed = Box(C2X, 252, C2W, 122, "B1 · Embed, offline", [
        "`ml/build_vectors.py` in Docker",
        "sklearn pinned to the SLC's version",
        "TF-IDF → SVD 96 dims → L2 normalise",
        "→ vectors, BM25 tokens, model.pkl",
    ], AMBER)
    store2 = Box(C3X, 252, C3W, 122, "B2 · Vectors + model file", [
        f"`CT.ELIG_VECTORS` {vr} rows",
        "96 rows per criterion, long and narrow",
        "the model file, uploaded into storage",
        "`curl -X PUT .../udf/model.pkl`",
    ], AMBER)

    p.append(_lane(C1X, 414, "LANE C", "the literature stays where it is"))
    pub = Box(C1X, 426, C1W, 76, "C1 · PubMed", [
        f"E-utilities, {pp} papers",
        "`snapshot committed to git`",
    ], AMBER)
    ice = Box(C2X, 426, C2W, 76, "C2 · Write Iceberg", [
        "`lake/load_iceberg.py` (pyiceberg)",
        f"{lk} trial–paper links",
    ], AMBER)
    lakeb = Box(C3X, 426, C3W, 76, "C3 · The lake", [
        "Iceberg on MinIO (S3) + REST catalog",
        "`never loaded into Exasol`",
    ], AMBER)

    for b in (src, shred, exa, embed, store2, pub, ice, lakeb):
        p.append(b.svg())

    p.append(_hop(src.right(), shred.left(), G1, "fetch"))
    p.append(_hop(shred.right(), exa.left(), G2, "CSV"))
    p.append(_drop(shred.bottom(), embed.top(), "criteria"))
    p.append(_hop(embed.right(), store2.left(), G2, "load"))
    p.append(_hop(pub.right(), ice.left(), G1, "records"))
    p.append(_hop(ice.right(), lakeb.left(), G2, "write"))

    # ============================================================ QUERY TIME
    # THREE routes, not two. The earlier version hung "Lake side" off the
    # retrieval chain, but sql/05_hybrid_search.sql.tmpl contains no reference to
    # CT_LAKE at all -- the lake is read by the agent, and by a SEPARATE
    # analytical statement. Drawing it inside the retrieval path was a lie.
    p.append(_band(16, 540, 1208, 640, "QUERY TIME",
                   "Three kinds of question, one engine \u2014 and only this band runs during a demo.",
                   "rgba(197,125,31,0.055)"))

    Q1X, Q1W = 44, 256
    Q2X, Q2W = 356, 284
    Q3X, Q3W = 696, 252
    Q4X, Q4W = 1020, 188

    # -- route 1: the agent writes its own SQL
    p.append(_lane(Q1X, 604, "ROUTE 1", "an agent asks \u2014 it writes the SQL itself  (tab 6)"))
    aask = Box(Q1X, 616, Q1W, 100, "A question, in English", [
        "typed into any MCP client",
        "\u201cwhich trials exclude prior",
        "anti-PD-1?\u201d",
    ], AMBER)
    mcp = Box(Q2X, 616, Q2W, 100, "Claude, over MCP", [
        "`exasol-mcp-server`, read-only",
        "lists and describes the schema,",
        "then runs its own query",
    ], AMBER)
    agsql = Box(Q3X, 616, Q3W, 100, "SQL the agent wrote", [
        "no statement written for it",
        "any schema, incl. `CT_LAKE`",
        "different every time",
    ], AMBER, note="nobody wrote this")

    # -- route 2: the app's fixed retrieval statement
    p.append(_lane(Q1X, 752, "ROUTE 2", "the app asks \u2014 one fixed statement, filled in  (tab 5)"))
    ask = Box(Q1X, 800, Q1W, 112, "The same question", [
        "split word by word against",
        "the layer's own vocabulary",
        "",
        "no language model here",
    ], TEAL)
    splitb = Box(Q2X, 776, Q2W, 152, "Semantic layer splits it", [
        "`AND t.PHASE='PHASE3'`",
        "`AND t.INDICATION='NSCLC'`",
        "`AND c.CRITERION_SECTION='EXCLUSION'`",
        "the rest becomes the query text",
        "same question \u2192 same SQL, always",
    ], TEAL)
    vec = Box(Q3X, 756, Q3W, 92, "Vector side", [
        "`CT.EMBED_QUERY()` Python UDF",
        f"GROUP BY {vr} rows",
        "`SUM(v.VAL * q.VAL)` is cosine",
    ], TEAL, note="model loaded from storage")
    lex = Box(Q3X, 862, Q3W, 78, "Lexical side", [
        "`CT.QUERY_TERMS()` Python UDF",
        "BM25 over CHUNK_TOKENS",
    ], TEAL)
    fuse = Box(Q4X, 780, Q4W, 100, "Fused &amp; filtered", [
        "RRF over both",
        "rankings; structured",
        "filter runs BEFORE",
        "any scoring",
    ], TEAL)

    # -- route 3: the analytical statement that actually reaches the lake
    p.append(_lane(Q1X, 964, "ROUTE 3", "an analytical question \u2014 the only one that reads the lake  (tab 3)"))
    anq = Box(Q1X, 976, Q1W, 92, "A counting question", [
        "\u201cwhich completed trials",
        "ever published?\u201d",
        "no retrieval involved",
    ], AMBER)
    lak = Box(Q2X, 976, Q2W, 92, "Native \u22c8 lakehouse", [
        "`CT.V_LANDSCAPE` (native)",
        "`LEFT JOIN CT_LAKE.TRIAL_PUBLICATIONS`",
        "one statement, two storage tiers",
    ], AMBER)
    lakeng = Box(Q3X, 976, Q3W, 92, "Read in place", [
        "Rust UDF running DataFusion",
        "Iceberg on object storage",
        f"+{cost['delta_ms']} ms over native",
    ], AMBER, note="nothing imported")

    ans = Box(Q4X, 976, Q4W, 92, "One answer", [
        "cites its NCT ID",
        "whichever route",
        "asked the question",
    ], INK)

    for b in (aask, mcp, agsql, ask, splitb, vec, lex, fuse, anq, lak, lakeng, ans):
        p.append(b.svg())

    gq1 = (Q1X + Q1W + Q2X) / 2
    gq2 = (Q2X + Q2W + Q3X) / 2
    gq3 = (Q3X + Q3W + Q4X) / 2

    p.append(_hop(aask.right(), mcp.left(), gq1))
    p.append(_hop(mcp.right(), agsql.left(), gq2, "tools"))
    p.append(_hop(agsql.right(), ans.left(0.2), gq3 - 22))

    p.append(_hop(ask.right(), splitb.left(), gq1))
    p.append(_bus(splitb.right(), [vec.left(), lex.left()], gq2))
    p.append(_merge([vec.right(), lex.right()], fuse.left(), gq3))
    p.append(_hop(fuse.right(0.5), ans.left(0.5), gq3 + 40) if False else
             _wire([fuse.bottom(), (fuse.x + fuse.w / 2, ans.y)], "ranked",
                   (fuse.x + fuse.w / 2, (fuse.y + fuse.h + ans.y) / 2)))

    p.append(_hop(anq.right(), lak.left(), gq1))
    p.append(_hop(lak.right(), lakeng.left(), gq2))
    p.append(_hop(lakeng.right(), ans.left(0.8), gq3))

    p.append('</svg>')
    return "".join(p)


COMPONENTS = [
    ("Source · trials", "ClinicalTrials.gov API v2",
     "Interventional, 2015+, oncology. Field-filtered at fetch. Snapshot committed to the repo so a demo never depends on the venue network."),
    ("Source · literature", "PubMed E-utilities",
     "Only records citing a trial's NCT number as a DataBank accession are kept — that accession is the join key."),
    ("Ingest · warehouse", "IMPORT FROM LOCAL CSV FILE",
     "Client-side bulk load over the driver's own loopback proxy. No staging area, no external table, no object store in the path."),
    ("Ingest · lake", "pyiceberg → Iceberg on MinIO",
     "Two tables written as Parquet behind an Iceberg REST catalog. Exasol is never told about the files."),
    ("Compute · offline", "Docker, sklearn pinned to the SLC",
     "TF-IDF → 96-dim SVD → L2 normalise. Pinned to sklearn 1.7.2 / numpy 1.26.4, or the pickle will not unpickle inside the UDF."),
    ("Storage · hot", "Exasol native tables",
     "Vectors stored long and narrow — one row per dimension — so cosine similarity is a join and a GROUP BY. No vector type, no index, no recall cliff."),
    ("Storage · artefacts", "a folder the engine reads",
     "The model file, the lakehouse engine and its language runtime, uploaded once with curl and read by the database at query time."),
    ("Storage · cold", "Iceberg on object storage",
     "Publication data: large, rarely changing, owned by another team. Read in place — stop the lake and the tables go empty."),
    ("Query · text", "Python UDFs + SQL",
     "EMBED_QUERY and QUERY_TERMS put the question into the documents' space; everything after that is arithmetic the engine parallelises."),
    ("Query · federation", "Lakehouse virtual schema",
     "exasol-labs/lakehouse-engine-rs — DataFusion inside a Rust UDF. The planner joins it to native tables in one statement."),
    ("Serving", "Streamlit",
     "This page. Every figure is queried live, so the narration cannot drift away from the data."),
]


# ============================================================ page 1 diagrams
# The challenge page was three blocks of prose. Both of its arguments are
# spatial -- a question splitting four ways, and four systems collapsing into
# one -- so they are drawn instead of described.

def _pill(x, y, w, text, fill, ink, mono=False):
    """A filled status pill. Deliberately NOT called _chip -- that name already
    belongs to the wire-label helper above, and shadowing it silently broke the
    main diagram."""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="26" rx="13" fill="{fill}"/>'
            f'<text x="{x + w/2}" y="{y+17}" text-anchor="middle" '
            f'font-family="{MONO if mono else SANS}" font-size="11.5" font-weight="700" '
            f'fill="{ink}">{text}</text>')


def four_shapes(na_pct, other_pct):
    """One question, four kinds of data, three of them blocked."""
    LANES = [
        ("“Phase 3, NSCLC, recruiting”", "coded in the registry",
         "a WHERE clause", "#E3F5F1", TEAL),
        ("“… that exclude prior anti-PD-1”", "free text, no column at all",
         "needs retrieval", "#FCEBEC", "#C4121F"),
        ("“What phase are these?”", f"coded, but {na_pct}% say NOT_APPLICABLE",
         "misleading", "#FEF3DC", AMBER),
        ("“Did any of them publish?”", "not in the warehouse at all",
         "another system", "#FCEBEC", "#C4121F"),
    ]
    p = ['<svg viewBox="0 0 1240 330" width="100%" role="img" '
         'aria-label="One clinical trial question splits into four kinds of data. One is coded '
         'and answerable with a WHERE clause; the other three are free text, misleadingly coded, '
         'or held in another system entirely." xmlns="http://www.w3.org/2000/svg">',
         f'<defs><marker id="ah2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
         f'markerHeight="6" orient="auto-start-reverse">'
         f'<path d="M0,0 L10,5 L0,10 z" fill="{WIRE}"/></marker></defs>']
    # the question
    p.append(f'<rect x="40" y="96" width="290" height="138" rx="14" fill="#081226"/>')
    p.append(f'<text x="64" y="132" font-family="{MONO}" font-size="10.5" font-weight="700" '
             f'letter-spacing="2" fill="rgba(255,255,255,.55)">ONE QUESTION</text>')
    for i, ln in enumerate(["Who else is competing", "for my Phase 3", "lung-cancer patients?"]):
        p.append(f'<text x="64" y="{166 + i*24}" font-family="{HEAD}" font-size="17" '
                 f'font-weight="700" fill="#ffffff">{ln}</text>')
    bus = 382
    ys = [70, 132, 194, 256]
    p.append(f'<path d="M330,165 L{bus},165" stroke="{WIRE}" stroke-width="1.8" fill="none"/>')
    p.append(f'<path d="M{bus},{ys[0]+29} L{bus},{ys[-1]+29}" stroke="{WIRE}" stroke-width="1.8"/>')
    for (title, sub, verdict, fill, ink), y in zip(LANES, ys):
        p.append(f'<path d="M{bus},{y+29} L434,{y+29}" stroke="{WIRE}" stroke-width="1.8" '
                 f'marker-end="url(#ah2)"/>')
        p.append(f'<circle cx="{bus}" cy="{y+29}" r="3" fill="{WIRE}"/>')
        p.append(f'<rect x="440" y="{y}" width="500" height="58" rx="12" fill="#ffffff" '
                 f'stroke="{LINE}"/>')
        p.append(f'<rect x="440" y="{y}" width="4" height="58" rx="2" fill="{ink}"/>')
        p.append(f'<text x="460" y="{y+24}" font-family="{HEAD}" font-size="14" font-weight="700" '
                 f'fill="{INK}">{title}</text>')
        p.append(f'<text x="460" y="{y+43}" font-family="{SANS}" font-size="12" '
                 f'fill="{MUTED}">{sub}</text>')
        p.append(_pill(968, y + 16, 210, verdict, fill, ink))
    p.append('</svg>')
    return "".join(p)


def before_after():
    """Four systems and three copies, against one engine."""
    p = ['<svg viewBox="0 0 1240 300" width="100%" role="img" '
         'aria-label="The usual architecture uses four systems and three copies of the corpus, '
         'joined in application code. This demo uses one engine holding all of it, with an agent '
         'reading the same schema." xmlns="http://www.w3.org/2000/svg">']
    # --- the usual way
    p.append(f'<text x="40" y="30" font-family="{MONO}" font-size="11" font-weight="700" '
             f'letter-spacing="2" fill="{MUTED}">THE USUAL ANSWER</text>')
    p.append(f'<rect x="40" y="46" width="530" height="228" rx="18" fill="rgba(196,18,31,.04)" '
             f'stroke="{LINE}" stroke-dasharray="4 5"/>')
    boxes = [("Warehouse", "the coded columns"), ("Vector database", "the free text"),
             ("Lake query engine", "the publications"), ("An application", "joins the three")]
    for i, (t, sub) in enumerate(boxes):
        x, y = 62 + (i % 2) * 254, 70 + (i // 2) * 92
        p.append(f'<rect x="{x}" y="{y}" width="234" height="70" rx="12" fill="#ffffff" '
                 f'stroke="{LINE}"/>')
        p.append(f'<text x="{x+16}" y="{y+27}" font-family="{HEAD}" font-size="14" '
                 f'font-weight="700" fill="{INK}">{t}</text>')
        p.append(f'<text x="{x+16}" y="{y+48}" font-family="{SANS}" font-size="12" '
                 f'fill="{MUTED}">{sub}</text>')
    p.append(_pill(62, 246, 232, "3 copies of the corpus", "#FCEBEC", "#C4121F"))
    p.append(_pill(316, 246, 232, "the join is unauditable", "#FCEBEC", "#C4121F"))
    # --- here
    p.append(f'<text x="670" y="30" font-family="{MONO}" font-size="11" font-weight="700" '
             f'letter-spacing="2" fill="{TEAL}">HERE</text>')
    p.append(f'<rect x="670" y="46" width="530" height="228" rx="18" fill="rgba(31,160,139,.05)" '
             f'stroke="{LINE}" stroke-dasharray="4 5"/>')
    p.append(f'<rect x="692" y="70" width="486" height="118" rx="14" fill="#ffffff" '
             f'stroke="{LINE}"/>')
    p.append(f'<rect x="692" y="70" width="5" height="118" rx="2.5" fill="{TEAL_FILL}"/>')
    p.append(f'<text x="714" y="98" font-family="{HEAD}" font-size="15" font-weight="700" '
             f'fill="{INK}">One engine</text>')
    for i, ln in enumerate(["columns, free text and vectors, together",
                            "publications read in place from object storage",
                            "one statement, one audit trail"]):
        p.append(f'<text x="714" y="{122 + i*21}" font-family="{SANS}" font-size="12" '
                 f'fill="{MUTED}">{ln}</text>')
    p.append(f'<rect x="692" y="200" width="486" height="54" rx="12" fill="#081226"/>')
    p.append(f'<text x="714" y="223" font-family="{HEAD}" font-size="14" font-weight="700" '
             f'fill="#ffffff">An agent, over MCP</text>')
    p.append(f'<text x="714" y="242" font-family="{SANS}" font-size="12" '
             f'fill="rgba(255,255,255,.72)">reads the same schema, writes its own SQL</text>')
    p.append(f'<path d="M934,200 L934,190" stroke="{WIRE}" stroke-width="1.8"/>')
    p.append('</svg>')
    return "".join(p)
