#!/bin/bash
# c3 (DESIGN.md). Usage (host, holding a heavy slot of 1 GB): bash dry/c3/run_c3.sh <ext dir>
#   <ext dir> holds matrix-a5/, bsimcmg-111.2.1/ and osdi/, as for C2. Decks come from C2's leak.py unchanged; only
#   their .temp line is set (c3.py retemp). C2 run 5's per-library results (gates/c2/runs) are read for checks 1 and 4.
#   Always all 18 libraries, into a fresh runs/.
set -euo pipefail
EXT=$(cd "$1" && pwd -W)
cd "$(dirname "$0")"
C2=../../gates/c2
KIT=$EXT/matrix-a5/MATRIX_A5_CFET_base
CDL=$KIT/cdl/gtA5_cfet_11nm_cdl
PARAMS=$EXT/bsimcmg-111.2.1/code/bsimcmg_parameters.include
OSDI=$EXT/osdi/bsimcmg_111_2_1.osdi
IMG=opentsense:g93a
# the same pinned inputs as C2 (gates/c2/run.sh), and C2 run 5's results as recorded in its record
[ "$(git -C "$EXT/matrix-a5" rev-parse HEAD)" = 56b467142c870284eb0cec1e89a680522e7a171d ] || { echo "kit commit differs"; exit 2; }
[ -z "$(git -C "$EXT/matrix-a5" status --porcelain)" ] || { echo "kit worktree dirty"; exit 2; }
sha256sum -c --quiet - <<EOF || { echo "pinned input hash differs"; exit 2; }
ce7b25c8f8b1706e1050db903173c8b0eda8424977b47ff1148192cd5bf6acac  $OSDI
33eed6409965c9584f7362bc4e64c9f54a10fff513bc78f43c10741310350697  $PARAMS
16918dc16766f83f778ec8a902dd36efdd5d14d219f8884f533897a863862669  $KIT/models/GT_A5_TTG.inc
EOF
for vt in svt lvt ulvt; do for c in TTG_25C SSG_125C FFG_125C; do
  [ -f "$C2/runs/GT_A5_${vt}_$c/result.json" ] || { echo "C2 run 5 result missing: $vt $c"; exit 2; }
done; done
rm -rf runs record; mkdir -p runs record
{ docker image inspect "$IMG" --format "image $IMG {{.Id}}"; echo "matrix-a5 56b467142c870284eb0cec1e89a680522e7a171d"
  sha256sum "$OSDI" "$PARAMS" "$KIT/models/GT_A5_TTG.inc" "$KIT"/lib/GT_A5_release/GT_A5_*_TTG_25C_nldm.lib \
    "$CDL"/*.cdl "$C2/leak.py" "$C2/ngspice_states.sh" c3.py run_c3.sh "$C2"/runs/GT_A5_*/result.json
} > record/sha256.txt
for vt in svt lvt ulvt; do
  for T in 25 45 65 85 105 125; do
    L=GT_A5_${vt}_TTG_${T}C
    mkdir -p "runs/$L"
    MSYS_NO_PATHCONV=1 python "$C2/leak.py" deck "$KIT/models/GT_A5_TTG.inc" "$PARAMS" "$CDL" \
      "$KIT/lib/GT_A5_release/GT_A5_${vt}_TTG_25C_nldm.lib" /osdi/bsimcmg_111_2_1.osdi "runs/$L" all
    python c3.py retemp "runs/$L" "$T"
    [ "$(tr -d '\r' < "runs/$L/.spiceinit")" = "osdi /osdi/bsimcmg_111_2_1.osdi" ] || { echo "bad .spiceinit in $L"; exit 1; }
  done
done
sha256sum runs/*/*.cir runs/*/models.inc runs/*/cases.json >> record/sha256.txt
MSYS_NO_PATHCONV=1 docker run --rm --memory 1g -v "$(pwd -W)/runs:/runs" -v "$EXT/osdi:/osdi:ro" \
  -v "$(cd "$C2" && pwd -W)/ngspice_states.sh:/ngspice_states.sh:ro" "$IMG" bash -c 'bash /ngspice_states.sh /runs/*/' \
  || echo "container exit $?" >> record/ngspice_rc.txt
for d in runs/*/; do
  L=$(basename "$d")
  echo "$L decks $(ls "$d"s????.cir | wc -l), exit 0: $(grep -lx 0 "$d"s????.rc 2>/dev/null | wc -l)," \
       "retried $(ls "$d"s????r.rc 2>/dev/null | wc -l), retry exit 0: $(grep -lx 0 "$d"s????r.rc 2>/dev/null | wc -l)"
done >> record/ngspice_rc.txt
for d in runs/*/; do python "$C2/leak.py" compare "${d%/}"; done
python c3.py tables runs "$C2/runs" record
