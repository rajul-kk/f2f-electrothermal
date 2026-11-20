"""Amendment 3 probe (after run 3; exploratory): run 3's option line sets gminsteps=200 and srcsteps=200 together, and
with both set some states that run 2 solved now fail (Newton to NaN, then spice3 gmin and source stepping fail).
This rebuilds run 3's own decks with one or both of those two options removed and reports, per variant, how many of
run 3's states without a DC point reach one, and whether states that did reach one keep their current.

  python a3_probe.py prepare <runs dir> <out dir> [--valid K]   decks: every run-3 state without a DC point, plus K
                                                                 that had one, per library, x VARIANTS
  bash run_decks.sh <out dir>/<lib>                              (per library; the registered image)
  python a3_probe.py report <runs dir> <out dir>                 -> <out dir>/report.json and a table
"""
import argparse
import collections
import glob
import json
import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from c2diag import copy_shared, load_json, read, text_of, values, write_atomic  # noqa: E402
from leak import DC_METHODS, method  # noqa: E402  (the gate's one log classifier, code lint L52)

DROP = {"nosrc": ("srcsteps",), "nogmin": ("gminsteps",), "neither": ("gminsteps", "srcsteps")}
OPTION = re.compile(r"^\.option .*$", re.M)


def state_ids(lib_dir):
    return sorted(int(re.search(r"s(\d+)\.cir$", f)[1]) for f in glob.glob(f"{lib_dir}/s*.cir"))


def run3_method(lib_dir, i):
    return method(*read(f"{lib_dir}/s{i:04d}"))


def current(log, i):
    v = values(log).get(f"i(vdd{i})")
    return v if v is not None and math.isfinite(v) else None


def prepare(runs, out, k_valid):
    total = 0
    for lib_dir in sorted(glob.glob(f"{runs}/GT_A5_*")):
        lib = os.path.basename(lib_dir)
        ids = state_ids(lib_dir)
        hard = [i for i in ids if run3_method(lib_dir, i) not in DC_METHODS]
        good = [i for i in ids if i not in set(hard)]
        step = max(1, len(good) // k_valid) if k_valid else len(good) + 1
        valid = good[::step][:k_valid]
        copy_shared(lib_dir, f"{out}/{lib}")
        for i in hard + valid:
            text = text_of(f"{lib_dir}/s{i:04d}.cir")
            line = OPTION.search(text)[0]
            for name, drop in DROP.items():
                kept = [kv for kv in line.split()[1:] if kv.split("=", 1)[0] not in drop]
                write_atomic(f"{out}/{lib}/{name}_s{i:04d}.cir", text.replace(line, ".option " + " ".join(kept), 1))
        write_atomic(f"{out}/{lib}/picked.json", json.dumps({"hard": hard, "valid": valid}))
        total += len(hard) + len(valid)
        print(f"{lib}: {len(hard)} without a DC point, {len(valid)} with")
    print(f"{total} states x {len(DROP)} variants")


def report(runs, out):
    rows = {}
    tot = collections.defaultdict(collections.Counter)
    worst = collections.defaultdict(float)
    for lib_dir in sorted(glob.glob(f"{out}/GT_A5_*")):
        lib = os.path.basename(lib_dir)
        picked = load_json(f"{lib_dir}/picked.json")
        r = {}
        for name in DROP:
            got = collections.Counter()
            rel = []
            for i in picked["hard"]:
                got[method(*read(f"{lib_dir}/{name}_s{i:04d}"))] += 1
            for i in picked["valid"]:
                log, rc = read(f"{lib_dir}/{name}_s{i:04d}")
                a, b = current(log, i), current(read(f"{runs}/{lib}/s{i:04d}")[0], i)
                ok = method(log, rc) in DC_METHODS and a is not None and b is not None
                rel.append(abs(a - b) / abs(b) if ok and b else math.inf)
            reached = sum(got[m] for m in DC_METHODS)
            r[name] = {"hard": len(picked["hard"]), "hard_reaching_dc": reached, "hard_methods": dict(got),
                       "valid": len(picked["valid"]), "valid_max_rel_change": max(rel) if rel else None}
            tot[name]["hard"] += len(picked["hard"])
            tot[name]["reached"] += reached
            if rel:
                worst[name] = max(worst[name], max(rel))
        rows[lib] = r
    rows["total"] = {n: {"hard": tot[n]["hard"], "hard_reaching_dc": tot[n]["reached"],
                         "valid_max_rel_change": worst[n]} for n in DROP}
    write_atomic(f"{out}/report.json", json.dumps(rows, indent=1))
    print(f"{'library':22s} " + " ".join(f"{n:>22s}" for n in DROP))
    for lib, r in rows.items():
        print(f"{lib:22s} " + " ".join(f"{r[n]['hard_reaching_dc']:>4d}/{r[n]['hard']:<4d} d={r[n]['valid_max_rel_change']:.1e}"
                                      .rjust(22) for n in DROP))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prepare")
    p.add_argument("runs")
    p.add_argument("out")
    p.add_argument("--valid", type=int, default=10)
    p = sp.add_parser("report")
    p.add_argument("runs")
    p.add_argument("out")
    a = ap.parse_args()
    if a.cmd == "prepare":
        prepare(a.runs, a.out, a.valid)
    else:
        report(a.runs, a.out)


if __name__ == "__main__":
    main()
