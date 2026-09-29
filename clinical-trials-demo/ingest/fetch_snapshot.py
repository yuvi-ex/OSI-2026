#!/usr/bin/env python3
"""Fetch a field-trimmed ClinicalTrials.gov v2 snapshot and write it gzipped.

Ships with the repo on purpose: a booth demo must never depend on the venue
network, and the API advertises no rate limit, so there is no quota to plan
around -- only a courtesy delay between pages.
"""
import gzip, json, sys, time, urllib.parse, urllib.request

# Trimmed to the semantic layer plus the two free-text surfaces the demo needs.
# Untrimmed records are several times larger and do not belong in git.
FIELDS = [
    "NCTId", "BriefTitle", "OverallStatus", "StudyType", "Phase",
    "LeadSponsorName", "LeadSponsorClass", "EnrollmentCount", "StartDate",
    "Condition", "LocationCountry",
    "EligibilityCriteria", "MinimumAge", "MaximumAge", "Sex", "HealthyVolunteers",
    "PrimaryOutcomeMeasure", "PrimaryOutcomeTimeFrame",
    "SecondaryOutcomeMeasure",
    "ArmGroupType", "ArmGroupLabel",
    "InterventionType", "InterventionName",
]
BASE = "https://clinicaltrials.gov/api/v2/studies"
# Interventional only, 2015 onward: keeps the snapshot booth-sized and the
# landscape current. Deliberately does NOT filter on phase -- ~22% of trials
# have no phase and losing them would hide a real failure mode.
ADV = "AREA[StudyType]INTERVENTIONAL AND AREA[StartDate]RANGE[2015-01-01,MAX]"


def page(cond, token=None, page_size=1000):
    q = {
        "query.cond": cond,
        "filter.advanced": ADV,
        "fields": "|".join(FIELDS),
        "pageSize": str(page_size),
        "countTotal": "true",
    }
    if token:
        q["pageToken"] = token
    url = BASE + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "exasol-ct-demo/1.0"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf8"))
        except Exception as e:                       # noqa: BLE001
            if attempt == 4:
                raise
            wait = 2 ** attempt
            print(f"    retry in {wait}s ({e})", file=sys.stderr)
            time.sleep(wait)


def fetch(cond, indication):
    out, token, total = [], None, None
    while True:
        d = page(cond, token)
        if total is None:
            total = d.get("totalCount")
            print(f"  {indication}: {total} trials", file=sys.stderr)
        for s in d.get("studies", []):
            s["_indication"] = indication      # provenance, so the union stays explainable
            out.append(s)
        token = d.get("nextPageToken")
        print(f"    {len(out)}/{total}", file=sys.stderr)
        if not token:
            break
        time.sleep(0.5)                        # courtesy, not a documented requirement
    return out


def main():
    dest = sys.argv[1] if len(sys.argv) > 1 else "data/trials_snapshot.json.gz"
    studies = []
    for cond, ind in [("non-small cell lung cancer", "NSCLC"),
                      ("breast cancer", "BREAST")]:
        studies += fetch(cond, ind)
    # One trial can match both conditions; keep the first and record the clash
    # rather than silently dropping a row.
    seen, uniq, dupes = set(), [], 0
    for s in studies:
        nct = s.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
        if not nct:
            continue
        if nct in seen:
            dupes += 1
            continue
        seen.add(nct)
        uniq.append(s)
    meta = {"fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "advanced_filter": ADV, "fields": FIELDS,
            "trials": len(uniq), "cross_listed_dropped": dupes}
    with gzip.open(dest, "wt", encoding="utf8") as f:
        json.dump({"_meta": meta, "studies": uniq}, f)
    print(f"\n{len(uniq)} trials -> {dest}  ({dupes} cross-listed duplicates dropped)",
          file=sys.stderr)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
