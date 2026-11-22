"""C2 scoring (registration.md): validity V1-V4, per library EXACT / DEVICE OFFSET / FAIL, and the temperature check
for c3; writes <runs>/summary.json and prints a table. Usage: python evaluate.py <runs dir>"""
import json
import pathlib
import sys

from leak import SKIP_RULES

TOL = 0.02
MIN_CELLS = 50
# Amendment 2 (option A): the kit's Liberty carries 7.0e-15 A per off PMOS that SPICE at gmin 1e-18 does not
# (diag/FINDINGS.md, finding 3). A state is scored only if its Liberty value is at least 100x one PMOS's floor power
# (floor share at most 1% per off PMOS); below that it is listed with its ratio.
FLOOR_A = 7.0e-15
FLOOR_FACTOR = 100
# Amendment 4: the floor is per PMOS, not per state (run 4, lvt SSG -40 C). A state's cut is FLOOR_FACTOR x its own
# kit floor power (leak.kit_floor_w, an upper bound from its operating point), never below Amendment 2's one-floor
# cut; a state without an operating point (invalid) keeps the one-floor cut.
LIBS = [f"GT_A5_{vt}_{pt}" for vt in ("svt", "lvt", "ulvt")
        for pt in ("TTG_25C", "SSG_m40C", "SSG_125C", "FFG_m40C", "FFG_125C")]


def cut_w(c, vdd):
    """The state's floor cut (Amendment 4): FLOOR_FACTOR x max(one floor, the state's kit floor power)."""
    return FLOOR_FACTOR * max(FLOOR_A * vdd, c.get("floor_w") or 0.0)


def ref(cases, when, vdd):
    """(ratio, problem) of inv_x1's state `when`. Missing, ambiguous or without a ratio is a problem (the library is
    VOID, as before Amendment 2); below the floor cut gives ratio None and no problem (a listed state cannot bound
    the others, so DEVICE OFFSET is not available)."""
    found = [c for c in cases if c["cell"].startswith("gtA5_cfet_11_inv_x1_") and c["when"] == when]
    if len(found) != 1:
        return None, f"reference {when}: {len(found)} cases"
    if found[0]["liberty_w"] < cut_w(found[0], vdd):
        return None, None
    return found[0]["ratio"], (None if found[0]["ratio"] is not None else f"reference {when}: no ratio")


def floor_check(compared):
    """Diagnostic, not a bar (Amendment 4): (SPICE + kit floor) / Liberty over the compared states whose floor is
    above 1% of Liberty. The kit floor is an upper bound (exact without PMOS stacks, high in them; diag/a4_floor.py),
    so this reads 1 or above; a minimum well below 0.98 would mean the floor is undercounted and the cut too low."""
    rs = [(c["ratio"] * c["liberty_w"] + c["floor_w"]) / c["liberty_w"] for c in compared
          if c.get("floor_w") is not None and c["floor_w"] > c["liberty_w"] / FLOOR_FACTOR]
    return {"states": len(rs), "min": min(rs, default=None), "max": max(rs, default=None)}


def score(r):
    cases, vdd = r["cases"], r["vdd"]
    def below(c):
        return c["liberty_w"] < cut_w(c, vdd)
    compared = [c for c in cases if c["ratio"] is not None]
    scored = [c for c in compared if not below(c)]
    s = {"temp": r["temp"], "vt": r["vt"], "cases": len(cases), "dropped": r["dropped"], "skipped": r["skipped"],
         # V1 covers states at or above the cut; an invalid state below it is named, not voiding (Amendment 2)
         "invalid": [f'{c["cell"]} {c["when"]}: {c["invalid"]}' for c in cases if c["invalid"] and not below(c)],
         "invalid_below_floor": [f'{c["cell"]} {c["when"]}: {c["invalid"]}' for c in cases
                                 if c["invalid"] and below(c)],
         "not_scored": [f'{c["cell"]} {c["when"]}: Liberty {c["liberty_w"]}' for c in cases
                        if c["invalid"] is None and c["liberty_w"] <= 0],
         "floor_cut_w": FLOOR_FACTOR * FLOOR_A * vdd,   # the smallest cut; each state's own is cut_w
         "below_floor": [f'{c["cell"]} {c["when"]}: Liberty {c["liberty_w"]:.3e} cut {cut_w(c, vdd):.3e} '
                         f'ratio {c["ratio"]:.4f}' for c in compared if below(c)],
         "retried": [f'{c["cell"]} {c["when"]}: {c["method"]}' for c in cases if c.get("retry")],
         "floor_check": floor_check(compared),
         "cases_scored": len(scored), "cells_compared": len({c["cell"] for c in compared})}
    (s["rN"], pn), (s["rP"], pp) = ref(cases, "(!A * Y)", vdd), ref(cases, "(A * !Y)", vdd)
    s["reference_problems"] = [p for p in (pn, pp) if p]
    s["V1"] = not s["invalid"]
    valid = [c for c in cases if c["invalid"] is None]
    # V2, like V1, covers states at or above the cut; an output off by more than 10% below it is named (Amendment 2)
    s["V2"] = s["V1"] and all(c["out_err_v"] <= 0.1 * vdd for c in valid if not below(c))
    s["out_err_below_floor"] = [f'{c["cell"]} {c["when"]}: {c["out_err_v"]:.3g} V' for c in valid
                                if below(c) and c["out_err_v"] > 0.1 * vdd]
    s["V4"] = s["cells_compared"] >= MIN_CELLS
    s["unregistered_skips"] = {k: v for k, v in r["skipped"].items() if not v.startswith(SKIP_RULES)}
    if not s["V1"] or s["reference_problems"]:
        s["verdict"] = "VOID"
        return s
    s["worst_out_err_v"] = max((c["out_err_v"] for c in valid), default=None)
    if not scored:
        s["verdict"] = "LISTED ONLY"   # every state below the floor cut: ratios listed, nothing scored
        return s
    rn, rp = s["rN"], s["rP"]
    s["ratio_min"], s["ratio_max"] = min(c["ratio"] for c in scored), max(c["ratio"] for c in scored)
    if 1 - TOL <= s["ratio_min"] and s["ratio_max"] <= 1 + TOL:
        s["verdict"] = "EXACT"
    elif None not in (rn, rp) and min(rn, rp) - TOL <= s["ratio_min"] and s["ratio_max"] <= max(rn, rp) + TOL:
        s["verdict"] = "DEVICE OFFSET"
    else:
        s["verdict"] = "FAIL"
    return s


def main(runs):
    missing = [lib for lib in LIBS if not (pathlib.Path(runs) / lib / "result.json").exists()]
    extra = [p.parent.name for p in pathlib.Path(runs).glob("*/result.json") if p.parent.name not in LIBS]
    libs = {lib: score(json.load(open(pathlib.Path(runs) / lib / "result.json"))) for lib in LIBS
            if lib not in missing}
    same_dropped = len({tuple(s["dropped"]) for s in libs.values()}) == 1
    valid = (not missing and not extra and same_dropped
             and all(s["V1"] and s["V2"] and s["V4"] and not s["unregistered_skips"] and s["verdict"] != "VOID"
                     for s in libs.values()))
    passed = valid and all(s["verdict"] != "FAIL" for s in libs.values())
    # c3: does an offset depend on temperature? rN, rP at -40 C against 125 C, per Vt and corner
    temp_shift = {}
    for vt in ("svt", "lvt", "ulvt"):
        for corner in ("SSG", "FFG"):
            lo, hi = libs.get(f"GT_A5_{vt}_{corner}_m40C"), libs.get(f"GT_A5_{vt}_{corner}_125C")
            if (lo and hi and "VOID" not in (lo["verdict"], hi["verdict"])
                    and None not in (lo["rN"], hi["rN"], lo["rP"], hi["rP"])):
                temp_shift[f"{vt}_{corner}"] = {k: abs(hi[k] - lo[k]) / min(hi[k], lo[k]) for k in ("rN", "rP")}
    listed_only = [k for k, s in libs.items() if s["verdict"] == "LISTED ONLY"]
    out = {"libraries": libs, "missing": missing, "extra": extra, "V3_same_dropped": same_dropped, "valid": valid,
           "c2": "PASS" if passed else ("FAIL" if valid else "VOID"), "listed_only": listed_only,
           "offset_change_m40_to_125C": temp_shift,
           "c3_offset_depends_on_T": {k: v for k, v in temp_shift.items() if max(v.values()) > TOL}}
    json.dump(out, open(f"{runs}/summary.json", "w"), indent=1)
    print("| Library | Cells compared | Cases | Scored | Listed (below floor cut) | rN | rP | Ratio range (scored) "
          "| Worst output error | Retried | Floor check (states: range) | Verdict |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    def f(x):
        return "-" if x is None else f"{x:.4f}"
    for k, s in libs.items():
        rng = f"{f(s.get('ratio_min'))}-{f(s.get('ratio_max'))}"
        err = "-" if s.get("worst_out_err_v") is None else f"{s['worst_out_err_v']:.2g} V"
        fc = s["floor_check"]
        print(f"| {k} | {s['cells_compared']} | {s['cases']} | {s['cases_scored']} | {len(s['below_floor'])} "
              f"| {f(s['rN'])} | {f(s['rP'])} | {rng} | {err} | {len(s['retried'])} "
              f"| {fc['states']}: {f(fc['min'])}-{f(fc['max'])} | {s['verdict']} |")
    print(f"missing {missing}; extra {extra}; V3 {same_dropped}; valid {valid}; C2 {out['c2']}"
          + (f"; LISTED ONLY (nothing scored): {', '.join(listed_only)}" if listed_only else ""))
    print("offset change -40 -> 125 C:", {k: {a: f"{b:.2%}" for a, b in v.items()} for k, v in temp_shift.items()})


if __name__ == "__main__":
    main(sys.argv[1])
