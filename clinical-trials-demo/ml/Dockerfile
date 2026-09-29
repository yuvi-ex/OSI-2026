# Pinned to the versions the Exasol SLC ships. If these drift, the UDF cannot
# unpickle the analyzer: py 3.12.3 / numpy 1.26.4 / sklearn 1.7.2 (verified in-DB).
FROM python:3.12-slim
ARG SK_VERSION=1.7.2
ARG NP_VERSION=1.26.4
RUN pip install --no-cache-dir \
      "numpy==${NP_VERSION}" "scikit-learn==${SK_VERSION}" \
      "scipy==1.14.1" "joblib==1.4.2" "pyarrow==17.0.0"
WORKDIR /w
COPY build_vectors.py parquet_to_csv.py /w/
ENTRYPOINT ["python", "/w/build_vectors.py"]
