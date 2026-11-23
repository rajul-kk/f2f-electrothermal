#!/bin/bash
# rs-dry S4 (dry/rs/DESIGN.md, dry/rs/GRT0029.md): asap7_3D with the upper tier's pin layer inside the global-routing
# range. S2 and S3 (record/2026-11-18_s2_v2, record/2026-11-18_s3_v1) fail asap7_3D in 3_place_upper with GRT-0029:
# every upper-tier cell pin is on M1_m only, which sits above MAX_ROUTING_LAYER = M2_m in the mirrored stack, and
# OpenROAD's global router rejects a pin with no shape at or below the max layer. asap7_nangate45_3D passes because
# its max layer (M3_add) is above M1_m. Here MAX_ROUTING_LAYER = M1_m (the whole stack above M2, M1_m included, which
# has tracks and RC in this platform), set in the environment, which Pin-3D's `?=` keeps and its jobs inherit.
# gcd first (minutes; does the flow now pass 3_place_upper and finish?), then ibex with the rest of the budget.
# Attach the output of rajulkabir/open3d-rs-s1-build (kernel source). Everything goes under $OUT/record.
set -uo pipefail
OUT=${OUT:-/kaggle/working}
B=${B:-/tmp/rs}
BUDGET_S=${BUDGET_S:-39600}
TAR_RESERVE_S=${TAR_RESERVE_S:-1800}
source "$(dirname "$0")/rs_lib.sh"
session_start
export MAX_ROUTING_LAYER=M1_m
log "MAX_ROUTING_LAYER=$MAX_ROUTING_LAYER (S4 override)"
run_case gcd asap7_3D
gcd_failed=$?
run_case ibex asap7_3D
exit $(( gcd_failed + $? ))
