#!/usr/bin/env bash
set -uo pipefail

write_state() {
  printf '%s\n' "$1" > /tmp/rs/pin3d/run_logs/dispatch/ord/nangate45_3D/gcd/task.1077812.1794958968128.state
}

write_rc() {
  printf '%s\n' "$1" > /tmp/rs/pin3d/run_logs/dispatch/ord/nangate45_3D/gcd/task.1077812.1794958968128.rc
}

write_phase() {
  printf '%s\n' "$1" > /tmp/rs/pin3d/run_logs/dispatch/ord/nangate45_3D/gcd/task.1077812.1794958968128.phase
}

child_pid=""
on_term() {
  if [[ -n "$child_pid" ]]; then
    kill "$child_pid" >/dev/null 2>&1 || true
  fi
  write_rc 143
  write_state failed
  exit 143
}

trap on_term HUP INT TERM

printf '%s\n' "$$" > /tmp/rs/pin3d/run_logs/dispatch/ord/nangate45_3D/gcd/task.1077812.1794958968128.pid
write_phase starting
write_state starting

mkdir -p /tmp/rs/pin3d/run_logs/nangate45_3D/ord/run
mkdir -p /tmp/rs/pin3d/run_logs/nangate45_3D/ord/eval

cd /tmp/rs/pin3d || {
  write_rc 1
  write_phase starting
  write_state failed
  exit 1
}

run_stage() {
  local phase="$1"
  local script_path="$2"
  local log_path="$3"
  write_phase "$phase"
  write_state running
  bash "$script_path" >"$log_path" 2>&1 &
  child_pid=$!
  wait "$child_pid"
  local rc=$?
  child_pid=""
  return "$rc"
}

rc=0

run_stage run /tmp/rs/pin3d/test/nangate45_3D/gcd/ord/run.sh /tmp/rs/pin3d/run_logs/nangate45_3D/ord/run/gcd_run.log
rc=$?
if [[ "$rc" -ne 0 ]]; then
  write_rc "$rc"
  write_phase run
  write_state failed
  exit "$rc"
fi

run_stage eval /tmp/rs/pin3d/test/nangate45_3D/gcd/ord/eval.sh /tmp/rs/pin3d/run_logs/nangate45_3D/ord/eval/gcd_eval.log
rc=$?
if [[ "$rc" -ne 0 ]]; then
  write_rc "$rc"
  write_phase eval
  write_state failed
  exit "$rc"
fi

write_rc 0
write_phase done
write_state ok
exit 0
