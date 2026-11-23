"""S5 (GRT0029.md, section S4): give asap7_3D the two routing layers above M1_m that asap7_nangate45_3D ships.

Copies, from the hybrid platform of the same Pin-3D checkout, the LEF layers V1_add, M2_add, V2_add and M3_add (one
contiguous block ending at END M3_add) and the vias that use them, into a new asap7_3D tech LEF right after M1_m;
and appends the hybrid platform's M2_add/M3_add tracks and *_add RC lines to new copies of asap7_3D's track and RC
scripts. The originals are not changed. Each anchor must be found as stated (the layer block and END M1_m exactly
once, two vias, 8 track and 4 RC lines), or nothing is written.

  python add_layers.py <pin3d dir>     prints the three new paths and the sha256 of inputs and outputs
"""
import hashlib
import re
import sys
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
    if "_add" in a7:
        raise SystemExit("asap7_3D LEF already has *_add layers")
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


def main(root):
    root = Path(root)
    text = {k: tuple((root / p).read_text() for p in v) for k, v in SRC.items()}
    out = {"lef": patch_lef(*text["lef"]),
           "tracks": append_lines(*text["tracks"], TRACK, 8, "hybrid M2_add/M3_add tracks"),
           "rc": append_lines(*text["rc"], RC, 4, "hybrid *_add RC lines")}
    for k, body in out.items():
        (root / OUT[k]).write_text(body)
    for p in [q for v in SRC.values() for q in v] + list(OUT.values()):
        print(hashlib.sha256((root / p).read_bytes()).hexdigest(), p)


if __name__ == "__main__":
    main(sys.argv[1])
