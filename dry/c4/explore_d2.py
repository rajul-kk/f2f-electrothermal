"""c4 dry, d2 exploration (after the export, so exploratory): why our worst drop differs from PDNSim's.

  python explore_d2.py <export dir> <out.json>

Records, for the README to cite (A25):
- d1 cost: PDNSim's own network solved by irmesh, wall time and tracemalloc peak, per net;
- PDNSim's pin nodes in pg_<net>.sp: every ITermNode by its number of distinct 1 mOhm partners (0 included), and how
  many v_<net>.csv terminals fall on a pin node another terminal already uses;
- per build variant (pin mode, cut grouping, cut classes on or off): irbuild.compare's row (worst drops, per-instance
  |diff| percentiles), plus wall time and the per-layer median |diff| of node voltages against PDNSim's network at
  shared (layer, x, y).
"""
import collections
import csv
import json
import os
import re
import sys
import time
import tracemalloc

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import irbuild  # noqa: E402
import pgspice  # noqa: E402

VARIANTS = [  # (net, pin_mode, group, cut classes)
    ("VDD", "spread", 1, True), ("VSS", "spread", 1, True), ("VDD", "point", 1, True),
    ("VDD", "spread", 1, False), ("VDD", "ties", 1, True), ("VDD", "ties", 6, True),
    ("VDD", "point", 4, True), ("VDD", "point", 16, True),
]
RPAT = re.compile(r"^R\S*\s+(\S+)\s+(\S+)\s+R=(\S+)", re.I)


def pdnsim_nodes(export_dir, net):
    """({(layer, x, y): volts} of PDNSim's grid nodes, cost, [pin node names])."""
    t0 = time.perf_counter()
    tracemalloc.start()
    names, v, _ = pgspice.solve_spice(os.path.join(export_dir, f"pg_{net}.sp"))
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    cost = {"nodes": len(names), "seconds": round(time.perf_counter() - t0, 2), "tracemalloc_peak_mb": peak / 2**20}
    grid, pins = {}, []
    for k, nm in enumerate(names):
        typ, layer, x, y = pgspice.parse_name(nm)
        if typ.lower() == "itermnode":
            pins.append(nm)
        else:
            grid[(layer, x, y)] = v[k]
    return grid, cost, pins


def pin_ties(export_dir, net, pins, dbu):
    partners = {p: set() for p in pins}
    with open(os.path.join(export_dir, f"pg_{net}.sp"), encoding="utf-8") as f:
        for line in f:
            m = RPAT.match(line)
            if m and float(m[3]) == 1e-3:
                for a, b in ((m[1], m[2]), (m[2], m[1])):
                    if a in partners:
                        partners[a].add(b)
    hist = collections.Counter(len(p) for p in partners.values())
    at = {pgspice.parse_name(p)[1:]: p for p in pins}
    used, unmatched = collections.Counter(), 0
    with open(os.path.join(export_dir, f"v_{net}.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["Layer"], round(float(r["X location"]) * dbu), round(float(r["Y location"]) * dbu))
            if key in at:
                used[key] += 1
            else:
                unmatched += 1
    return {"pin_nodes": len(pins), "pin_nodes_by_tie_count": {str(k): hist[k] for k in sorted(hist)},
            "terminals_on_a_pin_node": sum(used.values()), "terminals_unmatched": unmatched,
            "terminals_on_an_already_used_pin_node": sum(c - 1 for c in used.values())}


def main():
    export_dir, out_path = sys.argv[1], sys.argv[2]
    if os.path.exists(out_path):
        sys.exit(f"{out_path} exists: results are append-only")
    dbu = pgspice.export_dbu(export_dir)
    out = {"export_dir": os.path.basename(os.path.normpath(export_dir)), "d1": {}, "pin_ties": {}, "variants": []}
    grid = {}
    for net in ("VDD", "VSS"):
        grid[net], out["d1"][net], pins = pdnsim_nodes(export_dir, net)
        out["pin_ties"][net] = pin_ties(export_dir, net, pins, dbu)
        print(net, out["d1"][net], out["pin_ties"][net], flush=True)
    for net, mode, group, cc in VARIANTS:
        t0 = time.perf_counter()
        row, mesh, v = irbuild.compare(export_dir, net, mode, group, cc)
        layers = collections.defaultdict(list)
        for key, n in mesh.index.items():
            if key in grid[net]:
                layers[key[0]].append(abs(v[n] - grid[net][key]))
        row.update(seconds=round(time.perf_counter() - t0, 1),
                   layer_median_abs_diff_uv={k: float(np.median(x) * 1e6) for k, x in sorted(layers.items())},
                   layer_shared_nodes={k: len(x) for k, x in sorted(layers.items())})
        out["variants"].append(row)
        print(json.dumps(row), flush=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
