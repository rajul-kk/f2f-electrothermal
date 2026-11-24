#!/bin/bash
# rs-dry S6 (dry/rs/GRT0029.md, section S4; record/2026-11-19_s5_v1/NOTE.md): asap7_3D with two routing layers above
# the upper tier's M1_m, scoped to the 3D platform. S4 showed upper-tier pins need a layer above M1_m (FlexPA reaches
# instance pins by up vias only). S5 added the hybrid platform's V1_add/M2_add/V2_add/M3_add but set the files and
# MAX_ROUTING_LAYER in the environment, which also reached Pin-3D's 2D asap7 stages; their floorplan sourced the 3D RC
# script and stopped (EST-0205, V_HB_B). Here add_layers.py --config edits asap7_3D's config.mk in this session's
# clone instead: its hbrdl tech LEF, RC and track pointers go to the *_add copies, MAX_ROUTING_LAYER to M3_add, and
# ASAP7_HBT_RDL_RCX_RULES is emptied (the kit's 15-layer rules do not cover the new layers, so no final extraction).
# Nothing is exported. gcd first, then ibex. Attach the output of rajulkabir/open3d-rs-s1-build (kernel source).
set -uo pipefail
OUT=${OUT:-/kaggle/working}
B=${B:-/tmp/rs}
BUDGET_S=${BUDGET_S:-39600}
TAR_RESERVE_S=${TAR_RESERVE_S:-1800}
source "$(dirname "$0")/rs_lib.sh"
session_start
python3 "$(dirname "$0")/add_layers.py" "$B/pin3d" --config > "$R/add_layers.txt" 2>&1 \
  || { log "add_layers.py failed"; exit 1; }
cp "$B/pin3d/platforms/asap7_3D/config.mk" "$R/asap7_3D_config.mk"
log "S6: asap7_3D config.mk patched (add_layers.py --config); no environment overrides"
run_case gcd asap7_3D
gcd_failed=$?
run_case ibex asap7_3D
exit $(( gcd_failed + $? ))
