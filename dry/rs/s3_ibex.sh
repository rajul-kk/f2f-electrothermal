#!/bin/bash
# rs-dry S3 (dry/rs/DESIGN.md): restore S1's build on a fresh Kaggle CPU session and run Pin-3D's OpenROAD flow on
# ibex. S2 v2 (record/2026-11-18_s2_v2): gcd completes the OpenROAD run on asap7_nangate45_3D and fails in upper-tier
# placement (GRT-0029) on asap7_3D and nangate45_3D; its eval phase calls a Cadence step, so runs are --run-only.
# asap7_3D first (expected to fail within minutes; it shows whether ibex fails the same way), then
# asap7_nangate45_3D with the rest of the budget.
# Attach the output of rajulkabir/open3d-rs-s1-build (kernel source). Everything goes under $OUT/record.
set -uo pipefail
OUT=${OUT:-/kaggle/working}
B=${B:-/tmp/rs}
BUDGET_S=${BUDGET_S:-39600}
TAR_RESERVE_S=${TAR_RESERVE_S:-1800}
source "$(dirname "$0")/rs_lib.sh"
session_start
run_case ibex asap7_3D asap7_nangate45_3D
