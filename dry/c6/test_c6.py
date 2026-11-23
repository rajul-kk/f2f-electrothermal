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


def test_margin_raises_the_upper_end_until_runaway():
    calls = []

    class O:
        def __init__(self, st):
            self.status = st

    def classify(R, dyn, leak, amb):
        return O("converged" if leak < 5e3 else "runaway")

    def crit(R, dyn, make, amb, lo, hi, rtol):
        calls.append(hi)
        if make(hi) < 5e3:
            raise RuntimeError("bracket")
        return 4.9e3, 5.0e3, 20
    m = c6.margin(classify, crit, None, None, lambda s: s)
    assert calls == [1e3, 1e4] and m["s_lo"] == 4.9e3
    assert "error" in c6.margin(classify, lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
                                None, None, lambda s: 1.0 if s < 1e6 else 1e9)
    assert np.isfinite(m["probes"])


def test_summary_ratios_against_the_matching_frontside_stack():
    def case(stack, rise, s):
        return {"stack": stack, "workload": "uniform", "vt": "svt", "peak_rise_no_leak_k": rise, "status": "converged",
                "peak_t_k": 300 + rise, "rho": 0.1, "s_lo": s, "crit_leak_w_mm2_25c": s * 1e-3}
    res = {"stacks": {"fs_kbeol1.2": {"check_a_rel": 0.02}, "bs_kbeol1.2_tc50_kbs71": {"check_a_rel": 0.2}},
           "checks": {"b_max_abs_diff_k": 0.004, "d_rel": 1e-5},
           "cases": [case("fs_kbeol1.2", 2.0, 40.0), case("bs_kbeol1.2_tc50_kbs71", 3.0, 20.0)]}
    md = c6.summary(res)
    assert "| 1 of 2; outside: bs_kbeol1.2_tc50_kbs71 +20.0% |" in md
    row = next(line for line in md.splitlines() if line.startswith("| bs_kbeol1.2_tc50_kbs71"))
    assert "| 1.50 |" in row and "| 0.50 |" in row
