"""Stage styling, borrowed deliberately from the fraud demo's control surface so
the two booth screens read as one product.

Same tokens, same shapes: a dark gradient hero, translucent signal cards on it,
teal section kickers, and a dark "what to notice" card. What is different is the
job -- this screen argues a CASE rather than driving a pipeline, so it adds an
act structure (challenge / solution / notice) and a red accent for the places
the demo admits it fails.
"""

FONTS = ("https://fonts.googleapis.com/css2?"
         "family=Figtree:wght@400;500;600;700;800;900&"
         "family=JetBrains+Mono:wght@400;500;700&display=swap")

# The font link is an @import INSIDE <style>, never a <link> before it. A <link>
# opens a CommonMark type-6 HTML block, which ends at the first blank line -- so
# everything after the first blank line in this stylesheet renders on the page as
# literal text. `<style>` opens a type-1 block instead, which runs to </style>.
# Ported verbatim from the clinical-trials demo so the two presentations share
# one visual language. Tokens, hero, act rail, challenge/solution cards, KPI grid
# and the dark note card are unchanged. Everything under "kafka demo additions"
# is new and is written in the same idiom.
_SHEET = f"""
<style>
@import url('{FONTS}');
:root {{
  /* Exasol brand, taken from exasol.com's own stylesheet.
     One rule governs everything below: #00B2FF is a FILL, never text -- it
     measures 2.38:1 on white. The -ink variants are its accessible
     counterparts and every coloured word on the page uses one of those. */
  --navy:#081226; --navy-8:#10203F;
  --bg-top:#F4F7FB; --bg-bottom:#FFFFFF;
  --ink:#081226; --muted:#4A5464; --faint:#66748A;
  --blue:#00B2FF;  --blue-ink:#0076AD;  --blue-soft:#E2F4FF;
  --teal:#1FA08B;  --teal-ink:#12796A;  --teal-soft:#E3F5F1;
  --green:#5FC33B; --green-ink:#3E8722; --green-soft:#EDF8E6;
  --amber:#F59E0B; --amber-ink:#9A6206; --amber-soft:#FEF3DC;
  --bad:#C4121F;   --bad-ink:#C4121F;   --bad-soft:#FCEBEC;
  --line:rgba(8,18,38,0.10);
  --card:rgba(255,255,255,0.86);
  --shadow:0 18px 45px rgba(8,18,38,0.09);
}}
*, *::before, *::after {{ box-sizing:border-box; }}
html, body {{ overflow-x:hidden; }}
html, body, [class*="css"] {{ font-family:"Figtree",sans-serif; color:var(--ink); }}
.stApp {{
  background:
    radial-gradient(circle at top left, rgba(226,244,255,0.95), transparent 30%),
    radial-gradient(circle at top right, rgba(227,245,241,0.85), transparent 26%),
    linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 55%, #ffffff 100%);
}}
.block-container {{ padding:1.4rem 2.2rem 3rem !important; max-width:100% !important; }}
@media (min-width:1700px) {{ .block-container {{ padding-left:3.5rem !important;
  padding-right:3.5rem !important; }} }}
/* Prose stays at a readable measure even when the page is full width -- a line
   of body text 1800px wide is unreadable, however much room there is. */
.section-copy, .lede2, .dcard p, .lanex p, .pain .a, .tri .t {{ max-width:74ch; }}
h1,h2,h3 {{ font-family:"Figtree",sans-serif; letter-spacing:-0.03em; color:var(--ink); }}
code, pre, .mono {{ font-family:"JetBrains Mono",monospace !important; }}
[data-testid="stSidebar"], [data-testid="collapsedControl"], [data-testid="stToolbar"],
[data-testid="stHeaderActionElements"], #MainMenu, header[data-testid="stHeader"],
footer {{ display:none; }}

/* ---------- hero ---------- */
.hero-shell {{ position:relative;
  background:linear-gradient(135deg, #081226 0%, #10203F 58%, #12796A 100%);
  border-radius:28px; padding:1.8rem 1.9rem; box-shadow:var(--shadow);
  color:#f7fbff; margin-bottom:1.35rem; overflow:hidden; position:relative;
}}
.hero-shell::after {{
  content:""; position:absolute; inset:auto -40px -40px auto; width:220px; height:220px;
  background:radial-gradient(circle, rgba(255,255,255,0.17), transparent 65%);
}}
.hero-eyebrow {{ text-transform:uppercase; letter-spacing:.16em; font-size:.72rem;
  font-weight:600; color:rgba(255,255,255,.70); margin-bottom:.8rem; }}
.hero-title {{ font-family:"Figtree",sans-serif; font-size:2.2rem; line-height:1.02;
  font-weight:700; max-width:20ch; margin-bottom:.7rem; }}
.hero-copy {{ max-width:58rem; font-size:1rem; line-height:1.6; color:rgba(247,251,255,.82); }}
.signal-grid {{ display:grid; gap:.85rem; margin-top:1.15rem; grid-template-columns:repeat(4,minmax(0,1fr)); }}
.signal-card {{ border-radius:22px; border:1px solid rgba(255,255,255,.10);
  background:rgba(255,255,255,.10); padding:1rem; backdrop-filter:blur(8px); }}
.signal-label {{ text-transform:uppercase; letter-spacing:.12em; font-size:.68rem; font-weight:700;
  margin-bottom:.35rem; color:rgba(255,255,255,.62); }}
.signal-value {{ font-family:"Figtree",sans-serif; font-size:1.2rem; font-weight:700; }}
.signal-meta {{ color:rgba(255,255,255,.70); font-size:.88rem; margin-top:.2rem; }}
.signal-card.down {{ border-color:rgba(255,160,150,.45); background:rgba(196,18,31,.22); }}

/* ---------- section + act ---------- */
.section-kicker {{ text-transform:uppercase; letter-spacing:.16em; font-size:.7rem;
  font-weight:700; color:var(--teal); margin-bottom:.25rem; }}
.section-title {{ font-family:"Figtree",sans-serif; font-size:1.5rem; margin:0; }}
.section-copy {{ color:var(--muted); max-width:64rem; margin-top:.3rem; line-height:1.6; }}

.act-rail {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.6rem; margin:.2rem 0 1.4rem; }}
.act-chip {{ border-radius:14px; border:1px solid var(--line); background:rgba(255,255,255,.62);
  padding:.6rem .75rem; }}
.act-chip .n {{ font-family:"JetBrains Mono",monospace; font-size:.66rem; font-weight:700;
  letter-spacing:.14em; color:var(--faint); }}
.act-chip .t {{ font-size:.86rem; font-weight:600; line-height:1.3; margin-top:.1rem; }}
.act-chip.on {{ border-color:rgba(31,160,139,.35); background:linear-gradient(180deg,
  rgba(228,250,247,.96) 0%, rgba(255,255,255,.98) 100%); }}
.act-chip.on .n {{ color:var(--teal); }}

.chal {{ border-radius:22px; border:1px solid var(--line); box-shadow:var(--shadow);
  background:linear-gradient(180deg, rgba(255,246,244,.95) 0%, rgba(255,252,251,.98) 100%);
  border-left:5px solid var(--bad); padding:1.1rem 1.2rem; margin-bottom:.9rem; }}
.sol {{ border-radius:22px; border:1px solid var(--line); box-shadow:var(--shadow);
  background:linear-gradient(180deg, rgba(228,250,247,.92) 0%, rgba(255,255,255,.98) 100%);
  border-left:5px solid var(--teal); padding:1.1rem 1.2rem; margin-bottom:.9rem; }}
.chal .lbl, .sol .lbl {{ text-transform:uppercase; letter-spacing:.14em; font-size:.66rem;
  font-weight:700; margin-bottom:.4rem; }}
.chal .lbl {{ color:var(--bad); }}
.sol  .lbl {{ color:var(--teal); }}
.chal p, .sol p {{ margin:.35rem 0 0; line-height:1.6; }}
.chal .big {{ font-family:"Figtree",sans-serif; font-size:1.25rem; font-weight:700;
  line-height:1.25; }}
.sol .big {{ font-family:"Figtree",sans-serif; font-size:1.25rem; font-weight:700;
  line-height:1.25; }}

.note-card {{ border-radius:22px; border:1px solid rgba(255,255,255,.08); box-shadow:var(--shadow);
  background:linear-gradient(180deg, rgba(11,34,53,.96) 0%, rgba(19,45,69,.95) 100%);
  color:#f6fbff; padding:1.15rem; }}
.note-card .mini-kicker {{ text-transform:uppercase; letter-spacing:.12em; font-size:.68rem;
  font-weight:700; margin-bottom:.35rem; color:rgba(255,255,255,.66); }}
.note-card p, .note-card ul {{ margin:.45rem 0 0; line-height:1.55; color:inherit; }}
.note-card li {{ margin-bottom:.25rem; }}

/* ---------- numbers ---------- */
.kpi-grid {{ display:grid; gap:.85rem; grid-template-columns:repeat(4,minmax(0,1fr)); margin:.2rem 0 .4rem; }}
.kpi {{ border-radius:18px; border:1px solid var(--line); background:var(--card);
  box-shadow:var(--shadow); padding:.9rem 1rem; }}
.kpi .k {{ text-transform:uppercase; letter-spacing:.12em; font-size:.66rem; font-weight:700;
  color:var(--muted); }}
.kpi .v {{ font-family:"Figtree",sans-serif; font-size:1.65rem; font-weight:700;
  font-variant-numeric:tabular-nums; margin-top:.15rem; }}
.kpi .x {{ font-size:.82rem; color:var(--muted); margin-top:.1rem; line-height:1.4; }}
.kpi.hot {{ border-color:rgba(196,18,31,.28); background:linear-gradient(180deg,
  rgba(251,234,233,.95) 0%, rgba(255,252,252,.98) 100%); }}
.kpi.hot .v {{ color:var(--bad); }}
.kpi.good .v {{ color:var(--teal); }}

/* single-series bars: the row label names the bar, so no legend */
.bars {{ margin-top:.5rem; }}
.barrow {{ display:grid; grid-template-columns:190px 1fr 92px; gap:.7rem; align-items:center;
  padding:.28rem 0; }}
.barrow .lb {{ font-size:.86rem; color:var(--ink); }}
.barrow .tr {{ height:20px; background:rgba(8,18,38,.06); border-radius:6px; overflow:hidden; }}
.barrow .fl {{ height:100%; background:var(--teal); border-radius:6px; }}
.barrow .fl.warn {{ background:var(--amber); }}
.barrow .fl.bad {{ background:var(--bad); }}
.barrow .vv {{ font-family:"JetBrains Mono",monospace; font-size:.82rem; text-align:right;
  color:var(--muted); font-variant-numeric:tabular-nums; }}

/* result rows */
.res {{ border-radius:14px; border:1px solid var(--line); background:rgba(255,255,255,.80);
  padding:.6rem .8rem; margin-bottom:.4rem; }}
.res.bad {{ border-color:rgba(196,18,31,.35); background:rgba(251,234,233,.85); }}
.res .top {{ display:flex; gap:.6rem; align-items:baseline; flex-wrap:wrap; }}
.res .nct {{ font-family:"JetBrains Mono",monospace; font-size:.8rem; color:var(--muted); }}
.res .tag {{ font-size:.63rem; text-transform:uppercase; letter-spacing:.1em; font-weight:700;
  border-radius:999px; padding:.1rem .5rem; background:var(--teal-soft); color:var(--teal); }}
.res.bad .tag {{ background:var(--bad); color:#fff; }}
.res .sim {{ margin-left:auto; font-family:"JetBrains Mono",monospace; font-size:.76rem; color:var(--faint); }}
.res .tx {{ font-size:.88rem; color:var(--ink); margin-top:.22rem; line-height:1.45; }}

.tiers {{ display:grid; grid-template-columns:1fr auto 1fr; gap:.9rem; align-items:stretch; margin:.3rem 0 .2rem; }}
.tier {{ border-radius:18px; border:1px solid var(--line); background:var(--card);
  box-shadow:var(--shadow); padding:.9rem 1rem; }}
.tier .k {{ text-transform:uppercase; letter-spacing:.12em; font-size:.64rem; font-weight:700;
  color:var(--muted); }}
.tier .n {{ font-family:"Figtree",sans-serif; font-size:1.05rem; font-weight:700; margin-top:.15rem; }}
.tier .d {{ font-size:.82rem; color:var(--muted); margin-top:.2rem; line-height:1.45; }}
.tier.lake {{ border-color:rgba(245,158,11,.30); background:linear-gradient(180deg,
  rgba(255,247,234,.95) 0%, rgba(255,253,250,.98) 100%); }}
.joiner {{ display:flex; align-items:center; justify-content:center; font-family:"JetBrains Mono",monospace;
  font-size:.7rem; font-weight:700; letter-spacing:.12em; color:var(--teal); text-align:center;
  writing-mode:horizontal-tb; padding:0 .3rem; }}

.stTabs [data-baseweb="tab-list"] {{ gap:1.4rem; border-bottom:1px solid var(--line); }}
.stTabs [data-baseweb="tab"] {{ font-size:.92rem; font-weight:600; color:var(--muted); padding:.4rem 0; }}
.stTabs [aria-selected="true"] {{ color:var(--bad) !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background:var(--bad); }}

.stButton > button {{ font-family:"Figtree",sans-serif !important; font-weight:600 !important;
  border-radius:12px !important; border:1px solid rgba(31,160,139,.35) !important;
  background:linear-gradient(135deg,#081226 0%,#10203F 100%) !important; color:#fff !important; }}
@media (max-width:1000px) {{
  .signal-grid, .kpi-grid, .act-rail {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
  .tiers {{ grid-template-columns:1fr; }}
}}

/* ================= kafka demo additions ================= */
/* The five-hop rail. Same card language as .kpi, one per pipeline stage. */
.rail {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:.7rem; margin:.7rem 0 .2rem; }}
.stg {{ border-radius:18px; border:1px solid var(--line); background:var(--card);
  box-shadow:var(--shadow); padding:.8rem .95rem; transition:all .22s ease; }}
.stg .sys {{ font-family:"JetBrains Mono",monospace; font-size:.62rem; font-weight:700;
  letter-spacing:.13em; text-transform:uppercase; color:var(--faint); }}
.stg .what {{ font-size:.9rem; font-weight:600; margin-top:.12rem; }}
.stg .ms {{ font-family:"Figtree",sans-serif; font-size:1.6rem; font-weight:700;
  font-variant-numeric:tabular-nums; margin-top:.25rem; color:var(--faint); }}
.stg .ms small {{ font-size:.72rem; font-weight:600; margin-left:.1rem; }}
.stg.run {{ border-color:rgba(245,158,11,.38);
  background:linear-gradient(180deg, rgba(255,247,234,.96) 0%, rgba(255,253,250,.98) 100%); }}
.stg.run .ms {{ color:var(--amber); }}
.stg.done {{ border-color:rgba(31,160,139,.32); }}
.stg.done .ms {{ color:var(--ink); }}

/* The verdict. One number, allowed to be enormous. */
.verdict {{ border-radius:22px; border:1px solid var(--line); box-shadow:var(--shadow);
  padding:1.15rem 1.35rem; margin:.8rem 0 .7rem; display:flex; align-items:center;
  gap:1.9rem; flex-wrap:wrap; }}
.verdict .word {{ font-family:"Figtree",sans-serif; font-size:clamp(2.6rem,5.4vw,4.2rem);
  font-weight:700; letter-spacing:-.04em; line-height:1; }}
.verdict .m {{ text-transform:uppercase; letter-spacing:.12em; font-size:.66rem;
  font-weight:700; color:var(--muted); }}
.verdict .m b {{ display:block; font-family:"Figtree",sans-serif; font-size:1.75rem;
  font-weight:700; color:var(--ink); letter-spacing:-.02em; text-transform:none;
  font-variant-numeric:tabular-nums; margin-top:.1rem; }}
.v-approve {{ background:linear-gradient(180deg, rgba(228,250,247,.92) 0%, rgba(255,255,255,.98) 100%);
  border-left:5px solid var(--teal); }}
.v-approve .word {{ color:var(--teal); }}
.v-review {{ background:linear-gradient(180deg, rgba(255,247,234,.95) 0%, rgba(255,253,250,.98) 100%);
  border-left:5px solid var(--amber); }}
.v-review .word {{ color:var(--amber); }}
.v-block {{ background:linear-gradient(180deg, rgba(251,234,233,.95) 0%, rgba(255,252,252,.98) 100%);
  border-left:5px solid var(--bad); }}
.v-block .word {{ color:var(--bad); }}

/* Architecture strip: reuses .tier, six across with joiners. */
.archrow {{ display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:.55rem;
  align-items:stretch; margin:.4rem 0 .2rem; }}
.tier.exa {{ border-color:rgba(31,160,139,.32); background:linear-gradient(180deg,
  rgba(228,250,247,.92) 0%, rgba(255,255,255,.98) 100%); }}
.tier.exa .k {{ color:var(--teal); }}

/* The act rail here has seven steps, not four. */
.act-rail.seven {{ grid-template-columns:repeat(7,minmax(0,1fr)); }}
.act-chip.done {{ opacity:.55; }}

/* Receipt bars reuse .barrow; only the negative direction is new. */
.barrow .fl.neg {{ background:var(--blue-ink); }}


/* slim hero, shown once the story is running */
.hero-slim {{ display:flex; align-items:center; justify-content:space-between; gap:1rem;
  flex-wrap:wrap; border-radius:18px; padding:.7rem 1.1rem; margin-bottom:.8rem;
  background:linear-gradient(135deg, rgba(9,33,48,0.96) 0%, rgba(17,42,73,0.94) 60%,
  rgba(147,76,31,0.88) 100%); box-shadow:var(--shadow); color:#f7fbff; }}
.hs-t {{ font-family:"Figtree",sans-serif; font-size:1.05rem; font-weight:700; }}
.hs-t em {{ font-style:normal; color:#7fd6ff; }}
.hs-t span {{ font-family:"Figtree",sans-serif; font-weight:500; font-size:.85rem;
  color:rgba(247,251,255,.62); margin-left:.5rem; }}
.hs-m {{ display:flex; align-items:center; gap:.7rem; flex-wrap:wrap;
  font-size:.82rem; color:rgba(247,251,255,.75); }}
.hs-pill {{ text-transform:uppercase; letter-spacing:.1em; font-size:.6rem; font-weight:700;
  border-radius:999px; padding:.18rem .6rem; background:rgba(31,160,139,.45); color:#c9f5ec; }}
.hs-pill.down {{ background:rgba(196,18,31,.5); color:#ffd7d4; }}
.hs-num {{ font-family:"Figtree",sans-serif; font-weight:700; color:#fff; }}

/* the rail sits directly above the controls; keep the gap small */
div[data-testid="stHorizontalBlock"]:has(button[data-testid="stBaseButton-tertiary"]) {{
  margin-bottom:.35rem; }}
/* nav rail buttons: streamlit's own kinds carry the state */
div[data-testid="stHorizontalBlock"] button[data-testid="stBaseButton-secondary"],
div[data-testid="stHorizontalBlock"] button[data-testid="stBaseButton-tertiary"] {{
  font-family:"JetBrains Mono",monospace !important; font-size:.6rem !important;
  font-weight:700 !important; letter-spacing:.08em !important;
  padding:.24rem .1rem !important; border-radius:7px !important;
  min-height:0 !important; }}
div[data-testid="stHorizontalBlock"] button[data-testid="stBaseButton-secondary"] {{
  background:rgba(215,243,239,.7) !important; color:var(--teal) !important;
  border:1px solid rgba(31,160,139,.25) !important; }}
div[data-testid="stHorizontalBlock"] button[data-testid="stBaseButton-tertiary"] {{
  background:rgba(255,255,255,.5) !important; color:var(--faint) !important;
  border:1px solid var(--line) !important; }}
div[data-testid="stHorizontalBlock"] button[data-testid="stBaseButton-primary"] {{
  font-family:"JetBrains Mono",monospace !important; font-size:.6rem !important;
  font-weight:700 !important; letter-spacing:.08em !important;
  padding:.24rem .1rem !important; border-radius:7px !important; min-height:0 !important; }}

/* three-up row for the page-1 summary points */
.archrow.three {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
/* result grid on page 2 */
.restab {{ width:100%; border-collapse:collapse; font-size:.85rem; margin-top:.2rem; }}
.restab th {{ text-align:right; font-family:"JetBrains Mono",monospace; font-size:.58rem;
  letter-spacing:.09em; text-transform:uppercase; color:var(--faint); font-weight:700;
  padding:.3rem .55rem .4rem; border-bottom:1px solid var(--rule-firm,var(--line));
  line-height:1.25; vertical-align:bottom; }}
.restab th:first-child, .restab th:last-child {{ text-align:left; }}
.restab td {{ padding:.45rem .55rem; border-bottom:1px solid var(--line); color:var(--ink); }}
.restab td.merch {{ font-weight:600; }}
.restab td.num {{ text-align:right; font-variant-numeric:tabular-nums;
  font-family:"JetBrains Mono",monospace; font-size:.82rem; }}
.restab td.score {{ font-weight:700; }}
.restab td.empty {{ text-align:center; color:var(--muted); padding:1.2rem; }}
.restab tr.hot td {{ background:rgba(251,234,233,.75); }}
.restab tr.hot td.score {{ color:var(--bad); }}
.restab tr.warn td {{ background:rgba(251,238,218,.7); }}
.restab tr.warn td.score {{ color:var(--amber); }}
.restab tr:last-child td {{ border-bottom:0; }}
.pill-d {{ font-family:"JetBrains Mono",monospace; font-size:.6rem; font-weight:700;
  letter-spacing:.09em; border-radius:999px; padding:.18rem .55rem; }}
.d-approve {{ background:var(--teal-soft); color:var(--teal); }}
.d-review {{ background:var(--amber-soft); color:var(--amber); }}
.d-block {{ background:var(--bad); color:#fff; }}

/* the drawn architecture */
.archbox {{ border-radius:22px; border:1px solid var(--line); background:rgba(255,255,255,.72);
  box-shadow:var(--shadow); padding:.6rem .6rem .3rem; margin:.3rem 0 .5rem; overflow-x:auto; }}
.archbox svg {{ display:block; width:100%; height:auto; }}
.doclinks {{ font-size:.84rem; color:var(--muted); margin:0 0 .9rem; line-height:1.9; }}
.doclinks .dl-k {{ font-family:"JetBrains Mono",monospace; font-size:.62rem; font-weight:700;
  letter-spacing:.12em; text-transform:uppercase; color:var(--faint); margin-right:.7rem; }}
.doclinks a {{ color:var(--teal); text-decoration:none; border-bottom:1px solid rgba(31,160,139,.3); }}
.doclinks a:hover {{ border-bottom-color:var(--teal); }}

.runlabel {{ font-family:"JetBrains Mono",monospace; font-size:.68rem; font-weight:700;
  letter-spacing:.06em; color:var(--muted); margin:.6rem 0 -.2rem; }}
.howto {{ border-radius:14px; border:1px solid var(--line); border-left:4px solid var(--teal);
  background:rgba(215,243,239,.45); padding:.6rem .9rem; margin:.2rem 0 .7rem;
  font-size:.92rem; color:var(--muted); }}
.howto b {{ color:var(--ink); }}
.footnote {{ font-size:.78rem; color:var(--faint); line-height:1.55; margin-top:.5rem;
  max-width:70ch; }}
.footnote b {{ color:var(--muted); font-family:"JetBrains Mono",monospace; }}

/* agentic investigation steps */
.agstep {{ max-width:100%; overflow:hidden; border-radius:18px; border:1px solid var(--line); background:var(--card);
  box-shadow:var(--shadow); padding:.8rem 1rem; margin-bottom:.6rem;
  border-left:4px solid var(--teal); }}
.ag-why {{ font-size:1rem; font-weight:600; color:var(--ink); margin-bottom:.45rem; }}
.ag-sql {{ font-family:"JetBrains Mono",monospace; font-size:.74rem; line-height:1.5;
  color:var(--blue-ink); background:rgba(8,18,38,.04); border-radius:8px; padding:.5rem .65rem;
  white-space:pre-wrap; word-break:break-word; margin-bottom:.45rem; }}
.agtabwrap {{ max-width:100%; overflow-x:auto; }}
.agtab {{ width:100%; border-collapse:collapse; font-size:.76rem;
  font-family:"JetBrains Mono",monospace; table-layout:auto; }}
.agtab th, .agtab td {{ white-space:nowrap; }}
.agtab th {{ text-align:left; font-size:.6rem; letter-spacing:.08em; text-transform:uppercase;
  color:var(--faint); font-weight:700; padding:.25rem .5rem .3rem 0;
  border-bottom:1px solid var(--line); }}
.agtab td {{ padding:.28rem .5rem .28rem 0; border-bottom:1px solid var(--line);
  color:var(--muted); }}
.ag-more {{ font-size:.7rem; color:var(--faint); margin-top:.4rem; }}
.ag-err {{ font-size:.8rem; color:var(--bad); background:var(--bad-soft);
  border-radius:8px; padding:.4rem .6rem; }}
.note-card ul {{ margin:.5rem 0 .3rem 1.1rem; padding:0; }}
.note-card li {{ margin-bottom:.3rem; font-size:.95rem; }}

.ag-tool {{ font-family:"JetBrains Mono",monospace; font-size:.72rem; font-weight:700;
  letter-spacing:.06em; color:var(--teal); background:var(--teal-soft);
  border-radius:6px; padding:.15rem .5rem; }}
.idcard {{ border-radius:16px; border:1px solid var(--line); background:var(--card);
  box-shadow:var(--shadow); padding:.7rem 1rem; margin:.5rem 0 .8rem;
  border-left:4px solid var(--teal); }}
.id-k {{ text-transform:uppercase; letter-spacing:.12em; font-size:.6rem; font-weight:700;
  color:var(--muted); }}
.id-u {{ font-family:"JetBrains Mono",monospace; font-size:1.05rem; font-weight:700;
  color:var(--ink); margin-top:.1rem; }}
.id-b {{ font-size:.85rem; color:var(--muted); margin-top:.15rem; }}

.qpreview {{ font-size:.92rem; line-height:1.55; color:var(--muted);
  background:rgba(255,255,255,.65); border:1px solid var(--line);
  border-left:3px solid var(--faint); border-radius:10px;
  padding:.6rem .85rem; margin:-.2rem 0 .7rem; }}

/* the answer */
.ans-head {{ font-family:"Figtree",sans-serif; font-size:1.3rem; font-weight:700;
  line-height:1.35; color:var(--ink); margin:.9rem 0 .5rem; max-width:80ch; }}
.ans-ev {{ margin:.2rem 0 .9rem 1.15rem; padding:0; }}
.ans-ev li {{ margin-bottom:.35rem; font-size:1rem; line-height:1.5; color:var(--fg2,var(--muted)); }}
.ans-ev li::marker {{ color:var(--teal); }}
/* the rows the agent nominated as its evidence */
.prooftbl {{ border:1px solid var(--line); border-radius:14px; overflow:hidden;
  background:var(--card); box-shadow:var(--shadow); margin:.2rem 0 .35rem; }}
.prooftbl table {{ width:100%; border-collapse:collapse; font-size:.86rem; }}
.prooftbl th {{ text-align:left; font-family:"JetBrains Mono",monospace; font-size:.6rem;
  letter-spacing:.1em; text-transform:uppercase; color:var(--muted); font-weight:700;
  padding:.5rem .8rem; background:rgba(8,18,38,.035);
  border-bottom:1px solid var(--line); white-space:nowrap; }}
.prooftbl td {{ padding:.45rem .8rem; border-bottom:1px solid var(--line);
  color:var(--ink); white-space:nowrap; }}
.prooftbl tbody tr:last-child td {{ border-bottom:0; }}
.prooftbl td:not(:first-child) {{ font-variant-numeric:tabular-nums; }}
.proof-note {{ font-size:.78rem; color:var(--faint); margin:0 0 1rem .1rem; }}
/* recommended action */
.actbox {{ border-radius:16px; border:1px solid var(--line); background:var(--card);
  box-shadow:var(--shadow); border-left:4px solid var(--teal);
  padding:.8rem 1.1rem .9rem; margin:.2rem 0 1rem; }}
.act-k {{ text-transform:uppercase; letter-spacing:.12em; font-size:.6rem; font-weight:700;
  color:var(--teal); margin-bottom:.4rem; }}
.act-list {{ margin:0 0 0 1.1rem; padding:0; }}
.act-list li {{ margin-bottom:.3rem; font-size:.95rem; line-height:1.5; color:var(--ink); }}
.cites-k {{ text-transform:uppercase; letter-spacing:.12em; font-size:.6rem; font-weight:700;
  color:var(--teal); margin:.4rem 0 .3rem; }}
.working {{ border-radius:14px; border:1px dashed var(--line); background:rgba(255,255,255,.55);
  padding:1rem 1.2rem; font-size:.95rem; color:var(--muted); text-align:center; }}

.auditbox {{ border-radius:16px; border:1px solid var(--line); background:rgba(255,255,255,.6);
  padding:.75rem 1rem .6rem; margin:.9rem 0 .4rem; }}
.audittbl {{ width:100%; border-collapse:collapse; font-size:.76rem;
  font-family:"JetBrains Mono",monospace; }}
.audittbl th {{ text-align:left; font-size:.58rem; letter-spacing:.1em; text-transform:uppercase;
  color:var(--faint); font-weight:700; padding:.25rem .6rem .3rem 0;
  border-bottom:1px solid var(--line); }}
.audittbl td {{ padding:.28rem .6rem .28rem 0; border-bottom:1px solid var(--line);
  color:var(--muted); white-space:nowrap; }}
.audittbl tbody tr:last-child td {{ border-bottom:0; }}
.audittbl .au-u {{ color:var(--teal); font-weight:700; }}
.audittbl .au-n {{ text-align:right; font-variant-numeric:tabular-nums; }}
.audittbl .au-q {{ white-space:normal; word-break:break-word; color:var(--blue-ink); }}
/* "where it ran" ledger */
.ran {{ width:100%; border-collapse:collapse; font-size:.95rem; margin-top:.3rem; }}
.ran td {{ padding:.6rem 0; border-bottom:1px solid var(--line); }}
.ran td:last-child {{ text-align:right; font-weight:600; }}
.ran tr:last-child td {{ border-bottom:0; }}
.ran .no {{ color:var(--faint); text-decoration:line-through; }}
.ran tr.hit td:last-child {{ color:var(--teal); font-weight:700; }}
@media (max-width:1200px) {{
  .rail {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
  .archrow {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
  .act-rail.seven {{ grid-template-columns:repeat(4,minmax(0,1fr)); }}
}}
.pagehead {{ display:flex; align-items:center; gap:.9rem; margin:0 0 .9rem .1rem; }}
.pagehead img {{ height:26px !important; width:auto !important;
  max-width:104px !important; }}
.pagehead .ph-t {{ font-size:.72rem; font-weight:700; letter-spacing:.14em;
  text-transform:uppercase; color:var(--faint); }}
/* ---------- clinical-trials demo: classes the fraud screen does not use ----- */
.section-shell {{ margin:.1rem 0 1rem; }}
.bigtitle {{ font-family:"Figtree",sans-serif; font-size:1.95rem; line-height:1.14;
  letter-spacing:-.03em; font-weight:800; margin:.15rem 0 .5rem; max-width:34ch; }}
.lede2 {{ font-size:1.02rem; line-height:1.68; color:var(--muted); max-width:78ch;
  margin-bottom:1.1rem; }}
.lede2 em {{ color:var(--ink); font-style:italic; }}
.duo {{ display:grid; grid-template-columns:1fr 1fr; gap:1.1rem; margin:.2rem 0 1rem; }}
.dcard {{ border-radius:20px; border:1px solid var(--line); border-left:6px solid var(--teal);
  box-shadow:var(--shadow); padding:1.15rem 1.35rem; }}
.dcard.hard {{ border-left-color:var(--bad);
  background:linear-gradient(180deg, rgba(252,235,236,.85) 0%, rgba(255,252,252,.98) 100%); }}
.dcard.fix {{ border-left-color:var(--teal);
  background:linear-gradient(180deg, rgba(227,245,241,.85) 0%, rgba(252,255,254,.98) 100%); }}
.dcard .k {{ text-transform:uppercase; letter-spacing:.14em; font-size:.68rem; font-weight:700; }}
.dcard.hard .k {{ color:var(--bad-ink); }}
.dcard.fix .k {{ color:var(--teal-ink); }}
.dcard h3 {{ font-family:"Figtree",sans-serif; font-size:1.28rem; font-weight:700;
  letter-spacing:-.02em; margin:.35rem 0 .1rem; }}
.dcard p {{ font-size:.97rem; line-height:1.68; color:var(--ink); margin:.7rem 0 0; }}
.dcard code {{ font-family:"JetBrains Mono",monospace; font-size:.83rem; color:var(--teal-ink);
  background:var(--teal-soft); padding:.06rem .36rem; border-radius:5px; white-space:nowrap; }}
.dcard.hard code {{ color:var(--bad-ink); background:var(--bad-soft); }}
.triplet {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.9rem; margin-bottom:.4rem; }}
.tri {{ border-radius:16px; border:1px solid var(--line); background:var(--card);
  box-shadow:var(--shadow); padding:.85rem 1.05rem; }}
.tri .k {{ text-transform:uppercase; letter-spacing:.13em; font-size:.64rem; font-weight:700;
  color:var(--teal-ink); }}
.tri .t {{ font-size:.92rem; color:var(--muted); margin-top:.3rem; line-height:1.52; }}
.painrow {{ display:grid; grid-template-columns:1fr 1fr; gap:.85rem; margin:.4rem 0; }}
.pain {{ border-radius:18px; border:1px solid var(--line); background:var(--card);
  box-shadow:var(--shadow); padding:.95rem 1.05rem; }}
.pain .who {{ text-transform:uppercase; letter-spacing:.12em; font-size:.62rem;
  font-weight:700; color:var(--muted); }}
.pain .q {{ font-family:"Figtree",sans-serif; font-size:1.05rem; font-weight:700;
  margin-top:.2rem; line-height:1.3; }}
.pain .a {{ font-size:.88rem; color:var(--muted); margin-top:.3rem; line-height:1.5; }}
.pain.blocked {{ border-left:4px solid var(--bad); }}
.pain.solved {{ border-left:4px solid var(--teal); }}
.lanex {{ border-radius:18px; border:1px solid var(--line); background:var(--card);
  box-shadow:var(--shadow); padding:.9rem 1.1rem; margin-bottom:.6rem;
  border-left:5px solid var(--teal); }}
.lanex.b, .lanex.c {{ border-left-color:var(--amber); }}
.lanex.q {{ border-left-color:var(--blue); background:linear-gradient(180deg,
  rgba(226,244,255,.55) 0%, rgba(255,255,255,.98) 100%); }}
.lanex .tag {{ font-family:"JetBrains Mono",monospace; font-size:.66rem; font-weight:700;
  letter-spacing:.14em; text-transform:uppercase; color:var(--teal-ink); }}
.lanex.b .tag, .lanex.c .tag {{ color:var(--amber-ink); }}
.lanex.q .tag {{ color:var(--blue-ink); }}
.lanex p {{ margin:.35rem 0 0; font-size:.95rem; line-height:1.65; color:var(--muted); }}
.lanex b {{ color:var(--ink); font-weight:600; }}
.cmp {{ width:100%; border-collapse:collapse; font-size:.86rem; }}
.cmp th {{ text-align:left; font-size:.62rem; text-transform:uppercase; letter-spacing:.12em;
  color:var(--muted); border-bottom:1px solid var(--line); padding:.45rem .6rem; font-weight:700; }}
.cmp td {{ padding:.5rem .6rem; border-bottom:1px solid var(--line); vertical-align:top;
  color:var(--muted); line-height:1.45; }}
.cmp td.l {{ color:var(--ink); font-weight:600; white-space:nowrap; }}
.cmp td.m {{ font-family:"JetBrains Mono",monospace; color:var(--teal-ink); font-size:.8rem; }}
.evid {{ border-radius:14px; border:1px solid var(--line); background:rgba(255,255,255,.8);
  padding:.7rem .9rem; margin-bottom:.45rem; }}
.evid .k {{ text-transform:uppercase; letter-spacing:.12em; font-size:.6rem; font-weight:700;
  color:var(--teal-ink); }}
.evid .v {{ font-family:"JetBrains Mono",monospace; font-size:.82rem; color:var(--ink);
  margin-top:.2rem; word-break:break-word; }}
.verdictbox {{ border-radius:18px; padding:.9rem 1.1rem; margin-top:.5rem;
  border:1px solid var(--line); border-left:5px solid var(--teal);
  background:linear-gradient(180deg, rgba(227,245,241,.8) 0%, rgba(252,255,254,.98) 100%); }}
.verdictbox.bad {{ border-left-color:var(--bad);
  background:linear-gradient(180deg, rgba(252,235,236,.8) 0%, rgba(255,252,252,.98) 100%); }}
.verdictbox .k {{ text-transform:uppercase; letter-spacing:.13em; font-size:.64rem;
  font-weight:700; color:var(--teal-ink); }}
.verdictbox.bad .k {{ color:var(--bad-ink); }}
.verdictbox .t {{ font-size:.95rem; line-height:1.6; margin-top:.3rem; }}
.bignum {{ font-family:"Figtree",sans-serif; font-size:2.6rem; font-weight:800;
  line-height:1; letter-spacing:-.03em; }}
.bignum.bad {{ color:var(--bad-ink); }}
.bignum.good {{ color:var(--teal-ink); }}
.step {{ border-radius:12px; border:1px solid var(--line); background:rgba(255,255,255,.82);
  padding:.6rem .8rem; margin-bottom:.45rem; }}
.step.think {{ border-left:4px solid var(--muted); background:rgba(244,247,251,.8); }}
.step.tool {{ border-left:4px solid var(--teal); }}
.step .n {{ font-family:"JetBrains Mono",monospace; font-size:.64rem; font-weight:700;
  letter-spacing:.12em; text-transform:uppercase; color:var(--teal-ink); }}
.step .r {{ font-family:"JetBrains Mono",monospace; font-size:.73rem; color:var(--muted);
  margin-top:.3rem; word-break:break-word; }}
/* walkthrough mode: one idea per screen, read from the back of the room */
.stg {{ min-height:64vh; display:flex; flex-direction:column; justify-content:center;
  padding:1rem 0 2rem; }}
.stg .kick {{ font-family:"JetBrains Mono",monospace; font-size:1rem; font-weight:700;
  letter-spacing:.22em; text-transform:uppercase; color:var(--teal-ink); margin-bottom:.9rem; }}
.stg .big {{ font-family:"Figtree",sans-serif; font-size:clamp(2.4rem,5.1vw,4.3rem);
  font-weight:800; line-height:1.04; letter-spacing:-.035em; max-width:20ch; margin:0; }}
.stg .big em {{ font-style:normal; color:var(--teal-ink); }}
.stg .big s {{ text-decoration:none; color:var(--bad-ink); }}
.stg .sub {{ font-size:clamp(1.15rem,1.7vw,1.5rem); line-height:1.5; color:var(--muted);
  max-width:52ch; margin-top:1.1rem; }}
.stg .nums {{ display:flex; gap:3.2rem; flex-wrap:wrap; margin-top:2rem; }}
.stg .num .v {{ font-family:"Figtree",sans-serif; font-size:clamp(2.6rem,6vw,4.6rem);
  font-weight:800; line-height:1; letter-spacing:-.03em; font-variant-numeric:tabular-nums; }}
.stg .num .k {{ font-size:.95rem; text-transform:uppercase; letter-spacing:.13em;
  color:var(--muted); margin-top:.35rem; }}
.stg .num.bad .v {{ color:var(--bad-ink); }}
.stg .num.good .v {{ color:var(--teal-ink); }}
.stg .quote {{ font-family:"JetBrains Mono",monospace; font-size:clamp(1rem,1.5vw,1.3rem);
  line-height:1.6; background:rgba(255,255,255,.75); border:1px solid var(--line);
  border-left:5px solid var(--teal); border-radius:14px; padding:1rem 1.2rem; margin-top:1.4rem;
  max-width:62ch; }}
.stg .quote.bad {{ border-left-color:var(--bad); background:var(--bad-soft); }}
.stgbar {{ display:flex; gap:.4rem; margin:.2rem 0 1rem; }}
.stgdot {{ height:5px; flex:1; border-radius:3px; background:rgba(8,18,38,.12); }}
.stgdot.on {{ background:var(--teal); }}
@media (max-width:1100px) {{
  .duo, .triplet, .painrow {{ grid-template-columns:1fr; }}
}}
</style>
"""

# Belt and braces: with no blank lines there is no boundary for a markdown parser
# to end the HTML block on, whatever rule it implements. The source above stays
# readable; only what is injected is collapsed.
CSS = "\n".join(line for line in _SHEET.splitlines() if line.strip())
