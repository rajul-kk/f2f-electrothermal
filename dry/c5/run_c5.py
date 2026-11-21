"""c5 dry: generate MATRIX-A5's backside grid for each case, solve both nets with c4's builder and solver, and record
drops in mV per A/mm^2 beside a hand estimate (DESIGN.md, check c).

  python run_c5.py <kit base dir> <work dir> <out.json>

The generated grids go to <work dir> (large, local); <out.json> is new (append-only records).
"""
import hashlib
import json
import os
import platform
import sys
import time
import tracemalloc

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "c4")]     # python -I leaves the script's folder off the path
import irbuild  # noqa: E402

import bsgrid  # noqa: E402

KIT_FILES = ("PDK_PATHS.tcl", "lef/gtA5_cfet.tlef", "lef/gtA5_cfet_macros.lef", "qrc/GTA5_cfet.ict",
             "starrc/GTA5cfet.itf")
CODE_FILES = ("bsgrid.py", "run_c5.py", "../c4/irbuild.py", "../c4/irmesh.py")


def sha256s(base, rels):
    """{relative path: sha256} of files under base: what a record was made from, by content (A13)."""
    out = {}
    for rel in rels:
        with open(os.path.join(base, rel), "rb") as f:
            out[rel] = hashlib.sha256(f.read()).hexdigest()
    return out

CASES = [  # (name, side um, feed, bump pitch um, TSV cut cap, BPR resistivity source, hotspot)
    ("ring_L25", 25, "ring", None, None, "ict", False),
    ("ring_L50", 50, "ring", None, None, "ict", False),
    ("ring_L100", 100, "ring", None, None, "ict", False),
    ("ring_L50_tsv1", 50, "ring", None, 1, "ict", False),
    ("ring_L50_bpr_itf", 50, "ring", None, None, "itf", False),
    ("ring_L50_hotspot", 50, "ring", None, None, "ict", True),
    ("area_L50_p10", 50, "area", 10, None, "ict", False),
    ("area_L50_p20", 50, "area", 20, None, "ict", False),
    ("area_L100_p20", 100, "area", 20, None, "ict", False),
    ("area_L100_p40", 100, "area", 40, None, "ict", False),
]


def via_ohms(k, cut, v_layer, v_width, h_layer, h_width):
    """Ohms of the via the grid puts where a vertical strap of v_width crosses a horizontal one of h_width."""
    big = bsgrid.um(1000)
    hv, hh = bsgrid.um(v_width) // 2, bsgrid.um(h_width) // 2
    rule, cuts = bsgrid.cut_array(k["via"][cut], {v_layer: (-hv, -big, hv, big), h_layer: (-big, -hh, big, hh)})
    return rule["r_cut"] / len(cuts)


def estimate(k, side_um):
    """Hand estimate of the worst VDD drop for a ring-fed, uniformly loaded core, V per A/mm^2, as a series of
    straps: each layer a uniformly loaded strap held at both ends by the layer that feeds it, plus the via at each
    crossing (DESIGN.md, check c). Each via is the one the grid picks (bsgrid.cut_array)."""
    j = bsgrid.J_A_PER_UM2
    rs = k["sheet_ohm_sq"]
    wv, _, pv, _ = k["stripe_v"]
    wh, _, ph, _ = k["stripe_h"]
    rw, _, ro = k["ring"]
    i_bpr = 2 * j * k["site_y"]                    # A per um of one VDD rail: it feeds the whole row on each side
    span = side_um + 2 * (ro + rw / 2)             # BSM2 stripe between ring centres
    r_tsv = via_ohms(k, "TSV", k["stripe_v_layer"], wv, k["core_pin_layer"], k["bpr_width"])
    r_bsv1 = via_ohms(k, "BSV1", k["stripe_v_layer"], wv, k["pg_h"], wh)
    r_bsv2 = via_ohms(k, "BSV2", k["pg_v"], rw, k["pg_h"], wh)        # a BSM2 stripe end on a BSM3 ring side
    parts = {
        "BPR": i_bpr * pv ** 2 * rs["BPR"] / k["bpr_width"] / 8,
        "TSV": i_bpr * pv * r_tsv,
        "BSM1": j * pv * ph ** 2 * rs["BSM1"] / wv / 8,
        "BSV1": j * pv * ph * r_bsv1,
        "BSM2": j * ph * span ** 2 * rs["BSM2"] / wh / 8,
        "BSV2": j * ph * span / 2 * r_bsv2,                           # each end carries half the stripe's load
    }
    return {p: v * 1e3 for p, v in parts.items()} | {"sum": sum(parts.values()) * 1e3}


def solve_case(work, k, case):
    name, side, feed, pitch, tsv, rho, hot = case
    out = os.path.join(work, name)
    grid = bsgrid.write(out, k, side, feed, pitch or 20.0, tsv, hot)
    row = {"case": name, "grid": grid, "nets": {}}
    for net in ("VDD", "VSS"):
        t0 = time.perf_counter()
        mesh, v, pin_node, info = irbuild.solve_mesh(out, net, use_cutclass=False, rail_layer="BPR")
        secs = time.perf_counter() - t0
        supply = k["supply"]
        inst = irbuild.instance_voltages(v, pin_node, net)
        d = np.array([supply - x if net == "VDD" else x for x in inst.values()]) * 1e3
        layer = {}
        for lay, pts in mesh.on_layer.items():
            vv = v[[n for _, _, n in pts]]
            layer[lay] = float((supply - vv.min()) * 1e3 if net == "VDD" else vv.max() * 1e3)
        worst = max(inst, key=lambda n: (supply - inst[n]) if net == "VDD" else inst[n])
        row["nets"][net] = {"worst_mv": float(d.max()), "median_mv": float(np.median(d)), "worst_instance": worst,
                            "worst_node_drop_by_layer_mv": layer, "seconds": round(secs, 2), "info": info}
    return row


def main():
    kit_dir, work, out = sys.argv[1:4]
    if os.path.exists(out):
        sys.exit(f"{out} exists (records are append-only)")
    rows, ests = [], {}
    tracemalloc.start()
    for case in CASES:
        k = bsgrid.kit(kit_dir, case[5])
        rows.append(solve_case(work, k, case))
        if case[2] == "ring" and case[5] == "ict" and case[4] is None and not case[6]:
            ests[case[0]] = estimate(k, case[1])
        print(case[0], {n: round(r["worst_mv"], 4) for n, r in rows[-1]["nets"].items()}, flush=True)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    rec = {"what": "c5 dry: MATRIX-A5 backside grid IR drop, mV per A/mm^2 (DESIGN.md)", "kit": kit_dir,
           "kit_sha256": sha256s(kit_dir, KIT_FILES), "code_sha256": sha256s(HERE, CODE_FILES),
           "seconds_note": "solve times measured with tracemalloc running (upper bounds)",
           "load_a_per_mm2": bsgrid.J_A_PER_UM2 * 1e6, "pin_mode": "spread", "cases": rows,
           "hand_estimate_vdd_mv": ests, "tracemalloc_peak_mb": round(peak / 1e6, 1),
           "python": platform.python_version(), "numpy": np.__version__}
    with open(out, "x", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)


if __name__ == "__main__":
    main()
