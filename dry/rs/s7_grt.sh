#!/bin/bash
# rs-dry S7 (record/2026-11-19_s6_v1/NOTE.md): S6 again, with the kit's -gcell_size global-route flag dropped. S6
# showed the platform-scoped M2_add/M3_add patch works as far as it goes: Pin-3D's 2D asap7 stages pass and pin access
# completes (no DRT-0073). Global routing then got `-gcell_size`, which asap7_3D's config.mk adds whenever
# ASAP7_HBT_RDL is on, and which the pinned OpenROAD's global_route rejects (STA-0562). Pin-3D caught the error and
# went on with no route, so 5_2_route stopped. add_layers.py --config --drop-gcell also drops that line in this
# session's clone, so global routing uses OpenROAD's default gcell size (a deviation from the kit's 1.1 um, stated in
# the record). Nothing is exported. gcd first, then ibex. Attach the output of rajulkabir/open3d-rs-s1-build.
set -uo pipefail
OUT=${OUT:-/kaggle/working}
B=${B:-/tmp/rs}
BUDGET_S=${BUDGET_S:-39600}
TAR_RESERVE_S=${TAR_RESERVE_S:-1800}
source "$(dirname "$0")/rs_lib.sh"
session_start
python3 "$(dirname "$0")/add_layers.py" "$B/pin3d" --config --drop-gcell > "$R/add_layers.txt" 2>&1 \
  || { log "add_layers.py failed"; exit 1; }
cp "$B/pin3d/platforms/asap7_3D/config.mk" "$R/asap7_3D_config.mk"
log "S7: asap7_3D config.mk patched (add_layers.py --config --drop-gcell); no environment overrides"
run_case gcd asap7_3D
gcd_failed=$?
run_case ibex asap7_3D
exit $(( gcd_failed + $? ))
