#!/bin/bash
# rs-dry S2 (dry/rs/DESIGN.md): restore S1's build on a fresh Kaggle CPU session, list Pin-3D's OpenROAD runs and run
# gcd, the README's own example. v1 (record/2026-11-18_s2_v1): asap7_3D gcd fails in upper-tier placement (GRT-0029);
# v2 runs gcd on all three ord techs, each whatever the others did, to tell an asap7_3D problem from a flow-wide one.
# Attach the output of rajulkabir/open3d-rs-s1-build (kernel source). Everything goes under $OUT/record.
set -uo pipefail
OUT=${OUT:-/kaggle/working}
B=${B:-/tmp/rs}
BUDGET_S=${BUDGET_S:-39600}
TAR_RESERVE_S=${TAR_RESERVE_S:-1800}
source "$(dirname "$0")/rs_lib.sh"
trap 'finish_common $?' EXIT
start_memory
machine_and_tools
prepare_toolchain || exit $?
prepare_pin3d || exit 1
pin3d list --flow ord --list || exit 1
failed=0
for tech in asap7_3D asap7_nangate45_3D nangate45_3D; do
  if pin3d "gcd_$tech" --flow ord --tech "$tech" --case gcd; then log "gcd $tech ok"; else failed=$((failed + 1)); fi
done
log "gcd failed in $failed of 3 techs"
[ $failed -eq 0 ]
