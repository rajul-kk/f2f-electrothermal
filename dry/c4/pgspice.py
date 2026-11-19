"""c4 dry, step d1: solve PDNSim's own network (its `write_pg_spice` file) with irmesh and compare against PDNSim's
voltage file. Agreement here tests the solver at full size on the same network; the independent network build is d2.

  python pgspice.py <export dir> <net> [--name d1]    prints a JSON summary and writes <export dir>/<name>_<net>.json
                                                      (DBU from the export's log)

PDNSim's file (ir_solver.cpp writeSpiceFile at 5bbad751): `R<k> <node> <node> R=<ohm>`, `I<k> <node> 0 DC <amp>`
(currents %.3e, so rounded to 4 significant digits; sinks under its minimum current are left out), and
`V<k> <node> 0 DC <volt>`. Node names are `<type>_<layer>_<x>_<y>` in DBU (node.cpp 91-117; an instance pin's base
node is `ITermNode`). PDNSim stores currents positive and negates them on a non-ground net (ir_solver.cpp 1552-1556),
so on the ground net (source 0 V) the cells' current flows into the grid: the sinks are injections there.
"""
import argparse
import collections
import csv
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import irmesh  # noqa: E402

LINE = re.compile(r"^([RIV])\S*\s+(\S+)\s+(\S+)\s+(?:R=|DC\s+)(\S+)", re.I)


def read_spice(path):
    """(node names, edges (i, j, g), sinks {node: A}, sources {node: V}) from a write_pg_spice file."""
    names, index = [], {}

    def node(n):
        if n not in index:
            index[n] = len(names)
            names.append(n)
        return index[n]

    ei, ej, eg, sinks, sources = [], [], [], {}, {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            m = LINE.match(s)
            if not m:
                if s[:1].upper() in "RIV" and s[:1]:
                    raise ValueError(f"element line not understood: {s}")
                continue
            kind, a, b, val = m[1].upper(), m[2], m[3], float(m[4])
            if kind == "R":
                if val <= 0:
                    raise ValueError(f"non-positive resistance: {line.strip()}")
                ei.append(node(a))
                ej.append(node(b))
                eg.append(1.0 / val)
            elif kind == "I":
                if b != "0":
                    raise ValueError(f"current source not to ground: {line.strip()}")
                k = node(a)
                sinks[k] = sinks.get(k, 0.0) + val
            else:
                if b != "0":
                    raise ValueError(f"voltage source not to ground: {line.strip()}")
                sources[node(a)] = val
    return names, (np.array(ei), np.array(ej), np.array(eg)), sinks, sources


def solve_spice(path):
    names, (i, j, g), sinks, sources = read_spice(path)
    if not sources:
        raise ValueError("no voltage source")
    vs = set(sources.values())
    if len(vs) != 1:
        raise ValueError(f"sources at several voltages: {sorted(vs)}")
    sign = 1.0 if vs.pop() > 0 else -1.0          # supply net draws current out; ground net receives it
    sink = np.zeros(len(names))
    for k, a in sinks.items():
        sink[k] = sign * a
    v, _ = irmesh.solve(len(names), i, j, g, sources, sink)
    return names, v, len(i)


def parse_name(name):
    """(type, layer, x, y) of `<type>_<layer>_<x>_<y>`; the type may itself hold underscores."""
    head, layer, x, y = name.rsplit("_", 3)
    return head, layer, int(x), int(y)


def compare(export_dir, net, dbu):
    names, v, n_edges = solve_spice(os.path.join(export_dir, f"pg_{net}.sp"))
    at = {}
    for k, nm in enumerate(names):
        typ, layer, x, y = parse_name(nm)
        if typ.lower() == "itermnode":
            at[(layer, x, y)] = v[k]          # names are unique (read_spice), so so are these keys
    rows, missing, used = [], 0, collections.Counter()
    with open(os.path.join(export_dir, f"v_{net}.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["Layer"], round(float(r["X location"]) * dbu), round(float(r["Y location"]) * dbu))
            if key in at:
                rows.append((float(r["Voltage"]), at[key]))
                used[key] += 1
            else:
                missing += 1
    ref, ours = np.array(rows).T if rows else (np.array([]), np.array([]))
    d = ours - ref
    out = {"net": net, "dbu": dbu, "nodes": len(names), "edges": n_edges, "terminals_matched": len(rows),
           "terminals_unmatched": missing, "terminals_on_an_already_used_pin_node": sum(c - 1 for c in used.values()),
           "max_abs_diff_v": float(np.abs(d).max()) if len(d) else None,
           "pdnsim_worst_v": float(ref.min() if net == "VDD" else ref.max()) if len(ref) else None,
           "ours_worst_v": float(ours.min() if net == "VDD" else ours.max()) if len(ours) else None}
    return out


def export_dbu(export_dir):
    """The DBU per micron export.tcl printed ("DBU <n>" in export.log)."""
    with open(os.path.join(export_dir, "export.log"), encoding="utf-8", errors="replace") as f:
        m = re.search(r"^DBU (\d+)", f.read(), re.M)
    if not m:
        raise ValueError("export.log has no DBU line")
    return int(m[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export_dir")
    ap.add_argument("net", choices=["VDD", "VSS"])
    ap.add_argument("--name", default="d1", help="record name: writes <export dir>/<name>_<net>.json")
    a = ap.parse_args()
    path = os.path.join(a.export_dir, f"{a.name}_{a.net}.json")
    if os.path.exists(path):                                 # before the solve, so a refused run costs nothing
        sys.exit(f"{path} exists: results are append-only")
    out = compare(a.export_dir, a.net, export_dbu(a.export_dir))
    if not out["terminals_matched"]:
        sys.exit(f"no terminal of {a.net} matched a pin node: check the DBU ({out['dbu']}) and node names")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
