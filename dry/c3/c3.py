"""c3 (DESIGN.md): MATRIX-A5 leakage against temperature at TT, from C2's decks.

  python c3.py retemp <deck dir> <T>                  set every deck's .temp line to T (exactly one per deck)
  python c3.py tables <runs dir> <c2 runs dir> <out>  checks 1-4 and record/tables.json, summary.md
"""
import glob
import json
import math
import os
import re
import sys

VTS = ("svt", "lvt", "ulvt")
TEMPS = (25, 45, 65, 85, 105, 125)
TEMP_LINE = re.compile(r"^\.temp \S+$", re.M)


def lib_dir(vt, t):
    return f"GT_A5_{vt}_TTG_{t}C"


def retemp(out, t):
    """Every s*.cir in `out` gets `.temp <t>` in place of its one .temp line; cases.json's temp follows."""
    t = float(t)
    decks = sorted(glob.glob(os.path.join(out, "s*.cir")))
    if not decks:
        raise SystemExit(f"no decks in {out}")
    for p in decks:
        text = open(p, encoding="utf-8").read()
        new, n = TEMP_LINE.subn(f".temp {t}", text)
        if n != 1:
            raise SystemExit(f"{p}: {n} .temp lines")
        open(p, "w", encoding="utf-8", newline="\n").write(new)
    meta_path = os.path.join(out, "cases.json")
    meta = json.load(open(meta_path))
    meta["temp"] = t
    json.dump(meta, open(meta_path, "w"), indent=1)
    print(f"{out}: {len(decks)} decks at {t} C")


def states(result):
    """{(cell, when): mean SPICE power over the state's product terms, None if any term is invalid}."""
    groups = {}
    for c in result["cases"]:
        groups.setdefault((c["cell"], c["when"]), []).append(c["spice_w"])
    return {k: (sum(ws) / len(ws) if None not in ws else None) for k, ws in groups.items()}


def loglin_worst(ts, ps):
    """Worst relative residual of a least-squares fit ln P = a + b T (description only)."""
    ys = [math.log(p) for p in ps]
    n, mt, my = len(ts), sum(ts) / len(ts), sum(ys) / len(ys)
    b = sum((t - mt) * (y - my) for t, y in zip(ts, ys, strict=True)) / sum((t - mt) ** 2 for t in ts)
    a = my - b * mt
    return max(abs(math.exp(a + b * t) / p - 1) for t, p in zip(ts, ps, strict=True)) if n > 1 else 0.0


def median(xs):
    s = sorted(xs)
    return (s[len(s) // 2] + s[(len(s) - 1) // 2]) / 2 if s else None


def check_vt(vt, per_t, c2):
    """Checks 1-4 for one Vt. per_t: {T: states(...)}; c2: {name: states(...)} for C2 run 5's libraries."""
    keys = sorted(per_t[TEMPS[0]])
    c2_tt = c2[f"GT_A5_{vt}_TTG_25C"]
    ss, ff = c2[f"GT_A5_{vt}_SSG_125C"], c2[f"GT_A5_{vt}_FFG_125C"]
    r = {"states": len(keys),
         "parity_mismatch": [f"{k[0]} {k[1]}" for k in keys if per_t[25].get(k) != c2_tt.get(k)],
         "invalid": {t: [f"{k[0]} {k[1]}" for k in keys if per_t[t].get(k) is None] for t in TEMPS},
         "not_rising": [], "outside_bracket": [], "no_bracket": []}
    ratios = []
    for k in keys:
        ps = [per_t[t].get(k) for t in TEMPS]
        if None not in ps:
            r["not_rising"] += [f"{k[0]} {k[1]}: {a} C {pa:.4e} -> {b} C {pb:.4e}"
                                for a, b, pa, pb in zip(TEMPS, TEMPS[1:], ps, ps[1:], strict=False) if pb <= pa]
            ratios.append(ps[-1] / ps[0])
        lo, hi, p = ss.get(k), ff.get(k), per_t[125].get(k)
        if None in (lo, hi, p):
            r["no_bracket"].append(f"{k[0]} {k[1]}")
        elif not min(lo, hi) <= p <= max(lo, hi):
            r["outside_bracket"].append(f"{k[0]} {k[1]}: SS {lo:.4e} TT {p:.4e} FF {hi:.4e}")
    r["p125_over_p25"] = {"median": median(ratios), "min": min(ratios, default=None), "max": max(ratios, default=None)}
    return r


def table_vt(per_t):
    cells = {}
    for (cell, when) in sorted(per_t[TEMPS[0]]):
        cells.setdefault(cell, {"states": {}})["states"][when] = [per_t[t].get((cell, when)) for t in TEMPS]
    for c in cells.values():
        rows = list(c["states"].values())
        c["mean"] = [None if any(r[j] is None for r in rows) else sum(r[j] for r in rows) / len(rows)
                     for j in range(len(TEMPS))]
        c["loglin_worst_rel"] = None if None in c["mean"] else loglin_worst(TEMPS, c["mean"])
    return cells


def tables(runs, c2_runs, out):
    c2 = {os.path.basename(os.path.dirname(p)): states(json.load(open(p)))
          for p in glob.glob(os.path.join(c2_runs, "GT_A5_*", "result.json"))}
    report, tab = {}, {"temps_c": list(TEMPS), "unit": "W", "vdd_v": None, "vt": {}}
    for vt in VTS:
        per_t = {}
        for t in TEMPS:
            res = json.load(open(os.path.join(runs, lib_dir(vt, t), "result.json")))
            if res["temp"] != float(t):
                raise SystemExit(f"{lib_dir(vt, t)}: result temp {res['temp']}")
            tab["vdd_v"] = res["vdd"]
            per_t[t] = states(res)
        report[vt] = check_vt(vt, per_t, c2)
        cells = table_vt(per_t)
        tab["vt"][vt] = cells
        fits = [c["loglin_worst_rel"] for c in cells.values() if c["loglin_worst_rel"] is not None]
        report[vt]["loglin_worst_rel_max"] = max(fits, default=None)
    os.makedirs(out, exist_ok=True)
    json.dump(tab, open(os.path.join(out, "tables.json"), "w"), indent=1)
    json.dump(report, open(os.path.join(out, "checks.json"), "w"), indent=1)
    lines = ["| Vt | States | 1 parity mismatches | 2 invalid (any T) | 3 not rising | 4 outside SS-FF at 125 C "
             "| no bracket | P(125)/P(25) median (range) | log-linear fit worst |",
             "|---|---|---|---|---|---|---|---|---|"]
    for vt, r in report.items():
        inv = len({s for v in r["invalid"].values() for s in v})
        q = r["p125_over_p25"]
        rng = "-" if q["median"] is None else f"{q['median']:.2f} ({q['min']:.2f}-{q['max']:.2f})"
        fit = "-" if r["loglin_worst_rel_max"] is None else f"{r['loglin_worst_rel_max']:.1%}"
        lines.append(f"| {vt} | {r['states']} | {len(r['parity_mismatch'])} | {inv} | {len(r['not_rising'])} "
                     f"| {len(r['outside_bracket'])} | {len(r['no_bracket'])} | {rng} | {fit} |")
    open(os.path.join(out, "summary.md"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    {"retemp": retemp, "tables": tables}[sys.argv[1]](*sys.argv[2:])
