"""S5/S6 (GRT0029.md, section S4): give asap7_3D the two routing layers above M1_m that asap7_nangate45_3D ships.

Copies, from the hybrid platform of the same Pin-3D checkout, the LEF layers V1_add, M2_add, V2_add and M3_add (one
contiguous block ending at END M3_add) and the vias that use them, into a new asap7_3D tech LEF right after M1_m;
and appends the hybrid platform's M2_add/M3_add tracks and *_add RC lines to new copies of asap7_3D's track and RC
scripts. Each anchor must be found as stated (the layer block and END M1_m exactly once, two vias, 8 track and 4 RC
lines), or nothing is written.

With --config (S6) it also points asap7_3D's own config.mk at those copies, sets its MAX_ROUTING_LAYER to M3_add and
empties ASAP7_HBT_RDL_RCX_RULES (the kit's 15-layer extraction rules do not cover the new layers; config.mk then
unexports RCX_RULES). This keeps the change inside the 3D platform: Pin-3D runs synthesis and the first floorplan on
the 2D asap7 platform, which environment overrides would also reach (S5 v1: its floorplan sourced the 3D RC script).
The original config.mk is kept beside it as config.mk.orig; only the clone is changed, never a tracked file.

  python add_layers.py <pin3d dir> [--config]     prints the sha256 of every input and output
"""
import argparse
import hashlib
import re
import shutil
from pathlib import Path

HYB = "platforms/asap7_nangate45_3D"
A7 = "platforms/asap7_3D"
SRC = {"lef": (f"{HYB}/lef/asap7_nangate45_2A6M10M.lef", f"{A7}/lef/asap7_tech_1x_2A6M7M_hbrdl.lef"),
       "tracks": (f"{HYB}/openRoad/make_tracks.2A6M10M.tcl", f"{A7}/openRoad/make_tracks.2A6M7M_hbrdl.tcl"),
       "rc": (f"{HYB}/setRC_2A6M10M.tcl", f"{A7}/setRC_2A6M7M_hbrdl.tcl")}
OUT = {"lef": f"{A7}/lef/asap7_tech_1x_2A6M7M_hbrdl_add.lef",
       "tracks": f"{A7}/openRoad/make_tracks.2A6M7M_hbrdl_add.tcl",
       "rc": f"{A7}/setRC_2A6M7M_hbrdl_add.tcl"}
LAYERS = re.compile(r"^LAYER V1_add\n.*?^END M3_add\n", re.MULTILINE | re.DOTALL)
VIA = re.compile(r"^VIA (\S+) DEFAULT\n.*?^END \1\n", re.MULTILINE | re.DOTALL)
M1M_END = re.compile(r"^END M1_m\n", re.MULTILINE)
FIRST_VIARULE = re.compile(r"^VIARULE ", re.MULTILINE)
TRACK = re.compile(r"^make_tracks M[23]_add .*\n", re.MULTILINE)
RC = re.compile(r"^set_layer_rc -(?:layer|via) [MV][123]_add .*\n", re.MULTILINE)


def one(pattern, text, what):
    m = list(pattern.finditer(text))
    if len(m) != 1:
        raise SystemExit(f"{what}: {len(m)} matches, expected 1")
    return m[0]


def patch_lef(hyb, a7):
    """a7 is always the untouched hbrdl LEF (the output is a new file), so re-running regenerates the same copy."""
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
CONFIG_EDITS = [   # (exact line in asap7_3D's config.mk at Pin-3D 51a19d6f, its replacement)
    ("export ASAP7_HBT_RDL_RCX_RULES ?= $(PLATFORM_DIR)/asap7_tech_1x_2A6M7M_hbrdl.rcx_patterns.rules",
     "export ASAP7_HBT_RDL_RCX_RULES ?="),
    ("  ASAP7_OPENROAD_TECH_LEF := $(PLATFORM_DIR)/lef/asap7_tech_1x_2A6M7M_hbrdl.lef",
     f"  ASAP7_OPENROAD_TECH_LEF := $(PLATFORM_DIR)/{OUT['lef'].removeprefix(A7 + '/')}"),
    ("  ASAP7_OPENROAD_SET_RC_TCL := $(PLATFORM_DIR)/setRC_2A6M7M_hbrdl.tcl",
     f"  ASAP7_OPENROAD_SET_RC_TCL := $(PLATFORM_DIR)/{OUT['rc'].removeprefix(A7 + '/')}"),
    ("  ASAP7_OPENROAD_MAKE_TRACKS := $(PLATFORM_DIR)/openRoad/make_tracks.2A6M7M_hbrdl.tcl",
     f"  ASAP7_OPENROAD_MAKE_TRACKS := $(PLATFORM_DIR)/{OUT['tracks'].removeprefix(A7 + '/')}"),
    ("  export MAX_ROUTING_LAYER ?= M2_m", "  export MAX_ROUTING_LAYER ?= M3_add"),
]


def patch_config(text):
    """Each CONFIG_EDITS line must occur exactly once as a whole line; returns the edited text."""
    lines = text.split("\n")
    for old, new in CONFIG_EDITS:
        idx = [i for i, line in enumerate(lines) if line == old]
        if len(idx) != 1:
            raise SystemExit(f"config.mk: {len(idx)} lines equal to {old!r}, expected 1")
        lines[idx[0]] = new
    return "\n".join(lines)


def build(root, with_config):
    """{path: new text} for every output, all computed (and every anchor checked) before anything is written."""
    text = {k: tuple((root / p).read_text(encoding="utf-8") for p in v) for k, v in SRC.items()}
    out = {OUT["lef"]: patch_lef(*text["lef"]),
           OUT["tracks"]: append_lines(*text["tracks"], TRACK, 8, "hybrid M2_add/M3_add tracks"),
           OUT["rc"]: append_lines(*text["rc"], RC, 4, "hybrid *_add RC lines")}
    if with_config:
        out[CONFIG] = patch_config((root / CONFIG).read_text(encoding="utf-8"))   # written last (see main)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pin3d", type=Path)
    ap.add_argument("--config", action="store_true", help="also patch asap7_3D's config.mk (S6)")
    a = ap.parse_args()
    out = build(a.pin3d, a.config)
    inputs = [q for v in SRC.values() for q in v]
    if a.config:
        shutil.copyfile(a.pin3d / CONFIG, a.pin3d / f"{CONFIG}.orig")   # byte-identical original
        inputs.append(f"{CONFIG}.orig")
    for p in sorted(out, key=lambda p: p == CONFIG):    # config.mk last: a failed write leaves it untouched
        (a.pin3d / p).write_text(out[p], encoding="utf-8")
    for p in inputs + list(out):
        print(hashlib.sha256((a.pin3d / p).read_bytes()).hexdigest(), p)


if __name__ == "__main__":
    main()
