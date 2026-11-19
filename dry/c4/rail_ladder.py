"""c4 dry, d2 cause (exploratory, after the export): VDD rails (M1 + M2 joined by V1 cuts, held by M2-M3 vias) taken
out of PDNSim's network and out of ours (pin_mode point), compared as ladders.

  python rail_ladder.py <export dir> <out.json> [--rail Y:LOAD_X ...]

Default rails: y 15930 with the load at x 58644 (where our M2 differs most from PDNSim's), and y 14310 with the load
at x 42390 (PDNSim's worst VDD instance, place4109). Per rail it records:
- V1 edges in PDNSim's ladder by the x offset between their M1 and M2 node (ours are all 0);
- each ladder's lateral resistance per um with no loads (M2-M3 vias removed; left M2 node held, 1 mA drawn at the
  right), and PDNSim's ladder again with every V1 edge moved to join M1 and M2 at its M1 node's x; the continuum
  M1 || M2 from the layer resistances;
- each ladder alone with its M3 via nodes held at PDNSim's own voltages and PDNSim's loads on the rail (ITermNode
  currents) at the nearest M1 node: the voltage at the M1 node nearest the load;
- the same M1 node's voltage in each full grid (PDNSim's network solved by irmesh; ours as built).
"""
import argparse
import collections
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import irbuild  # noqa: E402
import irmesh  # noqa: E402
import pgspice  # noqa: E402

RPAT = re.compile(r"^R\S*\s+(\S+)\s+(\S+)\s+R=(\S+)", re.I)
IPAT = re.compile(r"^I\S*\s+(\S+)\s+\S+\s+DC\s+(\S+)", re.I)
LAYERS = {"M1", "M2", "M3"}
RAILS = ["15930:58644", "14310:42390"]


def pdnsim_rails(sp, ys):
    """{y: (edges [((layer, x), (layer, x), ohm)], loads [(x, A)])} for each rail y in PDNSim's SPICE network."""
    out = {y: ([], []) for y in ys}
    with open(sp, encoding="utf-8") as f:
        for line in f:
            m = RPAT.match(line)
            if m:
                a, b = pgspice.parse_name(m[1]), pgspice.parse_name(m[2])
                if a[3] == b[3] and a[3] in out and a[0].lower() == b[0].lower() == "node" and {a[1], b[1]} <= LAYERS:
                    out[a[3]][0].append(((a[1], a[2]), (b[1], b[2]), float(m[3])))
                continue
            m = IPAT.match(line)
            if m:
                _, _, x, y = pgspice.parse_name(m[1])
                if y in out:
                    out[y][1].append((x, float(m[2])))
    return out


def solve(edges, fixed_of, sink_of):
    idx = {}
    for a, b, _ in edges:
        idx.setdefault(a, len(idx))
        idx.setdefault(b, len(idx))
    i, j, r = zip(*[(idx[a], idx[b], r) for a, b, r in edges], strict=True)
    sink = np.zeros(len(idx))
    for n, c in sink_of(idx):
        sink[n] += c
    v, _ = irmesh.solve(len(idx), np.array(i), np.array(j), 1 / np.array(r), fixed_of(idx), sink)
    return idx, v


def nearest(idx, layer, x):
    """(x, node) of the node on `layer` nearest x, from {(layer, x): node}."""
    pts = sorted((xx, n) for (lay, xx), n in idx.items() if lay == layer)
    xs = np.array([p for p, _ in pts])
    return pts[int(np.abs(xs - x).argmin())]


def lateral(edges, x0=10000, x1=60000):
    e = [t for t in edges if {t[0][0], t[1][0]} <= {"M1", "M2"}]
    idx = {}
    for a, b, _ in e:
        idx.setdefault(a, len(idx))
        idx.setdefault(b, len(idx))
    left, right = nearest(idx, "M2", x0), nearest(idx, "M2", x1)
    _, v = solve(e, lambda ix: {left[1]: 0.0}, lambda ix: [(right[1], 1e-3)])
    return {"ohm_per_um": float(-v[right[1]] / 1e-3 / ((right[0] - left[0]) / 1000)),
            "x_from": left[0], "x_to": right[0]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export_dir")
    ap.add_argument("out")
    ap.add_argument("--rail", nargs="+", default=RAILS, help="Y:LOAD_X in DBU")
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"{a.out} exists: results are append-only")
    rails = [tuple(int(t) for t in r.split(":")) for r in a.rail]
    ys = {y for y, _ in rails}
    sp = os.path.join(a.export_dir, "pg_VDD.sp")
    names, vp, _ = pgspice.solve_spice(sp)
    pv = {}
    for k, nm in enumerate(names):
        t, layer, x, y = pgspice.parse_name(nm)
        if t.lower() == "node" and y in ys:
            pv[(y, layer, x)] = vp[k]
    pd = pdnsim_rails(sp, ys)
    mesh, v_ours, _, _ = irbuild.solve_mesh(a.export_dir, "VDD", pin_mode="point")
    keys = {n: k for k, n in mesh.index.items()}
    ours = collections.defaultdict(list)
    for i, j, g in mesh.edges:
        p, q = keys[i], keys[j]
        if p[2] == q[2] and p[2] in ys and {p[0], q[0]} <= LAYERS:
            ours[p[2]].append(((p[0], p[1]), (q[0], q[1]), 1 / g))
    _, _, res = irbuild.read_export_log(a.export_dir)
    r1, r2 = res["M1"] / 0.018, res["M2"] / 0.018           # ohm per um of the 18 nm rails
    out = {"pin_mode_ours": "point", "continuum_m1_parallel_m2_ohm_per_um": 1 / (1 / r1 + 1 / r2), "rails": []}
    for y, load_x in rails:
        edges, loads = pd[y]
        offsets = collections.Counter(abs(p[1] - q[1]) for p, q, _ in edges if {p[0], q[0]} == {"M1", "M2"})
        vertical = [((p if p[0] == "M1" else q), ("M2", (p if p[0] == "M1" else q)[1]), r)
                    if {p[0], q[0]} == {"M1", "M2"} else (p, q, r) for p, q, r in edges]
        row = {"y": y, "load_x": load_x, "v1_edge_x_offset_nm_pdnsim": {str(k): offsets[k] for k in sorted(offsets)},
               "lateral": {"pdnsim": lateral(edges), "ours": lateral(ours[y]),
                           "pdnsim_v1_vertical": lateral(vertical)},
               "isolated": {}, "full_grid": {}}
        for label, es in (("pdnsim", edges), ("ours", ours[y])):
            def fixed(idx, y=y):
                return {n: pv[(y, lay, x)] for (lay, x), n in idx.items() if lay == "M3"}

            def sinks(idx, loads=loads):
                return [(nearest(idx, "M1", x)[1], c) for x, c in loads]

            idx, v = solve(es, fixed, sinks)
            x, n = nearest(idx, "M1", load_x)
            row["isolated"][label] = {"nodes": len(idx), "edges": len(es), "m3_held": len(fixed(idx)),
                                      "load_total_a": sum(c for _, c in loads), "node_x": x, "v": float(v[n])}
            full = pv[(y, "M1", x)] if label == "pdnsim" else float(v_ours[mesh.index[("M1", x, y)]])
            row["full_grid"][label] = {"node_x": x, "v": float(full)}
        out["rails"].append(row)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
