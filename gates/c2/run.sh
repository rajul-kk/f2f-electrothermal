#!/bin/bash
# C2 (registration.md). Usage (host, holding a heavy slot of 1 GB): bash gates/c2/run.sh <ext dir>
#   <ext dir> holds matrix-a5/, bsimcmg-111.2.1/ and osdi/ (outside the repository). Always all 15 libraries, into a
#   fresh runs/, so the summary never mixes runs. A failed simulation still ends in evaluate.py (a VOID, recorded).
set -euo pipefail
EXT=$(cd "$1" && pwd -W)
cd "$(dirname "$0")"
KIT=$EXT/matrix-a5/MATRIX_A5_CFET_base
CDL=$KIT/cdl/gtA5_cfet_11nm_cdl
PARAMS=$EXT/bsimcmg-111.2.1/code/bsimcmg_parameters.include
OSDI=$EXT/osdi/bsimcmg_111_2_1.osdi
IMG=opentsense:g93a
# inputs pinned in registration.md; anything else is refused before a run
[ "$(git -C "$EXT/matrix-a5" rev-parse HEAD)" = 56b467142c870284eb0cec1e89a680522e7a171d ] || { echo "kit commit differs"; exit 2; }
[ -z "$(git -C "$EXT/matrix-a5" status --porcelain)" ] || { echo "kit worktree dirty"; exit 2; }
sha256sum -c --quiet - <<EOF || { echo "pinned input hash differs"; exit 2; }
ce7b25c8f8b1706e1050db903173c8b0eda8424977b47ff1148192cd5bf6acac  $OSDI
33eed6409965c9584f7362bc4e64c9f54a10fff513bc78f43c10741310350697  $PARAMS
16918dc16766f83f778ec8a902dd36efdd5d14d219f8884f533897a863862669  $KIT/models/GT_A5_TTG.inc
40d8eb01c8b0a9c0c07fc760e7c175c0c09735aae7637fe2e037c8c11002b5e6  $KIT/models/GT_A5_SSG.inc
9eb5e23a5886b11d30f396a2982683361079da61e96ec3e17dba4b8b2f4ad4b7  $KIT/models/GT_A5_FFG.inc
EOF
LIBS=$(cd "$KIT/lib/GT_A5_release" && ls GT_A5_*_nldm.lib | sed 's/_nldm.lib//')
rm -rf runs record; mkdir -p runs record
{ docker image inspect "$IMG" --format "image $IMG {{.Id}}"; echo "matrix-a5 56b467142c870284eb0cec1e89a680522e7a171d"
  sha256sum "$OSDI" "$PARAMS" "$KIT"/models/GT_A5_{TTG,SSG,FFG}.inc "$KIT"/lib/GT_A5_release/GT_A5_*_nldm.lib \
    "$CDL"/*.cdl leak.py evaluate.py run.sh registration.md
} > record/sha256.txt
for L in $LIBS; do
  CORNER=$(echo "$L" | cut -d_ -f4)          # GT_A5_<vt>_<corner>_<temp>
  mkdir -p "runs/$L"
  MSYS_NO_PATHCONV=1 python leak.py deck "$KIT/models/GT_A5_$CORNER.inc" "$PARAMS" "$CDL" \
    "$KIT/lib/GT_A5_release/${L}_nldm.lib" /osdi/bsimcmg_111_2_1.osdi "runs/$L" all
  # Git-Bash must not have rewritten the in-container OSDI path (lint L24)
  [ "$(tr -d '\r' < "runs/$L/.spiceinit")" = "osdi /osdi/bsimcmg_111_2_1.osdi" ] || { echo "bad .spiceinit in $L"; exit 1; }
done
sha256sum runs/*/*.cir runs/*/models.inc runs/*/cases.json runs/*/.spiceinit >> record/sha256.txt
# one deck per cell; its exit code goes to runs/<lib>/<cell>.rc (missing = failed; 124 = over the 2 min cap, where a
# cell alone takes about a second); leak.py compare marks a nonzero one invalid (V1)
MSYS_NO_PATHCONV=1 docker run --rm --memory 1g -v "$(pwd -W)/runs:/runs" -v "$EXT/osdi:/osdi:ro" "$IMG" \
  bash -c 'for d in /runs/*/; do cd "$d" || continue; for f in *.cir; do
             timeout 120 ngspice -b "$f" > "${f%.cir}.log" 2>&1; echo $? > "${f%.cir}.rc"; done; done' \
  || echo "container exit $?" >> record/ngspice_rc.txt
for L in $LIBS; do
  echo "$L decks $(ls runs/$L/*.cir | wc -l), exit 0: $(grep -lx 0 runs/$L/*.rc 2>/dev/null | wc -l)"
done >> record/ngspice_rc.txt
for L in $LIBS; do python leak.py compare "runs/$L"; done
python evaluate.py runs | tee record/summary.md
cp runs/summary.json record/
