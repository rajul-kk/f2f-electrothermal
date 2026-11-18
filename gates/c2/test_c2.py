"""Tests for C2's Amendment 2: per-state logs and the DC-point check in leak.compare, and the floor cut in evaluate."""
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
    cases = [{"cell": INV, "when": "(A * !Y)", "lit": {"A": 1, "Y": 0}, "outs": {"Y": 0}, "liberty_w": 1e-12}
             for _ in logs]
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


def test_an_invalid_case_voids_the_library():
    bad = case(INV, "(A * !Y)", 1e-11, None)
    bad["invalid"] = "no DC point (transient op)"
    assert ev.score(lib([case(INV, "(!A * Y)", 1e-11, 1.0), bad]))["verdict"] == "VOID"
