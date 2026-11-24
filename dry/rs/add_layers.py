"""S5 to S8 (GRT0029.md, section S4): give asap7_3D the two routing layers above M1_m that asap7_nangate45_3D ships.

Copies, from the hybrid platform of the same Pin-3D checkout, the LEF layers V1_add, M2_add, V2_add and M3_add (one
contiguous block ending at END M3_add) and the vias that use them, into a new asap7_3D tech LEF right after M1_m;
and appends the hybrid platform's M2_add/M3_add tracks and *_add RC lines to new copies of asap7_3D's track and RC
scripts. Each anchor must be found as stated (the layer block and END M1_m exactly once, two vias, 8 track and 4 RC
lines), or nothing is written.

--view picks which of asap7_3D's two tech views is copied: `hbrdl` (the default, S5-S7: the kit's HBM_B/HBM_T
bonding layers) or `direct` (S8: `asap7_tech_1x_2A6M7M.lef`, whose bonding layer hb_layer is a cut layer). The kit
switches between them with ASAP7_HBT_RDL.

With --config (S6) it also points asap7_3D's own config.mk at the copies of that view and sets MAX_ROUTING_LAYER to
M3_add. Extraction: on hbrdl it is turned off by emptying ASAP7_HBT_RDL_RCX_RULES (config.mk then unexports
RCX_RULES), because the kit's 15-layer hbrdl deck does not cover the two added layers (17 routing layers); on direct
ASAP7_HBT_RDL is pinned to 0 and RCX_RULES set to the kit's 15-layer asap7_tech_1x_2A6M7M deck, extracted from
rc_extract/input/asap7_tech_1x_2A6M7M.lef, whose *_add layers equal the ones copied here (a test checks this).
This keeps the change inside the 3D platform: Pin-3D runs synthesis
and the first floorplan on the 2D asap7 platform, which environment overrides would also reach (S5 v1).
With --drop-gcell as well (S7, hbrdl only) it also drops the kit's `GLOBAL_ROUTE_ARGS += -gcell_size` line: the
pinned OpenROAD's global_route rejects that flag (STA-0562; record/2026-11-19_s6_v1/NOTE.md). Without it, --config
on hbrdl makes exactly the edits S6 ran with.
The original config.mk is kept beside it as config.mk.orig; only the clone is changed, never a tracked file.

  python add_layers.py <pin3d dir> [--view hbrdl|direct] [--config [--drop-gcell]]
prints the sha256 of every input and output.
"""
import argparse
import hashlib
import re
import shutil
from pathlib import Path

HYB = "platforms/asap7_nangate45_3D"
A7 = "platforms/asap7_3D"
VIEWS = {"hbrdl": "_hbrdl", "direct": ""}        # suffix of the view's file names in asap7_3D
HYB_SRC = {"lef": f"{HYB}/lef/asap7_nangate45_2A6M10M.lef", "tracks": f"{HYB}/openRoad/make_tracks.2A6M10M.tcl",
           "rc": f"{HYB}/setRC_2A6M10M.tcl"}
LAYERS = re.compile(r"^LAYER V1_add\n.*?^END M3_add\n", re.MULTILINE | re.DOTALL)
VIA = re.compile(r"^VIA (\S+) DEFAULT\n.*?^END \1\n", re.MULTILINE | re.DOTALL)
M1M_END = re.compile(r"^END M1_m\n", re.MULTILINE)
FIRST_VIARULE = re.compile(r"^VIARULE ", re.MULTILINE)
TRACK = re.compile(r"^make_tracks M[23]_add .*\n", re.MULTILINE)
RC = re.compile(r"^set_layer_rc -(?:layer|via) [MV][123]_add .*\n", re.MULTILINE)


def a7_files(view, add=""):
    """asap7_3D's tech LEF, track and RC script for a view; add="_add" names the patched copies."""
    s = VIEWS[view] + add
    return {"lef": f"{A7}/lef/asap7_tech_1x_2A6M7M{s}.lef", "tracks": f"{A7}/openRoad/make_tracks.2A6M7M{s}.tcl",
            "rc": f"{A7}/setRC_2A6M7M{s}.tcl"}


def one(pattern, text, what):
    m = list(pattern.finditer(text))
    if len(m) != 1:
        raise SystemExit(f"{what}: {len(m)} matches, expected 1")
    return m[0]


def patch_lef(hyb, a7):
    """a7 is always the untouched view LEF (the output is a new file), so re-running regenerates the same copy."""
    layers = one(LAYERS, hyb, "hybrid V1_add..M3_add block").group(0)
    vias = [m.group(0) for m in VIA.finditer(hyb) if "_add ;" in m.group(0)]
    if len(vias) != 2:
        raise SystemExit(f"hybrid vias on *_add layers: {len(vias)}, expected 2")
    end = one(M1M_END, a7, "asap7_3D END M1_m").end()
    out = a7[:end] + "\n" + layers + a7[end:]
    vr = FIRST_VIARULE.search(out)   # the vias go after the fixed VIAs, before the first VIARULE
    if vr is None:
        raise SystemExit("asap7_3D LEF: no VIARULE to anchor the vias")
    return out[:vr.start()] + "\n".join(vias) + "\n" + out[vr.start():]


def append_lines(hyb, a7, pattern, n_expected, what):
    lines = pattern.findall(hyb)
    if len(lines) != n_expected:
        raise SystemExit(f"{what}: {len(lines)} lines, expected {n_expected}")
    return a7 + ("" if a7.endswith("\n") else "\n") + "".join(lines)


CONFIG = f"{A7}/config.mk"


def _pointers(view, indent):
    """The view's three file-pointer lines in config.mk, and their replacements pointing at the *_add copies."""
    old, new = a7_files(view), a7_files(view, "_add")
    names = {"lef": "TECH_LEF", "rc": "SET_RC_TCL", "tracks": "MAKE_TRACKS"}
    return [(f"{indent}ASAP7_OPENROAD_{names[k]} := $(PLATFORM_DIR)/{old[k].removeprefix(A7 + '/')}",
             f"{indent}ASAP7_OPENROAD_{names[k]} := $(PLATFORM_DIR)/{new[k].removeprefix(A7 + '/')}")
            for k in ("lef", "rc", "tracks")]


MAX_LAYER = ("  export MAX_ROUTING_LAYER ?= M2_m", "  export MAX_ROUTING_LAYER ?= M3_add")
DIRECT_DECK = f"{A7}/asap7_tech_1x_2A6M7M.rcx_patterns.rules"   # the kit's deck for M1..M7, M6_m..M1_m, M2/M3_add
GCELL_EDIT = ("  export GLOBAL_ROUTE_ARGS += -gcell_size $(ASAP7_HBT_RDL_GCELL_SIZE_UM)",
              "  # -gcell_size dropped: not a global_route flag in the pinned OpenROAD")   # S7, --drop-gcell
CONFIG_EDITS = {   # per view: (exact line in asap7_3D's config.mk at Pin-3D 51a19d6f, its replacement), in file order
    "hbrdl": [("export ASAP7_HBT_RDL_RCX_RULES ?= $(PLATFORM_DIR)/asap7_tech_1x_2A6M7M_hbrdl.rcx_patterns.rules",
               "export ASAP7_HBT_RDL_RCX_RULES ?="),
              *_pointers("hbrdl", "  "), GCELL_EDIT, MAX_LAYER],
    # direct: the view pinned with `override` (an ASAP7_HBT_RDL=1 in the environment would bring back the unpatched
    # hbrdl pointers); extraction on the kit's 2A6M7M deck, set last with `override` so it wins over line 29's `?=`
    # and the environment. The pointers and MAX_ROUTING_LAYER only apply under USE_FLOW=openroad, the deck always, so
    # Pin-3D's own LayerCount check (final_report.tcl, off by default; nangate45_3D turns it on) is turned on in place
    # of a dead comment line: any other TECH_LEF stops extraction with "RCX layer mismatch" instead of a wrong SPEF
    "direct": [("export ASAP7_HBT_RDL ?= 1", "override export ASAP7_HBT_RDL := 0"),
               *_pointers("direct", ""), MAX_LAYER,
               ("# export DEFAULT_3D_TECH_LEF ?= $(PLATFORM_DIR)/lef/asap7_tech_1x_6M7M.lef",
                "export PIN3D_REQUIRE_RCX_LAYER_MATCH := 1"),
               ("export RCX_RULES         ?= $(PLATFORM_DIR)/asap7_tech_1x_6M7M.rcx_patterns.rules",
                f"override export RCX_RULES := $(PLATFORM_DIR)/{DIRECT_DECK.removeprefix(A7 + '/')}")],
}


def config_edits(view="hbrdl", drop_gcell=False):
    """The edits in file order; the -gcell_size line (hbrdl only) is kept unless drop_gcell."""
    if drop_gcell and view != "hbrdl":
        raise SystemExit("--drop-gcell applies to the hbrdl view only")
    return [e for e in CONFIG_EDITS[view] if drop_gcell or e is not GCELL_EDIT]


def patch_config(text, edits):
    """Each edit's line must occur exactly once as a whole line; returns the edited text."""
    lines = text.split("\n")
    for old, new in edits:
        idx = [i for i, line in enumerate(lines) if line == old]
        if len(idx) != 1:
            raise SystemExit(f"config.mk: {len(idx)} lines equal to {old!r}, expected 1")
        lines[idx[0]] = new
    return "\n".join(lines)


def build(root, with_config, drop_gcell=False, view="hbrdl"):
    """{path: new text} for every output, all computed (and every anchor checked) before anything is written."""
    src, out_p = a7_files(view), a7_files(view, "_add")
    text = {k: ((root / HYB_SRC[k]).read_text(encoding="utf-8"), (root / src[k]).read_text(encoding="utf-8"))
            for k in HYB_SRC}
    out = {out_p["lef"]: patch_lef(*text["lef"]),
           out_p["tracks"]: append_lines(*text["tracks"], TRACK, 8, "hybrid M2_add/M3_add tracks"),
           out_p["rc"]: append_lines(*text["rc"], RC, 4, "hybrid *_add RC lines")}
    if with_config:   # config.mk is written last (see main)
        out[CONFIG] = patch_config((root / CONFIG).read_text(encoding="utf-8"), config_edits(view, drop_gcell))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pin3d", type=Path)
    ap.add_argument("--view", choices=sorted(VIEWS), default="hbrdl", help="asap7_3D tech view to patch")
    ap.add_argument("--config", action="store_true", help="also patch asap7_3D's config.mk (S6)")
    ap.add_argument("--drop-gcell", action="store_true", help="with --config: also drop -gcell_size (S7)")
    a = ap.parse_args()
    if a.drop_gcell and not a.config:
        ap.error("--drop-gcell needs --config")
    out = build(a.pin3d, a.config, a.drop_gcell, a.view)
    src = a7_files(a.view)
    inputs = [q for k in HYB_SRC for q in (HYB_SRC[k], src[k])]
    if a.config:
        shutil.copyfile(a.pin3d / CONFIG, a.pin3d / f"{CONFIG}.orig")   # byte-identical original
        inputs.append(f"{CONFIG}.orig")
    for p in sorted(out, key=lambda p: p == CONFIG):    # config.mk last: a failed write leaves it untouched
        (a.pin3d / p).write_text(out[p], encoding="utf-8", newline="\n")   # same bytes, so same hashes, on Windows
    for p in inputs + list(out):
        print(hashlib.sha256((a.pin3d / p).read_bytes()).hexdigest(), p)


if __name__ == "__main__":
    main()
