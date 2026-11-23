#!/bin/bash
# rs-dry S5 (dry/rs/GRT0029.md, section S4): asap7_3D with two routing layers above the upper tier's M1_m.
# S4 (record/2026-11-19_s4_v1) set MAX_ROUTING_LAYER = M1_m: GRT-0029 went, and gcd and ibex then failed pin access
# (DRT-0073) on upper-tier inner pins, because the detailed router reaches an instance pin only by an up via and
# M1_m is the top layer of every asap7_3D tech LEF. asap7_nangate45_3D, which routes, has V1_add/M2_add/V2_add/M3_add
# above M1_m. add_layers.py copies those layers, their two vias, tracks and RC from that platform into new asap7_3D
# files (the originals unchanged); the environment points TECH_LEF, MAKE_TRACKS and SET_RC_TCL at them and sets
# MAX_ROUTING_LAYER = M3_add, which Pin-3D's `?=` keeps and its jobs inherit. gcd first, then ibex.
# Attach the output of rajulkabir/open3d-rs-s1-build (kernel source). Everything goes under $OUT/record.
set -uo pipefail
OUT=${OUT:-/kaggle/working}
B=${B:-/tmp/rs}
BUDGET_S=${BUDGET_S:-39600}
TAR_RESERVE_S=${TAR_RESERVE_S:-1800}
source "$(dirname "$0")/rs_lib.sh"
session_start
python3 "$(dirname "$0")/add_layers.py" "$B/pin3d" > "$R/add_layers.txt" 2>&1 || { log "add_layers.py failed"; exit 1; }
P=$B/pin3d/platforms/asap7_3D
export TECH_LEF=$P/lef/asap7_tech_1x_2A6M7M_hbrdl_add.lef
export MAKE_TRACKS=$P/openRoad/make_tracks.2A6M7M_hbrdl_add.tcl
export SET_RC_TCL=$P/setRC_2A6M7M_hbrdl_add.tcl
export MAX_ROUTING_LAYER=M3_add
log "S5 overrides: TECH_LEF, MAKE_TRACKS, SET_RC_TCL to the *_add copies; MAX_ROUTING_LAYER=$MAX_ROUTING_LAYER"
run_case gcd asap7_3D
gcd_failed=$?
run_case ibex asap7_3D
exit $(( gcd_failed + $? ))
