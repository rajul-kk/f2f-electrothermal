#!/bin/bash
# rs-dry S2 (dry/rs/DESIGN.md): restore S1's build on a fresh Kaggle CPU session, list Pin-3D's OpenROAD runs and run
# gcd, the README's own example. v1 (record/2026-11-18_s2_v1): asap7_3D gcd fails in upper-tier placement (GRT-0029);
# v2 (record/2026-11-18_s2_v2): the run completes on asap7_nangate45_3D only, and the eval phase needs Cadence. This
# version (helpers moved into rs_lib.sh, runs --run-only) has not been run; v1 and v2 keep their scripts in their records.
# Attach the output of rajulkabir/open3d-rs-s1-build (kernel source). Everything goes under $OUT/record.
set -uo pipefail
OUT=${OUT:-/kaggle/working}
B=${B:-/tmp/rs}
BUDGET_S=${BUDGET_S:-39600}
TAR_RESERVE_S=${TAR_RESERVE_S:-1800}
source "$(dirname "$0")/rs_lib.sh"
session_start
LIST=1 pin3d list --flow ord --list || exit 1
run_case gcd asap7_3D asap7_nangate45_3D nangate45_3D
