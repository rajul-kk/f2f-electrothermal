"""irbuild on a hand-made export: one M1 rail, a via up to an M2 pad held by a block pin, one cell."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import irbuild  # noqa: E402

LOG = """DBU 1000
Supply voltage   : 7.00e-01 V
Layer resistance:
  M1: 2.0 Ohm per square
  V1: 10.0 Ohm per cut
  M2: 1.0 Ohm per square
Layer resistance:
  M1: 99 Ohm per square
"""
HEAD = "kind\tlayer\txlo\tylo\txhi\tyhi\tvia\tbottom\ttop\tcx\tcy\n"


def row(*f):
    return "\t".join(str(x) for x in f)


def via(name, xlo, xhi, cx, cuts):
    """A via row on the rail (y -10..10) and its cut rows, each cut a 10 nm square at x."""
    out = [row("via", "-", xlo, -10, xhi, 10, name, "M1", "M2", cx, 0)]
    out += [row("cut", "V1", x - 5, -5, x + 5, 5, name, "M1", "M2", cx, 0) for x in cuts]
    return out


def export(tmp_path, cell_x=(900, 1100), power=7e-4, extra=()):
    rows = [row("wire", "M1", 0, -10, 2000, 10, "-", "-", "-", "-", "-")]     # rail 2 um long, 20 nm wide
    rows += via("VIA12", -10, 10, 0, (-3, 3))                                   # small via at x = 0, 2 cuts
    rows += [row("bterm", "M2", -20, -20, 20, 20, "VDD", "-", "-", "-", "-")] + list(extra)
    (tmp_path / "export.log").write_text(LOG, encoding="utf-8")
    (tmp_path / "geom_VDD.tsv").write_text(HEAD + "\n".join(rows) + "\n", encoding="utf-8")
    (tmp_path / "iterms_VDD.tsv").write_text(
        "inst\tpin\tplaced\txlo\tylo\txhi\tyhi\n" + row("u1", "VDD", 1, cell_x[0], -10, cell_x[1], 10) + "\n",
        encoding="utf-8")
    (tmp_path / "inst_power.tsv").write_text(f"inst\tpower_w\nu1\t{power}\n", encoding="utf-8")
    return str(tmp_path)


def test_point_load_on_a_rail_matches_the_series_resistance(tmp_path):
    d = export(tmp_path)
    _, v, pins, info = irbuild.solve_mesh(d, "VDD", pin_mode="point")
    # 1 mA: via 10 / 2 cuts = 5 ohm, rail 1 um at 2 ohm/sq over 0.02 um = 100 ohm, pin 1 mOhm
    assert info["sources"] == 1 and info["total_current_a"] == pytest.approx(1e-3)
    assert 0.7 - v[pins["u1"][0][0]] == pytest.approx(1e-3 * (5 + 100 + 1e-3), rel=1e-9)


def test_spread_load_averages_the_rail_under_the_pin(tmp_path):
    d = export(tmp_path)
    _, v, pins, _ = irbuild.solve_mesh(d, "VDD", pin_mode="spread")
    # with no other rail node under the pin, spread is the centre node alone: same drop without the 1 mOhm
    assert 0.7 - v[pins["u1"][0]].mean() == pytest.approx(1e-3 * 105, rel=1e-9)


def test_a_repeated_via_row_and_cut_box_count_once(tmp_path):
    d = export(tmp_path, extra=via("VIA12", -10, 10, 0, (-3,)))
    _, v, pins, info = irbuild.solve_mesh(d, "VDD", pin_mode="point")
    assert info["duplicate_vias"] == 1
    assert 0.7 - v[pins["u1"][0][0]] == pytest.approx(1e-3 * (5 + 100 + 1e-3), rel=1e-9)


def test_a_long_via_array_gets_a_node_pair_per_cut(tmp_path):
    extra = via("VIAL", 0, 1200, 600, (400, 800)) + via("VIAS", 1300, 2000, 1650, (1400,))
    mesh, _, _, _ = irbuild.solve_mesh(export(tmp_path, extra=extra), "VDD", pin_mode="point")
    for x in (400, 800):                       # 1.2 um > ARRAY_UM: one node pair per cut
        assert ("M1", x, 0) in mesh.index and ("M2", x, 0) in mesh.index
    assert ("M1", 600, 0) not in mesh.index
    assert ("M1", 1650, 0) in mesh.index       # 0.7 um: one pair at the via centre


def test_ties_short_the_rail_under_a_pin(tmp_path):
    d = export(tmp_path, extra=via("VIAX", 1040, 1060, 1050, (1050,)))   # a second rail node under the pin
    mesh, v, _, _ = irbuild.solve_mesh(d, "VDD", pin_mode="ties")
    a, b = mesh.index[("M1", 1000, 0)], mesh.index[("M1", 1050, 0)]
    # 5 ohm of rail between them is bypassed by two 1 mOhm ties
    assert abs(v[a] - v[b]) < 1e-3 * 1e-2
    _, _, pins, _ = irbuild.solve_mesh(d, "VDD", pin_mode="spread")
    assert len(pins["u1"]) == 1 and len(pins["u1"][0]) == 2


def test_layer_resistance_reads_the_first_block_only():
    assert irbuild.layer_resistance(LOG) == {"M1": 2.0, "V1": 10.0, "M2": 1.0}


def test_effective_cuts_follow_the_cut_class_either_way_round():
    classes = irbuild.cut_classes(dbu=1000)
    assert irbuild.effective_cuts("V5", 24, 288, classes) == 8
    assert irbuild.effective_cuts("V5", 288, 24, classes) == 8
    assert irbuild.effective_cuts("V5", 24, 32, classes) == 1       # Vx has no CUTS: one cut
    assert irbuild.effective_cuts("V1", 18, 18, classes) == 1


def test_a_pin_off_every_rail_is_refused(tmp_path):
    d = export(tmp_path)
    (tmp_path / "iterms_VDD.tsv").write_text(
        "inst\tpin\tplaced\txlo\tylo\txhi\tyhi\n" + row("u1", "VDD", 1, 900, 500, 1100, 520) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no M1 rail"):
        irbuild.solve_mesh(d, "VDD")


def test_a_power_that_is_not_a_number_is_refused(tmp_path):
    with pytest.raises(ValueError, match="not a number"):
        irbuild.solve_mesh(export(tmp_path, power="-nan"), "VDD")


def test_a_pin_beyond_the_end_of_its_rail_is_refused(tmp_path):
    with pytest.raises(ValueError, match="no M1 rail"):
        irbuild.solve_mesh(export(tmp_path, cell_x=(2100, 2300)), "VDD")    # the rail ends at x = 2000


def test_the_supply_is_the_positive_one_whatever_the_net_order(tmp_path):
    d = export(tmp_path)
    (tmp_path / "export.log").write_text(LOG.replace("Supply voltage   : 7.00e-01 V",
                                                     "Supply voltage   : 0.00e+00 V\nSupply voltage   : 7.00e-01 V"),
                                         encoding="utf-8")
    assert irbuild.read_export_log(d)[1] == 0.7


def test_an_instance_takes_its_worst_pin_and_splits_current_over_pins(tmp_path):
    d = export(tmp_path)
    (tmp_path / "iterms_VDD.tsv").write_text(
        "inst\tpin\tplaced\txlo\tylo\txhi\tyhi\n" + row("u1", "VDD", 1, 900, -10, 1100, 10) + "\n"
        + row("u1", "VDD2", 1, 1900, -10, 2000, 10) + "\n", encoding="utf-8")
    _, v, pins, info = irbuild.solve_mesh(d, "VDD", pin_mode="point")
    near, far = (0.7 - v[ns[0]] for ns in pins["u1"])
    # 0.5 mA each: the shared 5 ohm via carries 1 mA; rail to x = 1000 carries both, 1000 -> 1950 the far pin's
    assert near == pytest.approx(1e-3 * 5 + 1e-3 * 100 + 0.5e-3 * 1e-3, rel=1e-9)
    assert far == pytest.approx(near + 0.5e-3 * 95, rel=1e-9)
    worst = irbuild.instance_voltages(v, pins, "VDD")["u1"]
    assert 0.7 - worst == pytest.approx(far)                # the lower of the two pins, not their mean


def test_metrics_compare_by_name():
    m = irbuild.metrics({"a": 0.69, "b": 0.70}, {"a": 0.689, "c": 0.7}, "VDD", 0.7)
    assert m["instances_compared"] == 1 and m["only_ours"] == 1 and m["only_pdnsim"] == 1
    assert m["max_abs_diff_uv"] == pytest.approx(1000)


def test_overlapping_wires_counts_shared_area_not_touching_edges():
    w = [{"layer": "M3", "xlo": a, "ylo": b, "xhi": c, "yhi": e} for a, b, c, e in
         ((0, 0, 10, 10), (5, 5, 15, 15), (10, 0, 20, 10), (30, 0, 40, 10))]
    w.append({"layer": "M4", "xlo": 0, "ylo": 0, "xhi": 10, "yhi": 10})
    assert irbuild.overlapping_wires(w) == 2       # (0-10, 5-15) and (5-15, 10-20); edge-touching and M4 not


def test_a_net_other_than_vdd_or_vss_is_refused(tmp_path):
    with pytest.raises(ValueError, match="only VDD"):
        irbuild.solve_mesh(export(tmp_path), "VDDA")


def test_two_nodes_across_a_wire_at_one_position_are_refused(tmp_path):
    # a long array with two cuts side by side at x = 400 (y -3 and +3): two M1 nodes at one x on the 20 nm rail
    extra = [row("via", "-", 0, -10, 1200, 10, "VIAL", "M1", "M2", 600, 0),
             row("cut", "V1", 395, -8, 405, 2, "VIAL", "M1", "M2", 600, 0),
             row("cut", "V1", 395, -2, 405, 8, "VIAL", "M1", "M2", 600, 0)]
    with pytest.raises(ValueError, match="one position"):
        irbuild.solve_mesh(export(tmp_path, extra=extra), "VDD", pin_mode="point")
