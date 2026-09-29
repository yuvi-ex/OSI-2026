#!/usr/bin/env bash
# Install the lakehouse engine into Exasol Personal -- the manual equivalent of
# the vendor installer, which CANNOT run here.
#
# deploy/scripts/install.sh targets a Personal *local* deployment over SSH using
# local/node_access.pem and connection.sshPort from deployment.json. Neither
# exists in the current Personal build, and the installer also requires exapump.
# It does not matter: on the local backend the VM shares /exa with the host, so
# BucketFS is an ordinary directory and "upload" is a copy. Everything below is
# what the installer would have done, done directly.
#
# Idempotent. Safe to re-run.
source "$(dirname "$0")/../lib/common.sh"

SLC_VERSION="${SLC_VERSION:-0.26.1}"       # must match the engine's exasol-udf-sdk
ENGINE_VERSION="${ENGINE_VERSION:-v0.46.1}"
ARCH="${ARCH:--aarch64}"                   # Apple Silicon; use "" for x86_64
DL="$WORK/lh"; mkdir -p "$DL"

SO_UDF_OBJECT="buckets/bfsdefault/default/udf/liblakehouse_engine.so"
RUST_DEF="RUST=localzmq+protobuf:///bfsdefault/default/slc/lakehouse-rustslc?lang=rust#buckets/bfsdefault/default/slc/lakehouse-rustslc/exaudf/exaudfclient"

say "L1. Fetch the Rust SLC and the engine"
[ -s "$DL/lc-rust.tar.gz" ] || curl -fsSL -o "$DL/lc-rust.tar.gz" \
  "https://github.com/exasol-labs/language-container-rs/releases/download/v$SLC_VERSION/lc-rust-$SLC_VERSION$ARCH.tar.gz"
[ -s "$DL/engine.tar.gz" ] || curl -fsSL -o "$DL/engine.tar.gz" \
  "https://github.com/exasol-labs/lakehouse-engine-rs/releases/download/$ENGINE_VERSION/lakehouse-engine$ARCH.tar.gz"
ok "SLC $SLC_VERSION, engine $ENGINE_VERSION"

say "L2. Place them in BucketFS (a directory, on this backend)"
mkdir -p "$BFS_DIR/udf" "$BFS_DIR/slc/lakehouse-rustslc"
rm -rf "$DL/x"; mkdir -p "$DL/x"
tar xzf "$DL/engine.tar.gz" -C "$DL/x"
cp "$DL/x/udf/liblakehouse_engine.so" "$BFS_DIR/udf/liblakehouse_engine.so"
[ -x "$BFS_DIR/slc/lakehouse-rustslc/exaudf/exaudfclient" ] || \
  tar xzf "$DL/lc-rust.tar.gz" -C "$BFS_DIR/slc/lakehouse-rustslc"
ok "$(ls -lh "$BFS_DIR/udf/liblakehouse_engine.so" | awk '{print $5}') engine .so + SLC in place"

say "L3. Register the RUST language (leaving PYTHON3 alone)"
# PYTHON3 must survive: CT.EMBED_QUERY and CT.QUERY_TERMS are Python UDFs.
CUR=$(exa_sql "SELECT SYSTEM_VALUE FROM EXA_PARAMETERS WHERE PARAMETER_NAME='SCRIPT_LANGUAGES';" 2>/dev/null | tail -1)
NEW=$(echo "$CUR $RUST_DEF" | awk '{sep=""; for(i=1;i<=NF;i++){if($i ~ /^RUST=/ && i<NF) continue; printf "%s%s",sep,$i; sep=" "}}')
exa_sql "ALTER SYSTEM SET SCRIPT_LANGUAGES = '$NEW';" >/dev/null
ok "$(echo "$NEW" | tr ' ' '\n' | cut -d= -f1 | tr '\n' ' ')"

say "L4. The engine's four scripts"
cat > "$WORK/lh_scripts.sql" <<EOF
CREATE SCHEMA IF NOT EXISTS LAKEHOUSE;
CREATE OR REPLACE RUST ADAPTER SCRIPT LAKEHOUSE.LAKEHOUSE_ADAPTER AS
%udf_object $SO_UDF_OBJECT
/
CREATE OR REPLACE RUST SCALAR SCRIPT LAKEHOUSE.LAKEHOUSE_SCAN(common VARCHAR(2000000), files VARCHAR(2000000))
EMITS (...) AS
%udf_object $SO_UDF_OBJECT
/
CREATE OR REPLACE RUST SCALAR SCRIPT LAKEHOUSE.LAKEHOUSE_VERSION()
RETURNS VARCHAR(100) AS
%udf_object $SO_UDF_OBJECT
/
CREATE OR REPLACE LUA SET SCRIPT LAKEHOUSE.LAKEHOUSE_DISTRIBUTE_FILES(files VARCHAR(2000000))
EMITS (files VARCHAR(2000000)) AS
function run(ctx)
    repeat
        ctx.emit(ctx.files)
    until not ctx.next()
end
/
EOF
exa_file "$WORK/lh_scripts.sql" >/dev/null
ok "engine loads: $(exa_sql "SELECT LAKEHOUSE.LAKEHOUSE_VERSION();" 2>/dev/null | tail -1)"

say "L5. Point a virtual schema at the lake"
# 192.168.64.1 is the VM's gateway back to the mac. 'localhost' would resolve
# INSIDE the VM and fail -- the trap the engine docs warn about for containers.
cat > "$WORK/lh_vs.sql" <<EOF
CREATE OR REPLACE CONNECTION LAKEHOUSE_CATALOG_CREDS
  TO 'http://$LAKE_HOST:$LAKE_CATALOG_PORT'
  USER ''
  IDENTIFIED BY '{
    "warehouse":  "s3://warehouse/",
    "region":     "us-east-1",
    "endpoint":   "http://$LAKE_HOST:$LAKE_S3_PORT",
    "access_key": "minioadmin",
    "secret_key": "minioadmin",
    "path_style": true
  }';
DROP VIRTUAL SCHEMA IF EXISTS CT_LAKE CASCADE;
CREATE VIRTUAL SCHEMA CT_LAKE
USING LAKEHOUSE.LAKEHOUSE_ADAPTER WITH
  CATALOG_CONNECTION = 'LAKEHOUSE_CATALOG_CREDS'
  NAMESPACE          = '$LAKE_NAMESPACE'
  ALLOW_HTTP         = 'true';
EOF
exa_file "$WORK/lh_vs.sql" >/dev/null
xsql "SELECT COLUMN_TABLE AS LAKE_TABLE, COUNT(*) AS COLUMNS
      FROM EXA_ALL_COLUMNS WHERE COLUMN_SCHEMA='CT_LAKE' GROUP BY 1 ORDER BY 1;"
say "ENGINE INSTALLED — the lake is queryable as CT_LAKE"
