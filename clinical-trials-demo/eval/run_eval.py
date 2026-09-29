#!/usr/bin/env python3
"""Measure the retrieval, and measure what the structured layer adds to it.

Every question runs TWICE: once on text alone, once with the criteria-section
filter from the semantic layer applied before scoring. The delta between those
two numbers is the whole argument of the demo, so it is the headline metric.

Reported per question:
  RECALL@k        gold chunks found in the top k
  SECTION_PURITY  fraction of the top k drawn from the intended section --
                  this is what polarity blindness actually costs
"""
import argparse, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))
import exasql  # noqa: E402
import search  # noqa: E402


def sql_rows(sql):
    return exasql.rows(sql)


def key(r):
    return (r["NCT_ID"], str(int(float(r["CHUNK_ID"]))))


def evaluate(q, k):
    gold = {key(r) for r in sql_rows(q["gold_sql"])}
    out = {"id": q["id"], "category": q["category"], "gold_size": len(gold),
           "gold_source": q["gold_source"], "intent": q["intent"]}
    for mode, section in (("text_only", None), ("with_section", q.get("section"))):
        rows = search.run(search.build(q["query"], section,
                                       q.get("trial_filter", ""), k))
        got = [key(r) for r in rows]
        hits = sum(1 for g in got if g in gold)
        want = q.get("section")
        pure = (sum(1 for r in rows if r["CRITERION_SECTION"] == want) / len(rows)
                if rows and want else None)
        out[mode] = {
            "returned": len(rows),
            "hits": hits,
            "recall_at_k": round(hits / min(k, len(gold)), 3) if gold else None,
            "precision_at_k": round(hits / len(rows), 3) if rows else None,
            "section_purity": round(pure, 3) if pure is not None else None,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--out", default="eval/results.json")
    a = ap.parse_args()
    spec = json.load(open(os.path.join(ROOT, "eval", "questions.json")))
    qs = spec["questions"]

    res = []
    for q in qs:
        print(f"  {q['id']:8s} {q['query'][:52]:54s}", end="", flush=True)
        try:
            r = evaluate(q, a.k)
            res.append(r)
            t, s = r["text_only"], r["with_section"]
            print(f"recall {t['recall_at_k']:.2f} -> {s['recall_at_k']:.2f}"
                  f"   purity {t['section_purity']} -> {s['section_purity']}")
        except Exception as e:                                   # noqa: BLE001
            print(f"ERROR {e}")
            res.append({"id": q["id"], "error": str(e)})

    ok = [r for r in res if "error" not in r]
    def avg(mode, m):
        v = [r[mode][m] for r in ok if r[mode].get(m) is not None]
        return round(sum(v) / len(v), 3) if v else None
    summary = {
        "k": a.k, "questions": len(qs), "evaluated": len(ok),
        "text_only":    {m: avg("text_only", m)    for m in ("recall_at_k", "precision_at_k", "section_purity")},
        "with_section": {m: avg("with_section", m) for m in ("recall_at_k", "precision_at_k", "section_purity")},
        "by_category": {},
        # Stated plainly so nobody mistakes this for a review-validated benchmark.
        "gold_sources": {s: sum(1 for q in qs if q["gold_source"] == s)
                         for s in {q["gold_source"] for q in qs}},
        "caveat": ("All gold sets are snapshot-sql: derived by predicate from the "
                   "loaded data, so they are reproducible but they are NOT an "
                   "independent ground truth. Review-derived questions are still "
                   "outstanding -- see eval/REVIEW_QUESTIONS.md."),
    }
    for cat in {q["category"] for q in qs}:
        sub = [r for r in ok if r["category"] == cat]
        if sub:
            summary["by_category"][cat] = {
                "n": len(sub),
                "recall_text_only": round(sum(r["text_only"]["recall_at_k"] for r in sub) / len(sub), 3),
                "recall_with_section": round(sum(r["with_section"]["recall_at_k"] for r in sub) / len(sub), 3),
                "purity_text_only": round(sum(r["text_only"]["section_purity"] for r in sub) / len(sub), 3),
                "purity_with_section": round(sum(r["with_section"]["section_purity"] for r in sub) / len(sub), 3),
            }
    json.dump({"summary": summary, "results": res},
              open(os.path.join(ROOT, a.out), "w"), indent=2)
    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
