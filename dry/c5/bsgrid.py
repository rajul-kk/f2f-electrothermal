"""c5 dry: MATRIX-A5's backside power grid, generated from the kit's own files in c4's export format, so c4's builder
and solver (dry/c4/irbuild.py, irmesh.py) run on it unchanged.

  python bsgrid.py <kit base dir> <out dir> [--side 50] [--feed ring|area] [--bump-pitch 20] [--tsv-cuts N]
                   [--bpr-rho ict|itf] [--hotspot]

Every kit number is read from the kit (DESIGN.md, Inputs): the stripe and ring plan and the supply from
PDK_PATHS.tcl; widths, the DEFAULT via generate rules and the fixed DEFAULT vias from the tech LEF; which rail is
VDD from the cell LEF's power pins; resistances from the QRC ICT (the tech LEF has none) and, as a variant, BPR's
width-dependent resistivity from the StarRC ITF. Quirks the converter owns (A19): the LEF names the backside vias
BSV1/BSV2, the ICT VBSM1/VBSM2, so each cut layer is matched to the ICT via joining the same two layers; the ICT
quotes a via's ohms for its own cut area, so R per cut is scaled to the LEF cut's area (VBSV2_0 cuts 0.5 um, the
ICT's VBSM2 0.4 um); non-DEFAULT generate rules (ViaBSV1Array, ViaBSV2Array) are skipped; the TSV rule's pitch
equals its cut size (0.02 um), so its cuts abut. All lengths in DBU (1 nm).

Layout, for a square core [0, side]:
- BPR rails (the cells' power pins) at every row boundary, row height = the site height; VDD on the boundaries where an
  unflipped row's cells have their VDD pin (MATRIX-A5: the top, so odd boundaries), rows alternately flipped;
- BSM1 vertical VDD/VSS stripe pairs (PG_STRIPE_VERT_*), BSM2 horizontal pairs (PG_STRIPE_HORZ_*), each running to its
  own net's ring; rings outside the core (PG_RING_*), VDD inner, horizontal sides on PG_H, vertical on PG_V;
- a via wherever two adjacent backside layers of one net overlap: the usable via with the lowest resistance that
  fits (--tsv-cuts caps the TSV array, a variant);
- one load cell per CELL_SITES sites in every row, a VDD pin on its VDD rail and a VSS pin on its VSS rail, drawing
  J x cell area (J = 1 A/mm^2; --hotspot: 10x in a 10 um square at the core centre). The mesh is linear: drop scales
  with J;
- sources: every ring side of the net on both ring layers (--feed ring), or a bump array at --bump-pitch centred in
  the core, each bump holding the BSM1 x BSM2 stripe crossing nearest it (--feed area; BSM3 above the bumps is taken
  as ideal: the kit has no bump plan).
"""
import argparse
import csv
import json
import math
import os
import re
import sys

DBU = 1000
J_A_PER_UM2 = 1e-6                     # 1 A/mm^2
CELL_SITES = 10                        # one load cell per 10 sites (0.39 um on MATRIX-A5)
HOTSPOT_UM, HOTSPOT_X = 10.0, 10.0
BACKSIDE = ("BPR", "BSM1", "BSM2", "BSM3")
TCL_NUMBERS = ("CFET_OP_VOLTAGE", "CFET_SITE_X", "CFET_SITE_Y", "PG_RING_WIDTH", "PG_RING_SPACING", "PG_RING_OFFSET",
               "PG_STRIPE_VERT_WIDTH", "PG_STRIPE_VERT_SPACING", "PG_STRIPE_VERT_SET_TO_SET",
               "PG_STRIPE_VERT_START_OFFSET", "PG_STRIPE_HORZ_WIDTH", "PG_STRIPE_HORZ_SPACING",
               "PG_STRIPE_HORZ_SET_TO_SET", "PG_STRIPE_HORZ_START_OFFSET")
TCL_NAMES = ("PG_H", "PG_V", "PG_STRIPE_VERT", "CORE_PIN_LAYER")


def read_fixed_vias(path, cut_layers):
    """[{"rule", "fixed": True, "layers": (a, b), "pads": {metal: (x0, y0, x1, y1) um}, "cut_layer", "cut": side um}]
    for every `VIA <name> DEFAULT` with one cut layer and two metal layers (LEF: the vias a router may drop without a
    non-default rule). A via whose cut layer has more than one shape, a POLYGON, or a non-square cut, or whose metal
    has more than one shape, gets cut=None (kit() refuses it only if it is backside)."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    out = []
    for name, body in re.findall(r"^VIA\s+(\S+)\s+DEFAULT\s*\n(.*?)^END\s+\1", text, re.M | re.S):
        blocks = re.findall(r"LAYER\s+(\S+)\s*;(.*?)(?=LAYER|\Z)", body, re.S)
        cuts = [(lay, blk) for lay, blk in blocks if lay in cut_layers]
        metals = [(lay, blk) for lay, blk in blocks if lay not in cut_layers]
        if len(cuts) != 1 or len(metals) != 2:
            continue

        def one_rect(blk):
            rects = re.findall(r"RECT\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", blk)
            return tuple(float(v) for v in rects[0]) if len(rects) == 1 and "POLYGON" not in blk else None

        lay, blk = cuts[0]
        c = one_rect(blk)
        pads = {m: one_rect(b) for m, b in metals}
        ok = c is not None and abs((c[2] - c[0]) - (c[3] - c[1])) <= 1e-9 and None not in pads.values()
        out.append({"rule": name, "fixed": True, "layers": tuple(sorted(pads)), "pads": pads, "cut_layer": lay,
                    "cut": c[2] - c[0] if ok else None})
    return out


def read_viarules(path):
    """{cut layer: [{"rule", "default", "metals": {layer: (enc1, enc2)}, "cut": side um, "pitch": (x, y) um}]} for
    every VIARULE ... GENERATE in a tech LEF (a cut layer may have several). LEF: a generate rule's SPACING is centre
    to centre; ENCLOSURE a b is the overhang on one pair of opposite sides and the other, in either orientation; a
    rule without DEFAULT is used only through a non-default rule."""
    out = {}
    with open(path, encoding="utf-8") as f:
        text = f.read()
    for name, flags, body in re.findall(r"^VIARULE\s+(\S+)\s+GENERATE([^\n]*)\n(.*?)^END\s+\1", text, re.M | re.S):
        metals, cut = {}, None
        for lay, block in re.findall(r"LAYER\s+(\S+)\s*;(.*?)(?=LAYER|\Z)", body, re.S):
            enc = re.search(r"ENCLOSURE\s+(\S+)\s+(\S+)", block)
            rect = re.search(r"RECT\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", block)
            if enc:
                metals[lay] = (float(enc[1]), float(enc[2]))
            elif rect:
                sp = re.search(r"SPACING\s+(\S+)\s+BY\s+(\S+)", block)
                x0, y0, x1, y1 = (float(v) for v in rect.groups())
                square = abs((x1 - x0) - (y1 - y0)) <= 1e-9 and sp
                # a non-square or unspaced cut is kept unusable (None): kit() refuses it only if it is backside
                cut = (lay, x1 - x0 if square else None, (float(sp[1]), float(sp[2])) if square else None)
        if cut and len(metals) == 2:
            out.setdefault(cut[0], []).append({"rule": name, "default": "DEFAULT" in flags.split(),
                                               "metals": metals, "cut": cut[1], "pitch": cut[2]})
    return out


def read_power_pin_y(path, net, layer):
    """Centre y (um) of the first macro's `net` pin shape on `layer` in a cell LEF (all macros share one row)."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    pin = re.search(rf"PIN\s+{net}\b(.*?)END\s+{net}\b", text, re.S)
    rect = pin and re.search(rf"LAYER\s+{layer}\s*;\s*RECT\s+\S+\s+(\S+)\s+\S+\s+(\S+)", pin[1])
    if not rect:
        raise ValueError(f"no {net} pin on {layer} in {path}")
    return (float(rect[1]) + float(rect[2])) / 2


AMBIGUOUS = None   # read_tcl_sets' value for a name set more than once or inside a brace block (if/proc)


def read_tcl_sets(path):
    """{name: value} for every 'set NAME value' line: a single-token value as text, any other value as ""; a name
    set more than once, or inside a brace block (whose branch this reader cannot evaluate), maps to AMBIGUOUS."""
    out, depth = {}, 0
    with open(path, encoding="utf-8") as f:
        for ln in f:
            code = "" if ln.lstrip().startswith("#") else ln
            m = re.match(r"\s*set\s+(\w+)\s+(.*?)\s*$", code)
            if m:
                single = re.fullmatch(r"[^\s\[{;]+", m[2])
                ambiguous = depth > 0 or m[1] in out
                out[m[1]] = AMBIGUOUS if ambiguous else (m[2] if single else "")
            depth += code.count("{") - code.count("}")
    return out


def read_lef_layers(path):
    """{layer: {"type", "width", "pitch"}} in um from a tech LEF (first pitch value)."""
    out, cur = {}, None
    with open(path, encoding="utf-8") as f:
        for ln in f:
            t = ln.split()
            if not t:
                continue
            if t[0] == "LAYER" and len(t) > 1:
                cur = out.setdefault(t[1], {})
            elif t[0] == "END":
                cur = None
            elif cur is not None and t[0] in ("TYPE", "WIDTH", "PITCH"):
                cur[t[0].lower()] = t[1] if t[0] == "TYPE" else float(t[1])
    return out


def read_ict(path):
    """({conductor: {"resistivity", "thickness"}}, {via: {"r", "area", "layers"}}) from a QRC ICT; a via's
    area_resistance is (ohm, um^2) of one cut."""
    with open(path, encoding="utf-8") as f:
        text = re.sub(r"#.*", "", f.read())
    cond, via = {}, {}
    for kind, name, body in re.findall(r"^\s*(conductor|via)\s+(\w+)\s*\{(.*?)\}", text, re.M | re.S):
        kv = {m[0]: m[1:] for m in (ln.split() for ln in body.splitlines()) if m}
        if kind == "conductor":
            cond[name] = {"resistivity": float(kv["resistivity"][0]), "thickness": float(kv["thickness"][0])}
        else:
            via[name] = {"r": float(kv["area_resistance"][0]), "area": float(kv["area_resistance"][1]),
                         "layers": frozenset((kv["bottom_layer"][0], kv["top_layer"][0]))}
    return cond, via


def itf_resistivity(path, layer, width_um):
    """The conductor's RHO_VS_SI_WIDTH_AND_THICKNESS value at width_um (one thickness), linear between table widths."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    block = re.search(rf"CONDUCTOR\s+{layer}\s*\{{(.*?)\n\}}", text, re.S)
    if not block:
        raise ValueError(f"ITF has no conductor {layer}")
    ws = [float(x) for x in re.search(r"WIDTH\s*\{([^}]*)\}", block[1])[1].split()]
    vs = [float(x) for x in re.search(r"VALUES\s*\{([^}]*)\}", block[1])[1].split()]
    if not ws[0] <= width_um <= ws[-1]:
        raise ValueError(f"{layer} width {width_um} outside the ITF table {ws[0]}-{ws[-1]}")
    for (w0, v0), (w1, v1) in zip(zip(ws, vs, strict=True), zip(ws[1:], vs[1:], strict=True), strict=False):
        if w0 <= width_um <= w1:
            return v0 + (v1 - v0) * (width_um - w0) / (w1 - w0)
    raise AssertionError


def kit(base, bpr_rho="ict"):
    """Everything the generator needs from the kit, in um and ohm, with each value's source."""
    tcl = read_tcl_sets(os.path.join(base, "PDK_PATHS.tcl"))
    tlef = os.path.join(base, "lef", "gtA5_cfet.tlef")
    lef = read_lef_layers(tlef)
    cond, ict = read_ict(os.path.join(base, "qrc", "GTA5_cfet.ict"))
    cut_layers = {n for n, d in lef.items() if d.get("type") == "CUT"}
    gen, fixed = read_viarules(tlef), read_fixed_vias(tlef, cut_layers)
    vias_k = {}
    # a router without non-default rules may use a cut layer's DEFAULT generate rules and its fixed DEFAULT vias;
    # each cut layer is matched to the ICT via joining the same two layers (LEF BSV1/BSV2, ICT VBSM1/VBSM2)
    for cut in sorted(set(gen) | {f["cut_layer"] for f in fixed}):
        cands = [r for r in gen.get(cut, []) if r["default"]] + [f for f in fixed if f["cut_layer"] == cut]
        pairs = {frozenset(r["metals"]) for r in gen.get(cut, [])} | {frozenset(f["layers"]) for f in fixed
                                                                      if f["cut_layer"] == cut}
        if not any(p <= set(BACKSIDE) for p in pairs):
            continue
        if len(pairs) != 1:
            raise ValueError(f"cut {cut}: its vias join different layer pairs {pairs}")
        pair = pairs.pop()
        bad = [r["rule"] for r in cands if r["cut"] is None]
        if bad or not cands:
            raise ValueError(f"cut {cut}: no usable DEFAULT via ({bad or 'none'})")
        match = [n for n, v in ict.items() if v["layers"] == pair]
        if len(match) != 1:
            raise ValueError(f"{cut} joins {sorted(pair)}: {len(match)} ICT vias do")
        v = ict[match[0]]
        # the ICT quotes ohms for its own cut area; a LEF cut of another size has R scaled by area (A19: e.g.
        # VBSV2_0 cuts 0.5 um, the ICT's VBSM2 0.4 um)
        vias_k[cut] = {"metals": sorted(pair), "ict_name": match[0], "ict_r": v["r"], "ict_area": v["area"],
                       "rules": [dict(r, r_cut=v["r"] * v["area"] / r["cut"] ** 2) for r in cands],
                       "non_default_rules_skipped": [r["rule"] for r in gen.get(cut, []) if not r["default"]]}
    rho = {lay: cond[lay]["resistivity"] for lay in BACKSIDE}
    if bpr_rho == "itf":
        rho["BPR"] = itf_resistivity(os.path.join(base, "starrc", "GTA5cfet.itf"), "BPR", lef["BPR"]["width"])
    sheet = {lay: rho[lay] / cond[lay]["thickness"] for lay in rho}
    ambiguous = [n for n in TCL_NUMBERS + TCL_NAMES if n in tcl and tcl[n] is AMBIGUOUS]
    if ambiguous:
        raise ValueError(f"PDK_PATHS.tcl sets {ambiguous} more than once or inside a block")
    f = {k: float(v) for k, v in tcl.items() if v and re.fullmatch(r"-?(\d+\.?\d*|\.\d+)", v)}
    missing = [n for n in TCL_NUMBERS if n not in f] + [n for n in TCL_NAMES if not tcl.get(n)]
    if missing:
        raise ValueError(f"PDK_PATHS.tcl lacks (or has a non-plain value for) {missing}")
    # which row boundary is VDD: a cell's VDD pin at the top of its (unflipped) row puts VDD on odd boundaries
    vdd_y = read_power_pin_y(os.path.join(base, "lef", "gtA5_cfet_macros.lef"), "VDD", tcl["CORE_PIN_LAYER"])
    return {
        "vdd_on_odd_boundaries": vdd_y > f["CFET_SITE_Y"] / 2,
        "supply": f["CFET_OP_VOLTAGE"], "site_x": f["CFET_SITE_X"], "site_y": f["CFET_SITE_Y"],
        "pg_h": tcl["PG_H"], "pg_v": tcl["PG_V"], "stripe_v_layer": tcl["PG_STRIPE_VERT"],
        "core_pin_layer": tcl["CORE_PIN_LAYER"],
        "ring": (f["PG_RING_WIDTH"], f["PG_RING_SPACING"], f["PG_RING_OFFSET"]),
        "stripe_v": (f["PG_STRIPE_VERT_WIDTH"], f["PG_STRIPE_VERT_SPACING"], f["PG_STRIPE_VERT_SET_TO_SET"],
                     f["PG_STRIPE_VERT_START_OFFSET"]),
        "stripe_h": (f["PG_STRIPE_HORZ_WIDTH"], f["PG_STRIPE_HORZ_SPACING"], f["PG_STRIPE_HORZ_SET_TO_SET"],
                     f["PG_STRIPE_HORZ_START_OFFSET"]),
        "bpr_width": lef["BPR"]["width"],
        "sheet_ohm_sq": sheet, "resistivity": rho, "bpr_rho_source": bpr_rho,
        "via": vias_k,
    }


def um(x):
    return int(round(x * DBU))


def rule_array(r, rects):
    """(nx, ny, region) of one rule's cut array where the two metal shapes ({layer: rect}) cross. A generate rule:
    each metal's enclosure is measured from that metal's own edges, in the orientation that fits the most cuts,
    cuts at the rule's centre-to-centre pitch. A fixed via: one cut at the overlap's centre, legal if its cut lies in
    the overlap and each metal pad lies in that metal's shape, unrotated or turned 90 degrees (pads turn together)."""
    a, b = rects.values()
    box = overlap(a, b)
    w = um(r["cut"])
    if r.get("fixed"):
        if not box or box[2] - box[0] < w or box[3] - box[1] < w:
            return 0, 0, None
        cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2

        def inside(lay, pad, turn):
            x0, y0, x1, y1 = (um(v) for v in pad)
            if turn:                                           # (x, y) -> (-y, x)
                x0, y0, x1, y1 = -y1, x0, -y0, x1
            m = rects[lay]
            return m[0] <= cx + x0 and cx + x1 <= m[2] and m[1] <= cy + y0 and cy + y1 <= m[3]

        if any(all(inside(lay, pad, turn) for lay, pad in r["pads"].items()) for turn in (False, True)):
            return 1, 1, box
        return 0, 0, None
    px, py = (um(p) for p in r["pitch"])
    best = (0, 0, 0, None)
    lays = list(r["metals"])
    opts = [((um(e1), um(e2)), (um(e2), um(e1))) for e1, e2 in (r["metals"][lay] for lay in lays)]
    for e0 in opts[0]:
        for e1 in opts[1]:
            reg = None
            for lay, (ex, ey) in zip(lays, (e0, e1), strict=True):
                x0, y0, x1, y1 = rects[lay]
                shrunk = (x0 + ex, y0 + ey, x1 - ex, y1 - ey)
                reg = shrunk if reg is None else overlap(reg, shrunk)
                if reg is None:
                    break
            if reg is None:
                continue
            nx = (reg[2] - reg[0] - w) // px + 1 if reg[2] - reg[0] >= w else 0
            ny = (reg[3] - reg[1] - w) // py + 1 if reg[3] - reg[1] >= w else 0
            if nx * ny > best[0]:
                best = (nx * ny, nx, ny, reg)
    return best[1], best[2], best[3]


def cut_array(v, rects, cap=None):
    """(rule, [cut boxes]) where two metal shapes ({layer: rect}) of one net cross: of the cut layer's usable vias
    that fit, the one giving the lowest via resistance, its cuts centred in the allowed region; at most cap cuts (those
    nearest the centre; the cap applies before the choice)."""
    best = None
    for r in v["rules"]:
        nx, ny, reg = rule_array(r, rects)
        n = min(nx * ny, cap) if cap else nx * ny
        if n and (best is None or r["r_cut"] / n < best[0]):
            best = (r["r_cut"] / n, r, nx, ny, reg)
    if best is None:
        raise ValueError(f"crossing {rects} fits no {[r['rule'] for r in v['rules']]} cut")
    _, r, nx, ny, (xlo, ylo, xhi, yhi) = best
    w = um(r["cut"])
    px, py = (um(p) for p in r["pitch"]) if not r.get("fixed") else (w, w)
    ox, oy = (xlo + xhi - (nx - 1) * px - w) // 2, (ylo + yhi - (ny - 1) * py - w) // 2
    cuts = [(ox + i * px, oy + j * py) for j in range(ny) for i in range(nx)]
    if cap and cap < len(cuts):                    # keep the cap's cuts nearest the region's centre
        mx, my = (xlo + xhi - w) / 2, (ylo + yhi - w) / 2
        cuts = sorted(cuts, key=lambda c: ((c[0] - mx) ** 2 + (c[1] - my) ** 2, c))[:cap]
    return r, [(x, y, x + w, y + w) for x, y in cuts]


def boundary_net(k, b):
    return "VDD" if (b % 2 == 1) == k["vdd_on_odd_boundaries"] else "VSS"


def overlap(a, b):
    box = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return box if box[0] < box[2] and box[1] < box[3] else None


def layout(k, side_um):
    """{net: {layer: [rect]}} for the stripes, rails and rings, and the ring rects per net (DBU)."""
    s = um(side_um)
    rw, rs, ro = (um(v) for v in k["ring"])
    shapes = {"VDD": {}, "VSS": {}}
    rings = {}
    for idx, net in enumerate(("VDD", "VSS")):                 # VDD inner ring, VSS outer
        lo = -ro - rw - idx * (rw + rs)
        hi = s - lo
        ring_h = [(lo, lo, hi, lo + rw), (lo, hi - rw, hi, hi)]   # bottom and top sides
        ring_v = [(lo, lo, lo + rw, hi), (hi - rw, lo, hi, hi)]   # left and right sides
        shapes[net].setdefault(k["pg_h"], []).extend(ring_h)
        shapes[net].setdefault(k["pg_v"], []).extend(ring_v)
        rings[net] = (lo, hi, rw)
    hb = um(k["bpr_width"]) // 2
    row = um(k["site_y"])
    for b in range(s // row + 1):                              # BPR rails at every row boundary
        net = boundary_net(k, b)
        shapes[net].setdefault(k["core_pin_layer"], []).append((0, b * row - hb, s, b * row + hb))
    w, sp, step, off = (um(v) for v in k["stripe_v"])
    for idx, net in enumerate(("VDD", "VSS")):                 # vertical stripes to the net's ring
        lo, hi, rwn = rings[net]
        x = off + idx * (w + sp)
        while x + w <= s:
            shapes[net].setdefault(k["stripe_v_layer"], []).append((x, lo, x + w, hi))
            x += step
    w, sp, step, off = (um(v) for v in k["stripe_h"])
    for idx, net in enumerate(("VDD", "VSS")):                 # horizontal stripes on PG_H
        lo, hi, rwn = rings[net]
        y = off + idx * (w + sp)
        while y + w <= s:
            shapes[net][k["pg_h"]].append((lo, y, hi, y + w))
            y += step
    return shapes, rings


def vias(k, shapes, tsv_cuts):
    """[(cut layer, via box, [cut boxes], bottom, top, rule)] for one net's shapes."""
    out = []
    for cut, v in k["via"].items():
        bot, top = v["metals"]
        for a in shapes.get(bot, ()):
            for b in shapes.get(top, ()):
                box = overlap(a, b)
                if box:
                    rule, cuts = cut_array(v, {bot: a, top: b}, tsv_cuts if cut == "TSV" else None)
                    out.append((cut, box, cuts, bot, top, rule))
    return out


def loads(k, side_um, hotspot):
    """[(instance, x0, x1, row, power W)]: one cell per CELL_SITES sites in every row."""
    s, row, cw = um(side_um), um(k["site_y"]), um(k["site_x"]) * CELL_SITES
    p_cell = J_A_PER_UM2 * (cw / DBU) * (row / DBU) * k["supply"]
    c0, c1 = (s - um(HOTSPOT_UM)) // 2, (s + um(HOTSPOT_UM)) // 2
    out = []
    for r in range(s // row):
        for c in range(s // cw):
            x0, x1 = c * cw, (c + 1) * cw
            hot = hotspot and c0 <= (x0 + x1) // 2 < c1 and c0 <= r * row + row // 2 < c1
            out.append((f"r{r}c{c}", x0, x1, r, p_cell * (HOTSPOT_X if hot else 1.0)))
    return out


def sources(k, shapes, rings, net, feed, bump_pitch_um, side_um):
    """bterm rects: every side of the net's ring (both ring layers), or one box per bump: at the net's BSM2 stripe
    and BSM1 stripe nearest the bump, around their crossing, so each bump holds exactly that crossing's node."""
    if feed == "ring":
        return [(lay, r) for lay in (k["pg_h"], k["pg_v"]) for r in shapes[net][lay]
                if r in ring_rects(rings[net])]
    lo, hi, rw = rings[net]
    h_stripes = [r for r in shapes[net][k["pg_h"]] if r[0] == lo and r[2] == hi and r[3] - r[1] < rw]
    v_stripes = shapes[net].get(k["stripe_v_layer"], [])
    if not h_stripes or not v_stripes:
        raise ValueError(f"{net}: no {k['pg_h']} or {k['stripe_v_layer']} stripe inside a {side_um} um core")
    p, s = um(bump_pitch_um), um(side_um)
    # n bumps per side at pitch p, the array centred in the core (v1 started at p/2 and stopped short of the far
    # edge: at side 50, pitch 20, bumps at 10 and 30 only, so the far corner was 26 um from any bump)
    n = max(1, int(side_um / bump_pitch_um + 0.5))
    first = (s - (n - 1) * p) // 2
    out = []
    for bx in (first + i * p for i in range(n)):
        vx = min(v_stripes, key=lambda r: abs((r[0] + r[2]) // 2 - bx))
        for by in (first + i * p for i in range(n)):
            hy = min(h_stripes, key=lambda r: abs((r[1] + r[3]) // 2 - by))
            out.append((k["pg_h"], (vx[0], hy[1], vx[2], hy[3])))
    return out


def ring_rects(ring):
    lo, hi, rw = ring
    return {(lo, lo, hi, lo + rw), (lo, hi - rw, hi, hi), (lo, lo, lo + rw, hi), (hi - rw, lo, hi, hi)}


def write(out_dir, k, side_um, feed="ring", bump_pitch_um=20.0, tsv_cuts=None, hotspot=False):
    """Writes geom_<net>.tsv, iterms_<net>.tsv, inst_power.tsv and export.log; returns a summary dict."""
    os.makedirs(out_dir, exist_ok=True)
    shapes, rings = layout(k, side_um)
    head = ["kind", "layer", "xlo", "ylo", "xhi", "yhi", "via", "bottom", "top", "cx", "cy"]
    summary = {"side_um": side_um, "feed": feed, "bump_pitch_um": bump_pitch_um if feed == "area" else None,
               "tsv_cuts_cap": tsv_cuts, "hotspot": hotspot, "bpr_rho_source": k["bpr_rho_source"], "nets": {}}
    # c4's export format has one resistance per cut layer name, so each (cut layer, via rule) pair is written as its
    # own cut layer "<cut>@<rule>" with that rule's resistance per cut in export.log
    used = {}                                              # "<cut>@<rule>" -> ohm per cut
    for net in ("VDD", "VSS"):
        vs = vias(k, shapes[net], tsv_cuts)
        with open(os.path.join(out_dir, f"geom_{net}.tsv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter="\t", lineterminator="\n")
            w.writerow(head)
            for lay, rs in shapes[net].items():
                for r in rs:
                    w.writerow(["wire", lay, *r, "-", "-", "-", "-", "-"])
            for n, (cut, box, cuts, bot, top, rule) in enumerate(vs):
                cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
                name = f"{cut}_{n}"
                layer = f"{cut}@{rule['rule']}"
                used[layer] = rule["r_cut"]
                w.writerow(["via", "-", *box, name, bot, top, cx, cy])
                for c in cuts:
                    w.writerow(["cut", layer, *c, name, bot, top, cx, cy])
            for lay, r in sources(k, shapes, rings, net, feed, bump_pitch_um, side_um):
                w.writerow(["bterm", lay, *r, "-", "-", "-", "-", "-"])
        per_layer = {lay: len(rs) for lay, rs in shapes[net].items()}
        cuts_by, rules_by = {}, {}
        for cut, _, cs, _, _, rule in vs:
            cuts_by.setdefault(cut, [0, 0])
            cuts_by[cut][0] += 1
            cuts_by[cut][1] += len(cs)
            rules_by.setdefault(cut, {}).setdefault(rule["rule"], 0)
            rules_by[cut][rule["rule"]] += 1
        summary["nets"][net] = {"shapes": per_layer, "vias_and_cuts": cuts_by, "vias_by_rule": rules_by}
    summary["ohm_per_cut"] = used
    cells = loads(k, side_um, hotspot)
    row, hb = um(k["site_y"]), um(k["bpr_width"]) // 2
    for net in ("VDD", "VSS"):
        with open(os.path.join(out_dir, f"iterms_{net}.tsv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter="\t", lineterminator="\n")
            w.writerow(["inst", "pin", "placed", "xlo", "ylo", "xhi", "yhi"])
            for name, x0, x1, r, _ in cells:
                b = r if boundary_net(k, r) == net else r + 1           # this row's boundary carrying the net
                w.writerow([name, net, 1, x0, b * row - hb, x1, b * row + hb])
    with open(os.path.join(out_dir, "inst_power.tsv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["inst", "power_w"])
        for name, *_, p in cells:
            w.writerow([name, repr(p)])
    with open(os.path.join(out_dir, "export.log"), "w", encoding="utf-8") as f:
        f.write("generated by dry/c5/bsgrid.py from MATRIX-A5's kit files (not an OpenROAD log)\n")
        f.write(f"DBU {DBU}\nSupply voltage : {k['supply']}\nSupply voltage : 0\nLayer resistance:\n")
        for lay, r in k["sheet_ohm_sq"].items():
            f.write(f"  {lay}: {r!r} Ohm per square\n")
        for layer, r in used.items():
            f.write(f"  {layer}: {r!r} Ohm per cut\n")
    summary.update(cells=len(cells), total_current_a=sum(c[-1] for c in cells) / k["supply"])
    with open(os.path.join(out_dir, "grid.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "kit": k}, f, indent=1)
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("kit_base")
    ap.add_argument("out_dir")
    ap.add_argument("--side", type=float, default=50.0)
    ap.add_argument("--feed", choices=("ring", "area"), default="ring")
    ap.add_argument("--bump-pitch", type=float, default=20.0)
    ap.add_argument("--tsv-cuts", type=int, default=None, help="cap on TSV cuts per crossing (default: no cap)")
    ap.add_argument("--bpr-rho", choices=("ict", "itf"), default="ict")
    ap.add_argument("--hotspot", action="store_true")
    a = ap.parse_args()
    finite = math.isfinite(a.side) and math.isfinite(a.bump_pitch)
    if not finite or a.side <= 0 or a.bump_pitch <= 0 or (a.tsv_cuts is not None and a.tsv_cuts < 1):
        sys.exit("side and bump pitch must be positive, tsv-cuts at least 1")
    print(json.dumps(write(a.out_dir, kit(a.kit_base, a.bpr_rho), a.side, a.feed, a.bump_pitch, a.tsv_cuts,
                           a.hotspot)))


if __name__ == "__main__":
    main()
