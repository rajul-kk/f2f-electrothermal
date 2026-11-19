#!/bin/bash
# c4 dry: the records the README cites after the second review (all append-only, new names). Usage: bash records_v2.sh
# The last line is rc=<number of failed steps>, so a log that ends rc=0 means every record was written.
set -uo pipefail
cd "$(dirname "$0")"
E=record/2026-11-18_c_export
failed=0
run() { "$@"; local rc=$?; echo "$* rc=$rc"; [ $rc -eq 0 ] || failed=$((failed + 1)); }
run python -I pgspice.py "$E" VDD --name d1v2
run python -I pgspice.py "$E" VSS --name d1v2
run python -I explore_d2.py "$E" record/2026-11-18_d2_explore_v2.json
run python -I rail_ladder.py "$E" record/2026-11-18_d2_rail_v2.json
echo "rc=$failed"
