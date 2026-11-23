"""Tests for add_layers.py on miniature copies of the two platforms' files."""
import pytest

import add_layers as al

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


def test_lef_refuses_a_second_application():
    with pytest.raises(SystemExit):
        al.patch_lef(HYB_LEF, al.patch_lef(HYB_LEF, A7_LEF))


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
