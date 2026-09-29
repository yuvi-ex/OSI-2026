"""Every number the story tells, fetched live.

Nothing on the screen is typed in by hand. If the corpus changes, the narration
changes with it -- which is the only way a claim on a booth screen stays true.

Cached, because a live demo cannot pay 300ms per tile on every rerun; the cache
is cleared by the Refresh control, not by a timer, so a number never changes
mid-sentence while someone is talking.
"""
import os, sys
import streamlit as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))
import exasql, split as qsplit, search           # noqa: E402

TTL = None          # never expire on a timer


def _one(sql, default=None):
    rows = exasql.rows(sql)
    return rows[0] if rows else default


def _vm_clock_skew():
    """Seconds between the Exasol VM's clock and this host's.

    Every S3 request is signed with the VM's clock. When the host sleeps, that
    clock FREEZES while the VM's hardware clock stays right -- and then the lake
    returns 403 PermissionDenied, which reads exactly like bad credentials and is
    not. Returns (skew_seconds, fix_command) or (None, None) if it cannot tell.
    """
    import glob, subprocess, time
    runtime = os.path.expanduser("~/.exasol/personal/deployments/default/local/runtime")
    hits = sorted(glob.glob(os.path.expanduser(
        "~/Library/Caches/.exasol/personal/runtime-artifacts/artifacts/"
        "exasol-local-runner/*/*/*/unpack/launcher")), key=os.path.getmtime, reverse=True)
    if not hits or not os.path.exists(os.path.join(runtime, "vm-runtime.json")):
        return None, None
    try:
        out = subprocess.run([hits[0], "run", "--", "date", "-u", "+%s"], cwd=runtime,
                             capture_output=True, text=True, timeout=25)
        vm = int(out.stdout.strip().splitlines()[-1])
    except Exception:
        return None, None
    return abs(int(time.time()) - vm), f'(cd {runtime} && "{hits[0]}" run -- hwclock -s)'


def fix_vm_clock():
    """Resync the Exasol VM's system clock from its own (correct) hardware clock.

    Returns (ok, message). No restart, no downtime, nothing else is touched.
    """
    import glob, subprocess
    runtime = os.path.expanduser("~/.exasol/personal/deployments/default/local/runtime")
    hits = sorted(glob.glob(os.path.expanduser(
        "~/Library/Caches/.exasol/personal/runtime-artifacts/artifacts/"
        "exasol-local-runner/*/*/*/unpack/launcher")), key=os.path.getmtime, reverse=True)
    if not hits:
        return False, "could not find the Exasol local-runner launcher"
    try:
        subprocess.run([hits[0], "run", "--", "hwclock", "-s"], cwd=runtime,
                       capture_output=True, timeout=40)
    except Exception as e:                                    # noqa: BLE001
        return False, "resync failed: %s" % str(e)[:160]
    skew, _ = _vm_clock_skew()
    if skew is None:
        return False, "resynced, but the new clock could not be read"
    if skew > 300:
        return False, "still %d s out after the resync" % skew
    return True, "clock resynced — %d s from this host" % skew


@st.cache_data(ttl=TTL, show_spinner=False)
def health():
    """What is up -- and when something is down, WHY.

    A status tile that says "Unavailable, start it with lake/up.sh" while the
    containers are perfectly healthy sends the presenter to fix the wrong thing
    in front of an audience. So the diagnosis is real: containers, then clock,
    then the query itself.
    """
    out = {"exasol": False, "lake": False, "engine": "", "err": "",
           "cause": "", "fix": "", "containers": 0, "skew": None}
    try:
        exasql.rows("SELECT 1;")
        out["exasol"] = True
    except Exception as e:
        out["err"] = str(e)[:200]
        out["cause"] = "Exasol is not answering"
        out["fix"] = "exasol status"
        return out

    import subprocess
    try:
        ps = subprocess.run(["docker", "ps", "--filter", "name=ct-lake-",
                             "--filter", "health=healthy", "-q"],
                            capture_output=True, text=True, timeout=25)
        out["containers"] = len([x for x in ps.stdout.split() if x])
    except Exception:
        out["containers"] = -1

    try:
        v = _one("SELECT LAKEHOUSE.LAKEHOUSE_VERSION() AS V;")
        out["engine"] = v["V"] if v else ""
        exasql.rows("SELECT 1 FROM CT_LAKE.PUBLICATIONS LIMIT 1;")
        out["lake"] = True
        return out
    except Exception as e:
        out["err"] = str(e)[:400]

    # Name the cause instead of guessing at it.
    if out["containers"] == 0:
        out["cause"] = "the lake containers are not running"
        out["fix"] = "./lake/up.sh"
        return out
    skew, fix = _vm_clock_skew()
    out["skew"] = skew
    if "RequestTimeTooSkewed" in out["err"] or (skew is not None and skew > 300):
        mins = f"{skew // 60} min" if skew else "several minutes"
        out["cause"] = (f"the Exasol VM's clock is {mins} behind this host, so every S3 request "
                        "fails signature validation (403). The containers are fine.")
        out["fix"] = fix or "resync the VM clock with hwclock -s"
    elif "LAKEHOUSE_VERSION" in out["err"] or "not found" in out["err"]:
        out["cause"] = "the lakehouse engine is not installed in Exasol"
        out["fix"] = "./lake/install_engine.sh"
    else:
        out["cause"] = "the lake is reachable but the query failed"
        out["fix"] = "see the error below"
    return out


@st.cache_data(ttl=TTL, show_spinner=False)
def totals():
    r = _one("""SELECT (SELECT COUNT(*) FROM CT.TRIALS)        AS TRIALS,
                       (SELECT COUNT(*) FROM CT.ELIG_CHUNKS)   AS CRITERIA,
                       (SELECT COUNT(*) FROM CT.ELIG_VECTORS)  AS VECTOR_ROWS,
                       (SELECT COUNT(DISTINCT COUNTRY) FROM CT.TRIAL_COUNTRIES) AS COUNTRIES;""")
    return {k.lower(): int(v) for k, v in r.items()}


@st.cache_data(ttl=TTL, show_spinner=False)
def lake_totals():
    r = _one("""SELECT (SELECT COUNT(*) FROM CT_LAKE.PUBLICATIONS) AS PAPERS,
                       (SELECT COUNT(*) FROM CT_LAKE.TRIAL_PUBLICATIONS) AS LINKS;""")
    return {k.lower(): int(v) for k, v in r.items()}


@st.cache_data(ttl=TTL, show_spinner=False)
def phase_mix():
    rows = exasql.rows("""SELECT PHASE, COUNT(*) AS N,
                                 ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(),1) AS PCT
                          FROM CT.V_TRIALS GROUP BY PHASE ORDER BY N DESC;""")
    return [{"label": r["PHASE"], "n": int(r["N"]), "pct": float(r["PCT"])} for r in rows]


@st.cache_data(ttl=TTL, show_spinner=False)
def endpoint_mix():
    rows = exasql.rows("""SELECT ENDPOINT_CATEGORY AS C, COUNT(*) AS N,
                                 ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(),1) AS PCT
                          FROM CT.V_TRIAL_ENDPOINTS WHERE OUTCOME_KIND='PRIMARY'
                          GROUP BY 1 ORDER BY N DESC;""")
    return [{"label": r["C"], "n": int(r["N"]), "pct": float(r["PCT"])} for r in rows]


@st.cache_data(ttl=TTL, show_spinner=False)
def section_mix():
    rows = exasql.rows("""SELECT CRITERION_SECTION AS S, COUNT(*) AS N,
                                 ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(),1) AS PCT
                          FROM CT.ELIG_CHUNKS GROUP BY 1 ORDER BY N DESC;""")
    return [{"label": r["S"], "n": int(r["N"]), "pct": float(r["PCT"])} for r in rows]


@st.cache_data(ttl=TTL, show_spinner=False)
def tokens(a, b):
    """The stopword proof, computed by the database, not asserted."""
    def terms(q):
        rows = exasql.rows("SELECT TERM FROM (SELECT CT.QUERY_TERMS('%s') FROM DUAL) ORDER BY TERM;"
                           % q.replace("'", "''"))
        return [r["TERM"] for r in rows]
    ta, tb = terms(a), terms(b)
    return {"a": ta, "b": tb, "identical": ta == tb}


@st.cache_data(ttl=TTL, show_spinner=False)
def ask(question, topk=5, deep=30):
    """The whole question -> split -> SQL -> both rankings path."""
    sp = qsplit.split(question)
    sec = sp["section"]
    sql = search.build(sp["text"], sec, sp["filter"], topk)
    res, ms, deep_rows = {}, 0, []
    for name, use in (("text_only", None), ("with_section", sec)):
        rows, took = exasql.rows_timed(search.build(sp["text"], use, sp["filter"], deep))
        if name == "with_section":
            deep_rows = rows
        res[name] = rows[:topk]
        ms = max(ms, took)
    return {"split": sp, "sql": sql, "results": res, "ms": ms,
            "blind_spot": qsplit.blind_spot(question, deep_rows, sec)}


@st.cache_data(ttl=TTL, show_spinner=False)
def publication_gap():
    rows = exasql.rows("""
        SELECT t.PHASE,
               COUNT(*)                                                    AS COMPLETED,
               COUNT(DISTINCT p.NCT_ID)                                    AS PUBLISHED,
               COUNT(*) - COUNT(DISTINCT p.NCT_ID)                         AS MISSING,
               ROUND(100.0*(COUNT(*)-COUNT(DISTINCT p.NCT_ID))/COUNT(*),1) AS PCT
        FROM CT.V_LANDSCAPE t
        LEFT JOIN CT_LAKE.TRIAL_PUBLICATIONS p ON p.NCT_ID = t.NCT_ID
        WHERE t.STATUS_GROUP='Completed' AND t.PHASE_IS_STATED
        GROUP BY t.PHASE ORDER BY COMPLETED DESC;""")
    return [{"phase": r["PHASE"], "completed": int(r["COMPLETED"]),
             "published": int(r["PUBLISHED"]), "missing": int(r["MISSING"]),
             "pct": float(r["PCT"])} for r in rows]


@st.cache_data(ttl=TTL, show_spinner=False)
def tier_cost():
    """Native vs lake, measured now. Both include client connect, so the honest
    figure is the DIFFERENCE -- which is what the caller is given."""
    import statistics
    def med(sql):
        return statistics.median([exasql.rows_timed(sql)[1] for _ in range(3)])
    nat = med("SELECT COUNT(*) AS N FROM CT.V_LANDSCAPE;")
    lake = med("SELECT COUNT(*) AS N FROM CT_LAKE.PUBLICATIONS;")
    return {"native_ms": int(nat), "lake_ms": int(lake), "delta_ms": int(lake - nat)}


@st.cache_data(ttl=TTL, show_spinner=False)
def eval_results():
    """The measured retrieval numbers, read from the eval's own output."""
    import json
    p = os.path.join(ROOT, "eval", "results.json")
    if not os.path.exists(p):
        return None
    # The eval writes {"summary": {...}, "results": [...]} and names the metric
    # recall_at_k, not recall. Flattened here so the page reads one shape.
    s = json.load(open(p))["summary"]
    return {
        "overall": {
            "recall_text_only":   s["text_only"]["recall_at_k"],
            "recall_with_section": s["with_section"]["recall_at_k"],
            "purity_text_only":   s["text_only"]["section_purity"],
            "purity_with_section": s["with_section"]["section_purity"],
        },
        "by_category": s.get("by_category", {}),
        "caveat": s.get("caveat", ""),
    }
