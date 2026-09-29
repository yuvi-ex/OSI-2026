#!/usr/bin/env python3
"""Fetch the publications that cite our trials, and keep the ones that do not.

THE JOIN IS REAL, NOT FUZZY. PubMed records carry the trial registry number as a
DataBank accession (`<DataBank><DataBankName>ClinicalTrials.gov`), so trial to
paper is an equi-join on NCT_ID -- no title matching, no heuristics, nothing that
needs a caveat on a booth screen.

The interesting output is not the matches. Measured on a sample of completed
trials, only about a third have a linked publication; the rest are the finding.

NOTE on that 'about a third': a paper that never cites its NCT number is
invisible here, so this UNDERCOUNTS publication. The demo says so rather than
claiming every unmatched trial is unpublished.

Writes data/pubmed_snapshot.json.gz -- committed, because a booth demo must never
depend on the venue network.
"""
import gzip, json, os, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

E = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
TOOL = "exasol-clinical-trials-demo"
SEARCH_BATCH = 100      # NCT ids per esearch
FETCH_BATCH = 200       # pmids per efetch
PAUSE = 0.4             # NCBI allows 3 req/s unauthenticated


def get(endpoint, params, retries=4):
    params = dict(params, tool=TOOL)
    url = E + endpoint + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def find_pmids(ncts):
    """esearch, batched: which PMIDs cite any of these trials."""
    pmids = set()
    for i in range(0, len(ncts), SEARCH_BATCH):
        chunk = ncts[i:i + SEARCH_BATCH]
        term = " OR ".join("%s[si]" % n for n in chunk)
        raw = get("esearch.fcgi", {"db": "pubmed", "term": term,
                                   "retmode": "json", "retmax": "1000"})
        pmids |= set(json.loads(raw)["esearchresult"].get("idlist", []))
        print("  esearch %5d/%d  pmids so far %d"
              % (min(i + SEARCH_BATCH, len(ncts)), len(ncts), len(pmids)), file=sys.stderr)
        time.sleep(PAUSE)
    return sorted(pmids)


def text(node, path):
    el = node.find(path)
    return "".join(el.itertext()).strip() if el is not None else ""


def parse_article(art):
    """One PubmedArticle -> a flat record. Absences stay empty, never guessed."""
    cit = art.find("MedlineCitation")
    if cit is None:
        return None
    pmid = text(cit, "PMID")
    a = cit.find("Article")
    if a is None:
        return None

    # Year: ArticleDate, then JournalIssue PubDate, then MedlineDate's first year.
    year = ""
    for path in ("ArticleDate/Year", "Journal/JournalIssue/PubDate/Year"):
        year = text(a, path)
        if year:
            break
    if not year:
        md = text(a, "Journal/JournalIssue/PubDate/MedlineDate")
        year = md[:4] if md[:4].isdigit() else ""

    doi = ""
    for aid in art.iter("ArticleId"):
        if aid.get("IdType") == "doi":
            doi = (aid.text or "").strip()

    # The join key. One paper can report more than one trial.
    ncts = []
    for bank in art.iter("DataBank"):
        if text(bank, "DataBankName") == "ClinicalTrials.gov":
            for acc in bank.iter("AccessionNumber"):
                v = (acc.text or "").strip().upper()
                if v.startswith("NCT"):
                    ncts.append(v)

    abstract = " ".join(
        "".join(s.itertext()).strip() for s in a.iter("AbstractText")).strip()

    return {
        "PMID": pmid,
        "DOI": doi,
        "TITLE": text(a, "ArticleTitle"),
        "JOURNAL": text(a, "Journal/ISOAbbreviation") or text(a, "Journal/Title"),
        "PUB_YEAR": year,
        "PUB_TYPES": sorted({(p.text or "").strip()
                             for p in a.iter("PublicationType") if p.text}),
        "NCT_IDS": sorted(set(ncts)),
        "ABSTRACT": abstract[:4000],
    }


def fetch_records(pmids):
    out = []
    for i in range(0, len(pmids), FETCH_BATCH):
        chunk = pmids[i:i + FETCH_BATCH]
        raw = get("efetch.fcgi", {"db": "pubmed", "id": ",".join(chunk),
                                  "retmode": "xml"})
        root = ET.fromstring(raw)
        for art in root.iter("PubmedArticle"):
            rec = parse_article(art)
            if rec and rec["NCT_IDS"]:      # keep only what actually joins
                out.append(rec)
        print("  efetch  %5d/%d  kept %d" % (min(i + FETCH_BATCH, len(pmids)),
                                             len(pmids), len(out)), file=sys.stderr)
        time.sleep(PAUSE)
    return out


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(root, "data", "trials_snapshot.json.gz")
    dest = os.path.join(root, "data", "pubmed_snapshot.json.gz")

    trials = json.load(gzip.open(src, "rt", encoding="utf8"))["studies"]
    ncts = sorted({s["protocolSection"]["identificationModule"]["nctId"] for s in trials})
    print("trials in snapshot: %d" % len(ncts), file=sys.stderr)

    pmids = find_pmids(ncts)
    print("distinct PMIDs: %d" % len(pmids), file=sys.stderr)

    recs = fetch_records(pmids)
    ours = set(ncts)
    linked = {n for r in recs for n in r["NCT_IDS"]} & ours
    print("publications kept: %d" % len(recs), file=sys.stderr)
    print("trials linked    : %d of %d (%.1f%%)"
          % (len(linked), len(ours), 100.0 * len(linked) / len(ours)), file=sys.stderr)

    with gzip.open(dest, "wt", encoding="utf8") as fh:
        json.dump({"publications": recs,
                   "source": "PubMed E-utilities, DataBank accession join",
                   "trials_in_scope": len(ours),
                   "trials_linked": len(linked)}, fh)
    print("wrote %s (%.1f MB)" % (dest, os.path.getsize(dest) / 1e6), file=sys.stderr)


if __name__ == "__main__":
    main()
