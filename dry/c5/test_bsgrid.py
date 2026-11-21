import collections
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "c4")]
import irbuild  # noqa: E402

import bsgrid  # noqa: E402

TCL = """set PG_H BSM2
set PG_V BSM3
set PG_STRIPE_VERT BSM1
set PG_RING_WIDTH    1.0
set PG_RING_SPACING  1.1
set PG_RING_OFFSET   0.5
set PG_STRIPE_VERT_WIDTH         0.2
set PG_STRIPE_VERT_SPACING       0.8
set PG_STRIPE_VERT_SET_TO_SET    2.0
set PG_STRIPE_VERT_START_OFFSET  0.0
set PG_STRIPE_HORZ_WIDTH         0.5
set PG_STRIPE_HORZ_SPACING       1.1
set PG_STRIPE_HORZ_SET_TO_SET    3.2
set PG_STRIPE_HORZ_START_OFFSET  2.4
set CORE_PIN_LAYER       BPR
set SROUTE_LAYER_RANGE   {BPR BSM3}
set CFET_OP_VOLTAGE 0.7
set CFET_SITE_X    0.039
set CFET_SITE_Y    0.072
"""
LEF_LAYERS = [("BSM3", "ROUTING", 1.0, 2.0), ("BSV2", "CUT", 0.4, None), ("BSM2", "ROUTING", 0.5, 1.6),
              ("BSV1", "CUT", 0.2, None), ("BSM1", "ROUTING", 0.2, 1.0), ("TSV", "CUT", 0.02, None),
              ("BPR", "ROUTING", 0.024, 0.072)]
VIARULES = """VIA VTSV_0 DEFAULT
  LAYER BPR ;
    RECT -0.045 -0.012 0.045 0.012 ;
  LAYER TSV ;
    RECT -0.045 -0.045 0.045 0.045 ;
  LAYER BSM1 ;
    RECT -0.100 -0.045 0.100 0.045 ;
END VTSV_0
VIA VBSV1_0 DEFAULT
  LAYER BSV1 ;
    RECT -0.100 -0.100 0.100 0.100 ;
  LAYER BSM1 ;
    RECT -0.100 -0.100 0.100 0.100 ;
  LAYER BSM2 ;
    RECT -0.100 -0.250 0.100 0.250 ;
END VBSV1_0
VIA VBSV2_0 DEFAULT
  LAYER BSV2 ;
    RECT -0.250 -0.250 0.250 0.250 ;
  LAYER BSM2 ;
    RECT -0.250 -0.250 0.250 0.250 ;
  LAYER BSM3 ;
    RECT -0.500 -0.250 0.500 0.250 ;
END VBSV2_0
VIARULE ViaTSVArray GENERATE DEFAULT
  LAYER BPR ;
    ENCLOSURE 0.004 0 ;
  LAYER BSM1 ;
    ENCLOSURE 0.004 0 ;
  LAYER TSV ;
    RECT -0.010 -0.010 0.010 0.010 ;
    SPACING 0.020 BY 0.020 ;
END ViaTSVArray
VIARULE ViaBSV1Array GENERATE
  LAYER BSM1 ;
    ENCLOSURE 0 0 ;
  LAYER BSM2 ;
    ENCLOSURE 0 0 ;
  LAYER BSV1 ;
    RECT -0.075 -0.075 0.075 0.075 ;
    SPACING 0.30 BY 0.30 ;
END ViaBSV1Array
VIARULE ViaBSV2Array GENERATE
  LAYER BSM2 ;
    ENCLOSURE 0 0 ;
  LAYER BSM3 ;
    ENCLOSURE 0 0 ;
  LAYER BSV2 ;
    RECT -0.125 -0.125 0.125 0.125 ;
    SPACING 0.50 BY 0.50 ;
END ViaBSV2Array
VIARULE via13 GENERATE DEFAULT
  LAYER M13 ;
    ENCLOSURE 0 0.012 ;
  LAYER RDL ;
    ENCLOSURE 0.012 0 ;
  LAYER V13 ;
    RECT -0.028 -0.028 0.028 0.028 ;
    SPACING 0.112 BY 0.112 ;
END via13
VIARULE via9_10 GENERATE DEFAULT
  LAYER M9 ;
    ENCLOSURE 0 0 ;
  LAYER M10 ;
    ENCLOSURE 0 0 ;
  LAYER V9 ;
    RECT -0.02 -0.03 0.02 0.03 ;
END via9_10
VIARULE viaTSV GENERATE DEFAULT
  LAYER BPR ;
    ENCLOSURE 0 0 ;
  LAYER BSM1 ;
    ENCLOSURE 0.015 0.015 ;
  LAYER TSV ;
    RECT -0.045 -0.045 0.045 0.045 ;
    SPACING 0.18 BY 0.18 ;
END viaTSV
VIARULE viaBSV1 GENERATE DEFAULT
  LAYER BSM1 ;
    ENCLOSURE 0.05 0.05 ;
  LAYER BSM2 ;
    ENCLOSURE 0.15 0.15 ;
  LAYER BSV1 ;
    RECT -0.1 -0.1 0.1 0.1 ;
    SPACING 0.4 BY 0.4 ;
END viaBSV1
VIARULE viaBSV2 GENERATE DEFAULT
  LAYER BSM2 ;
    ENCLOSURE 0.25 0.25 ;
  LAYER BSM3 ;
    ENCLOSURE 0.75 0.75 ;
  LAYER BSV2 ;
    RECT -0.25 -0.25 0.25 0.25 ;
    SPACING 1 BY 1 ;
END viaBSV2
"""
ITF = """CONDUCTOR BPR  {
		THICKNESS=0.032
		RHO_VS_SI_WIDTH_AND_THICKNESS {
			WIDTH { 0.009 0.012 0.016 0.018 0.021 0.027 0.036 0.048 }
			THICKNESS { 0.032 }
			VALUES { 0.132257171 0.127917946 0.125239238 0.124469375 0.123672020 0.122756504 0.122107225 0.121723039 }
		}
}
"""


def macro(vdd_y=(0.06, 0.084), vss_y=(-0.012, 0.012)):
    return "MACRO inv\n" + "".join(
        f"  PIN {n}\n    USE POWER ;\n    PORT\n      LAYER BPR ;\n        RECT -0.0225 {y0} 0.1785 {y1} ;\n"
        f"    END\n  END {n}\n" for n, (y0, y1) in (("VDD", vdd_y), ("VSS", vss_y))) + "END inv\n"


def ict(rho_bsm=0.1, rho_bpr=0.132257171, r_tsv=23.1, r_v1=0.231, r_v2=0.058, v1_layers=("BSM2", "BSM1")):
    c = "".join(f"conductor {n} {{\n  min_width {w}\n  thickness {t}\n  resistivity {r}\n}}\n" for n, w, t, r in
                [("BSM3", 1.0, 1.0, rho_bsm), ("BSM2", 0.5, 0.5, rho_bsm), ("BSM1", 0.2, 0.2, rho_bsm),
                 ("BPR", 0.024, 0.032, rho_bpr)])
    v = "".join(f"# a comment {{ with braces }}\nvia {n} {{\n  bottom_layer {b}\n  top_layer {t}\n  min_width {w}\n"
                f"  area_resistance {r} {w * w}\n}}\n" for n, b, t, w, r in
                [("TSV", "BSM1", "BPR", 0.02, r_tsv), ("VBSM1", *v1_layers, 0.2, r_v1),
                 ("VBSM2", "BSM3", "BSM2", 0.4, r_v2)])
    return c + v


def make_kit(tmp_path, vdd_y=(0.06, 0.084), tcl=TCL, viarules=VIARULES, **kw):
    for d in ("lef", "qrc", "starrc"):
        (tmp_path / d).mkdir(exist_ok=True)
    (tmp_path / "PDK_PATHS.tcl").write_text(tcl)
    (tmp_path / "lef" / "gtA5_cfet.tlef").write_text("".join(
        f"LAYER {n}\n  TYPE {t} ;\n  WIDTH {w} ;\n" + (f"  PITCH {p} ;\n" if p else "") + f"END {n}\n"
        for n, t, w, p in LEF_LAYERS) + viarules)
    (tmp_path / "lef" / "gtA5_cfet_macros.lef").write_text(macro(vdd_y))
    (tmp_path / "qrc" / "GTA5_cfet.ict").write_text(ict(**kw))
    (tmp_path / "starrc" / "GTA5cfet.itf").write_text(ITF)
    return str(tmp_path)


def test_kit_values_come_from_the_files(tmp_path):
    k = bsgrid.kit(make_kit(tmp_path))
    assert k["sheet_ohm_sq"]["BSM1"] == pytest.approx(0.5)
    assert k["sheet_ohm_sq"]["BSM2"] == pytest.approx(0.2)
    assert k["sheet_ohm_sq"]["BSM3"] == pytest.approx(0.1)
    assert k["sheet_ohm_sq"]["BPR"] == pytest.approx(0.132257171 / 0.032)
    assert set(k["via"]) == {"TSV", "BSV1", "BSV2"}                                  # via13 is frontside
    rules = {c: {r["rule"]: r for r in v["rules"]} for c, v in k["via"].items()}
    assert k["via"]["BSV1"]["ict_name"] == "VBSM1" and k["via"]["BSV1"]["metals"] == ["BSM1", "BSM2"]
    # DEFAULT generate rules and fixed DEFAULT vias are candidates; the non-DEFAULT ...Array rules are not
    assert set(rules["TSV"]) == {"ViaTSVArray", "viaTSV", "VTSV_0"}
    assert set(rules["BSV1"]) == {"viaBSV1", "VBSV1_0"} and k["via"]["BSV1"]["non_default_rules_skipped"] == [
        "ViaBSV1Array"]
    assert rules["TSV"]["ViaTSVArray"]["r_cut"] == pytest.approx(23.1)
    assert rules["TSV"]["VTSV_0"]["r_cut"] == pytest.approx(23.1 * 0.0004 / 0.09 ** 2)        # rescaled by area
    assert rules["BSV1"]["VBSV1_0"]["r_cut"] == pytest.approx(0.231)
    assert rules["BSV2"]["VBSV2_0"]["r_cut"] == pytest.approx(0.058 * 0.16 / 0.5 ** 2)
    assert rules["TSV"]["ViaTSVArray"]["pitch"] == (0.02, 0.02)
    assert rules["TSV"]["ViaTSVArray"]["metals"]["BPR"] == (0.004, 0.0)
    assert (k["supply"], k["site_y"], k["stripe_v"]) == (0.7, 0.072, (0.2, 0.8, 2.0, 0.0))
    assert k["vdd_on_odd_boundaries"]                                                # VDD pin at the row's top
    itf = bsgrid.kit(make_kit(tmp_path), bpr_rho="itf")
    assert itf["resistivity"]["BPR"] == pytest.approx(0.123672020 + (0.122756504 - 0.123672020) * 0.5)


def test_rail_polarity_follows_the_cells_pins(tmp_path):
    k = bsgrid.kit(make_kit(tmp_path, vdd_y=(-0.012, 0.012)))
    assert not k["vdd_on_odd_boundaries"]
    assert bsgrid.boundary_net(k, 0) == "VDD"


def test_a_via_with_no_ict_counterpart_is_refused(tmp_path):
    with pytest.raises(ValueError, match="BSV1"):
        bsgrid.kit(make_kit(tmp_path, v1_layers=("BSM3", "BSM1")))


def test_cut_arrays_follow_the_generate_rules(tmp_path):
    v = bsgrid.kit(make_kit(tmp_path))["via"]
    big = 10 ** 6

    def cross(vl, vw, hl, hw):              # a vertical strap of width vw crossing a horizontal one of width hw (DBU)
        return {vl: (-vw // 2, -big, vw // 2, big), hl: (-big, -hw // 2, big, hw // 2)}

    def pick(cut, rects):
        r, cs = bsgrid.cut_array(v[cut], rects)
        return r["rule"], len(cs)

    # each metal's enclosure from its own edges: BSM1 gives 0.004 along its length, BPR along its own, so a 0.2 x
    # 0.024 crossing holds 10 abutting 0.02 cuts; VTSV_0's 0.09 cut does not fit the 0.024 rail
    assert pick("TSV", cross("BSM1", 200, "BPR", 24)) == ("ViaTSVArray", 10)
    assert pick("BSV1", cross("BSM1", 200, "BSM2", 500)) == ("VBSV1_0", 1)          # viaBSV1's enclosures do not fit
    assert pick("BSV1", cross("BSM1", 200, "BSM2", 1000)) == ("VBSV1_0", 1)
    assert pick("BSV2", cross("BSM3", 1000, "BSM2", 500)) == ("VBSV2_0", 1)
    assert pick("BSV2", cross("BSM3", 1000, "BSM2", 1000)) == ("VBSV2_0", 1)
    assert pick("BSV1", cross("BSM1", 2000, "BSM2", 2000)) == ("viaBSV1", 20)       # 1.9 x 1.7 region: 5 x 4
    _, cuts = bsgrid.cut_array(v["TSV"], cross("BSM1", 200, "BPR", 24))
    assert cuts[0] == (-100, -10, -80, 10) and cuts[-1] == (80, -10, 100, 10)        # spans the stripe, centred on y
    with pytest.raises(ValueError, match="fits no"):
        bsgrid.cut_array(v["BSV2"], cross("BSM3", 200, "BSM2", 200))


def test_geometry_counts_match_a_hand_count(tmp_path):
    k = bsgrid.kit(make_kit(tmp_path))
    s = bsgrid.write(str(tmp_path / "g"), k, 6.0)
    vdd, vss = s["nets"]["VDD"], s["nets"]["VSS"]
    assert vdd["shapes"]["BPR"] + vss["shapes"]["BPR"] == 6000 // 72 + 1          # 84 rails, alternating
    assert vdd["shapes"]["BPR"] == 42                                              # odd boundaries 1..83
    assert vdd["shapes"]["BSM1"] == 3 and vss["shapes"]["BSM1"] == 3              # x = 0, 2, 4 (+1.0 for VSS)
    assert vdd["shapes"]["BSM2"] == 2 + 1 and vss["shapes"]["BSM2"] == 2 + 1      # ring sides + y = 2.4 / 4.0
    assert vdd["vias_and_cuts"]["TSV"] == [3 * 42, (2 * 10 + 9) * 42]   # x = 0 stripe: rail end
    assert vdd["vias_and_cuts"]["BSV1"] == [3 * 3, 3 * 3]                         # one fixed VBSV1_0 each
    assert vdd["vias_and_cuts"]["BSV2"] == [4 + 2, 4 + 2]                         # ring corners + stripe ends
    assert vdd["vias_by_rule"] == {"TSV": {"ViaTSVArray": 126}, "BSV1": {"VBSV1_0": 9}, "BSV2": {"VBSV2_0": 6}}
    assert set(s["ohm_per_cut"]) == {"TSV@ViaTSVArray", "BSV1@VBSV1_0", "BSV2@VBSV2_0"}
    assert s["cells"] == (6000 // 72) * (6000 // 390)
    assert s["total_current_a"] == pytest.approx(1e-6 * s["cells"] * 0.39 * 0.072)
    assert bsgrid.write(str(tmp_path / "g1"), k, 6.0, tsv_cuts=1)["nets"]["VDD"]["vias_and_cuts"]["TSV"][1] == 126


def test_each_rail_matches_an_independent_1d_solve_when_the_rest_is_ideal(tmp_path):
    # backside metal and vias ~1e-6 of BPR's: each VDD rail is held at 0.7 V at its TSV columns, so every pin's
    # voltage is that of a 1-D chain with point loads, solved here with a dense matrix
    k = bsgrid.kit(make_kit(tmp_path, rho_bsm=1e-7, r_tsv=1e-6, r_v1=1e-6, r_v2=1e-6))
    out = str(tmp_path / "g")
    bsgrid.write(out, k, 6.0)
    _, v, pin_node, _ = irbuild.solve_mesh(out, "VDD", pin_mode="point", use_cutclass=False, rail_layer="BPR")
    ours = irbuild.instance_voltages(v, pin_node, "VDD")
    r_um = k["sheet_ohm_sq"]["BPR"] / 0.024                                          # ohm per um of rail
    rows = collections.defaultdict(list)
    for name, x0, x1, r, p in bsgrid.loads(k, 6.0, False):
        b = r if r % 2 == 1 else r + 1                                               # VDD on odd boundaries
        rows[b].append(((x0 + x1) / 2000, p / 0.7, name))
    held = [0.1, 2.1, 4.1]                                                           # BSM1 VDD centres, um
    worst = 0.0
    for cells in rows.values():
        xs = sorted({x for x, _, _ in cells} | set(held))
        ix = {x: n for n, x in enumerate(xs)}
        g = np.zeros((len(xs), len(xs)))
        rhs = np.zeros(len(xs))
        for a, c in zip(xs, xs[1:], strict=False):
            ga = 1.0 / (r_um * (c - a))
            for p_, q in ((ix[a], ix[c]), (ix[c], ix[a])):
                g[p_, p_] += ga
                g[p_, q] -= ga
        for x, i, _ in cells:
            rhs[ix[x]] -= i
        for h in held:
            g[ix[h]] = 0.0
            g[ix[h], ix[h]] = 1.0
            rhs[ix[h]] = 0.7
        ref = np.linalg.solve(g, rhs)
        for x, _, name in cells:
            assert ours[name] == pytest.approx(ref[ix[x]], abs=1e-9)
            worst = max(worst, 0.7 - ref[ix[x]])
    assert worst > 1e-8                                                              # the check is not vacuous


def test_each_bump_holds_exactly_one_stripe_crossing(tmp_path):
    k = bsgrid.kit(make_kit(tmp_path))
    out = str(tmp_path / "g")
    bsgrid.write(out, k, 20.0, feed="area", bump_pitch_um=10.0)
    bterms = [g for g in irbuild.read_tsv(os.path.join(out, "geom_VDD.tsv")) if g["kind"] == "bterm"]
    assert len(bterms) == 4 and {g["layer"] for g in bterms} == {"BSM2"}
    _, _, _, info = irbuild.solve_mesh(out, "VDD", rail_layer="BPR")
    assert info["sources"] == 4


def test_the_bump_array_is_centred_in_the_core(tmp_path):
    k = bsgrid.kit(make_kit(tmp_path))
    out = str(tmp_path / "g")
    bsgrid.write(out, k, 50.0, feed="area", bump_pitch_um=20.0)   # 50 / 20 rounds to 3 bumps near 5, 25, 45 um
    xs = sorted({(int(g["xlo"]) + int(g["xhi"])) // 2 for g in irbuild.read_tsv(os.path.join(out, "geom_VDD.tsv"))
                 if g["kind"] == "bterm"})
    assert xs == [4100, 24100, 44100]                             # snapped to the VDD BSM1 stripes (x = 2k + 0.1)


@pytest.mark.parametrize("extra, match", [
    ("set CFET_OP_VOLTAGE 0.63\n", "more than once"),
    ('if {$corner eq "ss"} {\n  set CFET_SITE_Y 0.08\n}\n', "more than once or inside a block"),
])
def test_an_ambiguous_tcl_value_is_refused(tmp_path, extra, match):
    with pytest.raises(ValueError, match=match):
        bsgrid.kit(make_kit(tmp_path, tcl=TCL + extra))


def test_a_non_plain_tcl_value_is_named(tmp_path):
    bad = TCL.replace("set PG_STRIPE_HORZ_SET_TO_SET    3.2", "set PG_STRIPE_HORZ_SET_TO_SET    3.2 ;# um")
    with pytest.raises(ValueError, match="PG_STRIPE_HORZ_SET_TO_SET"):
        bsgrid.kit(make_kit(tmp_path, tcl=bad))


def test_a_fixed_via_must_keep_its_pads_on_the_wires(tmp_path):
    v = bsgrid.kit(make_kit(tmp_path))["via"]["BSV1"]
    fixed = next(r for r in v["rules"] if r["rule"] == "VBSV1_0")
    big = 10 ** 6
    # VBSV1_0's BSM2 pad is 0.2 x 0.5: it fits a 0.5 um horizontal stripe as drawn, and no way a 0.18 um one
    fits = {"BSM1": (-100, -big, 100, big), "BSM2": (-big, -250, big, 250)}
    assert bsgrid.rule_array(fixed, fits)[:2] == (1, 1)
    narrow = {"BSM1": (-100, -big, 100, big), "BSM2": (-big, -90, big, 90)}           # 0.18 um BSM2: pad hangs off
    assert bsgrid.rule_array(fixed, narrow)[:2] == (0, 0)


def test_a_fixed_backside_via_with_two_cuts_is_refused(tmp_path):
    one = "  LAYER BSV1 ;\n    RECT -0.100 -0.100 0.100 0.100 ;\n"
    two = VIARULES.replace(one, one + "    RECT 0.2 -0.1 0.4 0.1 ;\n", 1)
    assert two != VIARULES
    with pytest.raises(ValueError, match="BSV1"):
        bsgrid.kit(make_kit(tmp_path, viarules=two))


def test_capped_cuts_sit_at_the_centre(tmp_path):
    v = bsgrid.kit(make_kit(tmp_path))["via"]["TSV"]
    big = 10 ** 6
    _, cuts = bsgrid.cut_array(v, {"BSM1": (-100, -big, 100, big), "BPR": (-big, -12, big, 12)}, cap=1)
    assert len(cuts) == 1 and abs((cuts[0][0] + cuts[0][2]) / 2) <= 10                # centred on the stripe


def test_the_hand_estimate_adds_each_strap_and_via(tmp_path):
    import run_c5
    k = bsgrid.kit(make_kit(tmp_path))
    e = run_c5.estimate(k, 50)
    j, span = 1e-6, 50 + 2 * (0.5 + 0.5)
    assert e["BSM2"] == pytest.approx(j * 3.2 * span ** 2 * 0.2 / 0.5 / 8 * 1e3)
    assert e["BSV2"] == pytest.approx(j * 3.2 * span / 2 * (0.058 * 0.16 / 0.25) * 1e3)  # one VBSV2_0 per end
    assert e["sum"] == pytest.approx(sum(v for p, v in e.items() if p != "sum"))
