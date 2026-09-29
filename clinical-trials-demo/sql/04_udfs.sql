-- ===================================================================
-- The only Python that runs at query time. Documents were embedded offline;
-- these two scripts put the QUERY into the same space, so all the database
-- has to do afterwards is arithmetic.
-- ===================================================================

-- Query -> 96 normalised dimensions, one row each, to be joined against
-- CT.ELIG_VECTORS. EMITS because one input row becomes DIMS rows.
CREATE OR REPLACE PYTHON3 SCALAR SCRIPT CT.EMBED_QUERY(q VARCHAR(4000))
EMITS (DIM DECIMAL(9,0), VAL DOUBLE) AS
import joblib

# Module scope: loaded once per UDF VM, not once per row. The pickle is ~94MB
# (a bigram vocabulary dominates), so per-row loading would be unusable.
_M = None

def _model():
    global _M
    if _M is None:
        _M = joblib.load('/buckets/bfsdefault/default/ct/elig_model.pkl')
    return _M

def run(ctx):
    if ctx.q is None or not ctx.q.strip():
        return
    m = _model()
    # Exactly the transform the documents went through, in the same order.
    z = m['normalizer'].transform(m['svd'].transform(m['vectorizer'].transform([ctx.q])))
    for i, v in enumerate(z[0]):
        ctx.emit(i, float(v))
/

-- Query -> its BM25 terms, using the SAME analyzer and the SAME vocabulary as
-- the documents. Terms outside the vocabulary are dropped rather than scored,
-- which is why an out-of-vocabulary query degrades quietly instead of erroring.
CREATE OR REPLACE PYTHON3 SCALAR SCRIPT CT.QUERY_TERMS(q VARCHAR(4000))
EMITS (TERM VARCHAR(200), QTF DECIMAL(9,0)) AS
import joblib

_M = None

def _model():
    global _M
    if _M is None:
        _M = joblib.load('/buckets/bfsdefault/default/ct/elig_model.pkl')
    return _M

def run(ctx):
    if ctx.q is None or not ctx.q.strip():
        return
    m = _model()
    vec = m['vectorizer']
    analyzer = vec.build_analyzer()
    vocab = vec.vocabulary_
    counts = {}
    for t in analyzer(ctx.q):
        if t in vocab:
            counts[t] = counts.get(t, 0) + 1
    for t, c in counts.items():
        ctx.emit(t, c)
/
