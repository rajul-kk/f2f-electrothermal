"""C2 scoring (registration.md): validity V1-V4, per library EXACT / DEVICE OFFSET / FAIL, and the temperature check
for c3; writes <runs>/summary.json and prints a table. Usage: python evaluate.py <runs dir>"""
import json
import pathlib
import sys

from leak import SKIP_RULES

TOL = 0.02
MIN_CELLS = 50
LIBS = [f"GT_A5_{vt}_{pt}" for vt in ("svt", "lvt", "ulvt")
        for pt in ("TTG_25C", "SSG_m40C", "SSG_125C", "FFG_m40C", "FFG_125C")]


def ref(cases, when):
    found = [c["ratio"] for c in cases if c["cell"].startswith("gtA5_cfet_11_inv_x1_") and c["when"] == when]
    return found[0] if len(found) == 1 else None


def score(r):
    cases = r["cases"]
    scored = [c for c in cases if c["ratio"] is not None]
    s = {"temp": r["temp"], "vt": r["vt"], "cases": len(cases), "dropped": r["dropped"], "skipped": r["skipped"],
         "invalid": [f'{c["cell"]} {c["when"]}: {c["invalid"]}' for c in cases if c["invalid"]],
         "not_scored": [f'{c["cell"]} {c["when"]}: Liberty {c["liberty_w"]}' for c in cases
                        if c["invalid"] is None and c["liberty_w"] <= 0],
         "cells_compared": len({c["cell"] for c in scored}), "rN": ref(cases, "(!A * Y)"), "rP": ref(cases, "(A * !Y)")}
    s["V1"] = not s["invalid"]
    s["V2"] = s["V1"] and all(c["out_err_v"] <= 0.1 * r["vdd"] for c in cases)
    s["V4"] = s["cells_compared"] >= MIN_CELLS
    s["unregistered_skips"] = {k: v for k, v in r["skipped"].items() if not v.startswith(SKIP_RULES)}
    if not (s["V1"] and scored and s["rN"] is not None and s["rP"] is not None):
        s["verdict"] = "VOID"
        return s
    rn, rp = s["rN"], s["rP"]
    s["ratio_min"], s["ratio_max"] = min(c["ratio"] for c in scored), max(c["ratio"] for c in scored)
    s["worst_out_err_v"] = max(c["out_err_v"] for c in cases)
    if 1 - TOL <= s["ratio_min"] and s["ratio_max"] <= 1 + TOL:
        s["verdict"] = "EXACT"
    elif min(rn, rp) - TOL <= s["ratio_min"] and s["ratio_max"] <= max(rn, rp) + TOL:
        s["verdict"] = "DEVICE OFFSET"
    else:
        s["verdict"] = "FAIL"
    return s


def main(runs):
    missing = [l for l in LIBS if not (pathlib.Path(runs) / l / "result.json").exists()]
    extra = [p.parent.name for p in pathlib.Path(runs).glob("*/result.json") if p.parent.name not in LIBS]
    libs = {l: score(json.load(open(pathlib.Path(runs) / l / "result.json"))) for l in LIBS if l not in missing}
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
            if lo and hi and None not in (lo["rN"], hi["rN"], lo["rP"], hi["rP"]):
                temp_shift[f"{vt}_{corner}"] = {k: abs(hi[k] - lo[k]) / min(hi[k], lo[k]) for k in ("rN", "rP")}
    out = {"libraries": libs, "missing": missing, "extra": extra, "V3_same_dropped": same_dropped, "valid": valid,
           "c2": "PASS" if passed else ("FAIL" if valid else "VOID"), "offset_change_m40_to_125C": temp_shift,
           "c3_offset_depends_on_T": {k: v for k, v in temp_shift.items() if max(v.values()) > TOL}}
    json.dump(out, open(f"{runs}/summary.json", "w"), indent=1)
    print("| Library | Cells compared | Cases | rN | rP | Ratio range | Worst output error | Verdict |")
    print("|---|---|---|---|---|---|---|---|")
    f = lambda x: "-" if x is None else f"{x:.4f}"
    for k, s in libs.items():
        rng = f"{f(s.get('ratio_min'))}-{f(s.get('ratio_max'))}"
        err = "-" if s.get("worst_out_err_v") is None else f"{s['worst_out_err_v']:.2g} V"
        print(f"| {k} | {s['cells_compared']} | {s['cases']} | {f(s['rN'])} | {f(s['rP'])} | {rng} | {err} | {s['verdict']} |")
    print(f"missing {missing}; extra {extra}; V3 {same_dropped}; valid {valid}; C2 {out['c2']}")
    print("offset change -40 -> 125 C:", {k: {a: f"{b:.2%}" for a, b in v.items()} for k, v in temp_shift.items()})


if __name__ == "__main__":
    main(sys.argv[1])
