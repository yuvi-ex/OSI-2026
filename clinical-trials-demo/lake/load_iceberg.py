#!/usr/bin/env python3
"""Publish the PubMed snapshot into the lake as Iceberg tables.

TWO tables, not one. A publication can report several trials, so the link is
many-to-many; flattening it into a list column would make the join a lookup
instead of an equi-join, and the whole point of this source is that the join key
is real. PUB_TYPES stays a delimited string for the same reason a list column
would cost more than it is worth here.

Run with the venv that has pyiceberg:  .work/lakeenv/bin/python lake/load_iceberg.py
"""
import gzip, json, os, sys
import pyarrow as pa
from pyiceberg.catalog.rest import RestCatalog

# Host-side addresses. Exasol reaches the same lake on 192.168.64.1 -- the
# Iceberg metadata stores s3:// paths, not endpoints, so each side configures
# its own and they do not have to agree.
CATALOG_URI = os.environ.get("LAKE_CATALOG", "http://127.0.0.1:18181")
S3_ENDPOINT = os.environ.get("LAKE_S3", "http://127.0.0.1:19000")
NAMESPACE = "ct"

PUB_SCHEMA = pa.schema([
    ("pmid", pa.string()), ("doi", pa.string()), ("title", pa.string()),
    ("journal", pa.string()), ("pub_year", pa.int32()),
    ("pub_types", pa.string()), ("abstract", pa.string()),
])
LINK_SCHEMA = pa.schema([("nct_id", pa.string()), ("pmid", pa.string())])


def catalog():
    return RestCatalog("ct", **{
        "uri": CATALOG_URI,
        "warehouse": "s3://warehouse/",
        "s3.endpoint": S3_ENDPOINT,
        "s3.access-key-id": "minioadmin",
        "s3.secret-access-key": "minioadmin",
        "s3.path-style-access": "true",
        "s3.region": "us-east-1",
    })


def replace(cat, name, schema, table):
    ident = "%s.%s" % (NAMESPACE, name)
    if cat.table_exists(ident):
        cat.drop_table(ident)
    t = cat.create_table(ident, schema=schema)
    t.append(table)
    return t


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(root, "data", "pubmed_snapshot.json.gz")
    if not os.path.exists(src):
        sys.exit("no %s -- run ingest/fetch_pubmed.py first" % src)
    d = json.load(gzip.open(src, "rt", encoding="utf8"))
    pubs = d["publications"]

    def year(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    pub_tbl = pa.Table.from_pylist([{
        "pmid": p["PMID"], "doi": p["DOI"], "title": p["TITLE"],
        "journal": p["JOURNAL"], "pub_year": year(p["PUB_YEAR"]),
        "pub_types": "|".join(p["PUB_TYPES"]), "abstract": p["ABSTRACT"],
    } for p in pubs], schema=PUB_SCHEMA)

    links = [{"nct_id": n, "pmid": p["PMID"]} for p in pubs for n in p["NCT_IDS"]]
    link_tbl = pa.Table.from_pylist(links, schema=LINK_SCHEMA)

    cat = catalog()
    try:
        cat.create_namespace(NAMESPACE)
    except Exception:
        pass
    replace(cat, "publications", PUB_SCHEMA, pub_tbl)
    replace(cat, "trial_publications", LINK_SCHEMA, link_tbl)

    print("ct.publications        %7d rows" % pub_tbl.num_rows)
    print("ct.trial_publications  %7d rows  (%d distinct trials)"
          % (link_tbl.num_rows, len({l["nct_id"] for l in links})))


if __name__ == "__main__":
    main()
