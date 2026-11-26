"""c6 (DESIGN.md): frontside against backside-power stacks, leakage loop and runaway margin on MATRIX-A5's c3 tables.

  python c6.py leak <c3 tables.json> <out.json> <svt lib> <lvt lib> <ulvt lib>   host: leakage density (W/mm^2)
  python c6.py run <leak.json> <workdir> <out dir>      container: R per stack, loop, margin, checks
  python c6.py summary <c6.json> <summary.md>           host: checks a-d with verdicts, and the per-case table
"""
import argparse
import json
import os
import re
from pathlib import Path

import numpy as np

SIZE_UM, GRID, AMB_K, HTC = 1000.0, 32, 300.0, 5.0e4
DYN_W_MM2, HOT_TILES, HOT_X = 0.5, 4, 10.0
UTIL = 0.7
BASE_MATERIALS = {"silicon": {"k": 130, "cv": 1.63566e6}, "tim": {"k": 4.0, "cv": 2.0e6},
                  "copper": {"k": 400, "cv": 3.45e6}, "oxide": {"k": 1.4, "cv": 1.6e6}}
K_BEOL, T_CARRIER, K_BS = (0.6, 1.2, 3.0), (50, 200), (71, 10)
VTS = ("svt", "lvt", "ulvt")
WORKLOADS = ("uniform", "hotspot")
BRACKET = (1e-3, 1e3)          # DESIGN.md step 3, fixed before the run
A_TOL, D_TOL = 0.10, 1e-3      # checks a and d
B_TOL_K = 0.005                # check b: half of PACT's output step (it writes temperatures with two decimals)
B_STACK = "fs_kbeol1.2"        # check b's stack (DESIGN.md)
CELL_AREA = re.compile(r"^\s*cell\s*\(\s*\"?([^\")\s]+)\"?\s*\)\s*\{.*?^\s*area\s*:\s*([0-9.eE+-]+)\s*;",
                       re.MULTILINE | re.DOTALL)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(obj, path):
    """Atomic: a temporary file beside the target, then os.replace (L42)."""
    tmp = Path(f"{path}.tmp")
    tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def liberty_areas(text):
    """{cell: area um^2} from a Liberty file: the first `area` after each `cell (name) {`."""
    return {m.group(1): float(m.group(2)) for m in CELL_AREA.finditer(text)}


def leak_density(tables, areas_by_vt):
    """{vt: {"temps_c", "w_mm2", ...}}: mean over c3's cells of the cell-mean power, over their mean area, x UTIL."""
    out = {}
    for vt in VTS:
        cells = tables["vt"][vt]
        names = sorted(c for c, v in cells.items() if None not in v["mean"])
        missing = [c for c in names if c not in areas_by_vt[vt]]
        if missing:
            raise SystemExit(f"{vt}: no Liberty area for {missing[:5]}")
        mean_w = np.mean([cells[c]["mean"] for c in names], axis=0)
        mean_a = float(np.mean([areas_by_vt[vt][c] for c in names]))
        out[vt] = {"temps_c": tables["temps_c"], "cells": len(names), "mean_area_um2": mean_a,
                   "w_mm2": list(mean_w / (mean_a * 1e-6) * UTIL)}
    return out


def layer(name, material, um, **kw):
    return {"name": name, "material": material, "thickness_um": um, **kw}


def stack_dict(name, layers, extra, grid):
    """One stack: the base materials plus `extra`, the layers given; nothing else differs between stacks (A4)."""
    return {"name": name, "size_um": [SIZE_UM, SIZE_UM], "grid": [grid, grid], "ambient_K": AMB_K,
            "heat_sink": {"htc": HTC}, "materials": {**BASE_MATERIALS, **extra}, "layers": layers}


def stacks(grid=GRID):
    """{name: YAML dict}: 3 frontside and 12 backside stacks (DESIGN.md table); bottom face adiabatic."""
    top = [layer("spreader", "copper", 500, n_sub=10), layer("tim", "tim", 25, n_sub=3)]
    out = {}
    for kb in K_BEOL:
        beol = {f"beol_{kb}": {"k": kb, "cv": 2.0e6}}
        out[f"fs_kbeol{kb}"] = stack_dict(f"fs_kbeol{kb}", top + [
            layer("die", "silicon", 50, die=True, source_um=2, n_sub=6),
            layer("beol", f"beol_{kb}", 5, n_sub=2)], beol, grid)
        for tc in T_CARRIER:
            for ks in K_BS:
                name = f"bs_kbeol{kb}_tc{tc}_kbs{ks}"
                out[name] = stack_dict(name, top + [
                    layer("carrier", "silicon", tc, n_sub=max(4, tc // 12)), layer("bond", "oxide", 1),
                    layer("beol", f"beol_{kb}", 5, n_sub=2),
                    layer("die", "silicon", 0.5, die=True, source_um=0.1, source_side="top"),
                    layer("bspdn", f"bspdn_{ks}", 2)], {**beol, f"bspdn_{ks}": {"k": ks, "cv": 2.0e6}}, grid)
    return out


def one_d_k_per_w(st):
    """Series estimate of the uniform-load mean rise per W: half the source layer, then every layer between the
    sources and the sink, then 1 / (htc A)."""
    area = (SIZE_UM * 1e-6) ** 2
    mats = st["materials"]
    r = 1.0 / (HTC * area)
    for l in st["layers"]:
        k = mats[l["material"]]["k"]
        if l.get("die"):
            src = l["source_um"]
            above = src / 2 if l.get("source_side") == "top" else l["thickness_um"] - src / 2
            return r + above * 1e-6 / (k * area)
        r += l["thickness_um"] * 1e-6 / (k * area)
    raise SystemExit(f"{st['name']}: no die")


def dyn_tiles(workload, grid=GRID):
    """(grid*grid,) W per tile, row-major; the hotspot keeps the uniform total."""
    tile_mm2 = (SIZE_UM / grid / 1000) ** 2
    w = np.ones((grid, grid))
    if workload == "hotspot":
        c0 = (grid - HOT_TILES) // 2
        w[c0:c0 + HOT_TILES, c0:c0 + HOT_TILES] = HOT_X
    elif workload != "uniform":
        raise SystemExit(f"unknown workload {workload}")
    return (w / w.mean() * DYN_W_MM2 * tile_mm2).ravel()


def margin(critical_scale, R, dyn, make_leak):
    """The runaway scale inside DESIGN's fixed bracket; a bracket or convergence failure is returned as an error."""
    try:
        lo, hi, n = critical_scale(R, dyn, make_leak, AMB_K, lo=BRACKET[0], hi=BRACKET[1], rtol=1e-4)
    except RuntimeError as e:      # critical_scale's own failure: wrong bracket or a probe not converged
        return {"error": str(e)}
    return {"s_lo": lo, "s_hi": hi, "probes": n}


def run_cases(name, R, leak, grid, et, runaway):
    """Every workload x Vt on one stack's operator; a failing case is recorded and the rest go on (A16)."""
    n = grid * grid
    tile_mm2 = (SIZE_UM / grid / 1000) ** 2
    cases = []
    for wl in WORKLOADS:
        dyn = dyn_tiles(wl, grid)
        r0 = R @ dyn
        for vt in VTS:
            lw = np.asarray(leak[vt]["w_mm2"]) * tile_mm2

            def make(s, lw=lw, vt=vt):
                return et.LeakModel(leak[vt]["temps_c"], np.tile(lw, (n, 1)), np.arange(n), n, scale=s)
            case = {"stack": name, "workload": wl, "vt": vt, "dyn_w": float(dyn.sum()),
                    "peak_rise_no_leak_k": float(r0.max()), "mean_rise_no_leak_k": float(r0.mean())}
            try:
                o = runaway.classify(R, dyn, make(1.0), AMB_K)
                case.update({"status": o.status, "rho": o.rho, "iterations": o.iterations, "monotone": o.monotone,
                             "peak_t_k": float(o.T.max()), "mean_t_k": float(o.T.mean())})
                case.update(margin(runaway.critical_scale, R, dyn, make))
            except Exception as e:  # noqa: BLE001 (A16: any failure of one case is recorded, not fatal)
                case["error"] = f"{type(e).__name__}: {e}"
            if "s_lo" in case:
                case["crit_leak_w_mm2_25c"] = case["s_lo"] * leak[vt]["w_mm2"][0]
            cases.append(case)
            print(name, wl, vt, case.get("status"), case.get("s_lo"), case.get("error", ""), flush=True)
    return cases


def check_d(et, runaway):
    """One tile with exact exponential leakage c exp(a (T - 273.15)): bisection against the analytic boundary."""
    a, c, r1, d1 = 0.05, 1e-3, 50.0, 0.2
    temps = np.array([0.0, 200.0])

    def lm(s):
        return et.LeakModel(temps, [c * np.exp(a * temps)], [0], 1, scale=s)
    lo, _, _ = runaway.critical_scale(np.array([[r1]]), np.array([d1]), lm, AMB_K, lo=1e-3, hi=1e3, rtol=1e-6)
    return float(lo / (runaway.critical_scale_1tile(r1, d1, c, a, AMB_K) / c) - 1)


def one_hot(k, grid):
    P = np.zeros((grid, grid))
    P.flat[k] = 1.0
    return P


def operator(stack, grid, wd, response):
    """R[i, k]: rise at tile i per W in tile k (row-major tiles), from PACT's matrix, one basis pattern per tile."""
    n = grid * grid
    return response.build(stack, [{"die": one_hot(k, grid)} for k in range(n)], wd)[:, 0].reshape(n, n).T


def run(leak_path, workdir, out, grid=GRID, only=None):
    """only: stack names to run (None: all). c6.json is rewritten after every stack, so a kill keeps what finished."""
    import yaml
    from opentsense.stack import model
    from opentsense.thermal import electrothermal as et
    from opentsense.thermal import response, runaway
    from opentsense.thermal.run import run_pact

    leak = read_json(leak_path)
    os.makedirs(out, exist_ok=True)
    n = grid * grid
    planned = [n for n in stacks(grid) if not only or n in only]     # check c's denominator (C6-4)
    res = {"leak": leak, "grid": grid, "planned": planned, "cases": [], "stacks": {},
           "checks": {"d_rel": check_d(et, runaway)}}
    target = os.path.join(out, "c6.json")
    for name, st in stacks(grid).items():
        if name not in planned:
            continue
        wd = os.path.join(workdir, name)
        os.makedirs(wd, exist_ok=True)
        path = os.path.join(wd, "stack.yaml")
        Path(path).write_text(yaml.safe_dump(st, sort_keys=False), encoding="utf-8")
        try:
            stack = model.load(path)
            R = operator(stack, grid, wd, response)
        except Exception as e:  # noqa: BLE001 (A16: one stack's solver failure does not void the others)
            res["stacks"][name] = {"error": f"{type(e).__name__}: {e}"}
            write_json(res, target)
            continue
        mean_rise = float(R.sum(axis=1).mean() / n)                   # uniform 1 W total
        est = one_d_k_per_w(st)
        res["stacks"][name] = {"mean_rise_k_per_w": mean_rise, "one_d_k_per_w": est,
                               "check_a_rel": mean_rise / est - 1, "r_diag_max": float(R.diagonal().max())}
        if name == B_STACK:
            c = (grid // 2) * grid + grid // 2
            direct = run_pact(stack, {"die": one_hot(c, grid)}, os.path.join(wd, "direct"))["die"].ravel() - AMB_K
            res["checks"]["b_max_abs_diff_k"] = float(np.abs(R[:, c] - direct).max())
        res["cases"] += run_cases(name, R, leak, grid, et, runaway)
        write_json(res, target)
    res["complete"] = True          # the positive end marker the summary requires (L67)
    write_json(res, target)


def fs_of(name):
    """The frontside stack a backside stack is compared with: the same k_beol."""
    return "fs_" + name.split("_")[1]


def verdict(ok):
    return "PASS" if ok else "FAIL"


def check_rows(res):
    """Checks a-d against DESIGN.md's limits, each with a verdict; a missing value fails."""
    st, ch, cases = res["stacks"], res["checks"], res["cases"]
    err = [n for n, v in st.items() if "error" in v]
    a_out = [f"{n} {v['check_a_rel']:+.1%}" for n, v in st.items()
             if "error" not in v and abs(v["check_a_rel"]) > A_TOL]
    bad = [f"{c['stack']} {c['workload']} {c['vt']}: {c['error']}" for c in cases if "error" in c]
    planned = res.get("planned", list(st))          # a failed or never-reached stack leaves no case rows (C6-4)
    have = {(c["stack"], c["workload"], c["vt"]) for c in cases}
    bad += [f"{n} {wl} {vt}: no case row" for n in planned for wl in WORKLOADS for vt in VTS if (n, wl, vt) not in have]
    if not res.get("complete"):
        bad.append("no end marker: the run did not finish")
    b = ch.get("b_max_abs_diff_k")
    a_txt = f"{len(st) - len(a_out) - len(err)} of {len(st)}" + (f"; outside: {', '.join(a_out)}" if a_out else "") \
        + (f"; solver failed: {', '.join(err)}" if err else "")
    return [("a: mean rise within 10% of the 1-D estimate", a_txt, bool(st) and not a_out and not err),
            ("b: R column against a direct PACT run, max abs difference <= 0.005 K",
             "missing" if b is None else f"{b:.4f} K", b is not None and b <= B_TOL_K),
            ("c: margin located: bracket closed with every probe classified",
             f"{sum('error' not in c for c in cases)} of {len(planned) * len(WORKLOADS) * len(VTS)}"
             + (f"; not located: {'; '.join(bad)}" if bad else ""),
             bool(cases) and not bad),
            ("d: one-tile margin against the analytic boundary, abs relative difference <= 1e-3", f"{ch['d_rel']:+.2e}",
             abs(ch["d_rel"]) <= D_TOL)]


def summary(res):
    """Markdown: checks a-d with verdicts, then one row per case with BS / FS ratios at matching k_beol, workload
    and Vt. A run without its end marker is labelled incomplete."""
    lines = [] if res.get("complete") else ["**Incomplete run: c6.json has no end marker.**", ""]
    lines += ["| Check | Result | Verdict |", "|---|---|---|"]
    lines += [f"| {name} | {txt} | {verdict(ok)} |" for name, txt, ok in check_rows(res)]
    lines += ["", ("| Stack | Workload | Vt | Peak rise, no leakage (K) | x FS | Status at nominal | Peak T (K) | rho "
              "| s_crit | x FS | Critical leakage at 25 C (W/mm^2) |"), "|---|---|---|---|---|---|---|---|---|---|---|"]
    by = {(c["stack"], c["workload"], c["vt"]): c for c in res["cases"]}
    for (n, wl, vt), c in by.items():
        f = by.get((fs_of(n), wl, vt)) if n.startswith("bs_") else None
        rr = f"{c['peak_rise_no_leak_k'] / f['peak_rise_no_leak_k']:.2f}" if f else "-"
        sr = f"{c['s_lo'] / f['s_lo']:.2f}" if f and "s_lo" in c and "s_lo" in f else "-"
        s = f"{c['s_lo']:.4g}" if "s_lo" in c else "-"
        cl = f"{c['crit_leak_w_mm2_25c']:.4g}" if "s_lo" in c else "-"
        pk = f"{c['peak_t_k']:.2f}" if "peak_t_k" in c else "-"
        rho = f"{c['rho']:.4f}" if "rho" in c else "-"
        lines.append(f"| {n} | {wl} | {vt} | {c['peak_rise_no_leak_k']:.3f} | {rr} | {c.get('status', 'error')} "
                     f"| {pk} | {rho} | {s} | {sr} | {cl} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("leak")
    p.add_argument("tables")
    p.add_argument("out")
    p.add_argument("libs", nargs=3, metavar="LIB", help="TT 25 C Liberty for svt, lvt, ulvt in that order")
    p = sub.add_parser("run")
    p.add_argument("leak")
    p.add_argument("workdir")
    p.add_argument("out")
    p = sub.add_parser("summary")
    p.add_argument("c6_json")
    p.add_argument("out")
    a = ap.parse_args()
    if a.cmd == "leak":
        areas = {vt: liberty_areas(Path(p).read_text(encoding="utf-8", errors="replace"))
                 for vt, p in zip(VTS, a.libs, strict=True)}
        write_json(leak_density(read_json(a.tables), areas), a.out)
    elif a.cmd == "run":
        run(a.leak, a.workdir, a.out)
    else:
        Path(a.out).write_text(summary(read_json(a.c6_json)), encoding="utf-8")


if __name__ == "__main__":
    main()
