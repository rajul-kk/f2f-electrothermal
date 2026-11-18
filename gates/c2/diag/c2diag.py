"""c2-diag: decks, variants and reports for the diagnosis of C2 runs 1-2 (FINDINGS.md). Exploratory, not a gate.

Every deck is built from run 2's own files (`../runs/<lib>/`: models.inc, .spiceinit, the cell's subcircuit, option
and stimulus lines), so a variant differs from run 2 only in what its name says. ngspice runs through `run_decks.sh`.
`states` and `f2` read run 1-2's one-deck-per-cell layout (<cell>.cir/.log/.rc), not run 3's s<i> decks.
`ratio` repeats leak.compare's value checks for single decks; it is diagnosis-only and not used by the gate.

  python c2diag.py states  <lib dir> <out dir> [--cells C ...]   one deck per state (default: cells whose run 2 deck
                                                                 did not exit 0 or used the transient op)
  python c2diag.py variant <state dir> <out dir> --name N --set "opt=v ..." [--select hard|newton] [--limit K]
  python c2diag.py nodeset <state dir> <out dir> pass1|pass2      hard states: 25 C solution as .nodeset at -40 C
  python c2diag.py f2      <lib dir> <cell> <when> <out dir>     one state alone under five solver variants
  python c2diag.py summary <dir> [--prefix P]                    convergence method per deck -> <dir>/summary.json
  python c2diag.py ratios  <dir> <lib dir> [--prefix P]          SPICE / Liberty of single-term states reaching DC
  python c2diag.py floor   <runs dir>                            inv_x1 off-PMOS: Liberty minus SPICE per library
"""
import argparse
import collections
import glob
import json
import math
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leak import DC_METHODS, method  # noqa: E402,F401  (the gate's one log classifier, code lint L52)

CURRENT = re.compile(r"^\s*i\((vdd\d+)\)\s*=\s*(\S+)", re.M | re.I)
VOLT = re.compile(r"^\s*v\(([\w.]+)\)\s*=\s*(\S+)", re.M | re.I)
REG_OPTION = re.compile(r"^\.option .*$", re.M)
OUT_TOL = 0.10           # V2: an output within 10% of VDD of its literal


# ---------- reading ngspice logs ----------

def values(log):
    """{name: float} of every printed current and voltage, names lower case (ngspice prints them lower case)."""
    out = {f"i({k.lower()})": float(v) for k, v in CURRENT.findall(log)}
    out.update({f"v({k.lower()})": float(v) for k, v in VOLT.findall(log)})
    return out


def text_of(path, missing=None):
    """A file's text (undecodable bytes replaced: ngspice logs), or `missing` when it does not exist."""
    p = Path(path)
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else missing


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read(path_no_ext):
    """(log text, exit code) of one deck; a missing log is empty and a missing exit code is 'missing'."""
    return text_of(path_no_ext + ".log", ""), text_of(path_no_ext + ".rc", "missing").strip()


# ---------- reading run 2's decks ----------

def subckt(deck_text):
    return re.search(r"\.subckt .*?\.ends \S+\n", deck_text, re.S)[0]


def internal_nodes(sub):
    """Nets of the subcircuit that are not its ports (device terminals d g s e; the thermal node is ground)."""
    head, *body = sub.splitlines()
    ports = set(head.split()[2:])
    nets = {n for line in body if line.startswith("N") for n in line.split()[1:5]}
    return sorted(nets - ports - {"0"})


def stimulus(deck_text, i):
    return [line for line in deck_text.splitlines() if re.match(rf"(v{i}_\w+ |vdd{i} |x{i} )", line)]


def copy_shared(src, out):
    os.makedirs(out, exist_ok=True)
    for f in ("models.inc", ".spiceinit"):
        shutil.copyfile(os.path.join(src, f), os.path.join(out, f))


def write_atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


# ---------- commands ----------

def states(lib, out, cells=None):
    meta = load_json(f"{lib}/cases.json")
    if not cells:
        cells = sorted(c for c in {x["cell"] for x in meta["cases"]} if method(*read(f"{lib}/{c}")) not in DC_METHODS)
    copy_shared(lib, out)
    n = 0
    for cell in cells:
        text = text_of(f"{lib}/{cell}.cir")
        head = text.splitlines()[1:4]                     # .temp, .option, .include models.inc
        for i, c in enumerate(meta["cases"]):
            if c["cell"] != cell:
                continue
            prt = f"print i(vdd{i})" + "".join(f" v(o{i}_{p})" for p in c["outs"])
            write_atomic(f"{out}/s{i:04d}.cir", "\n".join(
                [f"* c2-diag state {i} {cell} {c['when']}"] + head + [subckt(text).rstrip()] + stimulus(text, i)
                + [".control", "op", prt, ".endc", ".end"]) + "\n")
            n += 1
    write_atomic(f"{out}/meta.json", json.dumps({"lib": os.path.abspath(lib), "cells": cells}, indent=1))
    print(f"{n} state decks from {len(cells)} cells")


def _select(state_dir, which, limit):
    rows = load_json(f"{state_dir}/summary.json")
    keep = {"hard": lambda m: m not in DC_METHODS, "newton": lambda m: m == "newton"}[which]
    picked = sorted(s for s, r in rows.items() if keep(r["method"]))
    return picked[:limit] if limit else picked


def variant(state_dir, out, name, settings, select, limit):
    """Copies of the selected state decks with `settings` (opt=value ...) replacing or extending the option line."""
    copy_shared(state_dir, out)
    new = dict(kv.split("=", 1) for kv in settings.split())
    picked = _select(state_dir, select, limit)
    for s in picked:
        text = text_of(f"{state_dir}/{s}.cir")
        line = REG_OPTION.search(text)[0]
        opts = dict(kv.split("=", 1) for kv in line.split()[1:])
        opts.update(new)
        new_line = ".option " + " ".join(f"{k}={v}" for k, v in opts.items())
        write_atomic(f"{out}/{name}_{s}.cir", text.replace(line, new_line, 1))
    print(f"{len(picked)} decks ({select}) with {settings}")


def nodeset(state_dir, out, step):
    copy_shared(state_dir, out)
    hard = _select(state_dir, "hard", 0)
    for s in hard:
        text = text_of(f"{state_dir}/{s}.cir")
        i = re.search(r"^x(\d+) ", text, re.M)[1]
        nodes = [f"x{i}.{n}" for n in internal_nodes(subckt(text))]
        if step == "pass1":
            text = re.sub(r"^\.temp \S+", ".temp 25", text, count=1, flags=re.M)
            extra = "".join(f" v({n})" for n in nodes)
            text = re.sub(r"^(print .*)$", lambda m, extra=extra: m[1] + extra, text, count=1, flags=re.M)
            write_atomic(f"{out}/p1_{s}.cir", text)
            continue
        got = values(read(f"{out}/p1_{s}")[0])
        if not nodes or any(f"v({n.lower()})" not in got for n in nodes):
            continue                                     # no full 25 C solution: counted as missing by the caller
        line = ".nodeset " + " ".join(f"v({n})={got[f'v({n.lower()})']}" for n in nodes)
        write_atomic(f"{out}/p2_{s}.cir", text.replace("\n.control", f"\n{line}\n.control", 1))
    print(f"{len(hard)} hard states, {step}")


def f2(lib, cell, when, out):
    """One state alone: run 2's own option line, then four variants of it."""
    meta = load_json(f"{lib}/cases.json")
    i = next(k for k, c in enumerate(meta["cases"]) if c["cell"] == cell and c["when"] == when)
    text = text_of(f"{lib}/{cell}.cir")
    reg = REG_OPTION.search(text)[0]
    sub = subckt(text)
    nodes = [f"x{i}.{n}" for n in internal_nodes(sub)]
    vdd = meta["vdd"]
    variants = {"registered": (reg, []), "tight_reltol": (re.sub(r"reltol=\S+", "reltol=1e-9", reg), []),
                "gmin_1e-15": (re.sub(r"gmin=\S+", "gmin=1e-15", reg), []),
                "nodeset_low": (reg, [".nodeset " + " ".join(f"v({n})=0" for n in nodes)]),
                "nodeset_high": (reg, [".nodeset " + " ".join(f"v({n})={vdd}" for n in nodes)])}
    copy_shared(lib, out)
    prt = f"print i(vdd{i}) " + " ".join(f"v(o{i}_{p})" for p in meta["cases"][i]["outs"]) + " " + \
        " ".join(f"v({n})" for n in nodes)
    for name, (opt, extra) in variants.items():
        write_atomic(f"{out}/{name}.cir", "\n".join(
            [f"* c2-diag f2 {cell} {when} {name}", f".temp {meta['temp']}", opt, ".include models.inc", sub.rstrip()]
            + stimulus(text, i) + extra + [".control", "op", prt, ".endc", ".end"]) + "\n")
    print(f"{len(variants)} decks, internal nodes {nodes}")


def summary(d, prefix=""):
    rows = {}
    for f in sorted(glob.glob(f"{d}/{prefix}*.cir")):
        s = os.path.basename(f)[:-4]
        log, rc = read(f[:-4])
        rows[s] = {"rc": rc, "method": method(log, rc)}
    if not prefix:
        write_atomic(f"{d}/summary.json", json.dumps(rows, indent=1))
    for m, k in sorted(collections.Counter(r["method"] for r in rows.values()).items()):
        print(f"{m:16s} {k}")
    return rows


def ratio(log, case, i, vdd):
    """SPICE / Liberty of one state deck's log, or None with the leak.compare checks plus V2 (outputs at their
    literal): a missing or non-finite value, or a supply that sinks current, gives None."""
    v = values(log)
    cur = v.get(f"i(vdd{i})")
    outs = [v.get(f"v(o{i}_{p.lower()})") for p in case["outs"]]
    if cur is None or None in outs or not all(map(math.isfinite, [cur] + outs)) or cur >= 0:
        return None
    if any(abs(o - vdd * b) > OUT_TOL * vdd for o, b in zip(outs, case["outs"].values(), strict=True)):
        return None
    return -cur * vdd / case["liberty_w"]


def ratios(d, lib, prefix=""):
    meta = load_json(f"{lib}/cases.json")
    nterms = collections.Counter((c["cell"], c["when"]) for c in meta["cases"])
    by, rejected = collections.defaultdict(list), 0
    for f in sorted(glob.glob(f"{d}/{prefix}*.cir")):
        log, rc = read(f[:-4])
        m = method(log, rc)
        i = int(re.search(r"s(\d+)\.cir$", f)[1])
        c = meta["cases"][i]
        if m not in DC_METHODS or nterms[(c["cell"], c["when"])] != 1 or c["liberty_w"] <= 0:
            continue
        r = ratio(log, c, i, meta["vdd"])
        if r is None:
            rejected += 1
            continue
        by[m].append((r, c["cell"]))
    for m, v in sorted(by.items()):
        v.sort()
        print(f"{m:16s} {len(v):4d}  min {v[0][0]:.4f}  median {v[len(v) // 2][0]:.4f}  max {v[-1][0]:.4f}")
    print(f"rejected by the value checks: {rejected}")
    out = collections.Counter(cell for v in by.values() for r, cell in v if not 0.98 <= r <= 1.02)
    print("cells with a ratio outside [0.98, 1.02]:", dict(out.most_common()))
    return by


def floor(runs):
    print(f"{'library':22s} {'Liberty W':>11s} {'SPICE W':>11s} {'missing A':>11s}")
    for f in sorted(glob.glob(os.path.join(runs, "GT_A5_*", "result.json"))):
        r = load_json(f)
        for c in r["cases"]:
            if c["cell"].startswith("gtA5_cfet_11_inv_x1_") and c["when"] == "(A * !Y)" and c["spice_w"] is not None:
                print(f"{os.path.basename(os.path.dirname(f)):22s} {c['liberty_w']:11.3e} {c['spice_w']:11.3e} "
                      f"{(c['liberty_w'] - c['spice_w']) / r['vdd']:11.3e}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("states")
    p.add_argument("lib")
    p.add_argument("out")
    p.add_argument("--cells", nargs="*")
    p = sp.add_parser("variant")
    p.add_argument("state_dir")
    p.add_argument("out")
    p.add_argument("--name", required=True)
    p.add_argument("--set", required=True)
    p.add_argument("--select", choices=["hard", "newton"], default="hard")
    p.add_argument("--limit", type=int, default=0)
    p = sp.add_parser("nodeset")
    p.add_argument("state_dir")
    p.add_argument("out")
    p.add_argument("step", choices=["pass1", "pass2"])
    p = sp.add_parser("f2")
    p.add_argument("lib")
    p.add_argument("cell")
    p.add_argument("when")
    p.add_argument("out")
    p = sp.add_parser("summary")
    p.add_argument("dir")
    p.add_argument("--prefix", default="")
    p = sp.add_parser("ratios")
    p.add_argument("dir")
    p.add_argument("lib")
    p.add_argument("--prefix", default="")
    p = sp.add_parser("floor")
    p.add_argument("runs")
    a = ap.parse_args()
    {"states": lambda: states(a.lib, a.out, a.cells),
     "variant": lambda: variant(a.state_dir, a.out, a.name, a.set, a.select, a.limit),
     "nodeset": lambda: nodeset(a.state_dir, a.out, a.step),
     "f2": lambda: f2(a.lib, a.cell, a.when, a.out),
     "summary": lambda: summary(a.dir, a.prefix),
     "ratios": lambda: ratios(a.dir, a.lib, a.prefix),
     "floor": lambda: floor(a.runs)}[a.cmd]()


if __name__ == "__main__":
    main()
