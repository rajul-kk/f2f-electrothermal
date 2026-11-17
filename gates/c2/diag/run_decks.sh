#!/bin/bash
# Run every <dir>/<prefix>*.cir in the registered image (ngspice 45.2, the kit's OSDI), one ngspice per deck with a
# cap of <cap> s; writes <deck>.log and <deck>.rc. Paths are resolved before anything else, so relative ones work.
# Usage: bash run_decks.sh <dir> [prefix] [cap seconds, default 120]
set -euo pipefail
DIR=$(cd "$1" && pwd -W); PREFIX=${2:-}; CAP=${3:-120}
OSDI=D:/Work/open3d-thermal-ext/osdi
MSYS_NO_PATHCONV=1 docker run --rm --memory 512m -v "$DIR:/w" -v "$OSDI:/osdi:ro" opentsense:g93a \
  bash -c "cd /w; for f in ${PREFIX}*.cir; do timeout $CAP ngspice -b \"\$f\" > \"\${f%.cir}.log\" 2>&1; echo \$? > \"\${f%.cir}.rc\"; done"
