#!/usr/bin/env python3
"""Build the retrieval artefacts offline, so the database only ever does maths.

Emits, for the eligibility chunks:
  elig_vectors.parquet  NCT_ID, CHUNK_ID, DIM, VAL   -- L2-normalised, so a dot
                        product IS cosine and similarity is a SQL GROUP BY
  chunk_tokens.parquet  NCT_ID, CHUNK_ID, TERM, TF   -- the BM25 side
  term_idf.parquet      TERM, DF, IDF
  chunk_len.parquet     NCT_ID, CHUNK_ID, LEN
  elig_model.pkl        vectorizer + SVD + normaliser, loaded by the query UDF

Determinism matters: the meetup kit taught us that an unordered scan plus a
positional split makes metrics wander. Chunks are sorted by (NCT_ID, CHUNK_ID)
before fitting and random_state is pinned.
"""
import argparse, csv, json, os, sys
import numpy as np
import pyarrow as pa, pyarrow.parquet as pq
from joblib import dump
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import Normalizer

csv.field_size_limit(10 ** 9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="/data/elig_chunks.csv")
    ap.add_argument("--out", default="/out")
    ap.add_argument("--dims", type=int, default=96)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    rows = []
    with open(a.chunks, newline="", encoding="utf8") as f:
        for r in csv.DictReader(f):
            rows.append((r["NCT_ID"], int(r["CHUNK_ID"]), r["CRITERION_SECTION"], r["CHUNK_TEXT"]))
    rows.sort(key=lambda x: (x[0], x[1]))          # determinism
    texts = [r[3] for r in rows]
    print(f"chunks: {len(rows)}", file=sys.stderr)

    vec = TfidfVectorizer(lowercase=True, stop_words="english", ngram_range=(1, 2),
                          min_df=3, max_df=0.6, sublinear_tf=True, max_features=300_000,
                          strip_accents="unicode")
    X = vec.fit_transform(texts)
    print(f"tfidf: {X.shape}", file=sys.stderr)

    svd = TruncatedSVD(n_components=a.dims, random_state=42, algorithm="randomized")
    norm = Normalizer(copy=False)                  # so dot product == cosine
    Z = norm.fit_transform(svd.fit_transform(X)).astype(np.float32)
    print(f"svd: {Z.shape}  explained={svd.explained_variance_ratio_.sum():.3f}",
          file=sys.stderr)

    nct = np.array([r[0] for r in rows], dtype=object)
    cid = np.array([r[1] for r in rows], dtype=np.int32)
    n, d = Z.shape
    pq.write_table(pa.table({
        "NCT_ID": pa.array(np.repeat(nct, d)),
        "CHUNK_ID": pa.array(np.repeat(cid, d)),
        "DIM": pa.array(np.tile(np.arange(d, dtype=np.int32), n)),
        "VAL": pa.array(Z.reshape(-1)),
    }), os.path.join(a.out, "elig_vectors.parquet"), compression="snappy")
    print(f"vectors: {n * d} rows", file=sys.stderr)

    # --- BM25 side, using the SAME analyzer so query and document agree ---
    analyzer = vec.build_analyzer()
    vocab = vec.vocabulary_
    t_nct, t_cid, t_term, t_tf, l_nct, l_cid, l_len = [], [], [], [], [], [], []
    df = {}
    for (nc, ci, _sec, txt) in rows:
        counts = {}
        toks = [t for t in analyzer(txt) if t in vocab]   # vocab-restricted = same space
        for t in toks:
            counts[t] = counts.get(t, 0) + 1
        l_nct.append(nc); l_cid.append(ci); l_len.append(len(toks))
        for t, c in counts.items():
            t_nct.append(nc); t_cid.append(ci); t_term.append(t); t_tf.append(c)
            df[t] = df.get(t, 0) + 1
    N = len(rows)
    terms = list(df)
    idf = [float(np.log(1.0 + (N - df[t] + 0.5) / (df[t] + 0.5))) for t in terms]
    pq.write_table(pa.table({"NCT_ID": pa.array(t_nct), "CHUNK_ID": pa.array(t_cid, type=pa.int32()),
                             "TERM": pa.array(t_term), "TF": pa.array(t_tf, type=pa.int32())}),
                   os.path.join(a.out, "chunk_tokens.parquet"), compression="snappy")
    pq.write_table(pa.table({"TERM": pa.array(terms), "DF": pa.array([df[t] for t in terms], type=pa.int32()),
                             "IDF": pa.array(idf, type=pa.float64())}),
                   os.path.join(a.out, "term_idf.parquet"), compression="snappy")
    pq.write_table(pa.table({"NCT_ID": pa.array(l_nct), "CHUNK_ID": pa.array(l_cid, type=pa.int32()),
                             "LEN": pa.array(l_len, type=pa.int32())}),
                   os.path.join(a.out, "chunk_len.parquet"), compression="snappy")
    print(f"tokens: {len(t_term)} rows, vocab {len(terms)}", file=sys.stderr)

    dump({"vectorizer": vec, "svd": svd, "normalizer": norm},
         os.path.join(a.out, "elig_model.pkl"), compress=3)
    meta = {"chunks": N, "dims": int(d), "vocab": len(terms),
            "avg_chunk_len": float(np.mean(l_len)),
            "explained_variance": float(svd.explained_variance_ratio_.sum()),
            "sklearn_pinned": True}
    json.dump(meta, open(os.path.join(a.out, "elig_model.meta.json"), "w"), indent=2)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
