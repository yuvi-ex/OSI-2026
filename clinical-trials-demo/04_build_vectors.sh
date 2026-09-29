#!/usr/bin/env bash
# STEP 4 — retrieval artefacts. Everything expensive happens OUTSIDE the database;
# the database is left with arithmetic it can parallelise.
source "$(dirname "$0")/lib/common.sh"

say "4a. Build the training image (sklearn pinned to the SLC's version)"
docker build -q -t "$ML_IMAGE" \
  --build-arg SK_VERSION="$SK_VERSION" --build-arg NP_VERSION="$NP_VERSION" "$KIT_ROOT/ml" \
  || die "docker build failed — is Docker running?"
ok "$ML_IMAGE"

say "4b. Embed the eligibility chunks (TF-IDF -> SVD -> L2 normalise)"
mkdir -p "$WORK/art"
docker run --rm -v "$WORK/csv:/data:ro" -v "$WORK/art:/out" "$ML_IMAGE" \
  --chunks /data/elig_chunks.csv --out /out --dims "$DIMS"

say "4c. Parquet -> CSV for the loader"
# Parquet is still what the embedding step writes. The bulk-load path is now the
# Exasol CLI's IMPORT FROM LOCAL CSV FILE, which does not read Parquet, so the
# artefacts are transcoded here -- in the same image, because pyarrow lives there
# and not on the host.
docker run --rm -v "$WORK/art:/out" --entrypoint python "$ML_IMAGE" \
  /w/parquet_to_csv.py --dir /out \
  chunk_len.parquet term_idf.parquet chunk_tokens.parquet elig_vectors.parquet

say "4d. Retrieval tables"
xsql -f "$KIT_ROOT/sql/02_retrieval_tables.sql" | tail -2
for pair in "chunk_len.csv:CT.CHUNK_LEN" "term_idf.csv:CT.TERM_IDF" \
            "chunk_tokens.csv:CT.CHUNK_TOKENS" "elig_vectors.csv:CT.ELIG_VECTORS"; do
  f="${pair%%:*}"; t="${pair##*:}"
  printf '    %-24s -> %s\n' "$f" "$t"
  exa_load "$t" "$WORK/art/$f" >/dev/null
done

say "4e. Model -> BucketFS"
# BucketFS HTTP is not exposed on Personal (2581 refuses; writes want a password
# nobody set). On the local backend it is a directory the VM SHARES WITH THE HOST,
# so putting the model there is a plain copy -- see lib/common.sh.
bfs_put "$WORK/art/elig_model.pkl" "ct/elig_model.pkl"

say "4f. The query-side UDFs"
xsql -f "$KIT_ROOT/sql/04_udfs.sql" | tail -2
xsql "SELECT COUNT(*) AS DIMS, ROUND(SQRT(SUM(VAL*VAL)),4) AS NORM
      FROM (SELECT CT.EMBED_QUERY('test query') FROM DUAL);"
ok "norm 1.0 means a dot product IS cosine"

say "4g. How big the vector table is"
xsql "SELECT COUNT(*) AS VECTOR_ROWS, COUNT(DISTINCT NCT_ID) AS TRIALS FROM CT.ELIG_VECTORS;"
say "STEP 4 DONE"
