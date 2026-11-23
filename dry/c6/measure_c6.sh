#!/bin/bash
# c6 cost probe (A10), before the full run: the largest stack (200 um carrier) alone at the full grid, in the same
# container and memory cap as run_c6.sh; prints wall time and peak RSS of python and of its PACT child processes.
# Usage (host, under the full run's slot): bash dry/c6/measure_c6.sh <opentsense repo>; needs runs/leak.json from a
# previous `c6.py leak` (it stops otherwise). Output goes to stdout only (the slot log); nothing is recorded.
set -euo pipefail
OTR=$(cd "$1" && pwd)
cd "$(dirname "$0")"
rm -rf probe; mkdir -p probe/pkg
git -C "$OTR" archive "$(git -C "$OTR" rev-parse HEAD)" opentsense | tar -x -C probe/pkg
[ -f runs/leak.json ] && cp runs/leak.json probe/leak.json
[ -f probe/leak.json ] || { echo "no runs/leak.json: run c6.py leak first"; exit 2; }
s=$(date +%s)
MSYS_NO_PATHCONV=1 docker run --rm --memory 1500m --memory-swap 1500m -v "$(pwd -W)/probe:/p" \
  -v "$(pwd -W)/c6.py:/c6/c6.py:ro" -e PYTHONPATH=/p/pkg:/c6 opentsense:g93a python -c '
import resource, c6
c6.run("/p/leak.json", "/p/work", "/p/out", only={"bs_kbeol0.6_tc200_kbs71"})
mb = lambda who: resource.getrusage(who).ru_maxrss / 1024
print(f"peak RSS python {mb(resource.RUSAGE_SELF):.0f} MB, children {mb(resource.RUSAGE_CHILDREN):.0f} MB")'
echo "probe wall $(( $(date +%s) - s )) s"
rm -rf probe
