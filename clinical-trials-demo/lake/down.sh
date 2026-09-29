#!/usr/bin/env bash
# Stop the lake. The Iceberg data survives in the named volume; `down -v` would
# destroy it and the virtual schema would go empty without any error.
set -euo pipefail
cd "$(dirname "$0")"
docker compose down
echo "lake stopped (data kept — 'docker compose down -v' to destroy it)"
