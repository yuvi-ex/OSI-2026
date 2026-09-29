"""
Kafka to SQL -- real-time analytics on an event stream, with Exasol.

    ./.venv/bin/streamlit run story_demo/app.py --server.port 8502

Three pages:
  1. The challenge -- why SQL over a stream is hard, and how Exasol closes it
  2. Live          -- fire events, see them on the Kafka topic, query them as SQL
  3. How it works  -- the architecture, and what this demo will not claim

Run story_demo/seed_story_persona.py once before first use.
"""
import base64
import json
import math
import re
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P
import story as S
import chapters as C
import architecture as ARCH
import agent as AG
from theme import CSS

st.set_page_config(page_title="Kafka to SQL — Exasol", layout="wide",
                   initial_sidebar_state="collapsed")


def html(fragment: str, target=st) -> None:
    """Collapse blank lines so Streamlit's markdown pass cannot end the HTML block."""
    target.markdown("\n".join(l for l in fragment.splitlines() if l.strip()),
                    unsafe_allow_html=True)


html(CSS)


def _logo(variant: str = "dark") -> str:
    """Exasol's official 2025 mark, inlined so the page needs no network."""
    f = Path(__file__).resolve().parent / "assets" / f"exasol_logo_{variant}.svg"
    try:
        b64 = base64.b64encode(f.read_bytes()).decode()
        return (f'<img src="data:image/svg+xml;base64,{b64}" alt="Exasol" '
                f'width="104" height="26" '
                f'style="height:26px;width:auto;max-width:104px;display:block;"/>')
    except Exception:
        return ""

STAGES = [("postgres", "PostgreSQL", "row committed"),
          ("kafka", "Debezium + Kafka", "change captured"),
          ("raw", "Exasol RAW", "merged"),
          ("features", "Exasol ANALYTICS", "features built"),
          ("score", "Python UDF", "scored")]

MCCS = [("5812", "Restaurants / cafes", 0.05), ("5411", "Groceries", 0.05),
        ("5541", "Fuel", 0.08), ("5045", "Electronics", 0.20),
        ("5999", "General retail", 0.20), ("5816", "Digital goods", 0.30),
        ("4511", "Airlines", 0.15), ("7011", "Hotels", 0.15),
        ("4829", "Wire transfer", 0.60), ("6051", "Currency exchange", 0.65),
        ("5933", "Pawn shops", 0.70), ("7995", "Gambling", 0.75)]

# Without these, every button click re-probes PostgreSQL, Kafka and Exasol
# synchronously before the hero renders -- which is why hero tiles came back
# blank after firing an event. Short TTLs keep the page live; the cache is
# cleared explicitly whenever we change the data ourselves.
@st.cache_data(ttl=30, show_spinner=False)
def cached_health():
    return P.connection_health()


@st.cache_data(ttl=10, show_spinner=False)
def cached_topic_stats():
    return P.topic_stats()


@st.cache_data(ttl=5, show_spinner=False)
def cached_tail(n: int):
    return P.topic_tail(n)


@st.cache_data(ttl=5, show_spinner=False)
def cached_scored(n: int):
    return P.scored_rows(n)


ss = st.session_state
ss.setdefault("last_run", None)
ss.setdefault("fired", 0)
ss.setdefault("health", None)
ss.setdefault("persona", "us")
ss.setdefault("agent_steps", None)


# ------------------------------------------------------------------ fragments
def rail(states: dict) -> str:
    out = []
    for key, sysname, what in STAGES:
        s = states.get(key, {})
        cls, ms = s.get("state", ""), s.get("ms")
        val = (f'{ms:,.0f}<small>ms</small>' if ms is not None
               else ("&middot;&middot;&middot;" if cls == "run" else "&mdash;"))
        out.append(f'<div class="stg {cls}"><div class="sys">{sysname}</div>'
                   f'<div class="what">{what}</div><div class="ms">{val}</div></div>')
    return '<div class="rail">' + "".join(out) + "</div>"


def verdict(r) -> str:
    cls = {"APPROVE": "v-approve", "REVIEW": "v-review", "BLOCK": "v-block"}[r.verdict]
    word = {"APPROVE": "APPROVED", "REVIEW": "REVIEW", "BLOCK": "BLOCKED"}[r.verdict]
    return (f'<div class="runlabel">Showing: {r.label}</div>'
            f'<div class="verdict {cls}"><div class="word">{word}</div>'
            f'<div class="m">fraud probability<b>{r.score:.5f}</b></div>'
            f'<div class="m">end to end<b>{r.total_ms/1000:.1f}s</b></div>'
            f'<div class="m">kafka offset<b>{r.kafka_offset}</b></div></div>')


def kpis(f: dict) -> str:
    yes = lambda x: str(x).upper() in ("TRUE", "1")
    items = [
        ("Amount", f"${float(f['AMOUNT_USD']):,.2f}", "this transaction", False),
        ("vs normal spend", f"{float(f['AMOUNT_VS_AVG_RATIO']):,.1f}x",
         "against a 30-day average", float(f['AMOUNT_VS_AVG_RATIO']) >= 5),
        ("Transactions this hour", f"{f['TXN_COUNT_1H']}", "she averages two a day",
         int(f['TXN_COUNT_1H']) >= 3),
        ("Merchant risk", f"{float(f['MCC_BASE_RISK']):.2f}", "category base weight",
         float(f['MCC_BASE_RISK']) >= 0.5),
        ("New country", "YES" if yes(f['IS_NEW_COUNTRY_30D']) else "no",
         "first time in 30 days", yes(f['IS_NEW_COUNTRY_30D'])),
        ("New device", "YES" if yes(f['IS_NEW_DEVICE_30D']) else "no",
         "unrecognised hardware", yes(f['IS_NEW_DEVICE_30D'])),
    ]
    return '<div class="kpi-grid">' + "".join(
        f'<div class="kpi{" hot" if hot else ""}"><div class="k">{k}</div>'
        f'<div class="v">{v}</div><div class="x">{x}</div></div>'
        for k, v, x, hot in items) + "</div>"


def section(kicker, title, copy="") -> str:
    return (f'<div class="section-kicker">{kicker}</div>'
            f'<div class="section-title">{title}</div>'
            + (f'<div class="section-copy">{copy}</div>' if copy else ""))


_ICONS = {
    "db": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/>'
          '<path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "stream": '<path d="M3 7h13l-3-3M21 17H8l3 3M3 12h18"/>',
    "cube": '<path d="M12 2l9 5v10l-9 5-9-5V7z"/><path d="M3 7l9 5 9-5M12 12v10"/>',
    "shield": '<path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
}
MCC_RISK = {m: r for m, _d, r in MCCS}


def _icon(name: str) -> str:
    return (f'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{_ICONS[name]}</svg>')


def flow_strip() -> str:
    """The whole pipeline as four pills -- replaces a paragraph of prose."""
    nodes = [("db", "PostgreSQL", "row written"), ("stream", "Kafka", "change event"),
             ("cube", "Exasol", "+30 days of context"), ("shield", "Decision", "scored in SQL")]
    return '<div class="flow">' + '<span class="farrow">&rarr;</span>'.join(
        f'<div class="fnode{" hl" if i == 3 else ""}"><div class="ic">{_icon(ic)}</div>'
        f'<div><div class="t">{t}</div><div class="s">{s}</div></div></div>'
        for i, (ic, t, s) in enumerate(nodes)) + "</div>"


def col_head(icon: str, title: str, chips) -> str:
    """Column header as icon + title + chips of what that side can see."""
    c = "".join(f'<span class="chip {k}">{t}</span>' for k, t in chips)
    return (f'<div class="colhead"><div class="fnode" style="padding:.25rem .7rem .25rem .3rem">'
            f'<div class="ic">{_icon(icon)}</div><div class="ttl">{title}</div></div>{c}</div>')


def _tone(x: float, mid: float, hi: float) -> str:
    return "hi" if x >= hi else ("mid" if x >= mid else "")


def bar(value: float, frac: float, label: str, tone: str) -> str:
    frac = max(0.03, min(1.0, frac))
    return (f'<div class="bar"><span>{label}</span><div class="trk">'
            f'<div class="fil {tone}" style="width:{frac * 100:.0f}%"></div></div></div>')


def kafka_events(events) -> str:
    if not events:
        return ('<div class="res"><div class="tx">No events on the topic yet. '
                'Fire one above.</div></div>')
    out = []
    for e in events:
        pl = e["payload"] or {}
        op = {"c": "INSERT", "u": "UPDATE", "d": "DELETE", "r": "SNAPSHOT"}.get(e["op"], e["op"] or "?")
        amt = pl.get("amount")
        try:
            amt = f"${float(amt):,.2f}"
        except (TypeError, ValueError):
            amt = "—"
        bad = e["op"] == "d"
        risk = _tone(MCC_RISK.get(str(pl.get("merchant_mcc", "")), 0), 0.3, 0.6)
        out.append(
            f'<div class="res{" bad" if bad else ""}"><div class="top">'
            f'<span class="tx" style="margin:0"><span class="risk {risk}"></span>'
            f'<b>{amt}</b> &nbsp;{pl.get("merchant_name","")}</span>'
            f'<span class="sim">{pl.get("channel","")} &middot; {pl.get("country_code","")}'
            f' &middot; p{e["partition"]}:{e["offset"]} &middot; {op}</span></div></div>')
    return "".join(out)


def sql_table(rows) -> str:
    """
    The result grid.

    Columns are named for what they mean, not what the schema calls them, and
    the DECISION column is computed by the query itself -- which is the point:
    the rule that blocks a payment is SQL, not application code.
    """
    head = ("<tr><th>merchant</th><th>amount</th><th>txns<br>last hour</th>"
            "<th>vs 30-day<br>average</th><th>merchant<br>risk</th>"
            "<th>fraud<br>score</th><th>decision</th></tr>")
    body = []
    for merchant, amount, n1h, ratio, mrisk, score, decision in rows:
        score, ratio, mrisk = float(score), float(ratio), float(mrisk)
        cls = {"BLOCK": "hot", "REVIEW": "warn"}.get(decision, "")
        pill = {"BLOCK": "d-block", "REVIEW": "d-review"}.get(decision, "d-approve")
        tone = {"BLOCK": "hi", "REVIEW": "mid"}.get(decision, "")
        # Log scale: 1x is a sliver, ~300x fills the track.
        rfrac = math.log10(max(ratio, 1)) / math.log10(300)
        body.append(
            f'<tr class="{cls}">'
            f'<td class="merch">{merchant}</td>'
            f'<td class="num">${float(amount):,.2f}</td>'
            f'<td class="num">{n1h}</td>'
            f'<td class="num">{bar(ratio, rfrac, f"{ratio:,.1f}x", _tone(ratio, 5, 50))}</td>'
            f'<td class="num">{bar(mrisk, mrisk, f"{mrisk:.2f}", _tone(mrisk, 0.3, 0.6))}</td>'
            f'<td class="num score">{bar(score, score, f"{score:.2f}", tone)}</td>'
            f'<td><span class="pill-d {pill}">{decision}</span></td></tr>')
    if not body:
        body.append('<tr><td colspan="7" class="empty">Nothing scored yet — '
                    'fire an event above.</td></tr>')
    return f'<table class="restab">{head}{"".join(body)}</table>'


def run_with_rail(placeholder, amount, merchant, mcc, channel, country, city, device):
    states: dict = {}
    html(rail(states), placeholder)

    def on_stage(name, state, ms=None):
        states[name] = {"state": "run" if state == "running" else "done", "ms": ms}
        html(rail(states), placeholder)

    r = P.run_event(amount, merchant, mcc, channel, country, city, device,
                    on_stage=on_stage)
    ss.fired += 1
    st.cache_data.clear()   # we just changed the data; let the panels re-read
    return r


# ------------------------------------------------------------------ hero
if ss.health is None:
    ss.health = cached_health()
h = ss.health
tstats = cached_topic_stats()
last_ms = f"{ss.last_run.total_ms/1000:.1f}s" if ss.last_run else "3.3s"
ana_ms = (f"{ss.last_run.analytics_ms:.0f} ms of that is the analytics \u2014 merge, "
          f"features and scoring. The rest is one-off connector startup."
          if ss.last_run else
          "About 0.6s of that is the analytics. The rest is one-off connector startup.")

html(f'<div class="pagehead">{_logo()}'
     f'<span class="ph-t">Kafka to SQL \u00b7 live demo</span></div>')

html(f'''
<div class="hero-shell">
  <div class="hero-eyebrow">Kafka to SQL &middot; live demo</div>
  <div class="hero-title">Streaming in. Querying out.</div>
  <div class="hero-copy">Event-driven systems capture everything in real time and make it
  hard to ask anything. This demo takes a card payment from PostgreSQL, through Debezium
  and Kafka, into Exasol &mdash; where it is landed, enriched against thirty days of history
  and scored by a model, all in SQL. Every number on this page is read live.</div>
  <div class="signal-grid">
    <div class="signal-card{'' if h['postgres']['ok'] else ' down'}">
      <div class="signal-label">PostgreSQL</div>
      <div class="signal-value">{'Connected' if h['postgres']['ok'] else 'Down'}</div>
      <div class="signal-meta">Source of truth, captured by Debezium</div></div>
    <div class="signal-card{'' if tstats['ok'] else ' down'}">
      <div class="signal-label">Kafka topic</div>
      <div class="signal-value">{tstats['messages'] if tstats['ok'] else 'Down'} events</div>
      <div class="signal-meta">{tstats['partitions']} partitions, Avro with Schema Registry</div></div>
    <div class="signal-card{'' if h['exasol']['ok'] else ' down'}">
      <div class="signal-label">Exasol</div>
      <div class="signal-value">{'Connected' if h['exasol']['ok'] else 'Down'}</div>
      <div class="signal-meta">Consumes the topic, builds features, runs the model</div></div>
    <div class="signal-card">
      <div class="signal-label">End to end</div>
      <div class="signal-value">{last_ms}</div>
      <div class="signal-meta">{ana_ms}</div></div>
  </div>
</div>''')

p1, p2, p3, p4 = st.tabs(["1 · The challenge", "2 · Live — Kafka to SQL",
                          "3 · How it works", "4 · Agentic investigation"])


# ------------------------------------------------------------------ page 1
with p1:
    # The headline now lives inside the figure, so the page carries only the
    # kicker above it and the three summary cards below.
    html(f'<div class="section-kicker">{C.PAGE1["kicker"]}</div>')
    html('<div class="archbox">' + ARCH.problem_diagram() + "</div>")
    cards = "".join(
        f'<div class="tier"><div class="k">{k}</div><div class="d">{d}</div></div>'
        for k, d in C.PAGE1["points"])
    html(f'<div class="archrow three">{cards}</div>')

# ------------------------------------------------------------------ page 2
with p2:
    html(section("Live", "Fire an event, then query it as SQL"))
    html(flow_strip())
    b1, b2, b3, _sp, b4 = st.columns([3, 3, 2, 3, 2])
    with b1:
        normal = st.button("Ordinary purchase", use_container_width=True, key="fn")
    with b2:
        fraud = st.button("Suspicious transaction", use_container_width=True,
                          type="primary", key="ff")
    with b3:
        refresh = st.button("Refresh", use_container_width=True, key="fr")
    with b4:
        rst = st.button("Reset data", use_container_width=True, key="rs")

    holder = st.empty()

    if rst:
        with st.spinner("Rewinding…"):
            removed, pruned = P.reset_story()
        ss.last_run, ss.fired = None, 0
        st.cache_data.clear()
        ss.health = cached_health()
        st.toast(f"Removed {removed} transactions, pruned {pruned} stale rows.")
        st.rerun()

    if normal:
        ss.last_run = run_with_rail(holder, 5.40, "Corner Coffee", "5812", "POS",
                                    "US", "Austin", P.HOME_DEVICE)
    elif fraud:
        ss.last_run = run_with_rail(holder, 8750.00, "LuckyBet Online", "7995",
                                    "ONLINE", "MT", "Valletta", S.FRAUD_DEVICE)
    elif ss.last_run is not None:
        html(rail({hp.name: {"state": "done", "ms": hp.ms} for hp in ss.last_run.hops}),
             holder)

    if ss.last_run is not None and ss.last_run.score is not None:
        html(verdict(ss.last_run))
        html(kpis(ss.last_run.features))

    st.write("")
    col_k, col_s = st.columns([1, 1.25])
    with col_k:
        html(col_head("stream", "Kafka sees",
                      [("", "amount"), ("", "merchant"), ("", "country"),
                       ("no", "history")]))
        html(kafka_events(cached_tail(6)))
    with col_s:
        html(col_head("cube", "Exasol knows",
                      [("add", "velocity"), ("add", "vs 30-day avg"),
                       ("add", "merchant risk"), ("add", "fraud score")]))
        sql, rows = cached_scored(8)
        html(sql_table(rows))
        with st.expander("Show the SQL"):
            # st.code keeps the line breaks and highlights the SQL; passing it
            # through markdown collapsed it into one wrapped paragraph.
            st.code(sql, language="sql")
            st.caption("Scores of exactly 1.00000 / 0.00000 are real: the logistic model "
                       "saturates on extreme features, and FRAUD_SCORE is DECIMAL(6,5).")

    with st.expander("Build your own transaction", expanded=True):
        with st.form("custom_form"):
            a, b, c = st.columns(3)
            with a:
                amount = st.number_input("Amount (USD)", 0.5, 500000.0, 4200.0, step=50.0)
                mcc_label = st.selectbox("Merchant category",
                                         [f"{m} · {d} (risk {r:.2f})" for m, d, r in MCCS],
                                         index=8)
            with b:
                merchant = st.text_input("Merchant", "FX Global Wire")
                channel = st.selectbox("Channel", ["ONLINE", "POS", "API", "MOBILE"], index=2)
            with c:
                country = st.selectbox("Country", ["US", "MT", "RU", "NG", "GB", "DE"], index=1)
                city = st.text_input("City", "Valletta")
            new_device = st.checkbox("Unrecognised device", value=True)
            go = st.form_submit_button("RUN IT THROUGH THE PIPELINE",
                                       use_container_width=True)
        if go:
            ph = st.empty()
            ss.last_run = run_with_rail(
                ph, amount, merchant, mcc_label.split(" · ")[0], channel, country, city,
                S.FRAUD_DEVICE if new_device else P.HOME_DEVICE)
            if ss.last_run.score is not None:
                html(verdict(ss.last_run))
                html(kpis(ss.last_run.features))


# ------------------------------------------------------------------ page 3
with p3:
    html(section(C.PAGE3["kicker"], C.PAGE3["title"], C.PAGE3["copy"]))
    # The four-phase journey: build it, stream it, score it, ask it. Every
    # snippet in it is the real statement, trimmed.
    html('<div class="archbox">' + ARCH.journey_diagram() + "</div>")

    links = " &nbsp;·&nbsp; ".join(
        f'<a href="{u}" target="_blank" rel="noopener">{t}</a>' for t, u in ARCH.DOC_LINKS)
    html(f'<div class="doclinks"><span class="dl-k">Official Exasol documentation</span>'
         f'{links}</div>')
    html(f'<div class="note-card"><div class="mini-kicker">The claim</div>'
         f'<p>{C.ARCH_NOTE}</p></div>')
    st.write("")
    l, r = st.columns([1.15, 1])
    with l:
        html(f'<div class="sol"><div class="lbl">Worth knowing</div>'
             f'<div class="big">The default settings make this 19x slower</div>'
             f'<p>{C.TUNING_NOTE}</p></div>')
    with r:
        if ss.last_run is not None and ss.last_run.score is not None:
            rows = "".join(
                f'<div class="barrow"><div class="lb">{n}</div>'
                f'<div class="tr"><div class="fl" style="width:'
                f'{min(100, hp.ms / max(x.ms for x in ss.last_run.hops) * 100):.0f}%">'
                f'</div></div><div class="vv">{hp.ms:,.0f} ms</div></div>'
                for hp, (_, n, _w) in zip(ss.last_run.hops, STAGES))
            html('<div class="section-kicker">Measured on the last run</div>'
                 f'<div class="bars">{rows}</div>')
        else:
            html('<div class="note-card"><div class="mini-kicker">No run yet</div>'
                 '<p>Fire an event on page 2 and the measured per-hop timings appear '
                 'here.</p></div>')

    st.write("")
    html(section("Stated up front", "What this demo will not claim"))
    for i in range(0, len(C.LIMITS), 2):
        cols = st.columns(2)
        for col, (title, body) in zip(cols, C.LIMITS[i:i + 2]):
            with col:
                html(f'<div class="chal"><div class="lbl">Limit</div>'
                     f'<div class="big">{title}</div><p>{body}</p></div>')


# ------------------------------------------------------------------ page 4
def _proof_table(proof) -> str:
    """The rows the agent nominated as its evidence, rendered as a table."""
    if not proof or "columns" not in proof:
        return ""
    cols, rows = proof["columns"][:7], proof["rows"]

    def cell(v):
        if v is None:
            return "&mdash;"
        t = str(v)
        if t.replace(".", "", 1).replace("-", "", 1).isdigit():
            try:
                f = float(t)
                return f"{f:,.2f}" if "." in t else f"{int(f):,}"
            except ValueError:
                pass
        return t[:38] + ("\u2026" if len(t) > 38 else "")

    head = "".join(f"<th>{c}</th>" for c in cols)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell(c)}</td>" for c in r[:7]) + "</tr>"
        for r in rows[:20])
    return (f'<div class="prooftbl"><table><thead><tr>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def answer_html(steps):
    """
    Answer first, then the rows, then the statement that produced them.

    Returns (html, evidence_sql, all_queries) so the caller can render the SQL
    with Streamlit's own highlighter rather than as flat text.
    """
    conclusion = next((s for s in steps if s.kind == "conclusion"), None)
    queries = [s for s in steps if s.kind == "tool"
               and s.tool == "execute_exasol_query" and not s.error and s.sql]

    if conclusion is None:
        err = next((s.text for s in steps if s.kind == "error"), "No conclusion.")
        return (f'<div class="chal"><div class="lbl">No answer</div>'
                f'<div class="big">The investigation did not conclude</div>'
                f'<p>{err}</p></div>', "", queries)

    d = conclusion.payload
    tone = {"CONFIRMED_FRAUD": "v-block", "LIKELY_FRAUD": "v-block",
            "INCONCLUSIVE": "v-review", "NOTHING_VISIBLE": "v-review",
            "LIKELY_LEGITIMATE": "v-approve"}.get(d.get("verdict", ""), "v-review")

    findings = "".join(f"<li>{f}</li>" for f in d.get("findings", []))
    actions = "".join(f"<li>{a}</li>" for a in d.get("actions", []))
    proof = d.get("_proof")
    table = _proof_table(proof)
    nrows = len(proof["rows"]) if proof and "rows" in proof else 0

    html_out = (
        f'<div class="verdict {tone}">'
        f'<div class="word" style="font-size:1.9rem">'
        f'{d.get("verdict","").replace("_"," ")}</div>'
        f'<div class="m">confidence<b>{d.get("confidence","")}</b></div>'
        f'<div class="m">statements run<b>{len(queries)}</b></div></div>'
        f'<div class="ans-head">{d.get("headline","")}</div>'
        f'<ul class="ans-ev">{findings}</ul>'
        + table
        + (f'<div class="proof-note">{nrows} row(s), returned by the statement below'
           f'</div>' if table else "")
        + (f'<div class="actbox"><div class="act-k">Recommended action</div>'
           f'<ol class="act-list">{actions}</ol></div>' if actions else "")
    )
    return html_out, d.get("evidence_sql", ""), queries


def audit_panel(persona) -> str:
    """
    The analyst's own audit trail, read back THROUGH the persona's own MCP
    session -- so the page is showing what that user is entitled to see of the
    log, not what SYS can see of it.
    """
    txt, err = AG.M.call_tool(persona, "execute_exasol_query", {"query":
        "SELECT ASKED_AT, DB_USER, ROWS_RETURNED, SQL_TEXT "
        "FROM FRAUD_DEMO.V_MY_AUDIT ORDER BY ASKED_AT DESC LIMIT 6"})
    if err:
        return ""
    try:
        d = json.loads(txt)
    except Exception:
        return ""
    if not d.get("rows"):
        return ""
    body = "".join(
        f'<tr><td>{str(r[0])[11:19]}</td><td class="au-u">{r[1]}</td>'
        f'<td class="au-n">{int(r[2])}</td>'
        f'<td class="au-q">{" ".join(str(r[3]).split())[:78]}\u2026</td></tr>'
        for r in d["rows"])
    return (f'<div class="auditbox">'
            f'<div class="cites-k">Audit \u2014 this analyst\'s own calls, read back as '
            f'them. The log names the database user; the agent has no identity of its '
            f'own, and no write path to this table.</div>'
            f'<table class="audittbl"><thead><tr><th>time</th><th>user</th>'
            f'<th>rows</th><th>statement</th></tr></thead><tbody>{body}</tbody>'
            f'</table></div>')


def render_answer(steps, persona=None) -> None:
    body, evidence_sql, queries = answer_html(steps)
    html(body)
    if evidence_sql:
        html('<div class="cites-k">Citation &mdash; the statement that produced '
             'this answer, run as this analyst</div>')
        st.code(" ".join(evidence_sql.split()), language="sql")
    if persona is not None:
        html(audit_panel(persona))
    if queries:
        with st.expander(f"The agent ran {len(queries)} statements to get there"):
            for i, qy in enumerate(queries, 1):
                rows = len(qy.table()[1] or [])
                st.caption(f"[{i}]  {rows} rows · {qy.ms:,.0f} ms")
                st.code(" ".join(qy.sql.split()), language="sql")


with p4:
    html(section("Agentic investigation",
                 "Same agent. Same question. Different identity.",
                 "The agent has no database credential of its own. It reaches Exasol "
                 "through the official MCP server, which authenticates as a <b>persona</b> "
                 "\u2014 a real database user holding SELECT on two row-filtered views and "
                 "nothing else. What the agent can see is decided by a GRANT, not by a "
                 "prompt."))

    pcols = st.columns(len(AG.M.PERSONAS))
    for col, persona in zip(pcols, AG.M.PERSONAS):
        with col:
            on = ss.get("persona", "us") == persona.key
            if st.button(persona.title, use_container_width=True,
                         type="primary" if on else "secondary",
                         key=f"p_{persona.key}"):
                ss.persona = persona.key
                ss.agent_steps = None
                st.rerun()

    current = AG.M.BY_KEY[ss.get("persona", "us")]
    html(f'<div class="idcard"><div class="id-k">Connected as</div>'
         f'<div class="id-u">{current.db_user}</div>'
         f'<div class="id-b">{current.blurb}</div></div>')

    labels = [lbl for lbl, _ in AG.QUESTIONS] + ["Write my own\u2026"]
    qc1, qc2 = st.columns([5, 2], vertical_alignment="bottom")
    with qc1:
        chosen = st.selectbox("The question", labels, key="agentqpick")
    with qc2:
        ask = st.button("ASK AS THIS ANALYST", use_container_width=True,
                        type="primary", key="agentgo")

    if chosen == labels[-1]:
        q = st.text_area("Your question", AG.DEFAULT_QUESTION, height=90, key="agentq")
    else:
        q = dict(AG.QUESTIONS)[chosen]
        html(f'<div class="qpreview">{q}</div>')

    slot = st.empty()

    if ask:
        seen = []

        def on_step(stp):
            seen.append(stp)
            n = sum(1 for x in seen if x.kind == "tool")
            # A one-line pulse, not the trace. Sixty seconds of a blank screen is
            # worse on stage than sixty seconds of a counter.
            html(f'<div class="working">Working\u2026 {n} quer'
                 f'{"y" if n == 1 else "ies"} so far</div>', slot)

        try:
            AG.investigate(current, question=q, on_step=on_step)
            ss.agent_steps = seen
            slot.empty()
            render_answer(seen, current)
        except Exception as exc:
            msg = str(exc)
            if "credit balance" in msg.lower():
                st.error("The Anthropic API key has no credit. Add credit at "
                         "console.anthropic.com \u2192 Plans & Billing, then try again.")
            elif "api_key" in msg.lower() or "authentication" in msg.lower():
                st.error("No Anthropic API key. Add ANTHROPIC_API_KEY to .env and "
                         "restart Streamlit.")
            else:
                st.error(f"The agent failed: {msg[:300]}")
    elif ss.get("agent_steps"):
        render_answer(ss.agent_steps, current)
    else:
        html('<div class="howto"><b>What to watch:</b> ask a question, then switch '
             'persona above and ask the identical one. The answer changes because the '
             'rows are gone \u2014 not because the agent behaved differently.</div>')
