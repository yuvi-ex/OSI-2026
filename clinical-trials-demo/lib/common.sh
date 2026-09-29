# Shared settings for the clinical-trials retrieval demo.
set -euo pipefail

KIT_ROOT="${KIT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
WORK="${WORK:-$KIT_ROOT/.work}"
DATA="${DATA:-$KIT_ROOT/data}"
mkdir -p "$WORK" "$DATA"

SCHEMA="${SCHEMA:-CT}"
# Retrieval width. 96 dims x ~10 chunks x ~10k trials is ~10M rows in the long
# vector table -- comfortable for Exasol, and small enough to rebuild in a break.
DIMS="${DIMS:-96}"
MAX_CHUNKS="${MAX_CHUNKS:-10}"
# The training image pins sklearn to whatever the SLC ships, or the pickle the
# UDF loads will refuse to unpickle. Verified: py 3.12.3 / numpy 1.26.4 / sklearn 1.7.2.
SK_VERSION="${SK_VERSION:-1.7.2}"
NP_VERSION="${NP_VERSION:-1.26.4}"
ML_IMAGE="${ML_IMAGE:-ct-vectors:local}"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[0;32mok\033[0m  %s\n' "$*"; }
warn() { printf '    \033[0;33m!!\033[0m  %s\n' "$*"; }
die()  { printf '\n\033[0;31merror: %s\033[0m\n' "$*" >&2; exit 1; }

# The question in English before the SQL -- the room reads this, the SQL is the proof.
ask() {
  printf '\n\033[7;1m  THE QUESTION                                                  \033[0m\n'
  while IFS= read -r line; do printf '\033[7m \033[0m  \033[1m%s\033[0m\n' "$line"; done
  printf '\033[7m \033[0m\n'
}

SHOW_SQL="${SHOW_SQL:-1}"

# --- talking to the database ------------------------------------------------
# 2026-09-21: `exapump` is gone from PATH. The Exasol CLI now ships a real SQL
# client, so that is the single route to the database: results on stdout as CSV,
# its own chatter on stderr, non-zero exit on a SQL error. -k because Personal
# serves a self-signed certificate.
EXA=(exasol connect -k --csv)
exa_sql()  { "${EXA[@]}" -c "$1"; }
exa_file() { "${EXA[@]}" -f "$1"; }

# Echo the statement before running it, to stderr: stdout is the result CSV and
# callers pipe it.
xsql() {
  if [ "$SHOW_SQL" = "1" ]; then
    local body
    if [ "${1:-}" = "-f" ]; then body="$(cat "$2")"; else body="$1"; fi
    printf '\n\033[0;90m--- SQL ---\033[0m\n%s\n\033[0;90m-----------\033[0m\n' "$body" >&2
  fi
  if [ "${1:-}" = "-f" ]; then exa_file "$2"; else exa_sql "$1"; fi
}

# Bulk load, the replacement for `exapump upload`. IMPORT FROM LOCAL CSV FILE is
# executed by the client, which streams the file to the database over its own
# loopback proxy -- so the path is a HOST path and needs no share and no copy.
# SKIP=1 because every CSV this kit writes carries a header row.
exa_load() {
  local table="$1" file="$2"
  [ -s "$file" ] || die "load $table: $file is missing or empty"
  case "$file" in /*) ;; *) file="$PWD/$file" ;; esac
  exa_sql "IMPORT INTO $table FROM LOCAL CSV FILE '${file//\'/\'\'}' SKIP=1;"
}

# Exasol Personal licenses 20 parallel connections and dash-server parks ~3 per
# board, idle, forever. Reclaim them or a later step dies one connection short
# and reports it as a credential failure.
free_connections() {
  local n
  n=$(exa_sql "SELECT COUNT(*) AS N FROM EXA_ALL_SESSIONS;" 2>/dev/null | tail -1 | grep -oE '^[0-9]+$' || echo 0)
  [ "${n:-0}" -gt 12 ] && warn "$n sessions open of 20 — consider: exasol stop && exasol start" || true
}

# --- BucketFS on Exasol Personal --------------------------------------------
# The BucketFS HTTP port is not exposed on Personal (2581 refuses, and writes
# want a bfs_write_password nobody set). On the local backend the node is a VM
# whose /exa is a folder SHARED WITH THE HOST, so BucketFS is an ordinary
# directory here and a write is a `cp` -- no SSH, no scp, no port that moves on
# every restart. (It used to be root SSH; `deployment.json` no longer publishes
# an sshPort, and the CLI's `exasol shell host` is interactive-only.)
DEPLOY_DIR="${DEPLOY_DIR:-$HOME/.exasol/personal/deployments/default}"
BFS_DIR="${BFS_DIR:-$DEPLOY_DIR/local/runtime/exa/bucketfs/bfsdefault/default}"
# The same directory as the UDF sandbox sees it.
BFS_UDF="${BFS_UDF:-/buckets/bfsdefault/default}"

# --- the lake ---------------------------------------------------------------
# The Exasol node is a VM; 192.168.64.1 is its gateway back to the host, which is
# where the lake containers publish their ports. 'localhost' resolves INSIDE the
# VM and fails -- the single most likely reason a lake query returns nothing.
LAKE_HOST="${LAKE_HOST:-192.168.64.1}"
LAKE_S3_PORT="${LAKE_S3_PORT:-19000}"
LAKE_CATALOG_PORT="${LAKE_CATALOG_PORT:-18181}"
LAKE_NAMESPACE="${LAKE_NAMESPACE:-ct}"

bfs_put() {
  local src="$1" dest="$2"
  mkdir -p "$(dirname "$BFS_DIR/$dest")"
  cp "$src" "$BFS_DIR/$dest"
  ls -lh "$BFS_DIR/$dest"
}
