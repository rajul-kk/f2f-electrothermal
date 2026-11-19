#!/bin/bash
# rs-dry shared helpers for S2 and S3 (sourced; make_notebooks.py ships it beside the session script). S1 keeps its own
# copy as it ran (record/2026-11-18_s1_v2). Needs OUT, B, BUDGET_S, TAR_RESERVE_S set by the caller.
# Pinned from S1 v2's record: the build tarball, its two main binaries, and the commits.
ORFS_URL=https://github.com/ieee-ceda-datc/ORFS-Research.git
ORFS_COMMIT=568eb04da9173695d6bfc1b10ba868e0b6b8a9fa
PIN3D_URL=https://github.com/CODA-Team/TaiWei-Pin-3D.git
PIN3D_COMMIT=51a19d6ffa8e4483a1a3357fb69c5038d720b0b8
S1_TARBALL_SHA=b003f6fcf73a5d96ee38bc14124d44976a8b47e69b1444f823d631e76ec78fed
S1_OPENROAD_SHA=5dacbf4700823c5ef87186910ab97d1f921c925245f32c8ced02161916801e3b
S1_YOSYS_SHA=af7339bae0527cdb4ca9d70895eadca8e0e133e05f78e21cdbf6e496136abc75
R=$OUT/record
T0=$(date +%s)
mkdir -p "$R" "$B"

log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$R/steps.log"; }
left() { echo $(( BUDGET_S - TAR_RESERVE_S - ($(date +%s) - T0) )); }

# machine-wide memory in use every 15 s (epoch, MiB = MemTotal - MemAvailable)
start_memory() {
  ( while :; do echo "$(date +%s) $(awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{print int((t-a)/1024)}' /proc/meminfo)"
      sleep 15; done ) >> "$R/memory.log" &
  MEMPID=$!
}

# step NAME CMD...: CMD under the remaining deadline; output in $R/NAME.log, GNU time's report in $R/NAME.time (its
# own file: S1 sent it to /dev/stderr, which reopened the log and overwrote its start); records and returns the rc
step() {
  local name=$1; shift
  local budget; budget=$(left)
  if [ "$budget" -le 60 ]; then log "skip $name: deadline reached"; echo "$name deadline" >> "$R/rc.txt"; return 124; fi
  log "start $name (at most ${budget}s)"
  local m0; m0=$(date +%s)
  local tv=(); [ -x /usr/bin/time ] && tv=(/usr/bin/time -v -o "$R/$name.time")
  "${tv[@]}" timeout -k 120 "$budget" "$@" > "$R/$name.log" 2>&1
  local rc=$?
  log "end $name rc=$rc after $(( $(date +%s) - m0 ))s"
  echo "$name $rc" >> "$R/rc.txt"
  return $rc
}

machine_and_tools() {
  { cat /etc/os-release; echo; uname -a; echo; nproc; free -g; echo; df -h /tmp "$OUT"; echo
    gcc --version | head -1; echo; grep -m1 "model name" /proc/cpuinfo; } > "$R/machine.txt" 2>&1
  [ -x /usr/bin/time ] || { apt-get update -qq && apt-get install -y -qq time; } > "$R/apt_time.log" 2>&1
  if ! command -v sudo >/dev/null; then   # ORFS's scripts call sudo; the session is root
    printf '%s\n' '#!/bin/sh' 'while [ $# -gt 0 ]; do' '  case "$1" in' \
      '    -u|-g|-p|-C|-h|-r|-t|-U) shift 2 ;;' '    --) shift; break ;;' '    -*) shift ;;' '    *) break ;;' \
      '  esac' 'done' 'exec "$@"' > /usr/local/bin/sudo
    chmod +x /usr/local/bin/sudo
    echo "added /usr/local/bin/sudo: drops sudo options and runs the command (the session is root)" >> "$R/shims.txt"
  fi
}

# the S1 tarball from the attached kernel output, checked against S1's hash, unpacked into $B/orfs
restore_build() {
  local tgz; tgz=$(find /kaggle/input -name orfs_install.tgz 2>/dev/null | head -1)
  [ -n "$tgz" ] || { log "S1 tarball not attached"; return 2; }
  local got; got=$(sha256sum "$tgz" | cut -d' ' -f1)
  echo "tarball $tgz $got (S1 $S1_TARBALL_SHA)" >> "$R/build_identity.txt"
  [ "$got" = "$S1_TARBALL_SHA" ] || { log "tarball hash differs from S1"; return 2; }
  tar -xzf "$tgz" -C "$B/orfs" || return 2
}

check_binaries() {   # $1: label; hashes and missing shared libraries of the two main binaries
  local or=$B/orfs/tools/install/OpenROAD/bin/openroad ys=$B/orfs/tools/install/yosys/bin/yosys
  { echo "== $1"; sha256sum "$or" "$ys"; ldd "$or" "$ys" | grep -c "not found" | sed 's/^/libraries not found: /'
    ldd "$or" "$ys" | grep "not found"; } >> "$R/build_identity.txt" 2>&1
  [ "$(sha256sum "$or" | cut -d' ' -f1)" = "$S1_OPENROAD_SHA" ] && [ "$(sha256sum "$ys" | cut -d' ' -f1)" = "$S1_YOSYS_SHA" ]
}

# ORFS at the pinned commit with submodules (setup.sh needs them), then ORFS's own setup.sh: it installs the system
# packages and the -common libraries the binaries were built against (S1 v2: 61 min). The tarball is unpacked again
# afterwards so the install tree is S1's, whatever setup.sh touched.
prepare_toolchain() {
  step clone git clone "$ORFS_URL" "$B/orfs" || return 1
  step checkout bash -c "cd '$B/orfs' && git checkout -q $ORFS_COMMIT && git submodule sync --recursive \
    && git submodule update --init --recursive" || return 1
  echo "ORFS-Research $(git -C "$B/orfs" rev-parse HEAD)" > "$R/commits.txt"
  restore_build || return 2
  check_binaries "before setup.sh" || { log "binaries differ from S1"; return 2; }
  echo "setup.sh run with SUDO_USER=root (it expects to be started via sudo; the session is root)" >> "$R/shims.txt"
  step setup bash -c "cd '$B/orfs' && SUDO_USER=root ./setup.sh" || return 1
  restore_build || return 2
  check_binaries "after setup.sh" || { log "binaries differ from S1"; return 2; }
  step versions bash -c "'$B/orfs/tools/install/OpenROAD/bin/openroad' -version \
    && '$B/orfs/tools/install/yosys/bin/yosys' -V" || return 2
}

# Pin-3D at its recorded commit; its env.sh takes ORFS_DIR and NUM_CORES from the environment
prepare_pin3d() {
  step clone_pin3d bash -c "git clone '$PIN3D_URL' '$B/pin3d' && cd '$B/pin3d' && git checkout -q $PIN3D_COMMIT" \
    || return 1
  echo "TaiWei-Pin-3D $(git -C "$B/pin3d" rev-parse HEAD)" >> "$R/commits.txt"
  cp "$B/pin3d/env.sh" "$R/pin3d_env.sh"
}

# pin3d NAME ARGS...: a run_experiments.py call from Pin-3D's folder with its env.sh sourced. run_experiments.py exits 0
# even when a run fails (S2 v1: "[STATUS] failed=1", rc 0), so it passes only if the log ends its runs ("All experiments
# completed.") and the last status line names no running or bad state; anything else, a missing line included, is rc 3.
# --list prints no status line, so callers pass LIST=1 for it. Arguments go in as "$@", never re-split by the inner shell.
pin3d() {
  local name=$1; shift
  step "$name" bash -c 'cd "$1" && export ORFS_DIR="$2" NUM_CORES=$(nproc) && source env.sh && shift 2 \
    && python3 run_experiments.py "$@"' _ "$B/pin3d" "$B/orfs" "$@" || return $?
  [ "${LIST:-0}" = 1 ] && return 0
  local status; status=$(grep '^\[STATUS\]' "$R/$name.log" | tail -1)
  if ! grep -q '^\[MAIN\] All experiments completed' "$R/$name.log" || [ -z "$status" ] \
     || echo "$status" | grep -Eq 'running=|failed=[1-9]|timeout|error|killed|lost'; then
    log "$name: run_experiments.py last status '${status:-none}'"; echo "$name status-failed" >> "$R/rc.txt"; return 3
  fi
}

# copies Pin-3D's logs and reports (small) into the record and tars its results and objects into the output
save_flow() {
  for d in logs reports run_logs; do [ -d "$B/pin3d/$d" ] && cp -r "$B/pin3d/$d" "$R/flow_$d"; done
  local parts=(); for d in results objects; do [ -d "$B/pin3d/$d" ] && parts+=("$d"); done
  if [ ${#parts[@]} -gt 0 ]; then
    timeout -k 30 $(( TAR_RESERVE_S - 300 )) tar -czf "$OUT/flow_results.tgz" -C "$B/pin3d" "${parts[@]}"
    log "results tar rc=$?"
    [ -f "$OUT/flow_results.tgz" ] && sha256sum "$OUT/flow_results.tgz" > "$R/flow_results.sha256"
  fi
}

finish_common() {   # the script's exit status, peak memory, disk; the caller's EXIT trap calls it first
  local rc=$1
  kill "$MEMPID" 2>/dev/null
  log "exit status $rc"
  echo "$rc" > "$R/exit_status.txt"
  save_flow
  awk 'BEGIN{m=0} $2>m{m=$2} END{print "peak machine memory in use MiB", m}' "$R/memory.log" >> "$R/steps.log"
  df -h /tmp "$OUT" > "$R/disk_end.txt" 2>&1
  du -sh "$B/pin3d"/* > "$R/flow_sizes.txt" 2>&1
}
