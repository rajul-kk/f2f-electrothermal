#!/bin/bash
# c6 (DESIGN.md). Usage (host, under a medium slot of 1.5 GB): bash dry/c6/run_c6.sh <ext dir> <opentsense repo>
#   <ext dir> holds matrix-a5/ (for the TT 25 C Liberty areas); <opentsense repo> is the FYP package's git repo,
#   read only: its HEAD is exported with git archive into runs/stage/pkg. Always a fresh runs/.
#   PKG=worktree instead takes the package's working tree as it stands (every file, tracked or not, no __pycache__), for a fix
#   that is queued but not yet committed; the record then keeps HEAD, `git status` of the package and the exact
#   package as opentsense_pkg.tgz with its sha256, so the run is reproducible without that commit.
#   One c6 run at a time: runs.lock (mkdir, atomic) is held from before the guards to the end. The image is launched by
#   the ID the record states. c6.py, leak.json and the package are staged once in runs/stage, mounted read only, and
#   their digests are checked before the run and again before the summary (Amendment 1; C6-1, C6-2).
set -euo pipefail
EXT=$(cd "$1" && pwd)
OTR=$(cd "$2" && pwd)
cd "$(dirname "$0")"
mkdir runs.lock 2>/dev/null || { echo "runs.lock exists: another c6 run is using runs/ (or one died: look, then rmdir it)"; exit 2; }
trap 'rmdir runs.lock' EXIT
IMG=opentsense:g93a
IMGID=$(docker image inspect "$IMG" --format '{{.Id}}')
LIB=$EXT/matrix-a5/MATRIX_A5_CFET_base/lib/GT_A5_release
[ "$(git -C "$EXT/matrix-a5" rev-parse HEAD)" = 56b467142c870284eb0cec1e89a680522e7a171d ] || { echo "kit commit differs"; exit 2; }
OTC=$(git -C "$OTR" rev-parse HEAD)
OUT=record/$(date +%F)_c6_${TAG:-v2}   # v1 (19 Nov) was stopped by hand, rc 137, before the review fixes
[ -e "$OUT" ] && { echo "$OUT exists: results are append-only"; exit 2; }
[ -e "$OUT.partial" ] && { echo "$OUT.partial exists: an earlier run did not finish; look at it, then move it aside"; exit 2; }
rm -rf runs; mkdir -p runs/stage/pkg runs/work runs/out "$OUT.partial"
S=runs/stage
cp c6.py "$S/c6.py"
case "${PKG:-head}" in
  head) git -C "$OTR" archive "$OTC" opentsense | tar -x -C "$S/pkg"; PKGDESC="opentsense $OTC" ;;
  worktree)
    (cd "$OTR" && find opentsense -type f -not -path '*/__pycache__/*' | sort | tar -czf - -T -) \
      > "$OUT.partial/opentsense_pkg.tgz"
    tar -xzf "$OUT.partial/opentsense_pkg.tgz" -C "$S/pkg"
    git -C "$OTR" status --porcelain -- opentsense > "$OUT.partial/opentsense_status.txt"
    PKGDESC="opentsense worktree over HEAD $OTC; package $(sha256sum "$OUT.partial/opentsense_pkg.tgz" | cut -c1-64)" ;;
  *) echo "PKG must be head or worktree"; exit 2 ;;
esac
python "$S/c6.py" leak ../c3/record/tables.json "$S/leak.json" \
  "$LIB/GT_A5_svt_TTG_25C_nldm.lib" "$LIB/GT_A5_lvt_TTG_25C_nldm.lib" "$LIB/GT_A5_ulvt_TTG_25C_nldm.lib"
manifest() { (cd "$S" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum); }   # every staged regular file (no symlinks, checked above)
[ -z "$(find "$S" ! -type f ! -type d)" ] || { echo "runs/stage holds a symlink or special file"; exit 2; }
manifest > "$OUT.partial/stage.sha256"   # what the run reads
{ echo "image $IMG $IMGID"; echo "$PKGDESC"
  echo "matrix-a5 56b467142c870284eb0cec1e89a680522e7a171d"
  sha256sum "$S/c6.py" run_c6.sh ../c3/record/tables.json "$S/leak.json" "$LIB"/GT_A5_*_TTG_25C_nldm.lib
} > "$OUT.partial/inputs.sha256"
cp "$S/leak.json" "$OUT.partial/leak.json"
# the whole staged tree is regenerated and compared, so an added file (a module on PYTHONPATH) fails too (C6-2b)
staged() {
  manifest | cmp -s - "$1" && return 0
  { echo "staged inputs changed:"; manifest | diff "$1" - | grep '^[<>]' | head -5; } >> "$OUT.partial/run.log"
  return 1
}
staged "$OUT.partial/stage.sha256" || { cat "$OUT.partial/run.log"; exit 2; }
s=$(date +%s)
MSYS_NO_PATHCONV=1 docker run --rm --memory 1500m --memory-swap 1500m -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$(pwd -W)/$S:/stage:ro" -v "$(pwd -W)/runs/work:/work" -v "$(pwd -W)/runs/out:/out" \
  -e PYTHONPATH=/stage/pkg "$IMGID" \
  bash -c 'cd /stage && python c6.py run /stage/leak.json /work /out' >> "$OUT.partial/run.log" 2>&1 && drc=0 || drc=$?
echo "docker rc=$drc after $(( $(date +%s) - s )) s" >> "$OUT.partial/run.log"
rc=$drc
# integrity checks, then the summary, then the wrapper's final rc, then publication (C6-2a): a stage mismatch
# after the run sets rc 3 (before it, exit 2 above), is logged, and suppresses the summary
[ -f runs/out/c6.json ] && cp runs/out/c6.json "$OUT.partial/"
if ! staged "$OUT.partial/stage.sha256"; then
  rc=3
elif [ -f "$OUT.partial/c6.json" ]; then   # the summary runs the staged c6.py the run used
  python "$S/c6.py" summary "$OUT.partial/c6.json" "$OUT.partial/summary.md" \
    || { echo "summary failed (rc $?)" >> "$OUT.partial/run.log"; [ "$rc" -eq 0 ] && rc=4; }
  staged "$OUT.partial/stage.sha256" || { rc=3; rm -f "$OUT.partial/summary.md"; }
fi
echo "rc=$rc (docker $drc; 3: staged inputs changed, 4: summary failed)" >> "$OUT.partial/run.log"
mv "$OUT.partial" "$OUT"                    # the record folder appears only once everything above has ended
tail -1 "$OUT/run.log"
exit $rc
