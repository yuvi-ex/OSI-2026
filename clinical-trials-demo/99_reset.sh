#!/usr/bin/env bash
# Drops the schema and the local build artefacts. Keeps the committed snapshot.
source "$(dirname "$0")/lib/common.sh"
[ "${1:-}" = "--yes" ] || { echo "This drops schema $SCHEMA. Re-run with --yes"; exit 1; }
exa_sql "DROP SCHEMA IF EXISTS $SCHEMA CASCADE;"
rm -rf "$BFS_DIR/ct" || true
rm -rf "$WORK"
say "reset — snapshot in data/ kept"
