#!/bin/bash
# c4 dry, step c: run export.tcl in G97's pinned ORFS image on G99's Ibex (k0), into dry/c4/record/<date>_c_export/.
# Usage (host, under a slot of 2.5 GB, like G97): bash dry/c4/export.sh <opentsense repo>
# Every input is checked before the record folder exists; exits with OpenROAD's exit code.
set -euo pipefail
OTD=$(cd "$1" && pwd)                       # absolute, so the cd below cannot change what $1 meant
OT=$(cd "$1" && pwd -W)
BUILDD=$(cd "$OTD/../../_build/g99/asap7-ibex-1400" && pwd)
BUILD=$(cd "$BUILDD" && pwd -W)
cd "$(dirname "$0")"
IMG=openroad/orfs@sha256:55266bc72fd67238407fa0c60da5a7f83c25ea14123829df769437d0dd0649ed   # G97's ORFS_IMAGE
RES=$BUILDD/results/asap7/ibex/base
INPUTS=(export.tcl "$OTD/gates/g96/dry/load_routed.tcl" "$OTD/gates/g100/runs/ibex-1400/sim/ibex/k0.vcd"
        "$RES/6_final.odb" "$RES/6_final.sdc" "$RES/6_final.spef")
for f in "${INPUTS[@]}"; do [ -f "$f" ] || { echo "missing $f"; exit 2; }; done
OUT=record/$(date +%F)_c_export
[ -e "$OUT" ] && { echo "$OUT exists: results are append-only"; exit 2; }
TMP=$OUT.partial
rm -rf "$TMP"; mkdir -p "$TMP"
{ sha256sum "${INPUTS[@]}"; echo "image $IMG"; } > "$TMP/inputs.sha256"
s=$(date +%s)
MSYS_NO_PATHCONV=1 docker run --rm --memory 2500m --memory-swap 2500m -v "$OT:/ot:ro" -v "$BUILD:/build:ro" \
  -v "$(pwd -W)/$TMP:/out" -v "$(pwd -W)/export.tcl:/c4/export.tcl:ro" \
  -e RES=/build/results/asap7/ibex/base -e CORNER=TT -e VTS=RVT -e VCD=/ot/gates/g100/runs/ibex-1400/sim/ibex/k0.vcd \
  -e VCD_SCOPE=tb/dut -e OUT=/out -e LOADER=/ot/gates/g96/dry/load_routed.tcl \
  "$IMG" /OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad -no_init -exit /c4/export.tcl \
  > "$TMP/export.log" 2>&1 && rc=0 || rc=$?
echo "rc=$rc after $(( $(date +%s) - s )) s" >> "$TMP/export.log"
mv "$TMP" "$OUT"                            # the record folder appears only once the run has ended
tail -1 "$OUT/export.log"
exit $rc
