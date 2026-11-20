"""Per-state leakage of MATRIX-A5 cells from SPICE (the kit's BSIM-CMG card in ngspice, Berkeley BSIM-CMG 111.2.1 as
OSDI) against the kit's own Liberty, at that Liberty's temperature and voltage.

  python leak.py deck <card .inc> <bsimcmg_parameters.include> <svt cdl dir> <liberty .lib> <osdi path in container>
                      <out dir> all|<cell> ...
  python leak.py compare <out dir>       (reads <out>/cases.json and each s<i>.log and s<i>.rc, writes
                                         <out>/result.json)

One deck per state (<out>/s<i>.cir for case i, sharing <out>/models.inc; Amendment 2): ngspice's gmin and source
stepping and its transient-op fallback act on the whole matrix, so one state that does not converge took a whole
library down in run 1 and moved its cell's other states to a transient op in run 2 (diag/FINDINGS.md, finding 2).

Combinational cells only: a cell is skipped, with its reason listed, if its Liberty has an ff or latch group, it has
no svt CDL or no input, or a leakage state cannot be set from its input ports. Other Vt flavours reuse the svt
netlist with the model and cell names swapped (V2 and the Liberty comparison test that).
"""
import json
import math
import os
import re
import sys

ASSIGN = re.compile(r"\b([A-Za-z]\w*)\s*=\s*\S+")
UNITS = {"1uW": 1e-6, "1nW": 1e-9, "1pW": 1e-12}
# BSIM-CMG adds V(e, di) * gmin to the junction current when BULKMOD != 0 (bsimcmg_body.include:2823): the PMOS cards
# have bulkmod = 1, so ngspice's default gmin (1e-12 S) adds 0.7 pA to every off PMOS (dry c1: +12%). The smallest
# states are ~1e-15 A, so gmin and abstol go to 1e-18; tighter settings did not converge.
# Amendment 2 raised the iteration limits (diag finding 1); Amendment 3 removes gminsteps and srcsteps again, since
# together they make Newton states fail (diag/a3_probe.py: without both, every state above the floor cut converges).
OPTIONS = ".option gmin=1e-18 abstol=1e-18 reltol=1e-5 itl1=50000"
DC_METHODS = ("newton", "gmin stepping", "source stepping")


def method(log, rc):
    """How ngspice reached its operating point: one of DC_METHODS, 'transient op' (exits 0 but is not a DC point),
    or 'failed'. Later fallbacks win: a log that tried gmin stepping and then the transient op is 'transient op'.
    The one classifier of ngspice logs (code lint L52); diag/c2diag.py imports it."""
    t = log.lower()
    if rc != "0":
        return "failed"
    if "transient op finished successfully" in t:
        return "transient op"
    if "source stepping completed" in t:
        return "source stepping"
    if "gmin stepping completed" in t:
        return "gmin stepping"
    return "newton"
# the skip reasons registration.md allows; any other skip (an unreadable cell) voids the run in evaluate.py
SKIP_RULES = ("sequential", "no VDD leakage state", "no svt CDL", "no input or supply", "state not settable")


def declared(params_include):
    """Parameter names the model code declares (`MP*, `BP*, `IP* macros), lower case."""
    return {n.lower() for n in re.findall(r"^`[MBI]P\w*\(\s*(\w+)", open(params_include).read(), re.M)}


def card(text, names):
    """The card for 111.2.1's module: devtype becomes TYPE (1 NMOS, -1 PMOS); every name the code does not declare is
    dropped (an OSDI model may ignore an unknown name silently). Returns the netlist text and the dropped names."""
    out, dropped = [], set()

    def keep(m):
        if m[1].lower() in names:
            return m[0]
        dropped.add(m[1].lower())
        return ""
    for line in map(str.strip, text.splitlines()):
        if not line or line.startswith("*"):
            continue
        m = re.match(r"\.model\s+(\S+)\s+([np])mos\s+level\s*=\s*72\s*$", line, re.I)
        if m:
            out.append(f".model {m[1]} bsimcmg_va type={1 if m[2].lower() == 'n' else -1}")
        elif line.startswith("+") and out:
            out.append(ASSIGN.sub(keep, line))
        else:
            raise ValueError(f"card line not understood: {line}")
    return "\n".join(out) + "\n", dropped


def read_cdl(path, vt):
    """One-cell CDL with continuation lines joined: (netlist for ngspice, ports, input pins). M devices become OSDI N
    instances (d g s e t), t grounded (exact while the cards' shmod = 0); svt names become vt names."""
    lines = []
    for l in open(path).read().splitlines():
        if l.startswith("+") and lines:
            lines[-1] += " " + l[1:]
        else:
            lines.append(l)
    ports = next(l for l in lines if l.lower().startswith(".subckt")).split()[2:]
    info = next((l for l in lines if l.startswith("*.PININFO")), "")
    inputs = [p.split(":")[0] for p in info.split()[1:] if p.endswith(":I")]
    out = [re.sub(r"^M(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", r"N\1 \2 \3 \4 \5 0", l, flags=re.I) for l in lines]
    if any(re.match(r"m", l, re.I) for l in out):
        raise ValueError(f"{path}: an M line was not converted")
    return "\n".join(out).replace("_svt", f"_{vt}") + "\n", ports, inputs


def liberty(lib_text):
    """{cell: (VDD leakage states [(when, W)], sequential?)}, plus the library's temperature, voltage and Vt."""
    unit = UNITS[re.search(r'leakage_power_unit\s*:\s*"(\S+)"', lib_text)[1]]
    temp = float(re.search(r"nom_temperature\s*:\s*(\S+);", lib_text)[1])
    vdd = float(re.search(r"nom_voltage\s*:\s*(\S+);", lib_text)[1])
    starts = [(m.start(), m[1]) for m in re.finditer(r"\n  cell \((\S+)\)", lib_text)]
    cells = {}
    for (s, name), (e, _) in zip(starts, starts[1:] + [(len(lib_text), "")]):
        seg = lib_text[s:e]
        states = []
        for block in re.findall(r"leakage_power \(\) \{([^}]*)\}", seg):   # any field order
            f = {k: v.strip() for k, v in re.findall(r"(\w+)\s*:\s*\"?([^\";]+)\"?\s*;", block)}
            if f.get("related_pg_pin") == "VDD" and "when" in f:
                states.append((f["when"], float(f["value"]) * unit))
        cells[name] = (states, bool(re.search(r"\n\s*(ff|latch|ff_bank|latch_bank)\s*\(", seg)))
    vt = re.fullmatch(r"gtA5_cfet_11_\w+_x\d+_(\w+)", starts[0][1])[1]
    return cells, temp, vdd, vt


def products(when):
    """'(A * !B) + (!A * B)' -> [{'A': 1, 'B': 0}, {'A': 0, 'B': 1}]; anything else is an error."""
    out = []
    for term in when.split("+"):
        lit = {}
        for t in term.strip().strip("()").split("*"):
            m = re.fullmatch(r"(!?)(\w+)", t.strip())
            if not m:
                raise ValueError(f"unsupported when: {when}")
            lit[m[2]] = 0 if m[1] else 1
        out.append(lit)
    return out


def cell_cases(name, states, sequential, cdl_path, vt):
    """(netlist, ports, inputs, [(when, W, literals)]), or a skip reason."""
    if sequential:
        return "sequential (ff or latch group)"
    if not states:
        return "no VDD leakage state"
    if not os.path.exists(cdl_path):
        return "no svt CDL"
    try:   # anything else that fails here is not a registered skip, so evaluate.py voids the run on it
        netlist, ports, inputs = read_cdl(cdl_path, vt)
        terms = [(when, ref, lit) for when, ref in states for lit in products(when)]
    except (ValueError, StopIteration) as e:
        return f"unreadable: {type(e).__name__}: {e}"
    if not inputs or not {"VDD", "VSS"} <= set(ports):
        return f"no input or supply: ports {ports}, inputs {inputs}"
    bad = [when for when, _, lit in terms if set(inputs) - set(lit) or set(lit) - set(ports)]
    if bad:
        return f"state not settable from the ports: {bad[0]}"
    return netlist, ports, inputs, terms


def deck(card_path, params_include, cdl_dir, lib, osdi, out, *names):
    cells, temp, vdd, vt = liberty(open(lib).read())
    models, dropped = card(open(card_path).read(), declared(params_include))
    names = sorted(cells) if names == ("all",) else list(names)
    cases, skipped = [], {}
    open(f"{out}/.spiceinit", "w").write(f"osdi {osdi}\n")   # OSDI must load before the netlist is parsed
    open(f"{out}/models.inc", "w").write(models)
    for name in names:
        got = cell_cases(name, *cells[name], f"{cdl_dir}/{name.replace(f'_{vt}', '_svt')}.cdl", vt)
        if isinstance(got, str):
            skipped[name] = got
            continue
        netlist, ports, inputs, terms = got
        for when, ref, lit in terms:
            i = len(cases)
            lines, nodes = [], []
            for p in ports:
                if p == "VDD":
                    nodes.append(f"vdd{i}")
                elif p == "VSS":
                    nodes.append("0")
                elif p in inputs:
                    nodes.append(f"i{i}_{p}")
                    lines.append(f"v{i}_{p} i{i}_{p} 0 {vdd * lit[p]}")
                else:
                    nodes.append(f"o{i}_{p}")
            lines += [f"vdd{i} vdd{i} 0 {vdd}", f"x{i} {' '.join(nodes)} {name}"]
            outs = {p: v for p, v in lit.items() if p not in inputs}
            cases.append({"cell": name, "when": when, "lit": lit, "outs": outs, "liberty_w": ref})
            prt = f"print i(vdd{i})" + "".join(f" v(o{i}_{p})" for p in outs)
            open(f"{out}/s{i:04d}.cir", "w").write("\n".join(
                [f"* leakage of one state, {name} {when}, {lib}", f".temp {temp}", OPTIONS, ".include models.inc",
                 netlist] + lines + [".control", "op", prt, ".endc", ".end"]) + "\n")
    json.dump({"temp": temp, "vdd": vdd, "vt": vt, "dropped": sorted(dropped), "skipped": skipped, "cases": cases},
              open(f"{out}/cases.json", "w"), indent=1)
    print(f"{len(cases)} cases from {len({c['cell'] for c in cases})} cells; skipped {skipped}")


def compare(out):
    """SPICE power per case. A case is invalid (V1) if its deck's ngspice did not exit 0 (`<out>/s<i>.rc`, missing
    counts as failed), did not reach a DC point (`method`: the transient op exits 0 but is not one; Amendment 2), its
    current or an output voltage is missing or not finite, or its supply does not source current. A state with several
    product terms is scored as the mean of its terms against the Liberty's one value."""
    meta = json.load(open(f"{out}/cases.json"))
    read = lambda f, none: open(f, encoding="utf-8", errors="replace").read() if os.path.exists(f) else none
    vdd = meta["vdd"]
    for i, c in enumerate(meta["cases"]):
        log, rc = read(f"{out}/s{i:04d}.log", ""), read(f"{out}/s{i:04d}.rc", "missing").strip()
        vals = {k.lower(): float(v) for k, v in re.findall(r"^\s*([iv]\([\w.]+\))\s*=\s*(\S+)", log, re.M)}
        c["method"] = method(log, rc)
        cur = vals.get(f"i(vdd{i})")
        volts = [vals.get(f"v(o{i}_{p.lower()})") for p in c["outs"]]
        c["invalid"] = (f"ngspice exit code {rc}" if rc != "0" else
                        f"no DC point ({c['method']})" if c["method"] not in DC_METHODS else
                        "no current" if cur is None or None in volts else
                        "not finite" if not all(map(math.isfinite, [cur] + volts)) else
                        "supply sinks current" if cur >= 0 else None)
        ok = c["invalid"] is None
        c["spice_w"] = -cur * vdd if ok else None
        c["out_err_v"] = max((abs(v - vdd * b) for v, b in zip(volts, c["outs"].values())), default=0.0) if ok else None
    groups = {}
    for c in meta["cases"]:
        groups.setdefault((c["cell"], c["when"]), []).append(c)
    for g in groups.values():
        ws = [c["spice_w"] for c in g]
        mean = sum(ws) / len(ws) if None not in ws else None
        for c in g:
            c["ratio"] = mean / c["liberty_w"] if mean is not None and c["liberty_w"] > 0 else None
    json.dump(meta, open(f"{out}/result.json", "w"), indent=1)
    bad = sum(c["invalid"] is not None for c in meta["cases"])
    print(f"{out}: {len(meta['cases'])} cases, {bad} invalid")

if __name__ == "__main__":
    {"deck": deck, "compare": compare}[sys.argv[1]](*sys.argv[2:])
