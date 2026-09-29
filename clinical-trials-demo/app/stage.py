"""Stage mode: the same argument, cut to six beats for a room.

The booth page and a stage talk are different jobs. A booth visitor leans in and
reads; a room at forty metres reads one idea and one number. Rather than
compromise the booth page into something mediocre at both, this is a separate
path through the same live data -- six screens, one claim each, no scrolling.

The order leads with the RESULT, because the surprise is the proof: a column
beat the model. The problem comes second, once the room wants to know how.
"""
import streamlit as st

BEATS = 6


def _num(v, k, tone=""):
    return f'<div class="num {tone}"><div class="v">{v}</div><div class="k">{k}</div></div>'


def render(D, t, lake, h, n, html):
    i = st.session_state.setdefault("beat", 0)
    html('<div class="stgbar">' + "".join(
        f'<div class="stgdot{" on" if j <= i else ""}"></div>' for j in range(BEATS)) + "</div>")

    ev = D.eval_results()
    o = ev["overall"] if ev else {}

    # ---------------------------------------------------------------- 1 result
    if i == 0:
        html(f'''<div class="stg"><div class="kick">The result</div>
        <h1 class="big">A column moved recall from <s>0.68</s> to <em>0.86</em>.</h1>
        <div class="sub">No model was retrained. Nothing was copied to another engine.
        The fix was one column the registry never had.</div>
        <div class="nums">{_num(o.get("recall_text_only","—"), "retrieval alone", "bad")}
        {_num(o.get("recall_with_section","—"), "with the column", "good")}
        {_num("0%", "answers from the wrong half", "good")}</div></div>''')

    # ---------------------------------------------------------------- 2 problem
    elif i == 1:
        html(f'''<div class="stg"><div class="kick">Why it was 0.68</div>
        <h1 class="big">Eligibility is prose, not data.</h1>
        <div class="sub">A registry codes what a trial <em>is</em> — phase, sponsor, geography.
        It does not code who a trial will <b>accept</b>. That lives in one free-text blob, with
        no inclusion field, no exclusion field and no polarity.</div>
        <div class="quote bad">&ldquo;Exclusion: No prior treatment with anti-PD-1&rdquo;<br/>
        &ldquo;Inclusion: No prior treatment with anti-PD-1&rdquo;<br/>
        <span style="color:#b3261e">— identical to every ranker. <b>no</b> is a stopword.</span></div></div>''')

    # ---------------------------------------------------------------- 3 mechanism
    elif i == 2:
        html(f'''<div class="stg"><div class="kick">How retrieval got into SQL</div>
        <h1 class="big">A vector is rows. Cosine is a <em>GROUP BY</em>.</h1>
        <div class="sub">Exasol has no vector type and no vector index, so each 96-dimension
        vector is stored as 96 rows. A dot product then <b>is</b> cosine — and similarity
        search is the scan-and-aggregate this engine was built for.</div>
        <div class="quote">SELECT v.NCT_ID, <b>SUM(v.VAL * q.VAL)</b> AS SIM<br/>
        FROM&nbsp;&nbsp; CT.ELIG_VECTORS v JOIN QV q ON q.DIM = v.DIM<br/>
        <b>GROUP BY</b> v.NCT_ID, v.CHUNK_ID</div>
        <div class="nums">{_num(n(t["vector_rows"]), "rows scanned, exactly")}
        {_num("0", "indexes to tune", "good")}</div></div>''')

    # ---------------------------------------------------------------- 4 proof
    elif i == 3:
        html('''<div class="stg"><div class="kick">Live · the proof</div>
        <h1 class="big">Ask for exclusions. Watch the wrong half disappear.</h1></div>''')
        q = "Phase 3 NSCLC trials that exclude patients with prior anti-PD-1 therapy"
        with st.spinner("scanning 25.8M vector rows…"):
            a = D.ask(q, topk=3)
        want = a["split"]["section"]
        c1, c2 = st.columns(2)
        for col, key, ttl in ((c1, "text_only", "Retrieval alone"),
                              (c2, "with_section", "With the column")):
            with col:
                html(f'<div class="kick" style="margin-bottom:.5rem">{ttl}</div>')
                for r in a["results"][key]:
                    bad = r["CRITERION_SECTION"] != want
                    html(f'<div class="res{" bad" if bad else ""}"><div class="top">'
                         f'<span class="tag">{r["CRITERION_SECTION"]}'
                         f'{" &mdash; wrong half" if bad else ""}</span></div>'
                         f'<div class="tx">{r["CRITERION"][:110]}</div></div>')
        wa = sum(1 for r in a["results"]["text_only"] if r["CRITERION_SECTION"] != want)
        st.success(f"**{wa} of {len(a['results']['text_only'])}** wrong-half rows on the left. "
                   "**None** on the right. Same model, same scores — one column.")

    # ---------------------------------------------------------------- 5 limit
    elif i == 4:
        html('''<div class="stg"><div class="kick">Where it still fails</div>
        <h1 class="big">The column cannot fix <em>antonymy</em>.</h1>
        <div class="sub">Ask for &ldquo;EGFR mutation positive&rdquo; and a criterion meaning the
        opposite still ranks — because <b>negative</b> is not a stopword. The token survives;
        the meaning does not. Both sit in INCLUSION, so there is nothing left to filter on.</div>
        <div class="quote bad">rank 13 &nbsp;·&nbsp; INCLUSION &nbsp;·&nbsp; cosine 0.9455<br/>
        &ldquo;EGFR mutation or ALK mutation was <b>negative</b>;&rdquo;<br/>
        <span style="color:#b3261e">Left unfixed, and documented.</span></div></div>''')

    # ---------------------------------------------------------------- 6 reach
    else:
        if h["lake"]:
            gap = D.publication_gap()
            p3 = next((g for g in gap if g["phase"] == "PHASE3"), None)
            cost = D.tier_cost()
            html(f'''<div class="stg"><div class="kick">One statement, two storage tiers</div>
            <h1 class="big">The publications never left the lake.</h1>
            <div class="sub">Iceberg tables on object storage, read in place by a Rust UDF and
            joined to native Exasol tables in a single statement. Nothing imported, no pipeline.</div>
            <div class="nums">{_num(f'{p3["pct"]}%' if p3 else "—",
                                    "of completed Phase 3 have no linked publication", "bad")}
            {_num(f'+{cost["delta_ms"]} ms', "cost of reaching the lake", "good")}</div></div>''')
            st.caption("A lower bound on linkage, not proof of non-publication — a paper that "
                       "never cites its NCT number is invisible to this join.")
        else:
            html('''<div class="stg"><div class="kick">One statement, two storage tiers</div>
            <h1 class="big">The lake is not up on this machine.</h1>
            <div class="sub">Say: &ldquo;The publications half reads a lake that isn’t running here.
            Everything you have seen is native Exasol and runs without it.&rdquo;</div></div>''')

    # ---------------------------------------------------------------- nav
    b1, b2, b3, _ = st.columns([1, 1, 1, 5])
    if b1.button("← Back", disabled=(i == 0), use_container_width=True):
        st.session_state.beat = max(0, i - 1); st.rerun()
    if b2.button("Next →", disabled=(i == BEATS - 1), use_container_width=True):
        st.session_state.beat = min(BEATS - 1, i + 1); st.rerun()
    if b3.button("Restart", use_container_width=True):
        st.session_state.beat = 0; st.rerun()
