#!/usr/bin/env python3
"""Split a plain question into the half that is a WHERE clause and the half that
is retrieval.

THIS IS NOT AN LLM AND MUST NOT LOOK LIKE ONE. It is a deterministic match of
the question's words against the semantic layer's OWN VOCABULARY, read live out
of CT.V_LANDSCAPE. That is the honest version of the claim the demo makes: the
layer is what makes the split possible, so the split is done by looking words up
IN the layer, and anything the layer cannot name is reported as unresolved
rather than guessed at.

Everything it cannot place stays in the text half, which is the point -- that
residue is exactly what retrieval exists for.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import exasql

# Columns a question is allowed to constrain. Deliberately the same allowlist
# the probe UI enforces: a booth screen is still a published port.
VOCAB_SQL = """
SELECT 'INDICATION'   AS COL, INDICATION   AS VAL FROM CT.V_LANDSCAPE GROUP BY 2
UNION ALL SELECT 'PHASE',        PHASE        FROM CT.V_LANDSCAPE GROUP BY 2
UNION ALL SELECT 'STATUS_GROUP', STATUS_GROUP FROM CT.V_LANDSCAPE GROUP BY 2
UNION ALL SELECT 'SPONSOR_TYPE', SPONSOR_TYPE FROM CT.V_LANDSCAPE GROUP BY 2
"""

# Words that name a coded value without spelling it. Each maps to a value that
# EXISTS in the vocabulary above -- checked at match time, never assumed.
SYNONYM = {
    "INDICATION":   {"nsclc": "NSCLC", "non-small cell": "NSCLC",
                     "non small cell": "NSCLC", "lung": "NSCLC",
                     "breast": "BREAST"},
    "PHASE":        {"phase 3": "PHASE3", "phase iii": "PHASE3", "phase3": "PHASE3",
                     "phase 2": "PHASE2", "phase ii": "PHASE2", "phase2": "PHASE2",
                     "phase 1": "PHASE1", "phase i": "PHASE1", "phase1": "PHASE1",
                     "phase 4": "PHASE4", "phase iv": "PHASE4"},
    "STATUS_GROUP": {"recruiting": "Open", "open": "Open", "enrolling": "Open",
                     "completed": "Completed", "stopped": "Stopped",
                     "halted": "Stopped", "terminated": "Stopped"},
    "SPONSOR_TYPE": {"industry": "Industry", "pharma": "Industry",
                     "academic": "Academic / other", "government": "Government"},
}

# Polarity cues -> which half of the criteria the question is about. This is the
# column the whole demo turns on, so the cue that fired is always shown.
# NOTE the -ing forms. "excluding brain metastases" is how people actually ask,
# and an earlier version matched only "exclude/excludes/excluded", so the section
# silently came back None and the whole polarity story quietly did not happen.
SECTION_CUE = [
    (r"\bexclud(?:e|es|ed|ing)\b",    "EXCLUSION"),
    (r"\bexclusion\b",               "EXCLUSION"),
    (r"\bnot eligible\b",            "EXCLUSION"),
    (r"\bineligible\b",              "EXCLUSION"),
    (r"\bwithout\b",                 "EXCLUSION"),
    (r"\bno prior\b",                "EXCLUSION"),
    (r"\bmust not\b",                "EXCLUSION"),
    (r"\brul(?:e|es|ed)\s+out\b",    "EXCLUSION"),
    (r"\bincluding\b",               "INCLUSION"),
    (r"\binclud(?:e|es|ed)\b",        "INCLUSION"),
    (r"\binclusion\b",               "INCLUSION"),
    (r"\beligible\b",                "INCLUSION"),
    (r"\brequir(?:e|es|ed|ing)\b",    "INCLUSION"),
    (r"\bmust have\b",               "INCLUSION"),
]

# Phrases that are clearly asking about a coded dimension but name no value the
# layer carries. Reported as unresolved -- the demo's own caveat, on screen.
UNRESOLVED_CUE = [
    (r"\bendpoint\b|\boutcome\b", "PRIMARY_ENDPOINT_CATEGORY",
     "derived from free text; 35.7% is 'Other / unclassified'"),
    (r"\bcomparator\b|\bcontrol arm\b|\bplacebo\b", "COMPARATOR_DESIGN",
     "whether a control exists is coded; WHICH drug it is stays prose"),
    (r"\bcro\b|\bcontract research\b", "(none)",
     "the registry has no CRO field -- leadSponsor is the pharma company"),
]

_vocab = None


def vocabulary():
    """{COL: {value_lower: VALUE}} read from the layer itself, once."""
    global _vocab
    if _vocab is None:
        v = {}
        for r in exasql.rows(VOCAB_SQL):
            if r["VAL"]:
                v.setdefault(r["COL"], {})[r["VAL"].lower()] = r["VAL"]
        _vocab = v
    return _vocab


def split(question):
    q = question.strip()
    low = q.lower()
    vocab = vocabulary()
    structured, consumed = [], []

    def take(col, value, phrase):
        # Only ever emit a value the layer actually holds.
        if value.lower() not in vocab.get(col, {}):
            return False
        if any(s["column"] == col for s in structured):
            return False
        structured.append({"column": col, "op": "=", "value": value,
                           "matched": phrase,
                           "clause": "AND t.%s = '%s'" % (col, value.replace("'", "''"))})
        consumed.append(phrase)
        return True

    # 1. Literal vocabulary values, longest first so "PHASE2/3" beats "PHASE2".
    for col, values in vocab.items():
        for vlow in sorted(values, key=len, reverse=True):
            if len(vlow) >= 4 and re.search(r"\b%s\b" % re.escape(vlow), low):
                take(col, values[vlow], values[vlow])

    # 2. The words people actually say.
    for col, table in SYNONYM.items():
        for phrase in sorted(table, key=len, reverse=True):
            if re.search(r"\b%s\b" % re.escape(phrase), low):
                take(col, table[phrase], phrase)

    # 3. Polarity -> CRITERION_SECTION.
    section, section_cue = None, None
    for pat, sec in SECTION_CUE:
        m = re.search(pat, low)
        if m:
            section, section_cue = sec, m.group(0)
            break

    # 4. What the layer cannot answer, said out loud.
    unresolved = []
    for pat, col, why in UNRESOLVED_CUE:
        if re.search(pat, low):
            unresolved.append({"column": col, "why": why})

    # 5. The residue IS the text half. Strip what the structured half consumed.
    text = q
    for phrase in sorted(consumed, key=len, reverse=True):
        text = re.sub(r"\b%s\b" % re.escape(phrase), " ", text, flags=re.I)
    if section_cue:
        text = re.sub(r"\b%s\b" % re.escape(section_cue), " ", text, flags=re.I)
    text = re.sub(r"\b(trials?|studies|study|patients?|participants?|subjects?|"
                  r"with|that|which|who|whose|whom|for|in|on|of|is|are|was|were|be|"
                  r"the|a|an|and|any|are|sponsored|enrolling)\b",
                  " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ,.;:-")

    return {
        "question": q,
        "structured": structured,
        "filter": " ".join(s["clause"] for s in structured),
        "section": section,
        "section_cue": section_cue,
        "text": text or q,
        "unresolved": unresolved,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(split(" ".join(sys.argv[1:])), indent=2))


# --- the blind spot the section column CANNOT close -------------------------
# When the opposite meaning is carried by a word that SURVIVES tokenisation
# ("negative" is not a stopword the way "no" is), the wrong criterion sits in the
# SAME section as the right one -- so there is nothing left to filter on. This
# finds it in a result list rather than asserting it, because its rank moves
# whenever the corpus does, and a booth claim that moved once will move again.
ANTONYM = {
    "positive": ["negative"], "negative": ["positive"],
    "present":  ["absent"],   "absent":   ["present"],
    "detected": ["undetected", "not detected"],
    "mutant":   ["wild-type", "wild type"],
    "with":     ["without"],
}


def blind_spot(question, rows, section):
    """First row in `rows` that sits in the intended section but says the
    opposite. Returns its 1-based rank, or None."""
    low = question.lower()
    wanted = []
    for word, opposites in ANTONYM.items():
        if re.search(r"\b%s\b" % re.escape(word), low):
            wanted += opposites
    if not wanted:
        return None
    for i, r in enumerate(rows, 1):
        if section and r.get("CRITERION_SECTION") != section:
            continue
        text = (r.get("CRITERION") or "").lower()
        for opp in wanted:
            if re.search(r"\b%s\b" % re.escape(opp), text):
                return {"rank": i, "nct": r.get("NCT_ID"),
                        "section": r.get("CRITERION_SECTION"),
                        "sim": r.get("VEC_SIM"), "term": opp,
                        "text": r.get("CRITERION")}
    return None
