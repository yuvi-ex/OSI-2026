#!/usr/bin/env python3
"""Parquet -> CSV, because the load path changed underneath us.

Parquet stays the build artefact: it is typed, it is a tenth of the size, and it
is what the embedding step naturally writes. But `exapump upload` (which read it
directly) is gone, and the Exasol CLI's bulk load is IMPORT FROM LOCAL CSV FILE,
which is CSV or nothing. So this transcodes, in batches, because ELIG_VECTORS is
25.8M rows and will not sit in memory twice.

Header row included -- the loader passes SKIP=1.
"""
import argparse, csv, os, sys
import pyarrow.parquet as pq


def convert(src, dest, batch_rows=500_000):
    f = pq.ParquetFile(src)
    n = 0
    with open(dest, "w", newline="", encoding="utf8") as fh:
        # LF only, and quote anything that needs it -- TERM is free text and a
        # criterion token can legitimately contain a comma or a quote.
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(f.schema_arrow.names)
        for batch in f.iter_batches(batch_size=batch_rows):
            cols = [c.to_pylist() for c in batch.columns]
            for row in zip(*cols):
                w.writerow(["" if v is None else v for v in row])
            n += batch.num_rows
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="/out", help="directory holding the .parquet files")
    ap.add_argument("files", nargs="+", help="parquet basenames to transcode")
    a = ap.parse_args()
    for name in a.files:
        src = os.path.join(a.dir, name)
        dest = src[:-len(".parquet")] + ".csv" if src.endswith(".parquet") else src + ".csv"
        n = convert(src, dest)
        print("    %-24s -> %-22s %10d rows  %6.1f MB"
              % (name, os.path.basename(dest), n, os.path.getsize(dest) / 1e6),
              file=sys.stderr)


if __name__ == "__main__":
    main()
