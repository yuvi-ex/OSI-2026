#!/usr/bin/env python3
"""A local page that explains itself: dataset, model, architecture, and results,
alongside the live search probe.

Stdlib only -- no pip, no venv, and no second Exasol connection pool parked
against the 20-connection ceiling. It imports bin/search.py rather than
reimplementing anything, so the page, the CLI and the eval harness cannot
disagree about what the retrieval does.
"""
import json, os, re, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))
import exasql                     # noqa: E402
import search                      # noqa: E402
import stats as statsmod           # noqa: E402
from ui_page import PAGE
from story_page import PAGE as STORY
import split as qsplit           # noqa: E402

PORT = int(os.environ.get("PORT", "8899"))

PRESETS = [
    ["The stopword failure", "prior treatment with an anti-PD-1 or anti-PD-L1 antibody",
     "EXCLUSION", ""],
    ["The antonymy failure", "EGFR mutation positive", "INCLUSION",
     "AND t.INDICATION='NSCLC'"],
    ["Worst recall in the eval", "no prior systemic chemotherapy for metastatic disease",
     "INCLUSION", ""],
    ["Structured + text", "EGFR mutation positive", "INCLUSION",
     "AND t.INDICATION='NSCLC' AND t.PHASE='PHASE3' AND t.STATUS_GROUP='Open'"],
    ["An easy case", "interstitial lung disease or pneumonitis", "EXCLUSION", ""],
]

# ---------------------------------------------------------------------------
# THE FILTER PARAMETER IS UNTRUSTED INPUT.
#
# bin/search.py substitutes {{TRIAL_FILTER}} into the SQL template verbatim, and
# the Exasol CLI executes whatever it is handed as SYS. On
# localhost that is a convenience; the moment this port is published -- a tunnel,
# a LAN address, a port-forward -- it is an unauthenticated SQL console on the
# database. So the HTTP surface does NOT accept SQL. It accepts equality clauses
# against an allowlist of columns and REBUILDS the SQL from the parsed parts.
#
# The CLI keeps its free-form --filter: that path is a trusted local shell.
FILTER_COLUMNS = {
    "INDICATION", "PHASE", "PHASE_IS_STATED", "STATUS_GROUP", "OVERALL_STATUS",
    "SPONSOR_TYPE", "LEAD_SPONSOR", "COMPARATOR_DESIGN",
    "PRIMARY_ENDPOINT_CATEGORY", "START_YEAR", "NCT_ID", "ARM_COUNT",
    "REGION_COUNT", "ENROLLMENT", "MIN_AGE_YEARS", "MAX_AGE_YEARS", "SEX",
}
# One clause: AND t.COLUMN = 'value'  |  AND t.COLUMN = 123
_CLAUSE = re.compile(
    r"""\s*AND\s+t\.(?P<col>[A-Z_][A-Z0-9_]*)\s*(?P<op>=|<>|!=|<=|>=|<|>)\s*"""
    r"""(?:'(?P<str>[^';\\]*)'|(?P<num>-?\d+(?:\.\d+)?))\s*""",
    re.IGNORECASE)


def safe_filter(raw):
    """Parse an allowlisted filter and rebuild it. Never passes input through.

    Returns (sql, None) or (None, reason). Anything that does not parse whole is
    refused rather than partially applied -- a filter that silently drops half of
    what was asked for is worse than an error.
    """
    if not raw or not raw.strip():
        return "", None
    text, out = raw, []
    while text.strip():
        m = _CLAUSE.match(text)
        if not m:
            return None, ("Filter not understood. Use clauses like "
                          "AND t.PHASE='PHASE3' — column names from the trial "
                          "view, equality or comparison, no functions or "
                          "subqueries.")
        col = m.group("col").upper()
        if col not in FILTER_COLUMNS:
            return None, f"Column {col} is not filterable. Allowed: " + \
                         ", ".join(sorted(FILTER_COLUMNS))
        op = "<>" if m.group("op") == "!=" else m.group("op")
        if m.group("num") is not None:
            out.append(f"AND t.{col} {op} {m.group('num')}")
        else:
            # Rebuilt from the captured value, which the pattern already forbids
            # quotes, semicolons and backslashes in.
            out.append("AND t.%s %s '%s'" % (col, op, m.group("str")))
        text = text[m.end():]
    return " " + " ".join(out), None


# The stats query set takes a couple of seconds; the page asks for it once on
# load, so cache it and let a reload past the TTL pick up new data.
_cache = {"at": 0.0, "val": None}
_TTL = 120.0


def cached_stats():
    import time
    now = time.time()
    if _cache["val"] is None or now - _cache["at"] > _TTL:
        v = statsmod.collect()
        v["presets"] = PRESETS
        _cache.update(at=now, val=v)
    return _cache["val"]


def query_terms(text):
    """Ask the database for the terms, so the page shows the SAME tokenisation
    the scoring uses rather than a JavaScript approximation of it."""
    sql = ("SELECT TERM FROM (SELECT CT.QUERY_TERMS('%s') FROM DUAL) ORDER BY TERM"
           % text.replace("'", "''"))
    return [r["TERM"] for r in statsmod.q(sql)]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        b = body.encode("utf8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        try:
            self.wfile.write(b)
        except BrokenPipeError:
            pass

    def _json(self, obj):
        self._send(200, json.dumps(obj), "application/json")

    def do_GET(self):
        u = urlparse(self.path)
        p = parse_qs(u.query)
        try:
            if u.path == "/":
                return self._send(200, PAGE, "text/html; charset=utf-8")
            if u.path == "/story":
                return self._send(200, STORY, "text/html; charset=utf-8")
            if u.path == "/api/story":
                q = (p.get("q") or [""])[0][:400]
                if not q.strip():
                    return self._json({"error": "ask something"})
                # The split is deterministic and comes from the layer's own
                # vocabulary, so the filter it produces is already allowlisted by
                # construction -- but it goes through the same guard as the probe
                # page rather than around it.
                sp = qsplit.split(q)
                filt, why = safe_filter(sp["filter"])
                if why:
                    return self._json({"error": why})
                sec = sp["section"]
                sql_shown = search.build(sp["text"], sec, filt, 5)
                # Fetch deeper than the page shows: the antonymy blind spot does
                # not sit in the top 5, and pretending it does would be the one
                # dishonest thing on the screen.
                DEEP = 30
                res, ms, deep = {}, 0, []
                for name, use in (("text_only", None), ("with_section", sec)):
                    rows, took = exasql.rows_timed(search.build(sp["text"], use, filt, DEEP))
                    if name == "with_section":
                        deep = rows
                    res[name] = rows[:5]
                    ms = max(ms, took)
                return self._json({
                    "split": sp,
                    "section_clause": ("AND c.CRITERION_SECTION = '%s'" % sec) if sec else "",
                    "sql": sql_shown,
                    "scan": dict(cached_stats()["totals"], dims=96, elapsed_ms=ms,
                                 vector_rows=cached_stats()["totals"]["vector_rows"],
                                 criteria=cached_stats()["totals"]["chunks"]),
                    "results": res,
                    "blind_spot": qsplit.blind_spot(q, deep, sec),
                    "deep_k": DEEP,
                })
            if u.path == "/stats":
                return self._json(cached_stats())
            if u.path == "/tokens":
                a = query_terms((p.get("a") or [""])[0])
                b = query_terms((p.get("b") or [""])[0])
                sa, sb = set(a), set(b)
                return self._json({"a": a, "b": b,
                                   "shared": sorted(sa & sb),
                                   "only_a": sorted(sa - sb),
                                   "only_b": sorted(sb - sa)})
            if u.path == "/search":
                q = (p.get("q") or [""])[0][:400]
                section = (p.get("section") or [None])[0]
                filt, why = safe_filter((p.get("filter") or [""])[0])
                if why:
                    return self._json({"error": why})
                # Bound the result set too: an unbounded topk on a published port
                # is a cheap way to make the database do a lot of work.
                topk = max(1, min(50, int((p.get("topk") or ["10"])[0])))
                out = {}
                for name, sec in (("text_only", None), ("with_section", section)):
                    sql = search.build(q, sec, filt, topk)
                    out[name] = {"sql": sql, "rows": search.run(sql)}
                return self._json(out)
            return self._send(404, "not found", "text/plain")
        except Exception as e:                                   # noqa: BLE001
            return self._json({"error": str(e)[:600]})


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"  probe UI -> http://127.0.0.1:{PORT}/")
    print("  tabs: Probe / Dataset / Model / Architecture / Results")
    print("  ctrl-c to stop")
    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}/")).start()
    srv.serve_forever()
