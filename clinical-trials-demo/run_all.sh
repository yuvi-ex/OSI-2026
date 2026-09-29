#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
for s in 01_snapshot 02_load_exasol 03_semantic_layer 04_build_vectors 05_search 06_eval; do
  ./$s.sh
done
# The lake is a second system, so it is brought up explicitly rather than assumed.
./lake/up.sh
./lake/install_engine.sh
.work/lakeenv/bin/python lake/load_iceberg.py
./07_lake.sh
./00_preflight.sh
