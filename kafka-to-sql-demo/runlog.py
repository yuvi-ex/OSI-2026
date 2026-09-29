"""
A durable record of what the demo actually did.

Everything on screen is transient: Streamlit session state dies on reload, and
the per-hop timings that make the pipeline credible exist only in memory. This
appends every fired event and every agent investigation to a JSONL file so the
numbers can be quoted in a deck, pasted into a slide, or checked back after the
event.

It records what happened. It never invents a number that was not measured.

    ./.venv/bin/python story_demo/runlog.py report      # paste-ready summary
    ./.venv/bin/python story_demo/runlog.py slide       # the producer/row-count pair
    ./.venv/bin/python story_demo/runlog.py tail 5
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

LOG = Path(__file__).resolve().parent / "runs" / "demo_runs.jsonl"


def _append(record: dict) -> None:
    record["at"] = datetime.now().isoformat(timespec="seconds")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def log_event(result, label: str = "") -> None:
    """One transaction fired through the pipeline."""
    try:
        _append({
            "kind": "event",
            "label": label or getattr(result, "label", ""),
            "txn_id": result.txn_id,
            "verdict": result.verdict,
            "score": result.score,
            "kafka_offset": result.kafka_offset,
            "total_ms": round(result.total_ms, 1),
            "analytics_ms": round(result.analytics_ms, 1),
            "hops": {h.name: round(h.ms, 1) for h in result.hops},
            "features": {k: str(v) for k, v in (result.features or {}).items()},
        })
    except Exception:
        pass          # logging must never break a live demo


def log_investigation(persona, question: str, steps) -> None:
    """One agent investigation, with the statements it ran."""
    try:
        conclusion = next((s for s in steps if s.kind == "conclusion"), None)
        queries = [s for s in steps if s.kind == "tool"
                   and s.tool == "execute_exasol_query" and not s.error]
        payload = dict(conclusion.payload) if conclusion else {}
        proof = payload.pop("_proof", None)
        _append({
            "kind": "investigation",
            "persona": persona.db_user,
            "question": question,
            "concluded": conclusion is not None,
            "verdict": payload.get("verdict"),
            "confidence": payload.get("confidence"),
            "headline": payload.get("headline"),
            "findings": payload.get("findings", []),
            "actions": payload.get("actions", []),
            "statements": [{"sql": " ".join(q.sql.split()),
                            "rows": len(q.table()[1] or []),
                            "ms": round(q.ms, 1)} for q in queries],
            "evidence_sql": payload.get("evidence_sql"),
            "evidence_rows": (proof or {}).get("rows", [])[:20],
            "evidence_columns": (proof or {}).get("columns", []),
        })
    except Exception:
        pass


def _load():
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


# ------------------------------------------------------------------ reporting
def report() -> str:
    rows = _load()
    ev = [r for r in rows if r["kind"] == "event"]
    inv = [r for r in rows if r["kind"] == "investigation"]
    out = ["# Demo run log", ""]
    if ev:
        tot = [e["total_ms"] for e in ev if e.get("total_ms")]
        ana = [e["analytics_ms"] for e in ev if e.get("analytics_ms")]
        out += [f"**{len(ev)} transactions fired.** End to end "
                f"{min(tot)/1000:.1f}–{max(tot)/1000:.1f}s "
                f"(median {sorted(tot)[len(tot)//2]/1000:.1f}s). "
                f"Of that, analytics {sum(ana)/len(ana):.0f} ms on average — "
                f"the rest is one-off connector startup.", ""]
        out += ["| when | transaction | verdict | score | end to end | analytics |",
                "|---|---|---|---|---|---|"]
        for e in ev[-12:]:
            out.append(f"| {e['at'][11:19]} | {e['label']} | **{e['verdict']}** | "
                       f"{e['score']:.5f} | {e['total_ms']/1000:.1f}s | "
                       f"{e['analytics_ms']:.0f} ms |")
        out.append("")
        hops = {}
        for e in ev:
            for k, v in (e.get("hops") or {}).items():
                hops.setdefault(k, []).append(v)
        if hops:
            out += ["**Per-hop, averaged over every run:**", "",
                    "| hop | mean |", "|---|---|"]
            for k in ("postgres", "kafka", "raw", "features", "score"):
                if k in hops:
                    out.append(f"| {k} | {sum(hops[k])/len(hops[k]):,.0f} ms |")
            out.append("")
    if inv:
        out += [f"**{len(inv)} agent investigations.**", ""]
        for i in inv[-8:]:
            n = len(i.get("statements", []))
            out.append(f"- `{i['persona']}` — **{i.get('verdict')}** "
                       f"({i.get('confidence')}), {n} statements — "
                       f"{(i.get('headline') or '')[:120]}")
        out.append("")
    return "\n".join(out) if rows else "No runs logged yet."


def slide() -> str:
    """The producer log / row-count pair, for the 'micro-batch import' slide."""
    ev = [r for r in _load() if r["kind"] == "event"]
    if not ev:
        return "No events logged yet."
    left = ["PRODUCER — what was fired", ""]
    right = ["EXASOL — the row count between imports", ""]
    for e in ev[-6:]:
        left.append(f"  {e['at'][11:19]}  {e['label']}")
        right.append(f"  offset {str(e.get('kafka_offset')):>4}   "
                     f"landed in {e['total_ms']/1000:>4.1f}s   {e['verdict']}")
    w = max(len(x) for x in left) + 4
    return "\n".join(f"{a:<{w}}{b}" for a, b in
                     zip(left + [""] * len(right), right + [""] * len(left)) if (a or b))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "report":
        print(report())
    elif cmd == "slide":
        print(slide())
    elif cmd == "tail":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        for r in _load()[-n:]:
            print(json.dumps(r, indent=2, default=str)[:1200])
    else:
        print(__doc__)
