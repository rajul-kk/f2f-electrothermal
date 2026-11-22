#!/bin/bash
# Runs inside the ngspice container: every state deck s<i>.cir in each library folder given, one at a time, each with
# a 2 min cap. Exit codes go to s<i>.rc (124 = over the cap). Amendment 4: a deck that may lack a DC point (nonzero
# exit, or the transient op in its log) is run once more as s<i>r.cir; leak.method on the logs decides validity.
# The trigger is deliberately wider than leak.method's "no DC point" (nonzero exit or "transient op finished
# successfully"), so it never misses a case method() rejects; extra retries only cost time and are not used.
# Usage: bash ngspice_states.sh <library dir>...
shopt -s nullglob
for d in "$@"; do
  cd "$d" || continue
  for f in s????.cir; do
    b=${f%.cir}
    timeout 120 ngspice -b "$f" > "$b.log" 2>&1; echo $? > "$b.rc"
    if [ "$(cat "$b.rc")" != 0 ] || grep -qi "transient op" "$b.log"; then
      timeout 120 ngspice -b "${b}r.cir" > "${b}r.log" 2>&1; echo $? > "${b}r.rc"
    fi
  done
done
