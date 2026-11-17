"""Tests for c2diag.py: the log classifier, value parsing, node selection, the ratio checks and the option rewrite."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import c2diag as cd  # noqa: E402

SUB = """.subckt cell A B Y VDD VSS
NM1 Y A net1 VSS 0 nmos_svt WGAA=0.011u L=0.012u M=1
NM2 net1 B VSS VSS 0 nmos_svt WGAA=0.011u L=0.012u M=1
NM3 Y A VDD VDD 0 pmos_svt WGAA=0.011u L=0.012u M=1
.ends cell
"""


@pytest.mark.parametrize("log, rc, want", [
    ("Note: Simulation executed", "0", "newton"),
    ("Note: Starting dynamic gmin stepping\nNote: Dynamic gmin stepping completed", "0", "gmin stepping"),
    ("Warning: source stepping failed\nNote: Source stepping completed", "0", "source stepping"),
    ("Note: Dynamic gmin stepping completed\nNote: Transient op finished successfully", "0", "transient op"),
    ("anything", "1", "failed"),
    ("anything", "124", "failed"),
    ("", "missing", "failed"),
])
def test_method(log, rc, want):
    assert cd.method(log, rc) == want


def test_values_lower_cases_and_reads_both_kinds():
    v = cd.values("i(vdd7) = -1.5e-12\nv(o7_Y) = 6.999e-01\nv(x7.net1) = 4.3e-02\n")
    assert v == {"i(vdd7)": -1.5e-12, "v(o7_y)": 0.6999, "v(x7.net1)": 0.043}


def test_internal_nodes_excludes_ports_and_ground():
    assert cd.internal_nodes(SUB) == ["net1"]


CASE = {"cell": "c", "when": "(A * !Y)", "outs": {"Y": 0}, "liberty_w": 1e-12}


@pytest.mark.parametrize("log, want", [
    ("i(vdd3) = -2e-12\nv(o3_Y) = 1e-6\n", 1.4),         # 2e-12 A x 0.7 V / 1e-12 W
    ("i(vdd3) = 2e-12\nv(o3_Y) = 1e-6\n", None),          # supply sinks current
    ("i(vdd3) = -nan\nv(o3_Y) = 1e-6\n", None),           # not finite
    ("v(o3_Y) = 1e-6\n", None),                           # no current
    ("i(vdd3) = -2e-12\nv(o3_Y) = 0.2\n", None),          # output not at its literal (V2)
])
def test_ratio_checks(log, want):
    got = cd.ratio(log, CASE, 3, 0.7)
    assert got == pytest.approx(want) if want is not None else got is None


def test_variant_replaces_and_extends_the_option_line(tmp_path):
    src = tmp_path / "states"
    src.mkdir()
    for f in ("models.inc", ".spiceinit"):
        (src / f).write_text("x\n", encoding="utf-8")
    deck = "* d\n.temp -40\n.option gmin=1e-18 abstol=1e-18 reltol=1e-5\n.include models.inc\n.end\n"
    for s in ("s0001", "s0002"):
        (src / f"{s}.cir").write_text(deck, encoding="utf-8")
    (src / "summary.json").write_text(json.dumps({"s0001": {"method": "transient op"},
                                                  "s0002": {"method": "newton"}}), encoding="utf-8")
    out = tmp_path / "v"
    cd.variant(str(src), str(out), "g", "gmin=1e-14 itl1=5000", "hard", 0)
    assert sorted(p.name for p in out.glob("*.cir")) == ["g_s0001.cir"]
    text = (out / "g_s0001.cir").read_text(encoding="utf-8")
    assert ".option gmin=1e-14 abstol=1e-18 reltol=1e-5 itl1=5000\n" in text
    assert (out / "models.inc").exists() and (out / ".spiceinit").exists()
