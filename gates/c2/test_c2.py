"""Tests for C2's harness: per-state logs and the DC-point check in leak.compare (Amendment 2), the floor cut in
evaluate (Amendment 2), and Amendment 4's retry deck, kit floor per state and per-state cut."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import evaluate as ev  # noqa: E402
import leak  # noqa: E402

INV = "gtA5_cfet_11_inv_x1_svt"


def write_case(d, i, log, rc="0"):
    (d / f"s{i:04d}.log").write_text(log, encoding="utf-8")
    (d / f"s{i:04d}.rc").write_text(rc + "\n", encoding="utf-8")


def run_compare(tmp_path, logs):
    cases = [{"cell": INV, "when": "(A * !Y)", "lit": {"A": 1, "Y": 0}, "outs": {"Y": 0}, "liberty_w": 1e-12,
              "pmos": []} for _ in logs]
    (tmp_path / "cases.json").write_text(json.dumps({"vdd": 0.7, "cases": cases}), encoding="utf-8")
    for i, (log, rc) in enumerate(logs):
        write_case(tmp_path, i, log, rc)
    leak.compare(str(tmp_path))
    return json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))["cases"]


def test_compare_reads_one_log_per_state_and_rejects_the_transient_op(tmp_path):
    ok = "i(vdd{i}) = -1.0e-12\nv(o{i}_y) = 1.0e-6\n"
    got = run_compare(tmp_path, [(ok.format(i=0), "0"),
                                 (ok.format(i=1) + "Note: Transient op finished successfully\n", "0"),
                                 (ok.format(i=2) + "Note: Dynamic gmin stepping completed\n", "0"),
                                 ("", "missing")])
    assert [c["method"] for c in got] == ["newton", "transient op", "gmin stepping", "failed"]
    assert got[0]["invalid"] is None and got[0]["spice_w"] == pytest.approx(0.7e-12)
    assert got[1]["invalid"] == "no DC point (transient op)" and got[1]["spice_w"] is None
    assert got[2]["invalid"] is None
    assert got[3]["invalid"] == "ngspice exit code missing"


def case(cell, when, liberty, ratio, out_err=0.0):
    return {"cell": cell, "when": when, "liberty_w": liberty, "ratio": ratio, "invalid": None, "out_err_v": out_err}


def lib(cases):
    return {"temp": 25, "vt": "svt", "vdd": 0.7, "dropped": [], "skipped": {}, "cases": cases}


CUT = 100 * 7.0e-15 * 0.7   # 4.9e-13 W


def test_states_below_the_floor_cut_are_listed_not_scored():
    s = ev.score(lib([case(INV, "(!A * Y)", 1e-11, 1.00), case(INV, "(A * !Y)", 1e-11, 1.01),
                      case("x", "(A)", CUT * 0.5, 0.3)]))
    assert s["verdict"] == "EXACT" and s["cases_scored"] == 2 and len(s["below_floor"]) == 1
    assert s["floor_cut_w"] == pytest.approx(CUT)


def test_a_library_with_every_state_below_the_cut_is_listed_only():
    s = ev.score(lib([case(INV, "(!A * Y)", CUT / 10, 0.5), case(INV, "(A * !Y)", CUT / 10, 0.4)]))
    assert s["verdict"] == "LISTED ONLY" and s["rN"] is None and s["rP"] is None


def test_a_reference_below_the_cut_allows_only_exact_or_fail():
    cases = [case(INV, "(!A * Y)", 1e-11, 0.95), case(INV, "(A * !Y)", CUT / 2, 0.90), case("x", "(A)", 1e-11, 0.96)]
    s = ev.score(lib(cases))
    assert s["rP"] is None and s["verdict"] == "FAIL"
    cases[1]["liberty_w"] = 1e-11
    assert ev.score(lib(cases))["verdict"] == "DEVICE OFFSET"


def test_a_missing_or_doubled_reference_still_voids_the_library():
    s = ev.score(lib([case(INV, "(!A * Y)", 1e-11, 1.0), case("x", "(A)", 1e-11, 1.0)]))
    assert s["verdict"] == "VOID" and s["reference_problems"] == ["reference (A * !Y): 0 cases"]
    two = [case(INV, "(!A * Y)", 1e-11, 1.0)] * 2 + [case(INV, "(A * !Y)", 1e-11, 1.0)]
    assert ev.score(lib(two))["verdict"] == "VOID"


def test_a_state_exactly_at_the_cut_is_scored():
    s = ev.score(lib([case(INV, "(!A * Y)", CUT, 1.0), case(INV, "(A * !Y)", CUT, 1.0)]))
    assert s["cases_scored"] == 2 and not s["below_floor"]


def test_listed_cells_count_for_v4():
    cells = [case(f"c{k}", "(A)", CUT / 2, 0.5) for k in range(ev.MIN_CELLS)]
    s = ev.score(lib([case(INV, "(!A * Y)", 1e-11, 1.0), case(INV, "(A * !Y)", 1e-11, 1.0)] + cells))
    assert s["V4"] and s["cases_scored"] == 2


def test_an_invalid_state_below_the_cut_is_named_not_voiding():
    bad = case("x", "(A)", CUT / 2, None, out_err=None)
    bad["invalid"] = "no DC point (transient op)"
    s = ev.score(lib([case(INV, "(!A * Y)", 1e-11, 1.0), case(INV, "(A * !Y)", 1e-11, 1.0), bad]))
    assert s["V1"] and s["V2"] and s["verdict"] == "EXACT"
    assert s["invalid_below_floor"] == ["x (A): no DC point (transient op)"]


def test_a_wrong_output_below_the_cut_is_named_not_voiding():
    off = case("x", "(A)", CUT / 2, 0.5, out_err=0.5)
    s = ev.score(lib([case(INV, "(!A * Y)", 1e-11, 1.0), case(INV, "(A * !Y)", 1e-11, 1.0), off]))
    assert s["V2"] and s["out_err_below_floor"] == ["x (A): 0.5 V"]
    off["liberty_w"] = 1e-11
    assert not ev.score(lib([case(INV, "(!A * Y)", 1e-11, 1.0), case(INV, "(A * !Y)", 1e-11, 1.0), off]))["V2"]


NAND2_X2 = """.subckt gtA5_cfet_11_nand2_x2_svt A B Y VDD VSS
NMM8 net17 A VSS VSS 0 nmos_svt WGAA=0.011u L=0.012u M=1
NMM7 Y B net17 VSS 0 nmos_svt WGAA=0.011u L=0.012u M=1
NMM2 Y A VDD VDD 0 pmos_svt WGAA=0.011u L=0.012u M=2
NMM0 net9 B VDD VDD 0 pmos_svt WGAA=0.011u L=0.012u
.ends gtA5_cfet_11_nand2_x2_svt
"""


def test_pmos_junctions_name_nodes_as_print_all_does():
    got = leak.pmos_junctions(NAND2_X2, ["A", "B", "Y", "VDD", "VSS"], ["i3_A", "i3_B", "o3_Y", "vdd3", "0"], 3)
    assert got == [[2, "vdd3", ["n.x3.nmm2#di", "o3_y"], ["n.x3.nmm2#si", "vdd3"]],
                   [1, "vdd3", ["n.x3.nmm0#di", "x3.net9"], ["n.x3.nmm0#si", "vdd3"]]]


def test_kit_floor_counts_each_biased_junction_times_m():
    pmos = [[2, "vdd3", ["n.x3.nmm2#di", "o3_y"], ["n.x3.nmm2#si", "vdd3"]],
            [1, "vdd3", ["n.x3.nmm0#di", "x3.net9"], ["n.x3.nmm0#si", "vdd3"]]]
    # drain of nmm2 low (2 fingers), nmm0 has no internal nodes: falls back to x3.net9 at 0.35 V
    volts = {"vdd3": 0.7, "o3_y": 0.0, "n.x3.nmm2#di": 0.0, "n.x3.nmm2#si": 0.7, "x3.net9": 0.35}
    assert leak.kit_floor_w(pmos, volts, 0.7) == pytest.approx(1e-14 * (2 * 0.7 + 0.35) * 0.7)
    assert leak.kit_floor_w(pmos, {"vdd3": 0.7}, 0.7) is None
    assert leak.kit_floor_w([[1, "vdd3", ["0"], ["vdd3"]]], {"vdd3": 0.7}, 0.7) == pytest.approx(0.7e-14 * 0.7)


def test_compare_uses_the_retry_only_when_the_first_deck_has_no_dc_point(tmp_path):
    pm = [[1, "vdd{i}", ["n.x{i}.nm2#di"], ["n.x{i}.nm2#si"]]]
    cases = [{"cell": INV, "when": "(A * !Y)", "lit": {"A": 1, "Y": 0}, "outs": {"Y": 0}, "liberty_w": 1e-12,
              "pmos": [[m, e.format(i=i), [d.format(i=i) for d in di], [s.format(i=i) for s in si]]
                       for m, e, di, si in pm]} for i in range(2)]
    (tmp_path / "cases.json").write_text(json.dumps({"vdd": 0.7, "cases": cases}), encoding="utf-8")
    log = ("i(vdd{i}) = -{c}e-12\nv(o{i}_y) = 1.0e-6\nvdd{i} = 7.000000e-01\nn.x{i}.nm2#di = 1.0e-6\n"
           "n.x{i}.nm2#si = 7.000000e-01\nvdd{i}#branch = -{c}e-12\n")
    write_case(tmp_path, 0, log.format(i=0, c=1.0))
    write_case(tmp_path, 1, log.format(i=1, c=9.0) + "Note: Transient op finished successfully\n")
    (tmp_path / "s0000r.log").write_text(log.format(i=0, c=5.0), encoding="utf-8")   # not used: s0000 has a DC point
    (tmp_path / "s0000r.rc").write_text("0\n", encoding="utf-8")
    (tmp_path / "s0001r.log").write_text(log.format(i=1, c=2.0) + "Note: spice3 gmin stepping completed\n",
                                         encoding="utf-8")
    (tmp_path / "s0001r.rc").write_text("0\n", encoding="utf-8")
    leak.compare(str(tmp_path))
    got = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))["cases"]
    assert [c["retry"] for c in got] == [False, True]
    assert got[1]["first_method"] == "transient op" and got[1]["first_rc"] == "0"
    assert got[0]["spice_w"] == pytest.approx(0.7e-12) and got[1]["spice_w"] == pytest.approx(1.4e-12)
    assert got[1]["method"] == "gmin stepping" and got[1]["invalid"] is None
    assert got[0]["floor_w"] == pytest.approx(1e-14 * (0.7 - 1e-6) * 0.7)


def test_the_cut_scales_with_the_states_own_floor():
    six = case("x", "(A * !Y)", CUT * 3, 0.95)
    six["floor_w"] = 6 * 7.0e-15 * 0.7   # six biased junctions: cut 6 x CUT, so listed
    refs = [case(INV, "(!A * Y)", 1e-11, 1.0), case(INV, "(A * !Y)", 1e-11, 1.0)]
    s = ev.score(lib(refs + [six]))
    assert s["verdict"] == "EXACT" and s["cases_scored"] == 2 and len(s["below_floor"]) == 1
    assert s["floor_check"]["states"] == 1
    assert s["floor_check"]["min"] == pytest.approx(0.95 + 6 * 7.0e-15 * 0.7 / (CUT * 3))
    six["floor_w"] = 0.0   # no biased junction: Amendment 2's one-floor cut, so scored and FAIL
    assert ev.score(lib(refs + [six]))["verdict"] == "FAIL"


def test_a_missing_junction_voltage_makes_the_state_invalid(tmp_path):
    cases = [{"cell": INV, "when": "(A * !Y)", "lit": {"A": 1, "Y": 0}, "outs": {"Y": 0}, "liberty_w": 1e-12,
              "pmos": [[1, "vdd0", ["n.x0.nm2#di"], ["n.x0.nm2#si"]]]}]
    (tmp_path / "cases.json").write_text(json.dumps({"vdd": 0.7, "cases": cases}), encoding="utf-8")
    write_case(tmp_path, 0, "i(vdd0) = -1.0e-12\nv(o0_y) = 1.0e-6\nvdd0 = 7.0e-01\n")   # no `print all` junctions
    leak.compare(str(tmp_path))
    got = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))["cases"][0]
    assert got["invalid"] == "junction voltage missing (kit floor)" and got["ratio"] is None


def test_an_invalid_state_keeps_the_one_floor_cut():
    # no operating point, so no floor: above the one-floor cut it voids, whatever its finger count
    bad = case("x", "(A * !Y)", CUT * 3, None, out_err=None)
    bad["invalid"], bad["floor_w"] = "ngspice exit code 124", None
    s = ev.score(lib([case(INV, "(!A * Y)", 1e-11, 1.0), case(INV, "(A * !Y)", 1e-11, 1.0), bad]))
    assert s["verdict"] == "VOID" and s["invalid"] == ["x (A * !Y): ngspice exit code 124"]


def test_an_invalid_case_voids_the_library():
    bad = case(INV, "(A * !Y)", 1e-11, None)
    bad["invalid"] = "no DC point (transient op)"
    assert ev.score(lib([case(INV, "(!A * Y)", 1e-11, 1.0), bad]))["verdict"] == "VOID"
