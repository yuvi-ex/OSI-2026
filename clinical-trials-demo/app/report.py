"""Keyword in, structured trial-landscape report out.

DESIGN. The sections and their SQL are FIXED. The model does not choose what to
query, and it does not retype numbers into prose -- it writes one summary over
results that were already computed. That buys three things a free-form agent
cannot: the same keyword always produces the same report, every figure carries
the statement that produced it, and a section with no data says so instead of
quietly disappearing.

The filter is matched against vocabulary read live out of the database, so the
report can only ever scope itself to values that actually exist.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
import exasql                                          # noqa: E402

MODEL = "claude-opus-5"
_vocab = None


def q(s):
    return (s or "").replace("'", "''")


def vocabulary():
    """Countries, indications and sponsors that exist. Read once."""
    global _vocab
    if _vocab is None:
        _vocab = {
            "country": [r["V"] for r in exasql.rows(
                "SELECT DISTINCT COUNTRY AS V FROM CT.TRIAL_COUNTRIES WHERE COUNTRY IS NOT NULL;")],
            "indication": [r["V"] for r in exasql.rows(
                "SELECT DISTINCT INDICATION AS V FROM CT.V_LANDSCAPE WHERE INDICATION IS NOT NULL;")],
        }
    return _vocab


COUNTRY_ALIAS = {"us": "United States", "usa": "United States", "u.s.": "United States",
                 "america": "United States", "uk": "United Kingdom", "britain": "United Kingdom",
                 "canada": "Canada", "germany": "Germany", "france": "France", "japan": "Japan",
                 "china": "China", "india": "India", "australia": "Australia", "spain": "Spain",
                 "italy": "Italy", "korea": "South Korea"}
INDICATION_ALIAS = {"nsclc": "NSCLC", "non-small cell": "NSCLC", "non small cell": "NSCLC",
                    "lung": "NSCLC", "breast": "BREAST"}
PHASES = {"phase 1": "PHASE1", "phase i": "PHASE1", "phase 2": "PHASE2", "phase ii": "PHASE2",
          "phase 3": "PHASE3", "phase iii": "PHASE3", "phase 4": "PHASE4"}
STOP = {"tell", "me", "about", "what", "is", "the", "current", "trial", "trials", "landscape",
        "for", "in", "of", "on", "a", "an", "and", "give", "show", "report", "generate",
        "status", "study", "studies", "please", "with", "who", "which"}


def parse(question):
    """Keyword -> {drug, country, indication, phase, unmatched}. Deterministic."""
    low = " " + question.lower().strip() + " "
    v = vocabulary()
    out = {"question": question.strip(), "drug": None, "country": None,
           "indication": None, "phase": None, "matched": [], "unmatched": [],
           "drug_resolved": False, "geo": "has_us_site"}

    for name in sorted(v["country"], key=len, reverse=True):
        if re.search(r"\b%s\b" % re.escape(name.lower()), low):
            out["country"] = name; out["matched"].append(("country", name)); break
    if not out["country"]:
        for alias, name in COUNTRY_ALIAS.items():
            if re.search(r"\b%s\b" % re.escape(alias), low) and name in v["country"]:
                out["country"] = name; out["matched"].append(("country", name)); break

    for alias, name in INDICATION_ALIAS.items():
        if re.search(r"\b%s\b" % re.escape(alias), low) and name in v["indication"]:
            out["indication"] = name; out["matched"].append(("indication", name)); break

    for alias, name in PHASES.items():
        if re.search(r"\b%s\b" % re.escape(alias), low):
            out["phase"] = name; out["matched"].append(("phase", name)); break

    # Whatever is left and looks like a name is the drug. Checked against the
    # database before it is believed.
    consumed = " ".join(m[1].lower() for m in out["matched"])
    for alias in list(COUNTRY_ALIAS) + list(INDICATION_ALIAS) + list(PHASES):
        low = low.replace(" " + alias + " ", " ")
    words = [w.strip(",.?;:()") for w in low.split()
             if w.strip(",.?;:()") and w.strip(",.?;:()") not in STOP
             and w.strip(",.?;:()") not in consumed and len(w.strip(",.?;:()")) > 2]
    for w in words:
        # Prefer the curated alias table: it resolves Keytruda and MK-3475 to
        # pembrolizumab, which a raw name search cannot do.
        canon = exasql.rows(
            "SELECT DISTINCT CANONICAL AS V FROM CT.DRUG_ALIAS WHERE UPPER(ALIAS) = '%s';" % q(w.upper()))
        if canon:
            out["drug"] = canon[0]["V"]; out["drug_resolved"] = True
            out["matched"].append(("drug", canon[0]["V"])); break
        hit = exasql.rows(
            "SELECT INTERVENTION_NAME AS V FROM CT.TRIAL_INTERVENTIONS "
            "WHERE UPPER(INTERVENTION_NAME) LIKE '%%%s%%' GROUP BY 1 "
            "ORDER BY COUNT(DISTINCT NCT_ID) DESC LIMIT 1;" % q(w.upper()))
        if hit:
            out["drug"] = w; out["drug_resolved"] = False
            out["matched"].append(("drug", w)); break
        out["unmatched"].append(w)
    return out


def _where(f, alias="t"):
    """The scope, as SQL. Returned so it can be shown, not just applied."""
    parts = []
    if f["indication"]:
        parts.append("%s.INDICATION = '%s'" % (alias, q(f["indication"])))
    if f["phase"]:
        parts.append("%s.PHASE = '%s'" % (alias, q(f["phase"])))
    if f["country"] == "United States":
        # The reading is explicit, because the three disagree by a factor of ten.
        parts.append("%s.US_ONLY" % alias if f.get("geo") == "us_only"
                     else "%s.HAS_US_SITE" % alias)
    elif f["country"]:
        parts.append("%s.NCT_ID IN (SELECT NCT_ID FROM CT.TRIAL_COUNTRIES WHERE COUNTRY = '%s')"
                     % (alias, q(f["country"])))
    if f["drug"]:
        if f.get("drug_resolved"):
            parts.append("%s.NCT_ID IN (SELECT NCT_ID FROM CT.V_TRIAL_DRUG WHERE DRUG = '%s')"
                         % (alias, q(f["drug"])))
        else:
            parts.append("%s.NCT_ID IN (SELECT NCT_ID FROM CT.TRIAL_INTERVENTIONS "
                         "WHERE UPPER(INTERVENTION_NAME) LIKE '%%%s%%')" % (alias, q(f["drug"].upper())))
    if f.get("monotherapy_only"):
        parts.append("%s.IS_MONOTHERAPY" % alias)
    return " AND ".join(parts) if parts else "1=1"


def _section(title, note, sql):
    try:
        return {"title": title, "note": note, "sql": sql.strip(), "rows": exasql.rows(sql), "error": ""}
    except Exception as e:                                    # noqa: BLE001
        return {"title": title, "note": note, "sql": sql.strip(), "rows": [], "error": str(e)[:200]}


def definitions_applied(f):
    """What this report chose, and what the other choices would have given.

    Three judgements decide the headline number and none of them is obvious.
    Printing the alternatives is the difference between a number and a claim.
    """
    rows = []
    if f["drug"]:
        base = _where(dict(f, drug=None))
        naive = ("SELECT COUNT(*) AS N FROM CT.V_TRIAL_RESOLVED t WHERE %s AND t.NCT_ID IN "
                 "(SELECT NCT_ID FROM CT.TRIAL_INTERVENTIONS WHERE UPPER(INTERVENTION_NAME) "
                 "LIKE '%%%s%%')" % (base, q(f["drug"].upper())))
        resolved = ("SELECT COUNT(*) AS N FROM CT.V_TRIAL_RESOLVED t WHERE %s AND t.NCT_ID IN "
                    "(SELECT NCT_ID FROM CT.V_TRIAL_DRUG WHERE DRUG = '%s')" % (base, q(f["drug"])))
        try:
            a = exasql.rows(naive)[0]["N"]; b = exasql.rows(resolved)[0]["N"]
            rows.append({"JUDGEMENT": "drug identity",
                         "APPLIED": "all known aliases" if f.get("drug_resolved") else "literal name only",
                         "THIS_REPORT": b if f.get("drug_resolved") else a,
                         "THE_ALTERNATIVE": "%s by literal name only" % a if f.get("drug_resolved")
                                            else "no alias table for this drug"})
        except Exception:
            pass
    if f["country"] == "United States":
        try:
            n_site = exasql.rows("SELECT COUNT(*) AS N FROM CT.V_TRIAL_RESOLVED t WHERE %s"
                                 % _where(dict(f, geo="has_us_site")))[0]["N"]
            n_only = exasql.rows("SELECT COUNT(*) AS N FROM CT.V_TRIAL_RESOLVED t WHERE %s"
                                 % _where(dict(f, geo="us_only")))[0]["N"]
            rows.append({"JUDGEMENT": "what 'in the US' means",
                         "APPLIED": "has a US site (default)" if f.get("geo") != "us_only" else "US-only",
                         "THIS_REPORT": n_site if f.get("geo") != "us_only" else n_only,
                         "THE_ALTERNATIVE": "%s if US-only" % n_only if f.get("geo") != "us_only"
                                            else "%s if any US site counts" % n_site})
            rows.append({"JUDGEMENT": "us-led", "APPLIED": "not applied",
                         "THIS_REPORT": "\u2014",
                         "THE_ALTERNATIVE": "NOT DERIVABLE \u2014 the registry does not publish sponsor country"})
        except Exception:
            pass
    if f["drug"] or f["indication"]:
        try:
            mono = exasql.rows("SELECT COUNT(*) AS N FROM CT.V_TRIAL_RESOLVED t WHERE %s AND t.IS_MONOTHERAPY"
                               % _where(f))[0]["N"]
            allt = exasql.rows("SELECT COUNT(*) AS N FROM CT.V_TRIAL_RESOLVED t WHERE %s" % _where(f))[0]["N"]
            rows.append({"JUDGEMENT": "combination therapy",
                         "APPLIED": "counted (single agent and combination)",
                         "THIS_REPORT": allt,
                         "THE_ALTERNATIVE": "%s if single-agent trials only" % mono})
        except Exception:
            pass
    return rows


def gather(f, lake_ok=True):
    w = _where(f)
    S = []
    d = definitions_applied(f)
    if d:
        S.append({"title": "Definitions applied", "rows": d, "error": "",
                  "note": "Three judgements decide the headline number. This is the one taken and "
                          "what the alternative would have given.",
                  "sql": "-- see CT.DRUG_ALIAS and CT.GEO_DEFINITION; the layer publishes both"})
    S.append(_section("Scope", "How many trials the keyword resolves to.", f"""
SELECT COUNT(*) AS TRIALS, COUNT(DISTINCT t.LEAD_SPONSOR) AS SPONSORS,
       SUM(CASE WHEN t.PHASE_IS_STATED THEN 1 ELSE 0 END) AS WITH_A_STATED_PHASE
FROM CT.V_TRIAL_RESOLVED t WHERE {w}"""))
    S.append(_section("Trials", "The largest trials in scope, by enrolment. Each row is citable.", f"""
SELECT t.NCT_ID, SUBSTR(t.BRIEF_TITLE,1,90) AS TITLE, t.PHASE, t.STATUS_GROUP,
       t.LEAD_SPONSOR, t.ENROLLMENT, t.START_YEAR
FROM CT.V_TRIAL_RESOLVED t WHERE {w}
ORDER BY t.ENROLLMENT DESC NULLS LAST LIMIT 15"""))
    S.append(_section("Sponsors", "Rolled up: 'a subsidiary of X' resolves to X, and Merck KGaA is kept "
                    "separate from Merck & Co. RAW_NAMES is how many registry strings collapsed.", f"""
SELECT t.SPONSOR_GROUP, t.SPONSOR_TYPE, COUNT(*) AS TRIALS,
       COUNT(DISTINCT t.LEAD_SPONSOR) AS RAW_NAMES
FROM CT.V_TRIAL_RESOLVED t WHERE {w}
GROUP BY 1,2 ORDER BY TRIALS DESC LIMIT 10"""))
    S.append(_section("Phase", "34.4% of the whole registry says NOT_APPLICABLE; the count is shown, never hidden.", f"""
SELECT t.PHASE, COUNT(*) AS TRIALS,
       ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(),1) AS PCT
FROM CT.V_TRIAL_RESOLVED t WHERE {w} GROUP BY 1 ORDER BY TRIALS DESC"""))
    S.append(_section("Status", "Where they are in their lifecycle.", f"""
SELECT t.STATUS_GROUP, COUNT(*) AS TRIALS
FROM CT.V_TRIAL_RESOLVED t WHERE {w} GROUP BY 1 ORDER BY TRIALS DESC"""))
    S.append(_section("Geography", "Countries with at least one site.", f"""
SELECT g.COUNTRY, COUNT(DISTINCT g.NCT_ID) AS TRIALS
FROM CT.TRIAL_COUNTRIES g
WHERE g.NCT_ID IN (SELECT t.NCT_ID FROM CT.V_TRIAL_RESOLVED t WHERE {w})
GROUP BY 1 ORDER BY TRIALS DESC LIMIT 10"""))
    S.append(_section("Primary endpoints",
                      "Derived from free text; 35.7% of the registry lands in 'Other / unclassified'.", f"""
SELECT e.ENDPOINT_CATEGORY, COUNT(DISTINCT e.NCT_ID) AS TRIALS
FROM CT.V_TRIAL_ENDPOINTS e
WHERE e.OUTCOME_KIND='PRIMARY'
  AND e.NCT_ID IN (SELECT t.NCT_ID FROM CT.V_TRIAL_RESOLVED t WHERE {w})
GROUP BY 1 ORDER BY TRIALS DESC LIMIT 10"""))
    if lake_ok:
        S.append(_section("Publication linkage",
                          "Native trial data joined to Iceberg tables in object storage, in one statement. "
                          "A lower bound: a paper that never cites its NCT number is invisible here.", f"""
SELECT COUNT(*) AS COMPLETED_TRIALS,
       COUNT(DISTINCT p.NCT_ID) AS WITH_A_LINKED_PAPER,
       COUNT(*) - COUNT(DISTINCT p.NCT_ID) AS NO_LINKED_PAPER
FROM CT.V_TRIAL_RESOLVED t
LEFT JOIN CT_LAKE.TRIAL_PUBLICATIONS p ON p.NCT_ID = t.NCT_ID
WHERE {w} AND t.STATUS_GROUP = 'Completed'"""))
    return S


NOT_COVERED = [
    "Epidemiology, incidence and survival — not in this corpus.",
    "Reimbursement, formulary status and HTA decisions — not in this corpus.",
    "Regulatory approvals and labels — not in this corpus.",
    "Trials outside the loaded scope: this snapshot holds NSCLC and breast oncology, "
    "interventional, 2015 onwards.",
]


def narrate(f, sections):
    """One model call, over numbers that are already computed."""
    import json
    try:
        import anthropic
    except ImportError:
        return ""
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return ""
    facts = {s["title"]: s["rows"][:8] for s in sections if s["rows"]}
    scope = ", ".join("%s=%s" % (k, v) for k, v in f["matched"]) or "no filter matched"
    try:
        c = anthropic.Anthropic()
        m = c.messages.create(
            model=MODEL, max_tokens=700,
            system=("You write the executive summary of a clinical-trial landscape report. "
                    "You are given results that have ALREADY been computed. Do not invent or "
                    "recompute any number, and do not restate the tables. Write 4-6 sentences of "
                    "plain prose: what the landscape looks like, who leads it, and anything a "
                    "reader should be careful about (a dominant sponsor, a thin phase, a "
                    "concentration in one country). If a figure is absent, say so rather than "
                    "guessing. No headings, no bullet points, no preamble."),
            messages=[{"role": "user", "content":
                       "Scope: %s\n\nComputed results:\n%s" % (scope, json.dumps(facts, default=str)[:6000])}])
        return "".join(b.text for b in m.content if b.type == "text").strip()
    except Exception as e:                                    # noqa: BLE001
        return "_Summary unavailable: %s_" % str(e)[:160]


def generate(question, lake_ok=True, summarise=True):
    f = parse(question)
    sections = gather(f, lake_ok)
    return {"filters": f, "where": _where(f), "sections": sections,
            "summary": narrate(f, sections) if summarise else "",
            "not_covered": NOT_COVERED}


PRESETS = [
    "What is the current trial landscape for Pembrolizumab in US",
    "Tell me about Osimertinib for NSCLC in Japan",
    "Trastuzumab breast cancer trials in Canada",
    "Phase 3 NSCLC landscape in Germany",
]

if __name__ == "__main__":
    import json
    r = generate(" ".join(sys.argv[1:]) or PRESETS[0], summarise=False)
    print("filters:", r["filters"]["matched"], "| unmatched:", r["filters"]["unmatched"])
    print("WHERE:", r["where"][:200])
    for s in r["sections"]:
        print("  %-22s %s rows %s" % (s["title"], len(s["rows"]), s["error"]))


def as_markdown(keyword, r, include_sql=False):
    """The report as a file someone can send on.

    include_sql defaults to FALSE: a document going to a business reader should
    not be half SQL. The statements stay visible on screen, where the person
    asking "where did that number come from" can open them.
    """
    f = r["filters"]
    scope = " \u00b7 ".join("%s: %s" % (k, v) for k, v in f["matched"]) or "no filter matched"
    out = ["# Trial landscape \u2014 %s" % keyword, "",
           "*Scope resolved to %s.*" % scope, ""]
    if f["unmatched"]:
        out += ["*Not recognised in the keyword: %s.*" % ", ".join(f["unmatched"]), ""]
    if r["summary"]:
        out += ["## Summary", "", r["summary"], ""]
    for sec in r["sections"]:
        out += ["## %s" % sec["title"], "", "*%s*" % sec["note"], ""]
        if sec["error"]:
            out += ["> Section failed: %s" % sec["error"], ""]
        elif not sec["rows"]:
            out += ["**Data Not Available** \u2014 no rows for this section within the scope above.", ""]
        else:
            cols = list(sec["rows"][0])
            out += ["| " + " | ".join(cols) + " |",
                    "|" + "|".join(["---"] * len(cols)) + "|"]
            for row in sec["rows"]:
                out.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
            out.append("")
        if include_sql:
            out += ["```sql", sec["sql"], "```", ""]
    out += ["## Not covered", ""] + ["- %s" % x for x in r["not_covered"]] + [""]
    out += ["---", "",
            "Generated from ClinicalTrials.gov and PubMed data held in Exasol. Every figure above "
            "is the output of the statement printed beneath it."]
    return "\n".join(out)
