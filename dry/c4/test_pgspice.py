"""pgspice: reading write_pg_spice files and joining PDNSim's voltage file, on a hand-made two-node-per-side case."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import pgspice  # noqa: E402

SP_VDD = """* Netlist for VDD on tt

* Resistive network
R0 Node_M2_0_0 Node_M1_1000_0 R=2.000000e+00
R1 Node_M1_1000_0 ITermNode_M1_1000_0 R=1.000000e-03

* Sinks
* Sink for u1/VDD
I0 ITermNode_M1_1000_0 0 DC 1.000e-03

* Sources
V0 Node_M2_0_0 0 DC 0.700000
"""


def write(tmp_path, net, sp, csv_rows):
    (tmp_path / f"pg_{net}.sp").write_text(sp, encoding="utf-8")
    (tmp_path / f"v_{net}.csv").write_text("Instance,Terminal,Layer,X location,Y location,Voltage\n"
                                           + "".join(f"{r}\n" for r in csv_rows), encoding="utf-8")


def test_supply_net_draws_current_and_joins_on_position(tmp_path):
    write(tmp_path, "VDD", SP_VDD, ["u1,VDD,M1,1.0000,0.0000,0.697999", "u2,VDD,M1,5.0000,0.0000,0.7"])
    out = pgspice.compare(str(tmp_path), "VDD", 1000)
    # 1 mA through 2.001 ohm: 0.7 - 0.002001
    assert out["ours_worst_v"] == pytest.approx(0.7 - 1e-3 * 2.001)
    assert out["terminals_matched"] == 1 and out["terminals_unmatched"] == 1
    assert out["max_abs_diff_v"] < 2e-6


def test_ground_net_receives_current(tmp_path):
    sp = SP_VDD.replace("0.700000", "0.000000")
    write(tmp_path, "VSS", sp, ["u1,VSS,M1,1.0000,0.0000,0.002001"])
    out = pgspice.compare(str(tmp_path), "VSS", 1000)
    assert out["ours_worst_v"] == pytest.approx(2.001e-3)
    assert out["max_abs_diff_v"] < 1e-12


def test_bad_netlists_are_refused(tmp_path):
    p = tmp_path / "x.sp"
    p.write_text("R0 a b R=-1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-positive"):
        pgspice.read_spice(str(p))
    p.write_text("R0 a b R=1\nV0 a 0 DC 0.7\nV1 b 0 DC 0.6\n", encoding="utf-8")
    with pytest.raises(ValueError, match="several voltages"):
        pgspice.solve_spice(str(p))


def test_name_parsing_keeps_underscores_in_the_type():
    assert pgspice.parse_name("ITerm_Node_M1_120_-40") == ("ITerm_Node", "M1", 120, -40)
    assert json.dumps(pgspice.parse_name("Node_M2_0_0")) == '["Node", "M2", 0, 0]'
