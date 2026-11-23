"""c6 (DESIGN.md): frontside against backside-power stacks, leakage loop and runaway margin on MATRIX-A5's c3 tables.

  python c6.py leak <c3 tables.json> <out.json> <lib per Vt...>   host: per-Vt leakage density curve (W/mm^2)
  python c6.py run <leak.json> <workdir> <out dir>                container: R per stack, loop, margin, checks
  python c6.py summary <c6.json> <summary.md>                     host: checks and the per-case table
"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

SIZE_UM, GRID, AMB_K, HTC = 1000.0, 32, 300.0, 5.0e4
DYN_W_MM2, HOT_TILES, HOT_X = 0.5, 4, 10.0
UTIL = 0.7
MATERIALS = {"silicon": {"k": 130, "cv": 1.63566e6}, "tim": {"k": 4.0, "cv": 2.0e6},
             "copper": {"k": 400, "cv": 3.45e6}, "oxide": {"k": 1.4, "cv": 1.6e6}}
K_BEOL, T_CARRIER, K_BS = (0.6, 1.2, 3.0), (50, 200), (71, 10)
VTS = ("svt", "lvt", "ulvt")
CELL_AREA = re.compile(r"^\s*cell\s*\(\s*\"?([^\")\s]+)\"?\s*\)\s*\{.*?^\s*area\s*:\s*([0-9.eE+-]+)\s*;",
                       re.MULTILINE | re.DOTALL)


def liberty_areas(text):
    """{cell: area um^2} from a Liberty file: the first `area` after each `cell (name) {`."""
    return {m.group(1): float(m.group(2)) for m in CELL_AREA.finditer(text)}


def leak_density(tables, areas_by_vt):
    """{vt: {"temps_c", "w_mm2"}}: mean over c3's cells of the cell-mean power, over their mean area, x UTIL."""
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


def stacks():
    """{name: YAML dict}: 3 frontside and 12 backside stacks (DESIGN.md table); bottom face adiabatic."""
    mats = dict(MATERIALS)
    out = {}
    top = [layer("spreader", "copper", 500, n_sub=10), layer("tim", "tim", 25, n_sub=3)]
    for kb in K_BEOL:
        mats[f"beol_{kb}"] = {"k": kb, "cv": 2.0e6}
        out[f"fs_kbeol{kb}"] = top + [layer("die", "silicon", 50, die=True, source_um=2, n_sub=6),
                                      layer("beol", f"beol_{kb}", 5, n_sub=2)]
        for tc in T_CARRIER:
            for ks in K_BS:
                mats[f"bspdn_{ks}"] = {"k": ks, "cv": 2.0e6}
                out[f"bs_kbeol{kb}_tc{tc}_kbs{ks}"] = top + [
                    layer("carrier", "silicon", tc, n_sub=max(4, tc // 12)), layer("bond", "oxide", 1),
                    layer("beol", f"beol_{kb}", 5, n_sub=2),
                    layer("die", "silicon", 0.5, die=True, source_um=0.1, source_side="top"),
                    layer("bspdn", f"bspdn_{ks}", 2)]
    return {n: {"name": n, "size_um": [SIZE_UM, SIZE_UM], "grid": [GRID, GRID], "ambient_K": AMB_K,
                "heat_sink": {"htc": HTC}, "materials": mats, "layers": ls} for n, ls in out.items()}


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


def dyn_tiles(workload):
    """(GRID*GRID,) W per tile, row-major; the hotspot keeps the uniform total."""
    tile_mm2 = (SIZE_UM / GRID / 1000) ** 2
    w = np.ones((GRID, GRID))
    if workload == "hotspot":
        c0 = (GRID - HOT_TILES) // 2
        w[c0:c0 + HOT_TILES, c0:c0 + HOT_TILES] = HOT_X
    elif workload != "uniform":
        raise SystemExit(f"unknown workload {workload}")
    return (w / w.mean() * DYN_W_MM2 * tile_mm2).ravel()


def margin(classify, critical_scale, R, dyn, make_leak):
    """critical_scale with the upper end raised by 10x (to 1e6) until it is runaway; errors are returned, not raised."""
    for hi in (1e3, 1e4, 1e5, 1e6):
        try:
            lo, hi_, n = critical_scale(R, dyn, make_leak, AMB_K, lo=1e-3, hi=hi, rtol=1e-4)
            return {"s_lo": lo, "s_hi": hi_, "probes": n}
        except RuntimeError as e:
            if classify(R, dyn, make_leak(hi), AMB_K).status == "converged":
                continue
            return {"error": str(e)}
    return {"error": "no runaway up to scale 1e6"}


def run(leak_path, workdir, out):
    import yaml
    from opentsense.stack import model
    from opentsense.thermal import electrothermal as et
    from opentsense.thermal import response, runaway
    from opentsense.thermal.run import run_pact

    leak = json.loads(Path(leak_path).read_text())
    os.makedirs(out, exist_ok=True)
    n = GRID * GRID
    tile_mm2 = (SIZE_UM / GRID / 1000) ** 2
    res = {"leak": leak, "cases": [], "stacks": {}, "checks": {}}
    for name, st in stacks().items():
        wd = os.path.join(workdir, name)
        os.makedirs(wd, exist_ok=True)
        path = os.path.join(wd, "stack.yaml")
        Path(path).write_text(yaml.safe_dump(st, sort_keys=False))
        stack = model.load(path)
        basis = []
        for k in range(n):
            P = np.zeros((GRID, GRID))
            P.flat[k] = 1.0
            basis.append({"die": P})
        R = response.build(stack, basis, wd)[:, 0].reshape(n, n).T   # R[i, k]: rise at tile i per W in tile k
        mean_rise = float(R.sum(axis=1).mean() / n)                   # uniform 1 W total
        est = one_d_k_per_w(st)
        res["stacks"][name] = {"mean_rise_k_per_w": mean_rise, "one_d_k_per_w": est,
                               "check_a_rel": mean_rise / est - 1, "r_diag_max": float(R.diagonal().max())}
        if name == "fs_kbeol1.2":
            c = (GRID // 2) * GRID + GRID // 2
            P = np.zeros((GRID, GRID))
            P.flat[c] = 1.0
            direct = run_pact(stack, {"die": P}, os.path.join(wd, "direct"))["die"].ravel() - AMB_K
            res["checks"]["b_max_abs_diff_k"] = float(np.abs(R[:, c] - direct).max())
        for wl in ("uniform", "hotspot"):
            dyn = dyn_tiles(wl)
            r0 = R @ dyn
            for vt in VTS:
                lw = np.asarray(leak[vt]["w_mm2"]) * tile_mm2

                def make(s, lw=lw, vt=vt):
                    return et.LeakModel(leak[vt]["temps_c"], np.tile(lw, (n, 1)), np.arange(n), n, scale=s)
                o = runaway.classify(R, dyn, make(1.0), AMB_K)
                case = {"stack": name, "workload": wl, "vt": vt, "dyn_w": float(dyn.sum()),
                        "peak_rise_no_leak_k": float(r0.max()), "mean_rise_no_leak_k": float(r0.mean()),
                        "status": o.status, "rho": o.rho, "iterations": o.iterations, "monotone": o.monotone,
                        "peak_t_k": float(o.T.max()), "mean_t_k": float(o.T.mean())}
                m = margin(runaway.classify, runaway.critical_scale, R, dyn, make)
                case.update(m)
                if "s_lo" in m:
                    case["crit_leak_w_mm2_25c"] = m["s_lo"] * leak[vt]["w_mm2"][0]
                res["cases"].append(case)
                print(name, wl, vt, o.status, case.get("s_lo"), flush=True)
    # check d: one tile, exact exponential leakage c exp(a (T - 273.15))
    a, c, r1, d1 = 0.05, 1e-3, 50.0, 0.2
    temps = np.array([0.0, 200.0])
    lm = (lambda s: et.LeakModel(temps, [c * np.exp(a * temps)], [0], 1, scale=s))
    lo, _, _ = runaway.critical_scale(np.array([[r1]]), np.array([d1]), lm, AMB_K, lo=1e-3, hi=1e3, rtol=1e-6)
    exact = runaway.critical_scale_1tile(r1, d1, c, a, AMB_K) / c
    res["checks"]["d_rel"] = float(lo / exact - 1)
    Path(out, "c6.json").write_text(json.dumps(res, indent=1))


def fs_of(name):
    """The frontside stack a backside stack is compared with: the same k_beol."""
    return "fs_" + name.split("_")[1]


def summary(res):
    """Markdown: checks a-d, then one row per case with the BS / FS ratios at matching k_beol, workload and Vt."""
    st, ch = res["stacks"], res["checks"]
    a = [f"{n} {v['check_a_rel']:+.1%}" for n, v in st.items() if abs(v["check_a_rel"]) > 0.10]
    bad = [f"{c['stack']} {c['workload']} {c['vt']}: {c['error']}" for c in res["cases"] if "error" in c]
    lines = ["| Check | Result |", "|---|---|",
             f"| a: mean rise within 10% of the 1-D estimate | {len(st) - len(a)} of {len(st)}"
             + (f"; outside: {', '.join(a)}" if a else "") + " |",
             f"| b: R column against a direct PACT run, max abs difference (K; PACT rounds to 0.01) | {ch.get('b_max_abs_diff_k', float('nan')):.4f} |",
             f"| c: margin located | {len(res['cases']) - len(bad)} of {len(res['cases'])}"
             + (f"; not located: {'; '.join(bad)}" if bad else "") + " |",
             f"| d: one-tile margin against the analytic boundary | {ch['d_rel']:+.2e} |", "",
             "| Stack | Workload | Vt | Peak rise, no leakage (K) | x FS | Status at nominal | Peak T (K) | rho "
             "| s_crit | x FS | Critical leakage at 25 C (W/mm^2) |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    by = {(c["stack"], c["workload"], c["vt"]): c for c in res["cases"]}
    for (n, wl, vt), c in by.items():
        f = by.get((fs_of(n), wl, vt)) if n.startswith("bs_") else None
        rr = f"{c['peak_rise_no_leak_k'] / f['peak_rise_no_leak_k']:.2f}" if f else "-"
        sr = f"{c['s_lo'] / f['s_lo']:.2f}" if f and "s_lo" in c and "s_lo" in f else "-"
        s = f"{c['s_lo']:.4g}" if "s_lo" in c else "-"
        cl = f"{c['crit_leak_w_mm2_25c']:.4g}" if "s_lo" in c else "-"
        lines.append(f"| {n} | {wl} | {vt} | {c['peak_rise_no_leak_k']:.3f} | {rr} | {c['status']} "
                     f"| {c['peak_t_k']:.2f} | {c['rho']:.4f} | {s} | {sr} | {cl} |")
    return "\n".join(lines) + "\n"


def main(argv):
    if argv[0] == "summary":
        Path(argv[2]).write_text(summary(json.loads(Path(argv[1]).read_text())), encoding="utf-8")
    elif argv[0] == "leak":
        tables = json.loads(Path(argv[1]).read_text())
        libs = dict(zip(VTS, argv[3:], strict=True))
        areas = {vt: liberty_areas(Path(p).read_text(encoding="utf-8", errors="replace")) for vt, p in libs.items()}
        Path(argv[2]).write_text(json.dumps(leak_density(tables, areas), indent=1))
    elif argv[0] == "run":
        run(*argv[1:])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
