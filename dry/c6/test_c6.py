"""Tests for c6.py's host-side parts: Liberty areas, leakage density, stacks, the 1-D estimate and the power maps."""
import numpy as np
import pytest

import c6

LIB = """library (x) {
  cell (inv_x1) {
    area : 0.0112 ;
    pin (A) { capacitance : 0.5 ; }
  }
  cell ("nand2_x1") {
    cell_footprint : nand2 ;
    area : 0.0168 ;
  }
}
"""


def test_liberty_areas_takes_each_cells_own_area():
    assert c6.liberty_areas(LIB) == {"inv_x1": 0.0112, "nand2_x1": 0.0168}


def test_leak_density_is_mean_power_over_mean_area_times_utilisation():
    tables = {"temps_c": [25, 125], "vt": {vt: {"inv_x1": {"mean": [1e-12, 2e-12]},
                                                "nand2_x1": {"mean": [3e-12, 6e-12]},
                                                "bad_x1": {"mean": [None, 1e-12]}} for vt in c6.VTS}}
    areas = {vt: {"inv_x1": 0.01, "nand2_x1": 0.03} for vt in c6.VTS}
    d = c6.leak_density(tables, areas)["svt"]
    assert d["cells"] == 2                                   # a cell with an empty mean is left out
    assert d["w_mm2"][0] == pytest.approx(2e-12 / 0.02e-6 * c6.UTIL)
    with pytest.raises(SystemExit):
        c6.leak_density(tables, {vt: {"inv_x1": 0.01} for vt in c6.VTS})


def test_stacks_count_names_and_shared_layers():
    s = c6.stacks()
    assert len(s) == 3 + 12
    fs, bs = s["fs_kbeol1.2"], s["bs_kbeol1.2_tc50_kbs71"]
    assert fs["layers"][:2] == bs["layers"][:2]              # same spreader and TIM
    assert [l["name"] for l in bs["layers"]] == ["spreader", "tim", "carrier", "bond", "beol", "die", "bspdn"]
    die = next(l for l in bs["layers"] if l.get("die"))
    assert die["source_side"] == "top" and die["thickness_um"] == 0.5


def test_each_stack_lists_only_the_materials_its_layers_use():
    for name, st in c6.stacks().items():
        used = {l["material"] for l in st["layers"]}
        assert set(st["materials"]) - set(c6.BASE_MATERIALS) == used - set(c6.BASE_MATERIALS), name
    assert c6.stacks(grid=8)["fs_kbeol0.6"]["grid"] == [8, 8]


def test_one_d_estimate_by_hand():
    area = 1e-6
    fs = c6.stacks()["fs_kbeol1.2"]
    hand = 1 / (c6.HTC * area) + 500e-6 / (400 * area) + 25e-6 / (4 * area) + 49e-6 / (130 * area)
    assert c6.one_d_k_per_w(fs) == pytest.approx(hand)
    bs = c6.stacks()["bs_kbeol1.2_tc50_kbs71"]
    extra = 50e-6 / (130 * area) + 1e-6 / (1.4 * area) + 5e-6 / (1.2 * area) + 0.05e-6 / (130 * area)
    assert c6.one_d_k_per_w(bs) == pytest.approx(hand - 49e-6 / (130 * area) + extra)


def test_hotspot_keeps_the_total_and_is_ten_times_denser():
    u, h = c6.dyn_tiles("uniform"), c6.dyn_tiles("hotspot")
    assert h.sum() == pytest.approx(u.sum()) == pytest.approx(c6.DYN_W_MM2 * 1.0)
    assert h.max() / h.min() == pytest.approx(c6.HOT_X) and (h == h.max()).sum() == c6.HOT_TILES ** 2
    with pytest.raises(SystemExit):
        c6.dyn_tiles("other")


def test_margin_uses_designs_fixed_bracket_only():
    calls = []

    def crit(R, dyn, make, amb, lo, hi, rtol):
        calls.append((lo, hi))
        return 9.9, 10.0, 20
    m = c6.margin(crit, None, None, None)
    assert calls == [c6.BRACKET] and m == {"s_lo": 9.9, "s_hi": 10.0, "probes": 20}


def test_margin_returns_the_bracket_failure_and_lets_other_errors_through():
    def outside(*a, **k):
        raise RuntimeError("bracket [0.001, 1000] does not contain the boundary")
    assert "does not contain" in c6.margin(outside, None, None, None)["error"]

    def broken(*a, **k):
        raise np.linalg.LinAlgError("singular")
    with pytest.raises(np.linalg.LinAlgError):     # run_cases records it per case (A16), margin does not hide it
        c6.margin(broken, None, None, None)


def test_summary_ratios_against_the_matching_frontside_stack():
    def case(stack, rise, s):
        return {"stack": stack, "workload": "uniform", "vt": "svt", "peak_rise_no_leak_k": rise, "status": "converged",
                "peak_t_k": 300 + rise, "rho": 0.1, "s_lo": s, "crit_leak_w_mm2_25c": s * 1e-3}
    res = {"stacks": {"fs_kbeol1.2": {"check_a_rel": 0.02}, "bs_kbeol1.2_tc50_kbs71": {"check_a_rel": 0.2}},
           "checks": {"b_max_abs_diff_k": 0.004, "d_rel": 1e-5},
           "cases": [case("fs_kbeol1.2", 2.0, 40.0), case("bs_kbeol1.2_tc50_kbs71", 3.0, 20.0)]}
    md = c6.summary(res)
    assert md.startswith("**Incomplete run")                  # no end marker
    assert "| 1 of 2; outside: bs_kbeol1.2_tc50_kbs71 +20.0% | FAIL |" in md
    assert "| 0.0040 K | PASS |" in md
    row = next(line for line in md.splitlines() if line.startswith("| bs_kbeol1.2_tc50_kbs71"))
    assert "| 1.50 |" in row and "| 0.50 |" in row


def test_checks_fail_on_missing_or_out_of_limit_values():
    base = {"stacks": {"fs_kbeol1.2": {"check_a_rel": 0.0}}, "checks": {"d_rel": 0.0}, "complete": True,
            "cases": [{"stack": "fs_kbeol1.2", "workload": "uniform", "vt": "svt", "peak_rise_no_leak_k": 1.0,
                       "error": "RuntimeError: bracket"}]}
    rows = {name[0]: ok for name, _, ok in c6.check_rows(base)}
    assert rows == {"a": True, "b": False, "c": False, "d": True}      # b missing, c has an error
    base["checks"]["b_max_abs_diff_k"] = 0.006
    assert not {n[0]: ok for n, _, ok in c6.check_rows(base)}["b"]
    assert not c6.summary(base).startswith("**Incomplete")
    assert not c6.check_rows({"stacks": {}, "checks": {"d_rel": 0.0}, "cases": []})[0][2]   # empty a fails
