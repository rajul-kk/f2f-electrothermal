"""c4 dry, step d2: build a power-grid mesh from the exported geometry (not from PDNSim's network), solve it with
irmesh and compare each instance's voltage with PDNSim's voltage file, joined by instance name.

  python irbuild.py <export dir> <net> [--pin-mode spread|point|ties]     writes <export dir>/d2_<net>.json

The model follows what step b read in PDNSim's source (record/2026-11-18_b_pdnsim_model.md), built independently:
- nodes at via centres on both layers; a via array whose box is longer than ARRAY_UM gets a node pair per cut, a
  small via one node pair with all its cuts (PDNSim splits at min(10 um, 10 x pitch); on this grid only the M1-M2
  rail arrays are that long); a cut shape counts as its LEF cut class's cuts (asap7_cutclass.tsv, as PDNSim's
  getEffectiveNumberOfCuts: a 24 x 288 nm V5 bar is 8 cuts). Repeated via rows and cut boxes are counted once;
- along each wire, the nodes inside it chained in order along its long axis, R = R_sq x length / width. Overlapping
  wires on one layer are not merged (PDNSim merges them); their count is reported (0 on G97's Ibex grid);
- vias R = R_cut / cuts, with R_sq and R_cut PDNSim's own per-layer values (export.log "Layer resistance");
- each instance draws P / VDD (P from inst_power.tsv). pin_mode "spread" (default): split evenly over the rail
  nodes under its pin's box, no extra conductor (the pin is the rail's own metal); "point": at the pin's centre
  through 1 mOhm; "ties" (PDNSim-like, exploratory): one pin node tied by 1 mOhm to every rail node under the pin,
  which shorts that stretch of rail (record/2026-11-18_d2_explore_v2.json);
- sources: every node on the block-pin layer inside a block-pin box, at VDD (or 0 V on the ground net).
Nodes are keyed by (layer, x, y) in DBU, so stacked vias share their middle node.
"""
import argparse
import collections
import csv
import json
import math
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import irmesh  # noqa: E402

ARRAY_UM = 1.0
TERM_OHM = 1e-3
PIN_MODES = ("spread", "point", "ties")
CUTCLASS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "asap7_cutclass.tsv")


def cut_classes(path=CUTCLASS, dbu=1000):
    """{cut layer: [(width, length, cuts)]} in DBU, rules with a cut count only (PDNSim skips the others)."""
    out = collections.defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader((ln for ln in f if not ln.startswith("#")), delimiter="\t"):
            if r["cuts"]:
                out[r["layer"]].append((round(float(r["width_um"]) * dbu), round(float(r["length_um"]) * dbu),
                                        int(r["cuts"])))
    return out


def effective_cuts(layer, dx, dy, classes):
    """PDNSim's getEffectiveNumberOfCuts (ir_network.cpp 1068-1094): a cut shape whose width and length match a
    class (either orientation) counts as that class's cuts, otherwise as 1."""
    for w, ln, n in classes.get(layer, ()):
        if (dx == w and dy == ln) or (dy == w and dx == ln):
            return n
    return 1


def layer_resistance(log_text):
    """{layer: ohm per square or per cut} from the first 'Layer resistance:' block PDNSim printed."""
    block = log_text.split("Layer resistance:", 1)[1]
    out = {}
    for m in re.finditer(r"^\s+(\S+): (\S+) Ohm per (square|cut)", block, re.M):
        if m[1] in out:
            break
        out[m[1]] = float(m[2])
    return out


def read_export_log(export_dir):
    """(DBU per micron, supply volts, {layer: resistance}) from export.log."""
    with open(os.path.join(export_dir, "export.log"), encoding="utf-8", errors="replace") as f:
        text = f.read()
    dbu = re.search(r"^DBU (\d+)", text, re.M)
    # one "Supply voltage" per analysed net (the ground net prints 0 V): the supply is the largest, whatever the order
    supplies = [float(s) for s in re.findall(r"Supply voltage\s*:\s*(\S+)", text)]
    if not dbu or not supplies or max(supplies) <= 0:
        raise ValueError("export.log lacks the DBU or a positive supply voltage")
    return int(dbu[1]), max(supplies), layer_resistance(text)


def read_tsv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def rect(g):
    return tuple(int(g[k]) for k in ("xlo", "ylo", "xhi", "yhi"))


def overlapping_wires(wires):
    """Pairs of same-layer wires whose rectangles share area (touching edges do not count)."""
    n = 0
    by = collections.defaultdict(list)
    for g in wires:
        by[g["layer"]].append(rect(g))
    for rs in by.values():
        rs.sort()                                            # sweep along x: only wires starting before this ends
        for k, (_, ylo, xhi, yhi) in enumerate(rs):
            for bxlo, bylo, _, byhi in rs[k + 1:]:
                if bxlo >= xhi:
                    break
                n += bylo < yhi and ylo < byhi
    return n


class Mesh:
    def __init__(self):
        self.index, self.edges = {}, []
        self.on_layer = collections.defaultdict(set)

    def node(self, layer, x, y):
        k = (layer, int(x), int(y))
        if k not in self.index:
            self.index[k] = len(self.index)
            self.on_layer[layer].add((int(x), int(y), self.index[k]))
        return self.index[k]

    def edge(self, a, b, r):
        if a != b:
            self.edges.append((a, b, 1.0 / r))


def add_vias(mesh, geom, res, classes, dbu, group, info, use_cutclass=True):
    cuts = collections.defaultdict(set)                      # via key -> its distinct cut boxes
    for g in geom:
        if g["kind"] == "cut":
            cuts[(g["via"], g["cx"], g["cy"])].add((g["layer"],) + rect(g))
    seen = set()
    for g in geom:
        if g["kind"] != "via":
            continue
        key = (g["via"], g["cx"], g["cy"], g["bottom"], g["top"])
        if key in seen:
            info["duplicate_vias"] += 1
            continue
        seen.add(key)
        bot, top = g["bottom"], g["top"]
        cs = sorted(cuts[(g["via"], g["cx"], g["cy"])], key=lambda c: (c[1], c[2]))
        if not cs:
            raise ValueError(f"via without cuts: {g}")
        r_cut = res[cs[0][0]]
        n_cuts = [effective_cuts(c[0], c[3] - c[1], c[4] - c[2], classes) if use_cutclass else 1 for c in cs]
        span = max(int(g["xhi"]) - int(g["xlo"]), int(g["yhi"]) - int(g["ylo"])) / dbu
        if span > ARRAY_UM:
            # group > 1 (exploratory only): consecutive cuts share one node pair at their mean position
            for s in range(0, len(cs), group):
                part = range(s, min(s + group, len(cs)))
                x = sum((cs[k][1] + cs[k][3]) // 2 for k in part) // len(part)
                y = sum((cs[k][2] + cs[k][4]) // 2 for k in part) // len(part)
                mesh.edge(mesh.node(bot, x, y), mesh.node(top, x, y), r_cut / sum(n_cuts[k] for k in part))
        else:
            x, y = int(g["cx"]), int(g["cy"])
            mesh.edge(mesh.node(bot, x, y), mesh.node(top, x, y), r_cut / sum(n_cuts))


def add_pins(mesh, geom, pins, pin_mode, rail_layer="M1"):
    """{instance: [[nodes of pin 1], [nodes of pin 2], ...]}: a pin's nodes share its current equally, and the pin's
    voltage is their mean."""
    rails = collections.defaultdict(list)                    # rail centre y -> [(xlo, xhi, ylo, yhi)]
    for g in geom:
        if g["kind"] == "wire" and g["layer"] == rail_layer:
            xlo, ylo, xhi, yhi = rect(g)
            rails[(ylo + yhi) // 2].append((xlo, xhi, ylo, yhi))
    ys = np.array(sorted(rails))
    placed = []
    for p in pins:                                           # pass 1: every pin's rail node exists before indexing
        x, y = (int(p["xlo"]) + int(p["xhi"])) // 2, (int(p["ylo"]) + int(p["yhi"])) // 2
        ry = int(ys[int(np.abs(ys - y).argmin())])
        if not any(xlo <= x <= xhi and ylo <= y <= yhi for xlo, xhi, ylo, yhi in rails[ry]):
            raise ValueError(f"pin {p['inst']}/{p['pin']} at ({x}, {y}) is on no {rail_layer} rail")
        placed.append((p, x, y, ry, mesh.node(rail_layer, x, ry)))
    index = collections.defaultdict(list)
    for rx, ry, rn in mesh.on_layer[rail_layer]:
        index[ry].append((rx, rn))
    xs = {}
    for ry in index:
        index[ry].sort()
        xs[ry] = np.array([a for a, _ in index[ry]])
    out = {}
    for p, x, y, ry, centre in placed:                       # pass 2
        if pin_mode == "point":
            base = mesh.node("pin", x, y)
            mesh.edge(base, centre, TERM_OHM)
            out.setdefault(p["inst"], []).append([base])
            continue
        lo, hi = np.searchsorted(xs[ry], int(p["xlo"])), np.searchsorted(xs[ry], int(p["xhi"]), side="right")
        under = sorted({index[ry][q][1] for q in range(lo, hi)} | {centre})
        if pin_mode == "ties":
            base = mesh.node("pin", x, y)
            for rn in under:
                mesh.edge(base, rn, TERM_OHM)
            out.setdefault(p["inst"], []).append([base])
        elif pin_mode == "spread":
            out.setdefault(p["inst"], []).append(under)
        else:
            raise ValueError(f"pin_mode {pin_mode}")
    return out


def add_wires(mesh, geom, res, dbu):
    """Chain the nodes inside each wire along its long axis. Nodes are found through a per-layer index on the wire's
    cross axis (y for horizontal wires, x for vertical), not by scanning every node of the layer for every wire."""
    index = {}

    def layer_index(lay, horiz):
        if (lay, horiz) not in index:
            by = collections.defaultdict(list)
            for x, y, n in mesh.on_layer[lay]:
                by[y if horiz else x].append((x if horiz else y, n))
            along = {}
            for c, pts in by.items():
                pts.sort()
                along[c] = (np.array([a for a, _ in pts]), [n for _, n in pts])
            index[(lay, horiz)] = (np.array(sorted(by)), along)
        return index[(lay, horiz)]

    for g in geom:
        if g["kind"] != "wire":
            continue
        lay = g["layer"]
        xlo, ylo, xhi, yhi = rect(g)
        horiz = xhi - xlo >= yhi - ylo
        width = (yhi - ylo if horiz else xhi - xlo) / dbu
        (c0, c1), (a0, a1) = ((ylo, yhi), (xlo, xhi)) if horiz else ((xlo, xhi), (ylo, yhi))
        cross, along = layer_index(lay, horiz)
        inside = []
        for c in cross[np.searchsorted(cross, c0):np.searchsorted(cross, c1, side="right")]:
            pos, nodes = along[int(c)]
            lo, hi = np.searchsorted(pos, a0), np.searchsorted(pos, a1, side="right")
            inside += zip(pos[lo:hi].tolist(), nodes[lo:hi], strict=True)
        inside.sort()
        for (p0, n0), (p1, n1) in zip(inside, inside[1:], strict=False):
            if p1 == p0:   # two nodes across the wire at one position: a 2-D array the chain cannot model
                raise ValueError(f"{lay} wire {rect(g)}: two nodes at one position along it ({p0}); not modelled")
            if p1 > p0:
                mesh.edge(n0, n1, res[lay] * (p1 - p0) / dbu / width)


def solve_mesh(export_dir, net, group=1, pin_mode="spread", use_cutclass=True, rail_layer="M1"):
    """(mesh, node voltages, {instance: [[nodes of each pin]]}, info dict). rail_layer: the layer the cells' power
    pins sit on (M1 on ASAP7; BPR on MATRIX-A5's backside grid, dry/c5)."""
    if net not in ("VDD", "VSS"):    # the polarity rules below (sources, sink sign, worst pin) know only these two
        raise ValueError(f"net {net}: only VDD (supply) and VSS (ground) are modelled")
    if pin_mode not in PIN_MODES:
        raise ValueError(f"pin_mode {pin_mode}")
    dbu, supply, res = read_export_log(export_dir)
    geom = read_tsv(os.path.join(export_dir, f"geom_{net}.tsv"))
    info = {"pin_mode": pin_mode, "group": group, "cut_classes": use_cutclass, "duplicate_vias": 0,
            "overlapping_wires": overlapping_wires([g for g in geom if g["kind"] == "wire"])}
    mesh = Mesh()
    add_vias(mesh, geom, res, cut_classes(dbu=dbu), dbu, group, info, use_cutclass)
    pins = [p for p in read_tsv(os.path.join(export_dir, f"iterms_{net}.tsv")) if p["placed"] == "1"]
    pin_node = add_pins(mesh, geom, pins, pin_mode, rail_layer)
    add_wires(mesh, geom, res, dbu)
    fixed = {}
    for g in geom:
        if g["kind"] == "bterm":
            xlo, ylo, xhi, yhi = rect(g)
            for x, y, n in mesh.on_layer[g["layer"]]:
                if xlo <= x <= xhi and ylo <= y <= yhi:
                    fixed[n] = 0.0 if net == "VSS" else supply
    sink = np.zeros(len(mesh.index))
    sign = 1.0 if net == "VDD" else -1.0
    used = skipped_no_pin = 0
    for r in read_tsv(os.path.join(export_dir, "inst_power.tsv")):
        p = float(r["power_w"]) if r["power_w"] else math.nan
        if not math.isfinite(p):
            raise ValueError(f"power of {r['inst']} is not a number: {r['power_w']!r}")
        pin_sets = pin_node.get(r["inst"])
        if not pin_sets:
            skipped_no_pin += p > 0
            continue
        used += 1
        for nodes in pin_sets:                               # P / VDD split equally over the pins, then the nodes
            for n in nodes:
                sink[n] += sign * p / supply / len(pin_sets) / len(nodes)
    info.update(sources=len(fixed), power_rows_used=used, powered_rows_without_pin=int(skipped_no_pin),
                total_current_a=float(abs(sink.sum())), nodes=len(mesh.index), edges=len(mesh.edges))
    i, j, gg = (np.array(c) for c in zip(*mesh.edges, strict=True))
    v, _ = irmesh.solve(len(mesh.index), i, j, gg, fixed, sink)
    return mesh, v, pin_node, info


def instance_voltages(v, pin_node, net):
    """An instance's voltage: its lowest pin on VDD, highest on VSS (a pin's voltage is its nodes' mean), the rule
    G97 Amendment 1 set for PDNSim's terminals."""
    pick = min if net == "VDD" else max
    return {inst: pick(float(np.mean(v[ns])) for ns in sets) for inst, sets in pin_node.items()}


def reference(export_dir, net):
    """PDNSim's instance voltages from v_<net>.csv by the same rule."""
    pick = min if net == "VDD" else max
    ref = {}
    with open(os.path.join(export_dir, f"v_{net}.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            v0 = float(r["Voltage"])
            ref[r["Instance"]] = pick(ref.get(r["Instance"], v0), v0)
    return ref


def metrics(ours, ref, net, supply):
    """Per-instance agreement of two {instance: volts} maps, joined by name."""
    common = sorted(set(ours) & set(ref))
    a, b = np.array([ours[k] for k in common]), np.array([ref[k] for k in common])
    level = 0.0 if net == "VSS" else supply
    drop_ref, drop_ours = np.abs(b - level), np.abs(a - level)
    d = np.abs(a - b)
    worst = int(np.argmax(drop_ref))
    return {"net": net, "instances_compared": len(common), "only_ours": len(set(ours) - set(ref)),
            "only_pdnsim": len(set(ref) - set(ours)), "pdnsim_worst_mv": float(drop_ref.max() * 1e3),
            "pdnsim_worst_instance": common[worst], "ours_worst_mv": float(drop_ours.max() * 1e3),
            "ours_worst_instance": common[int(np.argmax(drop_ours))],
            "ours_at_pdnsim_worst_instance_mv": float(drop_ours[worst] * 1e3),
            "median_abs_diff_uv": float(np.median(d) * 1e6), "p99_abs_diff_uv": float(np.percentile(d, 99) * 1e6),
            "max_abs_diff_uv": float(d.max() * 1e6),
            "relative_worst_drop_error": float((drop_ours.max() - drop_ref.max()) / drop_ref.max())}


def compare(export_dir, net, pin_mode="spread", group=1, use_cutclass=True):
    """(row of solve info and metrics, mesh, node voltages): the one comparison irbuild and explore_d2 share."""
    _, supply, _ = read_export_log(export_dir)
    mesh, v, pin_node, info = solve_mesh(export_dir, net, group, pin_mode, use_cutclass)
    row = dict(info, **metrics(instance_voltages(v, pin_node, net), reference(export_dir, net), net, supply))
    return row, mesh, v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export_dir")
    ap.add_argument("net", choices=["VDD", "VSS"])
    ap.add_argument("--pin-mode", choices=PIN_MODES, default="spread")
    a = ap.parse_args()
    suffix = "" if a.pin_mode == "spread" else f"_{a.pin_mode}"
    path = os.path.join(a.export_dir, f"d2_{a.net}{suffix}.json")
    if os.path.exists(path):
        sys.exit(f"{path} exists: results are append-only")
    out, _, _ = compare(a.export_dir, a.net, a.pin_mode)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
