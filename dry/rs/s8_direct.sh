#!/bin/bash
# rs-dry S8 (record/2026-11-19_s7_v1/NOTE.md): the two added layers on asap7_3D's direct tech view. S7 got global
# routing through on the kit's default hbrdl view, but detailed routing stopped at track assignment: HBM_T, the hbrdl
# bonding layer, has tracks 1 um apart, and the pinned OpenROAD makes its global-routing cells narrower than that
# (15 track pitches of routing layers 2-4; global_route has no setting), so some cells hold no HBM_T track
# (DRT-0406). The kit's -gcell_size 1.1 was meant to avoid this, but that build has no such flag. The direct view
# (asap7_tech_1x_2A6M7M.lef, ASAP7_HBT_RDL pinned to 0) bonds M7 to M6_m through hb_layer, a cut layer with no tracks.
# add_layers.py --view direct --config patches that view in this session's clone: the added layers, their tracks and
# RC, MAX_ROUTING_LAYER M3_add, and extraction on the kit's 15-layer asap7_tech_1x_2A6M7M deck, with Pin-3D's own
# LayerCount check turned on (final_report.tcl: "INFO(RC): verified ..." or "RCX layer mismatch"), so the run itself
# shows whether deck and tech agree. Nothing is exported. gcd first, then ibex. Attach the output of
# rajulkabir/open3d-rs-s1-build.
set -uo pipefail
OUT=${OUT:-/kaggle/working}
B=${B:-/tmp/rs}
BUDGET_S=${BUDGET_S:-39600}
TAR_RESERVE_S=${TAR_RESERVE_S:-1800}
source "$(dirname "$0")/rs_lib.sh"
session_start
python3 "$(dirname "$0")/add_layers.py" "$B/pin3d" --view direct --config > "$R/add_layers.txt" 2>&1 \
  || { log "add_layers.py failed"; exit 1; }
cp "$B/pin3d/platforms/asap7_3D/config.mk" "$R/asap7_3D_config.mk"
log "S8: asap7_3D direct view patched (add_layers.py --view direct --config); no environment overrides"
run_case gcd asap7_3D
gcd_failed=$?
run_case ibex asap7_3D
exit $(( gcd_failed + $? ))
