#!/bin/bash
# rs-dry S2 (dry/rs/DESIGN.md): restore S1's build on a fresh Kaggle CPU session, list Pin-3D's OpenROAD runs and run
# gcd on asap7_3D, the README's own example. If gcd fails, the toolchain (not ibex) is the problem.
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
pin3d gcd --flow ord --tech asap7_3D --case gcd || exit 1
log "gcd ok"
