"""The architecture, drawn.

Primitives ported from the clinical-trials demo so the two decks draw the same
way. Only diagram() below is specific to this pipeline.

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

INK, MUTED, FAINT = "#112235", "#5d6e84", "#8294a8"
TEAL, AMBER = "#0f766e", "#c57d1f"
LINE, WIRE = "#cfd8e3", "#93a3b6"
SANS = "IBM Plex Sans, system-ui, sans-serif"
HEAD = "Space Grotesk, IBM Plex Sans, sans-serif"
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


def _fan_down(src, targets, trunk_y, label=""):
    """
    One box out, a horizontal trunk, one drop per target.

    The build lanes are chains, but the feature step is genuinely a fan: the
    three families are computed in the same SQL pass over the same table. Drawing
    them as a chain would imply an order that does not exist.
    """
    xs = [t[0] for t in targets]
    out = [f'<path d="M{src[0]},{src[1]} L{src[0]},{trunk_y}" fill="none" '
           f'stroke="{WIRE}" stroke-width="1.8"/>',
           f'<path d="M{min(xs + [src[0]])},{trunk_y} L{max(xs + [src[0]])},{trunk_y}" '
           f'fill="none" stroke="{WIRE}" stroke-width="1.8"/>']
    for tx, ty in targets:
        out.append(f'<path d="M{tx},{trunk_y} L{tx},{ty}" fill="none" stroke="{WIRE}" '
                   f'stroke-width="1.8" marker-end="url(#ah)"/>')
        out.append(f'<circle cx="{tx}" cy="{trunk_y}" r="3" fill="{WIRE}"/>')
    if label:
        out.append(_chip(src[0], (src[1] + trunk_y) / 2, label))
    return "".join(out)


def _fan_in(sources, target, trunk_y, label=""):
    """The mirror: several boxes funnelling into one."""
    xs = [s_[0] for s_ in sources]
    out = [f'<path d="M{min(xs + [target[0]])},{trunk_y} L{max(xs + [target[0]])},{trunk_y}" '
           f'fill="none" stroke="{WIRE}" stroke-width="1.8"/>']
    for sx, sy in sources:
        out.append(f'<path d="M{sx},{sy} L{sx},{trunk_y}" fill="none" stroke="{WIRE}" '
                   f'stroke-width="1.8"/>')
        out.append(f'<circle cx="{sx}" cy="{trunk_y}" r="3" fill="{WIRE}"/>')
    out.append(f'<path d="M{target[0]},{trunk_y} L{target[0]},{target[1]}" fill="none" '
               f'stroke="{WIRE}" stroke-width="1.8" marker-end="url(#ah)"/>')
    if label:
        out.append(_chip(target[0], (trunk_y + target[1]) / 2, label))
    return "".join(out)


def diagram(history_rows=49, topic_msgs=None, last_hops=None):
    """
    Two bands, because the fact that matters most is WHEN each thing happens.
    BUILD TIME runs once before the event; QUERY TIME is the only band the
    audience ever watches, and it runs per transaction.

    Live figures are passed in so the picture cannot drift from the system.
    """
    ms = {k: f"{v:,.0f} ms" for k, v in (last_hops or {}).items()}
    g = lambda k, d: ms.get(k, d)
    topic = (f"{topic_msgs:,} events on the topic" if topic_msgs
             else "Avro + Schema Registry")

    p = ['<svg viewBox="0 0 1240 1610" width="100%" role="img" '
         'aria-label="Two bands. Build time runs once: the customer history is seeded and '
         'replayed into Exasol, the model is trained into BucketFS, and the Kafka connector '
         'is registered as UDF scripts. Query time runs per transaction: PostgreSQL to '
         'Debezium to Kafka to the Exasol import UDF, then a fan-out into velocity, '
         'deviation and geography features, fused into one scoring UDF and one decision." '
         'xmlns="http://www.w3.org/2000/svg">',
         f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" '
         f'markerHeight="6.5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{WIRE}"/>'
         f'</marker></defs>']

    # =================== BUILD TIME ===================
    # Ordered by dependency, top to bottom, so every arrow points down:
    #   the connector must exist before the history can be imported,
    #   and the history must exist before the model can be trained on it.
    p.append(_band(20, 16, 1200, 630, "BUILD TIME",
                   "Runs once, before the room fills. Each lane needs the one above it.",
                   "#f2f8f7"))

    p.append(_lane(C1X, 92, "LANE A", "the connector becomes a UDF"))
    a1 = Box(C1X, 104, C1W, 58, "A1 \u00b7 Download the JAR",
             ["`exasol-kafka-connector-extension 2.0.0`"], accent=AMBER)
    a2 = Box(C2X, 104, C2W, 58, "A2 \u00b7 Upload to BucketFS",
             ["`%jar /buckets/bfsdefault/\u2026`"], accent=AMBER)
    a3 = Box(C3X, 104, C3W, 58, "A3 \u00b7 KAFKA_CONSUMER",
             ["`CREATE JAVA SET SCRIPT \u2026 (...)`"])
    p += [a1.svg(), a2.svg(), a3.svg()]
    p.append(_hop(a1.right(), a2.left(), G1, "jar"))
    p.append(_hop(a2.right(), a3.left(), G2, "register"))

    p.append(_lane(C1X, 206, "LANE B", "the customer gets a past"))
    b1 = Box(C1X, 218, C1W, 104, "B1 \u00b7 Seed the customer",
             ["`seed_story_persona.py`", f"{history_rows} transactions over 30 days",
              "coffee, groceries, fuel \u2014 US only"],
             note="fixed seed: identical every rehearsal")
    b2 = Box(C2X, 218, C2W, 104, "B2 \u00b7 Debezium snapshot",
             ["reads the write-ahead log",
              "`banking_avro.public.transactions`", "one Avro message per row"],
             accent=AMBER)
    b3 = Box(C3X, 218, C3W, 104, "B3 \u00b7 Exasol, native tables",
             ["`IMPORT \u2026 FROM SCRIPT` \u2192 KAFKA_STAGE",
              "`MERGE` \u2192 RAW \u2192 CLEANSED",
              "baseline: $29.55 average purchase"],
             note="without this, every payment looks like fraud")
    p += [b1.svg(), b2.svg(), b3.svg()]
    p.append(_hop(b1.right(), b2.left(), G1, "snapshot"))
    p.append(_hop(b2.right(), b3.left(), G2, "avro"))
    # A3 -> B3: the import in B3 is literally the script registered in A3.
    p.append(_drop(a3.bottom(0.5), b3.top(0.5), "the import calls it"))

    p.append(_lane(C1X, 394, "LANE C", "the model becomes a function"))
    c1 = Box(C1X, 406, C1W, 104, "C1 \u00b7 Train, offline",
             ["`train_pipeline.py` in Docker",
              "logistic regression, 12 features",
              "sklearn pinned to the UDF sandbox"], accent=AMBER)
    c2 = Box(C2X, 406, C2W, 104, "C2 \u00b7 Model in BucketFS",
             ["`fraud_model.pkl` \u2014 coefficients + scaler",
              "Exasol's own file store",
              "mounted inside the UDF sandbox"], accent=AMBER)
    c3 = Box(C3X, 406, C3W, 104, "C3 \u00b7 Scoring UDF",
             ["`CREATE PYTHON3 SCALAR SCRIPT`",
              "`ANALYTICS.FRAUD_SCORE_UDF(\u2026)`",
              "loads the pickle once per VM"],
             note="from here, scoring is just SQL")
    p += [c1.svg(), c2.svg(), c3.svg()]
    p.append(_hop(c1.right(), c2.left(), G1, "model.pkl"))
    p.append(_hop(c2.right(), c3.left(), G2, "open()"))
    # B3 -> C1: the model is trained on the history lane B just loaded.
    p.append(_wire([b3.bottom(0.5), (b3.x + b3.w * 0.5, 358),
                    (c1.x + c1.w * 0.5, 358), c1.top(0.5)],
                   "labelled history", (640, 358)))

    p.append(_lane(C1X, 546, "LANE D", "the boundary is granted"))
    d1 = Box(C1X, 558, C1W, 76, "D1 \u00b7 Persona users",
             ["`CREATE USER FRAUD_ANALYST_US \u2026`",
              "one per business unit, plus a lead"])
    d2 = Box(C2X, 558, C2W, 76, "D2 \u00b7 Row-filtered views",
             ["joined to entitlements on `CURRENT_USER`",
              "evaluated by the engine, not by the caller"])
    d3 = Box(C3X, 558, C3W, 76, "D3 \u00b7 Grant, and nothing more",
             ["`GRANT SELECT ON \u2026 V_SCORED_TRANSACTIONS`",
              "no base tables, no catalogue, no writes"],
             note="this GRANT is the security boundary")
    p += [d1.svg(), d2.svg(), d3.svg()]
    p.append(_hop(d1.right(), d2.left(), G1, "identity"))
    p.append(_hop(d2.right(), d3.left(), G2, "least privilege"))

    # =================== QUERY TIME ===================
    p.append(_band(20, 668, 1200, 496, "QUERY TIME",
                   "Everything one transaction touches. One path, about three seconds, "
                   "no pipeline.",
                   "#fdf6ef"))
    p.append(_lane(C1X, 744, "ONE PAYMENT", "leaves the operational system"))
    q1 = Box(C1X, 756, C1W, 104, "1 \u00b7 PostgreSQL",
             ["a card payment is committed", "`INSERT INTO transactions`",
              "the source system knows nothing else"], note=g("postgres", "~4 ms"))
    q2 = Box(C2X, 756, C2W, 104, "2 \u00b7 Debezium \u2192 Kafka",
             ["change read off the WAL", topic,
              "durable, ordered, replayable"], accent=AMBER,
             note="~520 ms, commit to topic")
    q3 = Box(C3X, 756, C3W, 104, "3 \u00b7 Exasol consumes it",
             ["`IMPORT \u2026 FROM SCRIPT KAFKA_CONSUMER`",
              "`MERGE` \u2192 RAW, resumes at its own offset",
              "no Connect worker, no ETL service"],
             note=g("kafka", "~2.8 s") + " \u2014 mostly UDF startup")
    p += [q1.svg(), q2.svg(), q3.svg()]
    p.append(_hop(q1.right(), q2.left(), G1, "WAL"))
    p.append(_hop(q2.right(), q3.left(), G2, "consume"))

    p.append(_lane(C1X, 906, "THE CONTEXT", "three families, one SQL pass"))
    f1 = Box(C1X, 918, C1W, 92, "Velocity",
             ["`TXN_COUNT_1H`, `TXN_COUNT_24H`",
              "`AMOUNT_SUM_1H`, `AMOUNT_SUM_24H`"])
    f2 = Box(C2X, 918, C2W, 92, "Deviation",
             ["`AMOUNT_VS_AVG_RATIO`",
              "this payment \u00f7 her 30-day average"])
    f3 = Box(C3X, 918, C3W, 92, "Geography & device",
             ["`IS_NEW_COUNTRY_30D`, `IS_NEW_DEVICE_30D`",
              "`IS_CROSS_BORDER`, `IS_NIGHT_TXN`"])
    p += [f1.svg(), f2.svg(), f3.svg()]
    p.append(_fan_down(q3.bottom(0.5), [f1.top(0.5), f2.top(0.5), f3.top(0.5)], 892,
                       g("features", "~116 ms")))

    q6 = Box(340, 1052, 560, 84, "4 \u00b7 Scored, and decided, in one SELECT",
             ["`FRAUD_SCORE_UDF(amount, velocity, deviation, flags)`",
              "`CASE WHEN score >= 0.70 THEN 'BLOCK' \u2026 END`"],
             note=g("score", "~440 ms") + " \u2014 no model server, no feature store")
    p.append(q6.svg())
    p.append(_fan_in([f1.bottom(0.5), f2.bottom(0.5), f3.bottom(0.5)], q6.top(0.5), 1030,
                     "one row"))

    # =================== AGENT TIME ===================
    p.append(_band(20, 1188, 1200, 396, "AGENT TIME",
                   "Runs when somebody asks. The agent holds no database credential "
                   "of its own.",
                   "#f4f1fb"))
    p.append(_lane(C1X, 1264, "THE LOOP", "identity decides what comes back"))
    g1 = Box(C1X, 1276, C1W, 100, "1 \u00b7 An analyst asks",
             ["a persona is chosen", "a question in plain language",
              "no SQL written by hand"], accent=AMBER)
    g2 = Box(C2X, 1276, C2W, 100, "2 \u00b7 The agent",
             ["Claude, acting as an MCP client",
              "writes its own SQL, decides what to read",
              "holds no credential of its own"], accent=AMBER)
    g3 = Box(C3X, 1276, C3W, 100, "3 \u00b7 MCP server",
             ["the official `exasol-mcp-server`",
              "authenticates AS the persona",
              "writes refused, SQL parsed before it runs"])
    g4 = Box(C3X, 1422, C3W, 96, "4 \u00b7 Exasol, row-filtered",
             ["`CURRENT_USER` is applied by the engine",
              "SELECT on two views, nothing else"],
             note="another unit's rows are absent, not hidden")
    g5 = Box(C1X, 1422, C2X + C2W - C1X - 396, 96, "5 \u00b7 The answer",
             ["a verdict, findings, and the rows",
              "cited by the statement that produced it"])
    p += [g1.svg(), g2.svg(), g3.svg(), g4.svg(), g5.svg()]
    p.append(_hop(g1.right(), g2.left(), G1, "question"))
    p.append(_hop(g2.right(), g3.left(), G2, "tool call"))
    p.append(_drop(g3.bottom(0.5), g4.top(0.5), "as the persona"))
    # the loop: rows come back and the agent decides whether to ask again
    p.append(_wire([g4.top(0.82), (g4.x + g4.w * 0.82, 1399),
                    (g2.x + g2.w * 0.5, 1399), g2.bottom(0.5)],
                   "rows \u00b7 up to 5 times", (760, 1399), dash=True))
    p.append(_hop(g4.left(), g5.right(), 640, "the answer"))

    p.append('</svg>')
    return "".join(p)


DOC_LINKS = [
    ("Apache Kafka integration",
     "https://docs.exasol.com/db/latest/loading_data/connect_sources/kafka_integration.htm"),
    ("Kafka Connector Extension \u2014 user guide",
     "https://github.com/exasol/kafka-connector-extension/blob/main/doc/user_guide/user_guide.md"),
    ("User defined functions (UDFs)",
     "https://docs.exasol.com/db/latest/database_concepts/udf_scripts.htm"),
    ("Using Python in UDFs",
     "https://docs.exasol.com/db/latest/database_concepts/udf_scripts/python3.htm"),
    ("BucketFS",
     "https://docs.exasol.com/db/latest/database_concepts/bucketfs/bucketfs.htm"),
]


# ---------------------------------------------------------------------------
# The problem, drawn.
#
# Three panels: what arrives, what the decision needs, where that already is.
# The argument is spatial, so it belongs in a picture; the only words left are
# the ones a picture cannot say.
# ---------------------------------------------------------------------------
X_BLUE, X_BLUE_INK, X_BLUE_SOFT = "#00B2FF", "#0076AD", "#E2F4FF"
X_BAD, X_BAD_SOFT = "#C4121F", "#FCEBEC"
X_TEAL, X_TEAL_SOFT = "#12796A", "#E3F5F1"
X_AMBER_INK, X_AMBER_SOFT = "#9A6206", "#FEF3DC"
X_LINE = "#DCE3EE"


def _top_rounded(x, y, w, h, r=12) -> str:
    """A rect with only its top corners rounded -- a panel header."""
    return (f"M{x},{y+h} L{x},{y+r} Q{x},{y} {x+r},{y} L{x+w-r},{y} "
            f"Q{x+w},{y} {x+w},{y+r} L{x+w},{y+h} Z")


def _bang(cx, cy, r=11) -> str:
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{X_BAD}"/>'
            f'<rect x="{cx-1.4}" y="{cy-6}" width="2.8" height="7.5" rx="1.4" fill="#fff"/>'
            f'<circle cx="{cx}" cy="{cy+4.6}" r="1.7" fill="#fff"/>')


def _check(cx, cy, r=11) -> str:
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{X_TEAL}"/>'
            f'<path d="M{cx-5},{cy+0.3} L{cx-1.6},{cy+4} L{cx+5.2},{cy-4}" fill="none" '
            f'stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')


def _panel(x, y, w, h, head_a, head_b, accent, soft) -> str:
    """Panel shell: white body, tinted header, two-tone heading."""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#fff" '
            f'stroke="{X_LINE}" stroke-width="1.3"/>'
            f'<path d="{_top_rounded(x, y, w, 50)}" fill="{soft}"/>'
            f'<line x1="{x}" y1="{y+50}" x2="{x+w}" y2="{y+50}" stroke="{X_LINE}"/>'
            f'<text x="{x+22}" y="{y+32}" font-family="{HEAD}" font-size="15.5" '
            f'font-weight="800" letter-spacing="0.4" fill="{INK}">{head_a}'
            f'<tspan fill="{accent}"> {head_b}</tspan></text>')


def problem_diagram(amount="$8,750", merchant="LuckyBet Online", country="MT",
                    device="DEV-UNKNOWN-ANDROID-X", when="16:17:19", history_days=30):
    """One message, the decision it cannot support, and where the evidence sits."""
    p = ['<svg viewBox="0 0 1240 640" width="100%" role="img" '
         'aria-label="One Kafka message carries only this payment. A fraud decision needs four '
         'things that are not in the message: whether the amount is normal for this '
         'customer, whether the country and device have been used before, and what '
         'happened in the last hour. All of that lives in the warehouse, and reaches the '
         'decision only by overnight batch. The decision is due in seconds; its context '
         'arrives tomorrow. So put the event where the history already is." '
         'xmlns="http://www.w3.org/2000/svg">',
         f'<defs><marker id="ap" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
         f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#8FA0B4"/>'
         f'</marker><marker id="apr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
         f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{X_BAD}"/>'
         f'</marker></defs>']

    p.append(f'<text x="620" y="50" text-anchor="middle" font-family="{HEAD}" '
             f'font-size="31" font-weight="800" letter-spacing="-0.6" fill="{INK}">'
             f'One Kafka message is not enough to make a fraud decision</text>')

    # Column geometry. The second gutter is wider than the first because it has
    # to hold the "overnight batch" label: at 11.5px that word is ~60px, and the
    # original 50px gutter pushed it into both neighbouring panels.
    PY, PH = 92, 306
    P1X, P1W = 40, 328
    P2X, P2W = 408, 344
    P3X, P3W = 842, 358
    GUT1 = (P1X + P1W + P2X) / 2          # 388 -- narrow, unlabelled arrow
    GUT2 = (P2X + P2W + P3X) / 2          # 797 -- 90px wide, holds the label

    # ---------------- 1 · what arrives ----------------
    p.append(_panel(P1X, PY, P1W, PH, "THE EVENT ARRIVES", "NOW", X_BLUE_INK, X_BLUE_SOFT))
    p.append(f'<rect x="{P1X+24}" y="{PY+72}" width="{P1W-48}" height="146" rx="8" '
             f'fill="#F3F7FC"/>')
    p.append(f'<rect x="{P1X+24}" y="{PY+72}" width="5" height="146" rx="2.5" '
             f'fill="{X_BLUE}"/>')
    ty = PY + 100
    for k, v in (("amount", amount), ("merchant", merchant), ("country", country),
                 ("device", device), ("time", when)):
        p.append(f'<text x="{P1X+46}" y="{ty}" font-family="{MONO}" font-size="13.5" '
                 f'fill="{MUTED}">{k}: <tspan font-weight="700" fill="{INK}">{v}</tspan>'
                 f'</text>')
        ty += 27
    p.append(f'<text x="{P1X+24}" y="{PY+264}" font-family="{HEAD}" font-size="14.5" '
             f'font-weight="800" fill="{X_BLUE_INK}">Only this payment. No history.</text>')

    # ---------------- 2 · what the decision needs ----------------
    p.append(_panel(P2X, PY, P2W, PH, "THE DECISION NEEDS", "CONTEXT", X_BAD, X_BAD_SOFT))
    qy = PY + 86
    for q in (f"Is {amount} normal for this customer?",
              "Has this country been used before?",
              "Has this device been used before?",
              "What happened in the last hour?"):
        p.append(_bang(P2X + 30, qy - 5))
        p.append(f'<text x="{P2X+54}" y="{qy}" font-family="{SANS}" font-size="14" '
                 f'fill="{INK}">{q}</text>')
        qy += 44
    p.append(f'<line x1="{P2X+24}" y1="{PY+240}" x2="{P2X+P2W-24}" y2="{PY+240}" '
             f'stroke="{X_LINE}"/>')
    p.append(f'<text x="{P2X+24}" y="{PY+264}" font-family="{HEAD}" font-size="14.5" '
             f'font-weight="800" fill="{X_BAD}">None of this is in the message.</text>')

    # ---------------- 3 · where it already is ----------------
    p.append(_panel(P3X, PY, P3W, PH, "THE HISTORY LIVES", "ELSEWHERE", X_TEAL, X_TEAL_SOFT))
    hy = PY + 100
    for t in (f"Customer history, {history_days} days",
              "Recent transactions",
              "Device and country history"):
        p.append(_check(P3X + 30, hy - 5))
        p.append(f'<text x="{P3X+56}" y="{hy}" font-family="{SANS}" font-size="14" '
                 f'font-weight="700" fill="{INK}">{t}</text>')
        hy += 48
    p.append(f'<line x1="{P3X+24}" y1="{PY+240}" x2="{P3X+P3W-24}" y2="{PY+240}" '
             f'stroke="{X_LINE}"/>')
    p.append(f'<text x="{P3X+24}" y="{PY+264}" font-family="{HEAD}" font-size="14.5" '
             f'font-weight="800" fill="{X_TEAL}">In the warehouse, not in the stream.</text>')

    # ---------------- the two gaps ----------------
    p.append(f'<path d="M{P1X+P1W+8},{PY+150} L{P2X-8},{PY+150}" fill="none" '
             f'stroke="#8FA0B4" stroke-width="2.2" marker-end="url(#ap)"/>')
    # The context the decision needs is in the history -- but it only reaches
    # the decision by overnight batch. Drawn in the gutter between the two,
    # pointing from the history back to the decision that is waiting for it.
    gy = PY + PH / 2 + 6
    p.append(f'<path d="M{P3X-8},{gy} L{P2X+P2W+10},{gy}" fill="none" stroke="{X_BAD}" '
             f'stroke-width="2.4" stroke-dasharray="6 4" marker-end="url(#apr)"/>')
    pw, ph = 80, 34
    p.append(f'<rect x="{GUT2-pw/2}" y="{gy-ph-10}" width="{pw}" height="{ph}" rx="10" '
             f'fill="#fff" stroke="{X_BAD}" stroke-opacity="0.45"/>')
    for i, word in enumerate(("overnight", "batch")):
        p.append(f'<text x="{GUT2}" y="{gy-ph+5+i*13}" text-anchor="middle" '
                 f'font-family="{SANS}" font-size="11" font-weight="700" '
                 f'fill="{X_BAD}">{word}</text>')
    p.append(f'<text x="{GUT2}" y="{gy+22}" text-anchor="middle" font-family="{SANS}" '
             f'font-size="12" font-weight="800" fill="{X_BAD}">too late</text>')

    # ---------------- the consequence ----------------
    p.append(f'<rect x="40" y="428" width="1160" height="66" rx="12" fill="{X_BAD_SOFT}" '
             f'stroke="{X_BAD}" stroke-opacity="0.32"/>')
    p.append(_bang(84, 461, 15))
    p.append(f'<line x1="118" y1="444" x2="118" y2="478" stroke="{X_BAD}" '
             f'stroke-opacity="0.35" stroke-width="2"/>')
    p.append(f'<text x="140" y="469" font-family="{HEAD}" font-size="21" font-weight="800" '
             f'fill="{INK}">The decision is due in seconds. Its context arrives tomorrow.'
             f'</text>')

    # ---------------- the fix ----------------
    p.append(f'<rect x="40" y="512" width="1160" height="102" rx="12" fill="{X_TEAL_SOFT}" '
             f'stroke="{X_TEAL}" stroke-opacity="0.32"/>')
    p.append(_check(88, 563, 21))
    p.append(f'<text x="134" y="558" font-family="{HEAD}" font-size="27" font-weight="800" '
             f'letter-spacing="-0.4" fill="{X_TEAL}">Put the event where the history '
             f'already is.</text>')
    p.append(f'<text x="134" y="586" font-family="{SANS}" font-size="14" fill="{MUTED}">'
             f'When the event and its history are queryable together, fraud detection '
             f'becomes a query \u2014 not an overnight batch job.</text>')

    p.append('</svg>')
    return "".join(p)


# ---------------------------------------------------------------------------
# The journey, in four phases.
#
# Four bands, each a row of cards carrying the actual statement that does the
# work. The left rail names the phase and says when it runs; the cards say how.
# Every snippet below is the real thing, trimmed -- nothing invented to fill a
# box.
# ---------------------------------------------------------------------------
PH_BLUE   = ("#0076AD", "#E2F4FF")
PH_TEAL   = ("#12796A", "#E3F5F1")
PH_AMBER  = ("#9A6206", "#FEF3DC")
PH_INDIGO = ("#3545A0", "#ECEFF9")

CODE_BG, CODE_FG = "#F3F7FC", "#0B3D5C"


def _glyph(x, y, kind, colour):
    """A small mark so a card is recognisable before it is read."""
    g = [f'<rect x="{x}" y="{y}" width="26" height="26" rx="7" fill="{colour}" '
         f'fill-opacity="0.12"/>']
    cx, cy = x + 13, y + 13
    if kind == "file":
        g.append(f'<path d="M{cx-5},{cy-7} h7 l3,3 v11 h-10 z" fill="none" '
                 f'stroke="{colour}" stroke-width="1.6" stroke-linejoin="round"/>')
    elif kind == "db":
        g.append(f'<ellipse cx="{cx}" cy="{cy-5}" rx="7" ry="2.6" fill="none" '
                 f'stroke="{colour}" stroke-width="1.6"/>'
                 f'<path d="M{cx-7},{cy-5} v9 a7,2.6 0 0 0 14,0 v-9" fill="none" '
                 f'stroke="{colour}" stroke-width="1.6"/>')
    elif kind == "nodes":
        g.append(f'<circle cx="{cx-5}" cy="{cy-4}" r="2.4" fill="{colour}"/>'
                 f'<circle cx="{cx+5}" cy="{cy-4}" r="2.4" fill="{colour}"/>'
                 f'<circle cx="{cx}" cy="{cy+5}" r="2.4" fill="{colour}"/>'
                 f'<path d="M{cx-5},{cy-4} L{cx},{cy+5} L{cx+5},{cy-4}" fill="none" '
                 f'stroke="{colour}" stroke-width="1.4"/>')
    elif kind == "table":
        g.append(f'<rect x="{cx-7}" y="{cy-6}" width="14" height="12" rx="1.6" '
                 f'fill="none" stroke="{colour}" stroke-width="1.6"/>'
                 f'<path d="M{cx-7},{cy-2} h14 M{cx},{cy-6} v12" stroke="{colour}" '
                 f'stroke-width="1.2"/>')
    elif kind == "bars":
        for i, hgt in enumerate((5, 9, 13)):
            g.append(f'<rect x="{cx-6+i*5}" y="{cy+6-hgt}" width="3" height="{hgt}" '
                     f'rx="1" fill="{colour}"/>')
    elif kind == "shield":
        g.append(f'<path d="M{cx},{cy-7} l6,2.5 v5 c0,4-3,6.5-6,7.5 c-3-1-6-3.5-6-7.5 '
                 f'v-5 z" fill="none" stroke="{colour}" stroke-width="1.6" '
                 f'stroke-linejoin="round"/>')
    elif kind == "chat":
        g.append(f'<path d="M{cx-7},{cy-5} h14 v9 h-8 l-4,4 v-4 h-2 z" fill="none" '
                 f'stroke="{colour}" stroke-width="1.6" stroke-linejoin="round"/>')
    elif kind == "spark":
        g.append(f'<path d="M{cx},{cy-8} l1.8,5.4 l5.4,1.8 l-5.4,1.8 l-1.8,5.4 '
                 f'l-1.8,-5.4 l-5.4,-1.8 l5.4,-1.8 z" fill="{colour}"/>')
    elif kind == "person":
        g.append(f'<circle cx="{cx}" cy="{cy-4}" r="3.2" fill="none" stroke="{colour}" '
                 f'stroke-width="1.6"/><path d="M{cx-6},{cy+7} a6,5 0 0 1 12,0" '
                 f'fill="none" stroke="{colour}" stroke-width="1.6"/>')
    elif kind == "wave":
        g.append(f'<path d="M{cx-7},{cy} q3.5,-6 7,0 q3.5,6 7,0" fill="none" '
                 f'stroke="{colour}" stroke-width="1.6"/>')
    return "".join(g)


def _card(x, y, w, h, title, lines, colour, kind):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#fff" '
           f'stroke="{X_LINE}" stroke-width="1.2"/>',
           _glyph(x + 14, y + 12, kind, colour),
           f'<text x="{x+50}" y="{y+29}" font-family="{HEAD}" font-size="13.5" '
           f'font-weight="800" fill="{colour}">{title}</text>',
           f'<rect x="{x+14}" y="{y+44}" width="{w-28}" height="{h-56}" rx="6" '
           f'fill="{CODE_BG}"/>']
    # Five 12px lines starting at +58 end at +106, inside a block that runs to
    # +112. At the previous 13px step the fifth line fell outside the block.
    ty = y + 58
    for ln in lines[:5]:
        out.append(f'<text x="{x+24}" y="{ty}" font-family="{MONO}" font-size="9.6" '
                   f'fill="{CODE_FG}">{ln}</text>')
        ty += 12
    return "".join(out)


def _phase(y, h, num, name, desc_lines, pill, pal):
    colour, soft = pal
    out = [f'<rect x="30" y="{y}" width="1180" height="{h}" rx="14" fill="{soft}" '
           f'fill-opacity="0.45" stroke="{colour}" stroke-width="1.6"/>',
           f'<text x="52" y="{y+30}" font-family="{SANS}" font-size="11" '
           f'font-weight="800" letter-spacing="1.8" fill="{colour}">PHASE {num}</text>',
           f'<text x="52" y="{y+58}" font-family="{HEAD}" font-size="23" '
           f'font-weight="900" letter-spacing="-0.3" fill="{colour}">{name}</text>']
    ty = y + 80
    for d in desc_lines:
        out.append(f'<text x="52" y="{ty}" font-family="{SANS}" font-size="11.5" '
                   f'fill="{MUTED}">{d}</text>')
        ty += 15
    pw = len(pill) * 5.6 + 20
    out.append(f'<rect x="52" y="{y+h-36}" width="{pw}" height="21" rx="10.5" '
               f'fill="{colour}" fill-opacity="0.13"/>'
               f'<text x="{52+pw/2}" y="{y+h-21}" text-anchor="middle" '
               f'font-family="{SANS}" font-size="10" font-weight="700" '
               f'fill="{colour}">{pill}</text>')
    return "".join(out)


def _hub(x, y, w, h, lines):
    """
    The engine, drawn as the centre of gravity rather than one card in a row.

    Everything in phase 2 flows INTO this block and one thing comes out, which
    is the argument the whole diagram exists to make.
    """
    col, soft = PH_TEAL
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#fff" '
           f'stroke="{col}" stroke-width="2.2"/>',
           f'<path d="{_top_rounded(x, y, w, 62, 12)}" fill="{soft}"/>',
           f'<text x="{x+w/2}" y="{y+30}" text-anchor="middle" font-family="{HEAD}" '
           f'font-size="24" font-weight="900" letter-spacing="-0.4" fill="{col}">'
           f'Exasol</text>',
           f'<text x="{x+w/2}" y="{y+48}" text-anchor="middle" font-family="{SANS}" '
           f'font-size="9.5" font-weight="800" letter-spacing="1.6" fill="{col}">'
           f'REAL-TIME ANALYTICS ENGINE</text>',
           f'<rect x="{x+14}" y="{y+72}" width="{w-28}" height="{h-86}" rx="6" '
           f'fill="{CODE_BG}"/>']
    ty = y + 88
    for ln in lines[:6]:
        out.append(f'<text x="{x+24}" y="{ty}" font-family="{MONO}" font-size="9.6" '
                   f'fill="{CODE_FG}">{ln}</text>')
        ty += 12
    return "".join(out)


def _merge_into(sources, target, busx, colour="#7C8CA0"):
    """Several cards funnelling into one block."""
    ys = [p[1] for p in sources]
    out = [f'<path d="M{busx},{min(ys)} L{busx},{max(ys)}" fill="none" '
           f'stroke="{colour}" stroke-width="2"/>']
    for sx, sy in sources:
        out.append(f'<path d="M{sx},{sy} L{busx},{sy}" fill="none" stroke="{colour}" '
                   f'stroke-width="2"/><circle cx="{busx}" cy="{sy}" r="3" '
                   f'fill="{colour}"/>')
    out.append(f'<path d="M{busx},{target[1]} L{target[0]},{target[1]}" fill="none" '
               f'stroke="{colour}" stroke-width="2.2" marker-end="url(#jr)"/>')
    return "".join(out)


def _arrow_r(x1, x2, y, colour):
    return (f'<path d="M{x1},{y} L{x2},{y}" fill="none" stroke="{colour}" '
            f'stroke-width="2.2" marker-end="url(#jr)"/>')


def journey_diagram():
    """Four phases: build it, stream it, score it, ask it."""
    CX, CW, GAP = 246, 288, 30
    c = [CX, CX + CW + GAP, CX + 2 * (CW + GAP)]       # 246, 564, 882
    BH, BH2, BGAP = 168, 250, 26
    ys = [96]
    for hgt in (BH, BH2, BH):
        ys.append(ys[-1] + hgt + BGAP)

    p = ['<svg viewBox="0 0 1240 960" width="100%" role="img" '
         'aria-label="Four phases. First, a one-time setup: fetch the small plug-in that lets Exasol read Kafka, upload it into the database own storage, and give it a name in SQL so reading the stream becomes something SQL can do. Second, live: what normal looks like for each account and the payments arriving now both flow into Exasol, which merges them into one row holding the payment and its past. Third, scoring: compare the payment against that account own past, ask the model from inside the query, and turn the score into approve, review or block. Fourth, asking: a person asks a question in plain English, the agent reaches the database only through a read-only MCP server, signed in as that person, so it sees only what they may see, and returns an answer carrying the query that produced it." '
         'xmlns="http://www.w3.org/2000/svg">',
         'xmlns="http://www.w3.org/2000/svg">',
         f'<defs><marker id="jr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
         f'markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#7C8CA0"/>'
         f'</marker></defs>',
         f'<text x="40" y="44" font-family="{HEAD}" font-size="27" font-weight="900" '
         f'letter-spacing="-0.5" fill="{INK}">From Kafka event to agentic fraud '
         f'investigation</text>',
         f'<text x="40" y="68" font-family="{SANS}" font-size="14" fill="{MUTED}">'
         f'Build the context once. Score every payment as it lands. Ask in plain English.'
         f'</text>']

    # the four pages of the app, as a rail
    nav = [("1", "The challenge"), ("2", "Live Kafka to SQL"),
           ("3", "How it works"), ("4", "Agentic investigation")]
    nx = 700
    for i, (n, label) in enumerate(nav):
        cx = nx + i * 132
        if i:
            p.append(f'<line x1="{cx-132+14}" y1="40" x2="{cx-14}" y2="40" '
                     f'stroke="{X_LINE}" stroke-width="2"/>')
        col = [PH_BLUE, PH_TEAL, PH_AMBER, PH_INDIGO][i][0]
        p.append(f'<circle cx="{cx}" cy="40" r="13" fill="{col}"/>'
                 f'<text x="{cx}" y="45" text-anchor="middle" font-family="{HEAD}" '
                 f'font-size="12.5" font-weight="800" fill="#fff">{n}</text>'
                 f'<text x="{cx}" y="68" text-anchor="middle" font-family="{SANS}" '
                 f'font-size="10.5" fill="{MUTED}">{label}</text>')

    # ---------------- PHASE 1 ----------------
    y = ys[0]
    p.append(_phase(y, BH, 1, "BUILD TIME",
                    ["Connect the payment stream", "to the analytics engine."],
                    "One-time setup", PH_BLUE))
    col = PH_BLUE[0]
    p.append(_card(c[0], y+22, CW, BH-44, "Get the Kafka reader", [
        "-- a small plug-in that lets Exasol",
        "-- read a Kafka topic by itself",
        "curl -fSL -o kafka-connector.jar \\\\",
        "  https://github.com/exasol/..."], col, "file"))
    p.append(_card(c[1], y+22, CW, BH-44, "Upload it into Exasol storage", [
        "-- one upload puts the file inside",
        "-- the database\u2019s own storage",
        "curl -X PUT --data-binary \\",
        "  @kafka-connector.jar \\",
        "  http://.../default/"], col, "db"))
    p.append(_card(c[2], y+22, CW, BH-44, "Name it, once, in SQL", [
        "-- one CREATE statement gives the",
        "-- uploaded file a name SQL can call",
        "-- After this, reading the stream is",
        "-- just another thing SQL can do",
        "CREATE JAVA SET SCRIPT KAFKA_CONSUMER"], col, "nodes"))
    p.append(_arrow_r(c[0]+CW+6, c[1]-6, y+BH/2, "#7C8CA0"))
    p.append(_arrow_r(c[1]+CW+6, c[2]-6, y+BH/2, "#7C8CA0"))

    # ---------------- PHASE 2 ----------------
    # Taller than its neighbours: two sources stack on the left and funnel into
    # the engine, which is the point of the picture.
    y = ys[1]
    p.append(_phase(y, BH2, 2, "LIVE",
                    ["Events and historical context", "are queryable together."],
                    "Live data + history", PH_TEAL))
    col = PH_TEAL[0]
    SW = 252
    p.append(_card(c[0], y+22, SW, 100, "What normal looks like", [
        "-- each account\u2019s own history:",
        "-- how often, how much, where",
        "SELECT AVG(AMOUNT_USD) FROM ..."], col, "person"))
    p.append(_card(c[0], y+134, SW, 100, "Payments arriving now", [
        "-- Exasol pulls from Kafka itself;",
        "-- nothing sits in between",
        "IMPORT INTO ... FROM SCRIPT ..."], col, "wave"))
    HX, HW = c[0] + SW + 62, 330
    p.append(_hub(HX, y+22, HW, BH2-44, [
        "MERGE INTO RAW.TRANSACTIONS t",
        "USING KAFKA_STAGE.TRANSACTIONS s",
        "   ON t.TXN_ID = s.TXN_ID",
        "-- latest row per key, deletes applied,",
        "-- resumes at its own stored offset"]))
    p.append(_merge_into([(c[0]+SW+6, y+72), (c[0]+SW+6, y+184)],
                         (HX-6, y+22+(BH2-44)/2), c[0]+SW+34))
    p.append(_card(HX+HW+62, y+69, CW-40, 112, "The payment, with its past", [
        "-- one row holding both the payment",
        "-- and what is normal for her",
        "SELECT AMOUNT_USD, TXN_COUNT_1H,",
        "       FRAUD_SCORE FROM ..."], col, "table"))
    p.append(_arrow_r(HX+HW+6, HX+HW+56, y+22+(BH2-44)/2, "#7C8CA0"))

    # ---------------- PHASE 3 ----------------
    y = ys[2]
    p.append(_phase(y, BH, 3, "QUERY TIME",
                    ["Turn a payment into a risk", "score and a decision."],
                    "Scoring in the database", PH_AMBER))
    col = PH_AMBER[0]
    p.append(_card(c[0], y+22, CW, BH-44, "Compare it against normal", [
        "-- this payment vs this account\u2019s own",
        "-- past: how often, and how large",
        "COUNT(*) OVER (... 1 HOUR ...) ,",
        "AMOUNT_USD / AVG_30D"], col, "bars"))
    p.append(_card(c[1], y+22, CW, BH-44, "Ask the model, inside the query", [
        "-- the model runs in the database,",
        "-- called like any other function",
        "SELECT FRAUD_SCORE_UDF(",
        "   amount, count_1h, ...) AS SCORE"], col, "spark"))
    p.append(_card(c[2], y+22, CW, BH-44, "Approve, review or block", [
        "-- the rule that stops a payment is",
        "-- visible SQL, not hidden code",
        "CASE WHEN SCORE >= 0.70 THEN 'BLOCK'",
        "     WHEN SCORE >= 0.30 THEN 'REVIEW'",
        "     ELSE 'APPROVE' END"], col, "shield"))
    p.append(_arrow_r(c[0]+CW+6, c[1]-6, y+BH/2, "#7C8CA0"))
    p.append(_arrow_r(c[1]+CW+6, c[2]-6, y+BH/2, "#7C8CA0"))

    # ---------------- PHASE 4 ----------------
    y = ys[3]
    p.append(_phase(y, BH, 4, "AGENT TIME",
                    ["Anyone can ask a question", "and get a checkable answer."],
                    "Plain English to SQL", PH_INDIGO))
    col = PH_INDIGO[0]
    p.append(_card(c[0], y+22, CW, BH-44, "An analyst asks", [
        '"Some payments on your book were',
        ' blocked. Work out what is going on',
        ' and tell me what to do."',
        "-- no SQL written by hand"], col, "chat"))
    p.append(_card(c[1], y+22, CW, BH-44, "Through MCP, as that person", [
        "-- the agent never touches the",
        "-- database directly. It goes through",
        "-- an MCP server, read-only, signed",
        "-- in as the analyst",
        "EXA_USER = FRAUD_ANALYST_US"], col, "spark"))
    p.append(_card(c[2], y+22, CW, BH-44, "An answer you can check", [
        "-- every claim carries the query",
        "-- that produced it",
        "SELECT MERCHANT_NAME, AMOUNT_USD,",
        "       SCORE, DECISION FROM ..."], col, "shield"))
    p.append(_arrow_r(c[0]+CW+6, c[1]-6, y+BH/2, "#7C8CA0"))
    p.append(_arrow_r(c[1]+CW+6, c[2]-6, y+BH/2, "#7C8CA0"))

    # phase to phase
    for i, hgt in enumerate((BH, BH2, BH)):
        yy = ys[i] + hgt
        p.append(f'<path d="M620,{yy+4} L620,{ys[i+1]-6}" fill="none" '
                 f'stroke="{[PH_BLUE, PH_TEAL, PH_AMBER][i][0]}" stroke-width="2.4" '
                 f'marker-end="url(#jr)"/>')

    p.append('</svg>')
    return "".join(p)


# ---------------------------------------------------------------------------
# The same four phases, drawn as a picture rather than a page of code: every
# card is a mark, a title and a few words. The statements themselves are
# rendered separately (JOURNEY_SQL), one click away.
# ---------------------------------------------------------------------------
FIG = "Figtree, system-ui, sans-serif"

JOURNEY_SQL = [
    ("1 · Build once", "-- fetch the connector, upload it to BucketFS, register it\n"
     "curl -fSL -o kafka-connector.jar https://github.com/exasol/kafka-connector-extension/...\n"
     "curl -X PUT --data-binary @kafka-connector.jar http://.../default/\n"
     "CREATE JAVA SET SCRIPT KAFKA_EXTENSION.KAFKA_CONSUMER (...) EMITS (...) AS ...;"),
    ("2 · Live", "IMPORT INTO KAFKA_STAGE.TRANSACTIONS\n"
     "FROM SCRIPT KAFKA_EXTENSION.KAFKA_CONSUMER WITH TOPIC_NAME = '...' ...;\n\n"
     "MERGE INTO RAW.TRANSACTIONS t\nUSING KAFKA_STAGE.TRANSACTIONS s ON t.TXN_ID = s.TXN_ID\n"
     "WHEN MATCHED THEN UPDATE ... WHEN NOT MATCHED THEN INSERT ...;"),
    ("3 · Score", "SELECT COUNT(*) OVER (PARTITION BY ACCOUNT_ID ORDER BY TS\n"
     "         RANGE BETWEEN INTERVAL '1' HOUR PRECEDING AND CURRENT ROW) AS TXN_COUNT_1H,\n"
     "       AMOUNT_USD / AVG_30D                                     AS AMOUNT_VS_AVG_RATIO,\n"
     "       FRAUD_SCORE_UDF(amount, count_1h, ...)                   AS FRAUD_SCORE,\n"
     "       CASE WHEN FRAUD_SCORE >= 0.70 THEN 'BLOCK'\n"
     "            WHEN FRAUD_SCORE >= 0.30 THEN 'REVIEW' ELSE 'APPROVE' END AS DECISION\n"
     "FROM ...;"),
    ("4 · Ask", "-- the agent's only route: the official MCP server, signed in as the analyst\n"
     "EXA_USER = FRAUD_ANALYST_US      -- SELECT on two row-filtered views, nothing else\n"
     "SELECT MERCHANT_NAME, AMOUNT_USD, FRAUD_SCORE, DECISION\n"
     "FROM FRAUD_DEMO.V_SCORED_TRANSACTIONS ...;"),
]


def _vcard(x, y, w, h, title, caption, colour, kind, solid=False):
    fill, tcol, ccol = (colour, "#fff", "#ffffffcc") if solid else ("#fff", INK, MUTED)
    icon_col = "#fff" if solid else colour
    cy = y + h / 2
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" '
            f'stroke="{colour if solid else X_LINE}" stroke-width="1.3"/>'
            f'<g transform="translate({x+14},{cy-18}) scale(1.385)">'
            f'{_glyph(0, 0, kind, icon_col)}</g>'
            f'<text x="{x+66}" y="{cy-3}" font-family="{FIG}" font-size="15.5" '
            f'font-weight="800" fill="{tcol}">{title}</text>'
            f'<text x="{x+66}" y="{cy+16}" font-family="{FIG}" font-size="12.5" '
            f'fill="{ccol}">{caption}</text>')


def _vphase(y, h, num, name, when, pal):
    colour, soft = pal
    return (f'<rect x="20" y="{y}" width="1200" height="{h}" rx="18" fill="{soft}" '
            f'fill-opacity="0.55"/>'
            f'<circle cx="58" cy="{y+h/2}" r="19" fill="{colour}"/>'
            f'<text x="58" y="{y+h/2+6}" text-anchor="middle" font-family="{FIG}" '
            f'font-size="17" font-weight="800" fill="#fff">{num}</text>'
            f'<text x="90" y="{y+h/2-3}" font-family="{FIG}" font-size="19" '
            f'font-weight="800" fill="{colour}">{name}</text>'
            f'<text x="90" y="{y+h/2+17}" font-family="{FIG}" font-size="12" '
            f'font-weight="600" fill="{MUTED}">{when}</text>')


def journey_visual():
    """Build once, stream, score, ask -- one picture, no code."""
    C, W, CH = [262, 582, 902], 290, 74          # card columns, width, height
    BH, BH2, GAP = 110, 170, 18
    ys = [10]
    for hgt in (BH, BH2, BH):
        ys.append(ys[-1] + hgt + GAP)
    total = ys[-1] + BH + 10
    arrow = "#7C8CA0"
    p = [f'<svg viewBox="0 0 1240 {total}" width="100%" role="img" '
         f'xmlns="http://www.w3.org/2000/svg" aria-label="Four phases: build the Kafka '
         f'reader into Exasol once; stream every payment into Exasol next to its history; '
         f'score it in SQL; ask about it in plain English through a read-only MCP server.">',
         f'<defs><marker id="jv" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
         f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{arrow}"/>'
         f'</marker></defs>']

    def row(y, h, cards, pal):
        cy = y + h / 2
        for i, (t, cap, kind) in enumerate(cards):
            p.append(_vcard(C[i], cy - CH / 2, W, CH, t, cap, pal[0], kind))
            if i:
                p.append(f'<path d="M{C[i-1]+W+4},{cy} L{C[i]-6},{cy}" stroke="{arrow}" '
                         f'stroke-width="2.2" marker-end="url(#jv)"/>')

    y = ys[0]
    p.append(_vphase(y, BH, 1, "Build", "once", PH_BLUE))
    row(y, BH, [("Kafka reader for Exasol", "one open-source JAR", "file"),
                ("Into BucketFS", "Exasol's own file store", "db"),
                ("Registered in Exasol", "one CREATE SCRIPT statement", "nodes")], PH_BLUE)

    y = ys[1]
    col = PH_TEAL[0]
    p.append(_vphase(y, BH2, 2, "Stream", "every payment", PH_TEAL))
    sh, sw = 62, W - 50            # narrower sources leave room for two clean arrows
    s1, s2 = y + BH2 / 2 - sh - 8, y + BH2 / 2 + 8
    p.append(_vcard(C[0], s1, sw, sh, "Account history", "30 days of normal", col, "person"))
    p.append(_vcard(C[0], s2, sw, sh, "Payments arriving",
                    "from PostgreSQL, via Kafka", col, "wave"))
    hub_y, hub_h = y + 18, BH2 - 36
    p.append(_vcard(C[1], hub_y, W, hub_h, "Exasol", "stage \u2192 merge \u2192 features",
                    col, "db", solid=True))
    # two arrows converging on the engine's left edge
    for sy, ty in ((s1 + sh / 2, y + BH2 / 2 - 16), (s2 + sh / 2, y + BH2 / 2 + 16)):
        p.append(f'<path d="M{C[0]+sw+6},{sy} C{C[0]+sw+40},{sy} {C[1]-40},{ty} {C[1]-8},{ty}" '
                 f'fill="none" stroke="{arrow}" stroke-width="2.2" marker-end="url(#jv)"/>')
    p.append(_vcard(C[2], y + BH2 / 2 - CH / 2, W, CH, "Payment + its past",
                    "one row, ready to score", col, "table"))
    p.append(f'<path d="M{C[1]+W+4},{y+BH2/2} L{C[2]-6},{y+BH2/2}" stroke="{arrow}" '
             f'stroke-width="2.2" marker-end="url(#jv)"/>')

    y = ys[2]
    p.append(_vphase(y, BH, 3, "Score", "every payment, in SQL", PH_AMBER))
    row(y, BH, [("Compare to normal", "velocity · deviation", "bars"),
                ("Model in the query", "Python UDF, called from SQL", "spark"),
                ("Approve · Review · Block", "a CASE anyone can read", "shield")],
        PH_AMBER)

    y = ys[3]
    p.append(_vphase(y, BH, 4, "Ask", "whenever someone asks", PH_INDIGO))
    row(y, BH, [("Analyst asks", "in plain English", "chat"),
                ("MCP, as that person", "read-only · row-filtered", "person"),
                ("Answer with proof", "every claim cites its SQL", "shield")], PH_INDIGO)

    for i, hgt in enumerate((BH, BH2, BH)):
        yy = ys[i] + hgt
        p.append(f'<path d="M58,{yy-26} L58,{ys[i+1]+22}" stroke="{[PH_BLUE, PH_TEAL, PH_AMBER][i][0]}" '
                 f'stroke-width="2.4" stroke-dasharray="3 4"/>')
    p.append("</svg>")
    return "".join(p)


def problem_two_verdicts(amount="$8,750", merchant="LuckyBet Online", country="Malta"):
    """
    The same payment decided twice: by the stream alone, in seconds and blind,
    and by the warehouse, correctly but nine hours later. Every fact on the
    right is true of the seeded customer (49 payments, avg $29.55, max $91.27,
    US only, one device); the 02:00 batch is the typical status quo, not this demo.
    """
    p = ['<svg viewBox="0 0 1240 560" width="100%" role="img" '
         'xmlns="http://www.w3.org/2000/svg" aria-label="The same 8,750 dollar payment, '
         'decided twice. At 16:17 the stream alone approves it, because one message has '
         'nothing to compare against. At 02:00 the nightly warehouse flags it as fraud: 296 '
         'times her average spend, her first payment outside the US, on a device she has '
         'never used. The right answer existed, but arrived after the money had gone. So '
         'put the event where the history already is.">',
         f'<defs><marker id="tv" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
         f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{X_BAD}"/>'
         f'</marker></defs>',
         f'<text x="620" y="46" text-anchor="middle" font-family="{FIG}" font-size="32" '
         f'font-weight="800" letter-spacing="-0.6" fill="{INK}">Same payment. Two verdicts.'
         f'</text>',
         f'<text x="620" y="76" text-anchor="middle" font-family="{FIG}" font-size="15" '
         f'fill="{MUTED}">{amount} · {merchant} · {country} · an unrecognised '
         f'device</text>']

    def card(x, w, when, who, verdict, vcol, soft, lines, mark):
        y, h = 104, 262
        out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="#fff" '
               f'stroke="{vcol}" stroke-opacity="0.35" stroke-width="1.5"/>',
               f'<path d="{_top_rounded(x, y, w, 50, 16)}" fill="{soft}"/>',
               f'<text x="{x+26}" y="{y+32}" font-family="{FIG}" font-size="13" '
               f'font-weight="800" letter-spacing="1.4" fill="{vcol}">{when}</text>',
               f'<text x="{x+w-26}" y="{y+32}" text-anchor="end" font-family="{FIG}" '
               f'font-size="13" font-weight="700" fill="{MUTED}">{who}</text>',
               mark(x + 50, y + 104, 22),
               f'<text x="{x+88}" y="{y+120}" font-family="{FIG}" font-size="44" '
               f'font-weight="900" letter-spacing="-1" fill="{vcol}">{verdict}</text>']
        ly = y + 172
        for ln in lines:
            out.append(f'<circle cx="{x+34}" cy="{ly-5}" r="3.5" fill="{vcol}"/>'
                       f'<text x="{x+50}" y="{ly}" font-family="{FIG}" font-size="15.5" '
                       f'fill="{INK}">{ln}</text>')
            ly += 30
        return "".join(out)

    X1, X2, W = 40, 700, 500
    p.append(card(X1, W, "16:17:19", "the stream alone", "APPROVED", X_AMBER_INK, X_AMBER_SOFT,
                  ["Sees one message", "Nothing to compare it against",
                   "No reason to stop it"],
                  lambda cx, cy, r: _check(cx, cy, r).replace(X_TEAL, X_AMBER_INK)))
    p.append(card(X2, W, "02:00 NEXT DAY", "the nightly warehouse", "FRAUD", X_BAD, X_BAD_SOFT,
                  ["296× her average spend ($29.55)",
                   "Her first payment outside the US",
                   "A device she has never used"], _bang))

    # nine hours between them
    gx, gy = (X1 + W + X2) / 2, 235
    p.append(f'<path d="M{X1+W+10},{gy} L{X2-12},{gy}" stroke="{X_BAD}" stroke-width="2.4" '
             f'stroke-dasharray="6 5" marker-end="url(#tv)"/>'
             f'<rect x="{gx-58}" y="{gy-44}" width="116" height="30" rx="15" fill="#fff" '
             f'stroke="{X_BAD}" stroke-opacity="0.45"/>'
             f'<text x="{gx}" y="{gy-24}" text-anchor="middle" font-family="{FIG}" '
             f'font-size="14" font-weight="800" fill="{X_BAD}">9 hours later</text>')

    # the consequence
    p.append(f'<rect x="40" y="388" width="1160" height="62" rx="14" fill="{X_BAD_SOFT}" '
             f'stroke="{X_BAD}" stroke-opacity="0.32"/>')
    p.append(_bang(80, 419, 14))
    p.append(f'<text x="110" y="427" font-family="{FIG}" font-size="21" font-weight="800" '
             f'fill="{INK}">The right answer existed. It arrived after the {amount} had gone.'
             f'</text>')

    # the fix
    p.append(f'<rect x="40" y="468" width="1160" height="80" rx="14" fill="{X_TEAL_SOFT}" '
             f'stroke="{X_TEAL}" stroke-opacity="0.32"/>')
    p.append(_check(84, 508, 20))
    p.append(f'<text x="124" y="503" font-family="{FIG}" font-size="25" font-weight="800" '
             f'letter-spacing="-0.4" fill="{X_TEAL}">Put the event where the history already '
             f'is.</text>')
    p.append(f'<text x="124" y="530" font-family="{FIG}" font-size="14.5" fill="{MUTED}">'
             f'One verdict, in seconds, with the full history behind it — live on the next '
             f'page.</text>')
    p.append("</svg>")
    return "".join(p)


def problem_workflow(amount="$8,750", merchant="LuckyBet Online", country="MT",
                     device="DEV-UNKNOWN-ANDROID-X"):
    """
    The landing page: one payment walked through today's world as a timeline,
    then what it costs, then the fix.

    Customer facts are the seeded history (49 payments, avg $29.55, US only, one
    device). Industry figures, cited on the page:
      * $33.41B card fraud losses worldwide, 2024 -- Nilson Report (Jan 2026)
      * $5+ total cost per $1 of fraud, North American FIs -- LexisNexis Risk
        Solutions, True Cost of Fraud (Sep 2025)
    """
    W, GAP, X0 = 272, 24, 40
    xs = [X0 + i * (W + GAP) for i in range(4)]
    cx = [x + W / 2 for x in xs]
    AY, CY, CH = 132, 170, 252                     # axis y, card top, card height
    blue, amber, bad, teal = X_BLUE_INK, X_AMBER_INK, X_BAD, X_TEAL
    p = ['<svg viewBox="0 0 1240 706" width="100%" role="img" '
         'xmlns="http://www.w3.org/2000/svg" aria-label="One payment, today: at 16:17:19 an '
         '8,750 dollar payment arrives as a single message. The decision is due within '
         'seconds but needs context the message does not carry. The stream alone approves '
         'it. At 02:00 the nightly warehouse flags it as fraud, nine hours too late. Card '
         'fraud cost 33.4 billion dollars worldwide in 2024, and every dollar lost costs a '
         'bank more than five. The fix: put the event where the history already is.">',
         f'<defs><marker id="wf" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
         f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#8FA0B4"/>'
         f'</marker><marker id="wfr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
         f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{bad}"/>'
         f'</marker></defs>',
         f'<text x="620" y="42" text-anchor="middle" font-family="{FIG}" font-size="31" '
         f'font-weight="800" letter-spacing="-0.6" fill="{INK}">The right answer, nine hours '
         f'too late</text>',
         f'<text x="620" y="70" text-anchor="middle" font-family="{FIG}" font-size="15" '
         f'fill="{MUTED}">One card payment, followed through a typical stream-plus-warehouse '
         f'setup</text>']

    # ---- the timeline ----
    steps = [("16:17:19", blue), ("16:17:20", bad), ("16:17:21", amber), ("02:00 next day", bad)]
    for i in range(3):
        a, b = cx[i] + 20, cx[i + 1] - 22
        if i < 2:
            p.append(f'<path d="M{a},{AY} L{b},{AY}" stroke="#8FA0B4" stroke-width="2.4" '
                     f'marker-end="url(#wf)"/>')
        else:
            p.append(f'<path d="M{a},{AY} L{b},{AY}" stroke="{bad}" stroke-width="2.4" '
                     f'stroke-dasharray="7 5" marker-end="url(#wfr)"/>'
                     f'<rect x="{(a+b)/2-50}" y="{AY-14}" width="100" height="28" rx="14" '
                     f'fill="#fff" stroke="{bad}" stroke-opacity="0.5"/>'
                     f'<text x="{(a+b)/2}" y="{AY+5}" text-anchor="middle" font-family="{FIG}" '
                     f'font-size="13.5" font-weight="800" fill="{bad}">9 hours</text>')
    for i, (t, col) in enumerate(steps):
        p.append(f'<text x="{cx[i]}" y="{AY-30}" text-anchor="middle" font-family="{FIG}" '
                 f'font-size="13" font-weight="800" letter-spacing="0.8" fill="{col}">{t}</text>'
                 f'<circle cx="{cx[i]}" cy="{AY}" r="17" fill="{col}"/>'
                 f'<text x="{cx[i]}" y="{AY+6}" text-anchor="middle" font-family="{FIG}" '
                 f'font-size="16" font-weight="800" fill="#fff">{i+1}</text>')

    def card(i, col, soft, head, body, foot):
        x = xs[i]
        out = [f'<rect x="{x}" y="{CY}" width="{W}" height="{CH}" rx="14" fill="#fff" '
               f'stroke="{col}" stroke-opacity="0.3" stroke-width="1.4"/>',
               f'<path d="{_top_rounded(x, CY, W, 46, 14)}" fill="{soft}"/>',
               f'<text x="{x+20}" y="{CY+29}" font-family="{FIG}" font-size="15.5" '
               f'font-weight="800" fill="{col}">{head}</text>']
        out += body(x)
        out.append(f'<line x1="{x+20}" y1="{CY+CH-44}" x2="{x+W-20}" y2="{CY+CH-44}" '
                   f'stroke="{X_LINE}"/>'
                   f'<text x="{x+20}" y="{CY+CH-18}" font-family="{FIG}" font-size="14" '
                   f'font-weight="800" fill="{col}">{foot}</text>')
        return "".join(out)

    def message(x):
        o = [f'<rect x="{x+18}" y="{CY+62}" width="{W-36}" height="112" rx="8" fill="#F3F7FC"/>',
             f'<rect x="{x+18}" y="{CY+62}" width="4" height="112" rx="2" fill="{X_BLUE}"/>']
        ty = CY + 86
        for k, v in (("amount", amount), ("merchant", merchant), ("country", country),
                     ("device", device)):
            o.append(f'<text x="{x+34}" y="{ty}" font-family="{MONO}" font-size="11.5" '
                     f'fill="{MUTED}">{k}: <tspan font-weight="700" fill="{INK}">{v}</tspan>'
                     f'</text>')
            ty += 25
        return o

    def listing(items, mark, col):
        def f(x):
            o, ty = [], CY + 84
            for t in items:
                o.append(mark(x + 32, ty - 5, 9).replace(X_TEAL, col) if mark else "")
                o.append(f'<text x="{x+50}" y="{ty}" font-family="{FIG}" font-size="14" '
                         f'fill="{INK}">{t}</text>')
                ty += 32
            return o
        return f

    def verdict(word, col, mark, lines):
        def f(x):
            o = [mark(x + 38, CY + 88, 17).replace(X_TEAL, col),
                 f'<text x="{x+66}" y="{CY+100}" font-family="{FIG}" font-size="32" '
                 f'font-weight="900" letter-spacing="-0.8" fill="{col}">{word}</text>']
            ty = CY + 138
            for t in lines:
                o.append(f'<circle cx="{x+30}" cy="{ty-5}" r="3" fill="{col}"/>'
                         f'<text x="{x+42}" y="{ty}" font-family="{FIG}" font-size="13.5" '
                         f'fill="{INK}">{t}</text>')
                ty += 24
            return o
        return f

    p.append(card(0, blue, X_BLUE_SOFT, "The payment arrives", message,
                  "Only this payment. No history."))
    p.append(card(1, bad, X_BAD_SOFT, "A decision is due now",
                  listing(["Is this normal for her?", "Has she paid from Malta before?",
                           "Is this her device?", "What happened this hour?"], _bang, bad),
                  "None of it is in the message."))
    p.append(card(2, amber, X_AMBER_SOFT, "The stream decides alone",
                  verdict("APPROVED", amber, _check,
                          ["Nothing to compare against", "No reason to stop it"]),
                  f"{amount} leaves the account."))
    p.append(card(3, bad, X_BAD_SOFT, "The warehouse catches up",
                  verdict("FRAUD", bad, _bang,
                          ["296× her average spend", "First payment outside the US",
                           "A device she has never used"]),
                  "Right answer. Too late."))

    # ---- what it costs ----
    SY = 446
    p.append(f'<rect x="40" y="{SY}" width="1160" height="132" rx="16" fill="{X_BAD_SOFT}" '
             f'stroke="{bad}" stroke-opacity="0.25"/>'
             f'<text x="64" y="{SY+30}" font-family="{FIG}" font-size="12.5" font-weight="800" '
             f'letter-spacing="1.4" fill="{bad}">WHAT THE GAP COSTS</text>')
    stats = [(f"{amount} → ~$43,750", "this one payment, at the true cost of fraud",
              "every $1 lost costs a bank $5+ · LexisNexis, 2025"),
             ("$33.4 billion", "lost to card fraud worldwide in 2024",
              "Nilson Report, 2026"),
             ("9 hours", "between the decision and the evidence",
              "a typical nightly batch window")]
    sw = 1160 / 3
    for i, (big, what, src) in enumerate(stats):
        x = 40 + i * sw + 24
        if i:
            p.append(f'<line x1="{40+i*sw}" y1="{SY+46}" x2="{40+i*sw}" y2="{SY+116}" '
                     f'stroke="{bad}" stroke-opacity="0.2"/>')
        p.append(f'<text x="{x}" y="{SY+74}" font-family="{FIG}" font-size="30" '
                 f'font-weight="900" letter-spacing="-0.6" fill="{INK}">{big}</text>'
                 f'<text x="{x}" y="{SY+97}" font-family="{FIG}" font-size="14" '
                 f'fill="{INK}">{what}</text>'
                 f'<text x="{x}" y="{SY+116}" font-family="{FIG}" font-size="11.5" '
                 f'fill="{MUTED}">{src}</text>')

    # ---- the fix ----
    FY = 596
    p.append(f'<rect x="40" y="{FY}" width="1160" height="96" rx="16" fill="{X_TEAL_SOFT}" '
             f'stroke="{teal}" stroke-opacity="0.32"/>')
    p.append(_check(86, FY + 48, 22))
    p.append(f'<text x="128" y="{FY+42}" font-family="{FIG}" font-size="26" font-weight="800" '
             f'letter-spacing="-0.4" fill="{teal}">Put the event where the history already is.'
             f'</text>'
             f'<text x="128" y="{FY+70}" font-family="{FIG}" font-size="15" fill="{MUTED}">'
             f'Step 2 answered from 30 days of history, in seconds — so step 3 says BLOCKED. '
             f'Live on the next page.</text>')
    p.append("</svg>")
    return "".join(p)
