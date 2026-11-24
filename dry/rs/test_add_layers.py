"""Tests for add_layers.py on miniature copies of the two platforms' files, and on the real Pin-3D checkout at
51a19d6f when it is present locally (OPEN3D_PIN3D, default D:/Work/open3d-thermal-ext/pin3d; skipped otherwise)."""
import os
import re
import subprocess
from pathlib import Path

import pytest

import add_layers as al

PIN3D = Path(os.environ.get("OPEN3D_PIN3D", "D:/Work/open3d-thermal-ext/pin3d"))
real = pytest.mark.skipif(not (PIN3D / al.CONFIG).is_file(), reason="no local Pin-3D checkout")

HYB_LEF = """LAYER M1_m
  TYPE ROUTING ;
END M1_m

LAYER V1_add
  TYPE CUT ;
END V1_add

LAYER M2_add
  TYPE ROUTING ;
END M2_add

LAYER V2_add
  TYPE CUT ;
END V2_add

LAYER M3_add
  TYPE ROUTING ;
END M3_add

VIA via1_0 DEFAULT
  LAYER M1 ; RECT 0 0 1 1 ;
END via1_0

VIA VIA_M1m_M2add DEFAULT
  LAYER M1_m ;   RECT 0 0 1 1 ;
  LAYER M2_add ; RECT 0 0 1 1 ;
END VIA_M1m_M2add

VIA VIA_M2add_M3add DEFAULT
  LAYER M2_add ; RECT 0 0 1 1 ;
  LAYER M3_add ; RECT 0 0 1 1 ;
END VIA_M2add_M3add
END LIBRARY
"""
A7_LEF = """LAYER M2_m
  TYPE ROUTING ;
END M2_m

LAYER M1_m
  TYPE ROUTING ;
END M1_m

VIA VIA12 Default
  LAYER M1 ; RECT 0 0 1 1 ;
END VIA12

VIARULE M2_m_M1_m GENERATE DEFAULT
END M2_m_M1_m
END LIBRARY
"""
HYB_TRACKS = "make_tracks M1_m -x_pitch 0.036\n" + "".join(f"make_tracks M2_add -y_offset {i}\n" for i in range(7)) \
    + "make_tracks M3_add -x_pitch 0.036\n"
HYB_RC = ("set_layer_rc -layer M1_m -resistance 1\nset_layer_rc -layer M2_add -resistance 2\n"
          "set_layer_rc -layer M3_add -resistance 3\nset_layer_rc -via V1_add -resistance 4\n"
          "set_layer_rc -via V2_add -resistance 5\n")


def test_lef_gets_the_layer_block_after_m1m_and_both_vias_before_the_viarule():
    out = al.patch_lef(HYB_LEF, A7_LEF)
    order = [out.index(s) for s in ("END M1_m", "LAYER V1_add", "END M3_add", "VIA VIA12", "VIA VIA_M1m_M2add",
                                    "VIA VIA_M2add_M3add", "VIARULE M2_m_M1_m")]
    assert order == sorted(order)
    assert "via1_0" not in out                       # only the vias on *_add layers are copied
    assert out.replace(al.LAYERS.search(HYB_LEF).group(0), "", 1).count("_add") == 3   # the vias' layer lines
    assert out.count("LAYER M1_m\n") == 1 and out.endswith("END LIBRARY\n")


def test_lef_refuses_when_the_layer_block_is_missing():
    with pytest.raises(SystemExit):
        al.patch_lef(HYB_LEF.replace("LAYER V1_add", "LAYER V1_xx"), A7_LEF)


def test_tracks_and_rc_append_only_the_added_layers():
    t = al.append_lines(HYB_TRACKS, "make_tracks M1_m -x_pitch 0.036", al.TRACK, 8, "tracks")
    assert t.startswith("make_tracks M1_m -x_pitch 0.036\nmake_tracks M2_add") and t.count("_add") == 8
    rc = al.append_lines(HYB_RC, "set_layer_rc -layer M1_m -resistance 1\n", al.RC, 4, "rc")
    assert rc.count("_add") == 4 and rc.count("M1_m") == 1


def test_tracks_refuse_an_unexpected_count():
    with pytest.raises(SystemExit):
        al.append_lines(HYB_TRACKS, "", al.TRACK, 7, "tracks")


HBRDL = al.config_edits("hbrdl")                           # without the -gcell_size line
CONFIG = "\n".join(old for old, _ in HBRDL) + "\nexport OTHER ?= 1\n"


def test_config_edits_each_line_once_and_nothing_else():
    out = al.patch_config(CONFIG, al.config_edits("hbrdl"))
    assert out.splitlines() == [new for _, new in HBRDL] + ["export OTHER ?= 1"]
    assert "MAX_ROUTING_LAYER ?= M3_add" in out and "lef/asap7_tech_1x_2A6M7M_hbrdl_add.lef" in out
    assert "export ASAP7_HBT_RDL_RCX_RULES ?=\n" in out


def test_config_refuses_a_missing_or_repeated_line():
    with pytest.raises(SystemExit):
        al.patch_config(CONFIG.replace("M2_m", "M4_m"), al.config_edits("hbrdl"))
    with pytest.raises(SystemExit):
        al.patch_config(CONFIG + HBRDL[-1][0] + "\n", al.config_edits("hbrdl"))
    with pytest.raises(SystemExit):                            # --drop-gcell needs the -gcell_size line
        al.patch_config(CONFIG, al.config_edits("hbrdl", True))
    with pytest.raises(SystemExit):                            # and applies to hbrdl only
        al.config_edits("direct", True)


def test_direct_view_is_pinned_and_extracts_on_the_2a_deck():
    news = [new for _, new in al.config_edits("direct")]
    assert news[0] == "override export ASAP7_HBT_RDL := 0"
    assert news[-1] == "override export RCX_RULES := $(PLATFORM_DIR)/asap7_tech_1x_2A6M7M.rcx_patterns.rules"
    assert "export PIN3D_REQUIRE_RCX_LAYER_MATCH := 1" in news   # the flow checks the deck against the tech
    assert all("_hbrdl" not in new and "gcell" not in new for new in news)


ROUTING = re.compile(r"^LAYER (\S+)\n(?:(?!^END ).*\n)*?\s*TYPE ROUTING ;", re.MULTILINE)


@real
def test_direct_layers_and_deck_match_the_kits_2a_stack():
    kit = (PIN3D / "platforms/rc_extract/input/asap7_tech_1x_2A6M7M.lef").read_text(encoding="utf-8")
    ours = al.build(PIN3D, with_config=False, view="direct")[al.a7_files("direct", "_add")["lef"]]
    for layer in ("V1_add", "M2_add", "V2_add", "M3_add"):
        block = re.compile(rf"^LAYER {layer}\n.*?^END {layer}\n", re.MULTILINE | re.DOTALL)
        assert block.search(ours).group(0) == block.search(kit).group(0), layer
    layers = ROUTING.findall(ours)            # what final_report.tcl's check counts, in the order the deck models
    assert layers == ROUTING.findall(kit) and len(layers) == 15
    deck = (PIN3D / al.DIRECT_DECK).read_text(encoding="utf-8")
    assert re.search(r"LayerCount\s+15\b", deck)


@real
def test_real_checkout_is_the_pinned_commit():
    head = subprocess.run(["git", "-C", str(PIN3D), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout
    assert head.startswith("51a19d6f")


@real
@pytest.mark.parametrize("view, drop_gcell", [("hbrdl", False), ("hbrdl", True), ("direct", False)])
def test_real_files_take_every_edit_and_only_those(view, drop_gcell):
    out = al.build(PIN3D, with_config=True, drop_gcell=drop_gcell, view=view)   # builds in memory, writes nothing
    cfg = (PIN3D / al.CONFIG).read_text(encoding="utf-8").splitlines()
    new = out[al.CONFIG].splitlines()
    changed = [(a, b) for a, b in zip(cfg, new, strict=True) if a != b]
    assert changed == al.config_edits(view, drop_gcell)
    if view == "hbrdl":
        assert ("-gcell_size $(" in out[al.CONFIG]) != drop_gcell
    else:                                     # the line stays, inside the hbrdl block the pin switches off
        assert "override export ASAP7_HBT_RDL := 0" in new
    lef = out[al.a7_files(view, "_add")["lef"]]
    order = [lef.index(s) for s in ("END M1_m", "LAYER V1_add", "END M3_add", "VIA VIA_M1m_M2add",
                                    "VIA VIA_M2add_M3add", "VIARULE ")]
    assert order == sorted(order)
    orig = (PIN3D / al.a7_files(view)["lef"]).read_text(encoding="utf-8")
    assert lef.count("\n") - orig.count("\n") == 101          # 4 layers + 2 vias, nothing else
    for p in al.a7_files(view, "_add").values():
        assert not (PIN3D / p).exists()                        # the tracked checkout is untouched
