"""For Amendment 2's floor cut: per library, how many leakage states would be listed rather than scored, i.e. have a
Liberty value above 0 but below the one-floor cut (FLOOR_FACTOR x FLOOR_A x VDD). Reads cases.json, so it can run
before ngspice. Since Amendment 4 this is only the smallest cut: each state's own cut (evaluate.cut_w) needs its
operating point, and the listed states are in summary.json's `below_floor`. Usage: python threshold_share.py <runs>"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluate import FLOOR_A, FLOOR_FACTOR  # noqa: E402  (the one-floor cut's constants, A9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs")
    a = ap.parse_args()
    for f in sorted(glob.glob(os.path.join(a.runs, "GT_A5_*", "cases.json"))):
        m = json.loads(Path(f).read_text(encoding="utf-8"))
        cut = FLOOR_FACTOR * FLOOR_A * m["vdd"]
        states = {(c["cell"], c["when"]): c["liberty_w"] for c in m["cases"]}
        below = sum(0 < v < cut for v in states.values())
        print(f"{os.path.basename(os.path.dirname(f)):22s} states {len(states):4d}  below {cut:.1e} W: {below:4d}"
              f" ({100 * below / len(states):5.1f}%)")


if __name__ == "__main__":
    main()
