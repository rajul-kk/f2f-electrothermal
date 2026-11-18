#!/bin/bash
# rs-dry S1 (dry/rs/DESIGN.md): build ORFS-Research at the pinned commit on a Kaggle CPU session and record what it
# cost. Writes everything under $OUT/record; the install tree goes to $OUT/orfs_install.tgz (also when the build
# fails, so a partial tree can be inspected). Never edits ORFS files; any shim it adds is listed in the record.
# One deadline covers every step and leaves TAR_RESERVE for the final save, inside Kaggle's 12 h session.
set -uo pipefail
ORFS_URL=https://github.com/ieee-ceda-datc/ORFS-Research.git
ORFS_COMMIT=568eb04da9173695d6bfc1b10ba868e0b6b8a9fa
OPENROAD_COMMIT=305d3ba2ddfd00591924cc586ad408179f566afe      # the README's tested bundled OpenROAD
PIN3D_URL=https://github.com/CODA-Team/TaiWei-Pin-3D.git
OUT=${OUT:-/kaggle/working}
B=${B:-/tmp/rs}
BUDGET_S=${BUDGET_S:-39600}          # 11 h for every step, from the script's start
TAR_RESERVE_S=${TAR_RESERVE_S:-1800} # kept back from the budget for finish()
R=$OUT/record
T0=$(date +%s)
mkdir -p "$R" "$B"

log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$R/steps.log"; }
left() { echo $(( BUDGET_S - TAR_RESERVE_S - ($(date +%s) - T0) )); }

# Machine-wide memory in use, sampled every 15 s for the whole run (ru_maxrss in time -v counts one process only;
# a parallel build's total is the sum). memory.log: epoch, MiB used (MemTotal - MemAvailable).
( while :; do echo "$(date +%s) $(awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{print int((t-a)/1024)}' /proc/meminfo)"
    sleep 15; done ) >> "$R/memory.log" &
MEMPID=$!

TIMEV=()
# step NAME CMD...: runs CMD under the remaining deadline, output in $R/NAME.log, per-step resources in
# $R/time_NAME.txt when /usr/bin/time is available; records and returns the rc (124 = deadline)
step() {
  local name=$1; shift
  local budget; budget=$(left)
  if [ "$budget" -le 60 ]; then log "skip $name: deadline reached"; echo "$name deadline" >> "$R/rc.txt"; return 124; fi
  log "start $name (at most ${budget}s)"
  local m0; m0=$(date +%s)
  "${TIMEV[@]}" timeout -k 120 "$budget" "$@" > "$R/$name.log" 2>&1
  local rc=$?
  log "end $name rc=$rc after $(( $(date +%s) - m0 ))s"
  echo "$name $rc" >> "$R/rc.txt"
  return $rc
}

finish() {   # always: the script's exit status, whatever install tree exists, its hashes, peak memory
  local rc=$?
  kill "$MEMPID" 2>/dev/null
  log "exit status $rc"
  echo "$rc" > "$R/exit_status.txt"
  if [ -d "$B/orfs/tools/install" ]; then
    # inside the reserve, with time left to log and hash (a cut tarball is logged as tar rc 124, not hashed)
    timeout -k 30 $(( TAR_RESERVE_S - 300 )) tar -czf "$OUT/orfs_install.tgz" -C "$B/orfs" tools/install
    local trc=$?
    log "tar rc=$trc"
    [ $trc -eq 0 ] && sha256sum "$OUT/orfs_install.tgz" > "$R/tarball.sha256"
    find "$B/orfs/tools/install" -type f -path '*/bin/*' -exec sha256sum {} + | sed "s|$B/orfs/||" | sort -k2 \
      > "$R/binaries.sha256"
  else
    log "no install tree to save"
  fi
  awk 'BEGIN{m=0} $2>m{m=$2} END{print "peak machine memory in use MiB", m}' "$R/memory.log" >> "$R/steps.log"
  df -h /tmp "$OUT" > "$R/disk_end.txt" 2>&1
}
trap finish EXIT

# the machine
{ cat /etc/os-release; echo; uname -a; echo; nproc; free -g; echo; df -h /tmp "$OUT"; echo
  gcc --version | head -1; echo; grep -m1 "model name" /proc/cpuinfo; } > "$R/machine.txt" 2>&1
if [ ! -x /usr/bin/time ]; then
  { apt-get update -qq && apt-get install -y -qq time; } > "$R/apt_time.log" 2>&1
fi
if [ -x /usr/bin/time ]; then TIMEV=(/usr/bin/time -v -o /dev/stderr); else
  log "no /usr/bin/time (apt_time.log): per-step resources not recorded, memory.log still is"; fi
# time -v writes to stderr, which goes into each step's log; peak per-process RSS is its "Maximum resident" line

# ORFS's scripts call sudo; the session runs as root, so the shim drops sudo's options and runs the command
if ! command -v sudo >/dev/null; then
  cat > /usr/local/bin/sudo <<'EOF'
#!/bin/sh
while [ $# -gt 0 ]; do
  case "$1" in
    -u|-g|-p|-C|-h|-r|-t|-U) shift 2 ;;
    --) shift; break ;;
    -*) shift ;;
    *) break ;;
  esac
done
exec "$@"
EOF
  chmod +x /usr/local/bin/sudo
  echo "added /usr/local/bin/sudo: drops sudo options and runs the command (the session is root)" >> "$R/shims.txt"
fi

# sources at the pinned commits: plain clone, check out, then submodules from that commit's .gitmodules
step clone git clone "$ORFS_URL" "$B/orfs" || exit 1
step checkout bash -c "cd '$B/orfs' && git checkout -q $ORFS_COMMIT && git submodule sync --recursive \
  && git submodule update --init --recursive" || exit 1
{ echo "ORFS-Research $(git -C "$B/orfs" rev-parse HEAD)"; git -C "$B/orfs" submodule status --recursive; } \
  > "$R/commits.txt"
got=$(git -C "$B/orfs/tools/OpenROAD" rev-parse HEAD 2>/dev/null || echo none)
echo "bundled OpenROAD $got (README tested $OPENROAD_COMMIT): $([ "$got" = $OPENROAD_COMMIT ] && echo match \
  || echo DIFFERS)" >> "$R/commits.txt"
step clone_pin3d git clone "$PIN3D_URL" "$B/pin3d" && echo "TaiWei-Pin-3D $(git -C "$B/pin3d" rev-parse HEAD)" \
  >> "$R/commits.txt"

# dependencies and build (ORFS's own scripts, unchanged)
step setup bash -c "cd '$B/orfs' && ./setup.sh" || exit 1
step build bash -c "cd '$B/orfs' && ./build_openroad.sh --local --threads $(nproc)" || exit 1

# what was built: both binaries must exist and run
OR=$B/orfs/tools/install/OpenROAD/bin/openroad
YS=$B/orfs/tools/install/yosys/bin/yosys
step versions bash -c "'$OR' -version && '$YS' -V" || { log "binaries missing or not runnable after build"; exit 2; }
log "build ok"
