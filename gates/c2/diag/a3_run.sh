#!/bin/bash
# Amendment 3 probe: runs the variant decks a3_probe.py prepared in every <out>/GT_A5_* folder, then the report.
# As run on 18 Nov:  python -I a3_probe.py prepare ../runs a3 --valid 10  (run 3's runs/, since moved to
#                    open3d-thermal-ext/c2_run3_runs), then  bash a3_run.sh a3 <that runs dir>
# Usage: bash a3_run.sh <out> <run-3 runs dir>   (both required; relative paths are from the caller's directory)
set -uo pipefail
[ $# -eq 2 ] || { echo "usage: a3_run.sh <out> <run-3 runs dir>"; exit 2; }
OUT=$(cd "$1" && pwd) || exit 2
RUNS=$(cd "$2" && pwd) || exit 2
cd "$(dirname "$0")"
ls -d "$OUT"/GT_A5_* >/dev/null 2>&1 || { echo "no GT_A5_* folders in $OUT"; exit 2; }
for d in "$OUT"/GT_A5_*; do
  bash run_decks.sh "$d" "" 120 || echo "run_decks failed in $d"
  echo "done $(basename "$d") $(date +%T)"
done
python -I a3_probe.py report "$RUNS" "$OUT"
echo "rc=$?"
