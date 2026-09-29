#!/usr/bin/env python3
"""Shred the snapshot into flat CSVs for the bulk loader.

The important part is eligibility. ClinicalTrials.gov gives ONE free-text blob
with no structured inclusion/exclusion split -- the split exists only as prose
headings. We recover it here, per chunk, because "which section did this come
from" is precisely what a similarity score cannot tell you.
"""
import csv, gzip, json, os, re, sys

OUT = sys.argv[2] if len(sys.argv) > 2 else ".work/csv"

# Headings seen in the wild: "Inclusion Criteria:", "INCLUSION CRITERIA",
# "Key Inclusion Criteria", "Patient Inclusion Criteria" ...
SEC_RE = re.compile(
    r"^\s*(?:key\s+|main\s+|patient\s+|subject\s+)?(inclusion|exclusion)\s*"
    r"(?:criteria)?\s*[:\-–]?\s*$", re.I)
INLINE_RE = re.compile(
    r"(?:key\s+|main\s+)?(inclusion|exclusion)\s+criteria\s*[:\-–]", re.I)
# Bullets: "-", "*", "1.", "1)", "a.", "(1)"
BULLET_RE = re.compile(r"^\s*(?:[-*•–]|\(?\d{1,2}[.)]|\(?[a-z][.)])\s+", re.I)


def phase_of(mod):
    ph = (mod or {}).get("phases") or []
    if not ph:
        return "UNKNOWN", ""            # ~22% of trials. Never silently drop these.
    raw = "|".join(ph)
    if ph == ["NA"]:
        return "NOT_APPLICABLE", raw
    nums = sorted({p.replace("PHASE", "") for p in ph if p.startswith("PHASE")})
    return ("PHASE" + "/".join(nums), raw) if nums else (raw, raw)


def age_years(s):
    if not s:
        return ""
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*(year|month|week|day)", s, re.I)
    if not m:
        return ""
    v, u = float(m.group(1)), m.group(2).lower()
    return round(v * {"year": 1, "month": 1 / 12, "week": 1 / 52, "day": 1 / 365}[u], 3)


def chunk_eligibility(text):
    """-> [(section, chunk_text)] with section in INCLUSION/EXCLUSION/UNKNOWN."""
    if not text:
        return []
    # Normalise the inline form onto its own line so one parser handles both.
    text = INLINE_RE.sub(lambda m: "\n" + m.group(1).title() + " Criteria:\n", text)
    section, buf, out = "UNKNOWN", [], []

    def flush():
        if buf:
            t = re.sub(r"\s+", " ", " ".join(buf)).strip()
            if len(t) >= 15:                       # drop "N/A", stray punctuation
                out.append((section, t))
            buf.clear()

    for line in text.split("\n"):
        if not line.strip():
            continue
        m = SEC_RE.match(line)
        if m:
            flush()
            section = m.group(1).upper()
            continue
        if BULLET_RE.match(line):                  # a new criterion starts here
            flush()
            buf.append(BULLET_RE.sub("", line).strip())
        else:
            buf.append(line.strip())               # continuation of the current one
    flush()
    return out


def w(name, header):
    os.makedirs(OUT, exist_ok=True)
    f = open(os.path.join(OUT, name), "w", newline="", encoding="utf8")
    # LF only, header row first: the loader passes SKIP=1 and CRLF corrupts the
    # last column of every row.
    c = csv.writer(f, lineterminator="\n")
    c.writerow(header)
    return f, c


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "data/trials_snapshot.json.gz"
    with gzip.open(src, "rt", encoding="utf8") as fh:
        d = json.load(fh)
    studies = d["studies"]

    files = {}
    files["t"] = w("trials.csv", ["NCT_ID", "INDICATION", "BRIEF_TITLE", "OVERALL_STATUS",
                                  "STUDY_TYPE", "PHASE", "PHASE_RAW", "LEAD_SPONSOR",
                                  "SPONSOR_CLASS", "ENROLLMENT", "START_DATE",
                                  "MIN_AGE_YEARS", "MAX_AGE_YEARS", "SEX",
                                  "HEALTHY_VOLUNTEERS", "ELIG_CHARS", "ELIGIBILITY_TEXT"])
    files["c"] = w("trial_conditions.csv", ["NCT_ID", "CONDITION_NAME"])
    files["g"] = w("trial_countries.csv", ["NCT_ID", "COUNTRY"])
    files["o"] = w("trial_outcomes.csv", ["NCT_ID", "SEQ", "OUTCOME_KIND", "MEASURE", "TIME_FRAME"])
    files["a"] = w("trial_arms.csv", ["NCT_ID", "SEQ", "ARM_TYPE", "ARM_LABEL"])
    files["i"] = w("trial_interventions.csv", ["NCT_ID", "SEQ", "INTERVENTION_TYPE", "INTERVENTION_NAME"])
    files["e"] = w("elig_chunks.csv", ["NCT_ID", "CHUNK_ID", "CRITERION_SECTION", "CHUNK_TEXT"])

    n = {"trials": 0, "chunks": 0, "incl": 0, "excl": 0, "unk": 0, "no_elig": 0}
    for s in studies:
        p = s.get("protocolSection", {}) or {}
        idm, stm, dsm = p.get("identificationModule", {}), p.get("statusModule", {}), p.get("designModule", {})
        spm, elm = p.get("sponsorCollaboratorsModule", {}), p.get("eligibilityModule", {}) or {}
        com, ocm = p.get("conditionsModule", {}) or {}, p.get("outcomesModule", {}) or {}
        aim, ctm = p.get("armsInterventionsModule", {}) or {}, p.get("contactsLocationsModule", {}) or {}
        nct = idm.get("nctId")
        if not nct:
            continue
        phase, praw = phase_of(dsm)
        elig = elm.get("eligibilityCriteria") or ""
        enr = (dsm.get("enrollmentInfo") or {}).get("count", "")
        files["t"][1].writerow([
            nct, s.get("_indication", ""), idm.get("briefTitle", ""),
            stm.get("overallStatus", ""), dsm.get("studyType", ""), phase, praw,
            (spm.get("leadSponsor") or {}).get("name", ""),
            (spm.get("leadSponsor") or {}).get("class", ""),
            enr, (stm.get("startDateStruct") or {}).get("date", ""),
            age_years(elm.get("minimumAge")), age_years(elm.get("maximumAge")),
            elm.get("sex", ""), elm.get("healthyVolunteers", ""), len(elig), elig])
        n["trials"] += 1

        for c in (com.get("conditions") or []):
            files["c"][1].writerow([nct, c])
        seen_country = set()
        for loc in (ctm.get("locations") or []):
            cy = loc.get("country")
            if cy and cy not in seen_country:
                seen_country.add(cy)
                files["g"][1].writerow([nct, cy])
        for kind, key in (("PRIMARY", "primaryOutcomes"), ("SECONDARY", "secondaryOutcomes")):
            for i, o in enumerate(ocm.get(key) or []):
                files["o"][1].writerow([nct, i, kind, o.get("measure", ""), o.get("timeFrame", "")])
        for i, a in enumerate(aim.get("armGroups") or []):
            # type is absent on a meaningful minority -- record it as UNSPECIFIED
            # rather than NULL so "trials with no coded comparator" is queryable.
            files["a"][1].writerow([nct, i, a.get("type") or "UNSPECIFIED", a.get("label", "")])
        for i, iv in enumerate(aim.get("interventions") or []):
            files["i"][1].writerow([nct, i, iv.get("type", ""), iv.get("name", "")])

        chunks = chunk_eligibility(elig)
        if not chunks:
            n["no_elig"] += 1
        for i, (sec, txt) in enumerate(chunks):
            files["e"][1].writerow([nct, i, sec, txt])
            n["chunks"] += 1
            n["incl" if sec == "INCLUSION" else "excl" if sec == "EXCLUSION" else "unk"] += 1

    for f, _ in files.values():
        f.close()
    print(json.dumps(n, indent=2))
    print(f"\ncsv -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
