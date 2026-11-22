"""Amendment 4 probe, floor check in detail: for each library folder, (SPICE + kit floor) / Liberty over the states
whose kit floor is above 1% of their Liberty value, binned, with the states outside [0.98, 1.02] named. A floor that
is right puts these near 1. Usage: python -I a4_floor.py <library result dir>..."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluate import FLOOR_FACTOR  # noqa: E402

BINS = (0.98, 1.02, 1.05, 1.10, 1.20)


def check(d):
    r = json.loads((Path(d) / "result.json").read_text(encoding="utf-8"))
    seen, rows = set(), []
    for c in r["cases"]:
        key = (c["cell"], c["when"])
        if key in seen or c["ratio"] is None or c["floor_w"] is None:
            continue
        seen.add(key)
        if c["floor_w"] > c["liberty_w"] / FLOOR_FACTOR:
            rows.append(((c["ratio"] * c["liberty_w"] + c["floor_w"]) / c["liberty_w"], c["ratio"],
                         c["floor_w"] / c["liberty_w"], c["cell"], c["when"]))
    counts = {f"<{BINS[0]}": sum(x[0] < BINS[0] for x in rows)}
    for lo, hi in zip(BINS, BINS[1:] + (float("inf"),), strict=True):
        counts[f"{lo}-{hi}"] = sum(lo <= x[0] < hi for x in rows)
    out = sorted(x for x in rows if not 0.98 <= x[0] <= 1.02)
    return {"library": Path(d).name, "states": len(rows), "bins": counts,
            "outside": [f"{fc:.4f} (ratio {ra:.4f}, floor {fs:.3f} of Liberty) {cell} {when}"
                        for fc, ra, fs, cell, when in out]}


if __name__ == "__main__":
    print(json.dumps([check(d) for d in sys.argv[1:]], indent=1))
