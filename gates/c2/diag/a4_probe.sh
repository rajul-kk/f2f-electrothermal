#!/bin/bash
# Amendment 4 probe: Amendment 4's decks (retry deck, `print all`) for the libraries named, then leak.py compare and
# evaluate.py, into <out>. It checks two things before run 5: the retry reaches a DC point for run 4's above-cut state
# without one, and the kit floor computed from each operating point accounts for the gap in the floored states
# (evaluate.py's floor_check). evaluate.py reports the other libraries as missing; only the named ones are read.
# Usage (host, holding a heavy slot of 1 GB): bash diag/a4_probe.sh <ext dir> <out> <library>...
set -euo pipefail
[ $# -ge 3 ] || { echo "usage: a4_probe.sh <ext dir> <out> <library>..."; exit 2; }
EXT=$(cd "$1" && pwd -W)
mkdir -p "$2"
OUT=$(cd "$2" && pwd -W)
shift 2
cd "$(dirname "$0")/.."
KIT=$EXT/matrix-a5/MATRIX_A5_CFET_base
DIRS=()
for L in "$@"; do
  rm -rf "${OUT:?}/$L"; mkdir -p "$OUT/$L"   # fresh, so no deck, log or retry file of an earlier probe is read
  DIRS+=("/runs/$L")
  MSYS_NO_PATHCONV=1 python leak.py deck "$KIT/models/GT_A5_$(echo "$L" | cut -d_ -f4).inc" \
    "$EXT/bsimcmg-111.2.1/code/bsimcmg_parameters.include" "$KIT/cdl/gtA5_cfet_11nm_cdl" \
    "$KIT/lib/GT_A5_release/${L}_nldm.lib" /osdi/bsimcmg_111_2_1.osdi "$OUT/$L" all
done
MSYS_NO_PATHCONV=1 docker run --rm --memory 1g -v "$OUT:/runs" -v "$EXT/osdi:/osdi:ro" \
  -v "$(pwd -W)/ngspice_states.sh:/ngspice_states.sh:ro" opentsense:g93a bash /ngspice_states.sh "${DIRS[@]}"
for L in "$@"; do python leak.py compare "$OUT/$L"; done
python evaluate.py "$OUT"
