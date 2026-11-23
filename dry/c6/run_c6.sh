#!/bin/bash
# c6 (DESIGN.md). Usage (host, under a medium slot of 1.5 GB): bash dry/c6/run_c6.sh <ext dir> <opentsense repo>
#   <ext dir> holds matrix-a5/ (for the TT 25 C Liberty areas); <opentsense repo> is the FYP package's git repo,
#   read only: its HEAD is exported with git archive into runs/pkg and mounted read only. Always a fresh runs/.
set -euo pipefail
EXT=$(cd "$1" && pwd)
OTR=$(cd "$2" && pwd)
cd "$(dirname "$0")"
IMG=opentsense:g93a
LIB=$EXT/matrix-a5/MATRIX_A5_CFET_base/lib/GT_A5_release
[ "$(git -C "$EXT/matrix-a5" rev-parse HEAD)" = 56b467142c870284eb0cec1e89a680522e7a171d ] || { echo "kit commit differs"; exit 2; }
OTC=$(git -C "$OTR" rev-parse HEAD)
OUT=record/$(date +%F)_c6_v1
[ -e "$OUT" ] && { echo "$OUT exists: results are append-only"; exit 2; }
rm -rf runs; mkdir -p runs/pkg runs/work "$OUT.partial"
git -C "$OTR" archive "$OTC" opentsense | tar -x -C runs/pkg
python c6.py leak ../c3/record/tables.json runs/leak.json \
  "$LIB/GT_A5_svt_TTG_25C_nldm.lib" "$LIB/GT_A5_lvt_TTG_25C_nldm.lib" "$LIB/GT_A5_ulvt_TTG_25C_nldm.lib"
{ docker image inspect "$IMG" --format "image $IMG {{.Id}}"; echo "opentsense $OTC"
  echo "matrix-a5 56b467142c870284eb0cec1e89a680522e7a171d"
  sha256sum c6.py run_c6.sh ../c3/record/tables.json runs/leak.json "$LIB"/GT_A5_*_TTG_25C_nldm.lib
} > "$OUT.partial/inputs.sha256"
cp runs/leak.json "$OUT.partial/leak.json"
s=$(date +%s)
MSYS_NO_PATHCONV=1 docker run --rm --memory 1500m --memory-swap 1500m -v "$(pwd -W)/runs:/runs" \
  -v "$(pwd -W)/c6.py:/c6/c6.py:ro" -e PYTHONPATH=/runs/pkg:/c6 "$IMG" \
  bash -c 'cd /c6 && python c6.py run /runs/leak.json /runs/work /runs/out' > "$OUT.partial/run.log" 2>&1 && rc=0 || rc=$?
echo "rc=$rc after $(( $(date +%s) - s )) s" >> "$OUT.partial/run.log"
[ -f runs/out/c6.json ] && cp runs/out/c6.json "$OUT.partial/"
mv "$OUT.partial" "$OUT"                    # the record folder appears only once the run has ended
[ "$rc" = 0 ] && python c6.py summary "$OUT/c6.json" "$OUT/summary.md"
tail -1 "$OUT/run.log"
exit $rc
