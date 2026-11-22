"""Tests for c3.py: the .temp rewrite, state grouping, checks 1-4 and the table."""
import json
import math

import pytest

import c3


def write_deck(d, name, text):
    (d / name).write_text(text, encoding="utf-8")


def test_retemp_changes_only_the_temp_line(tmp_path):
    body = "* leakage\n.temp 25.0\n.option gmin=1e-18\n.end\n"
    write_deck(tmp_path, "s0000.cir", body)
    write_deck(tmp_path, "s0000r.cir", body)
    (tmp_path / "cases.json").write_text(json.dumps({"temp": 25.0, "cases": []}))
    c3.retemp(str(tmp_path), "85")
    for n in ("s0000.cir", "s0000r.cir"):
        assert (tmp_path / n).read_text() == body.replace(".temp 25.0", ".temp 85.0")
    assert json.loads((tmp_path / "cases.json").read_text())["temp"] == 85.0


def test_retemp_refuses_a_deck_without_exactly_one_temp_line(tmp_path):
    write_deck(tmp_path, "s0000.cir", ".temp 25.0\n.temp 25.0\n")
    (tmp_path / "cases.json").write_text(json.dumps({"temp": 25.0}))
    with pytest.raises(SystemExit):
        c3.retemp(str(tmp_path), "45")


def test_states_mean_of_terms_and_invalid_term_voids_state():
    res = {"cases": [{"cell": "a", "when": "w", "spice_w": 1.0}, {"cell": "a", "when": "w", "spice_w": 3.0},
                     {"cell": "b", "when": "w", "spice_w": None}, {"cell": "b", "when": "w", "spice_w": 2.0}]}
    assert c3.states(res) == {("a", "w"): 2.0, ("b", "w"): None}


def test_loglin_worst_is_zero_for_an_exact_exponential():
    ts = list(c3.TEMPS)
    assert c3.loglin_worst(ts, [1e-12 * math.exp(0.03 * t) for t in ts]) < 1e-12


def synthetic(scale=1.0):
    """One Vt, two states, rising with T; C2's SS/FF at 125 C bracket TT."""
    per_t = {t: {("c", "s1"): 1e-12 * (1 + t / 100) * scale, ("c", "s2"): 2e-12 * (1 + t / 100)} for t in c3.TEMPS}
    c2 = {"GT_A5_svt_TTG_25C": dict(per_t[25]),
          "GT_A5_svt_SSG_125C": {k: v * 0.5 for k, v in per_t[125].items()},
          "GT_A5_svt_FFG_125C": {k: v * 2.0 for k, v in per_t[125].items()}}
    return per_t, c2


def test_check_vt_passes_a_clean_case():
    per_t, c2 = synthetic()
    r = c3.check_vt("svt", per_t, c2)
    assert r["parity_mismatch"] == [] and r["not_rising"] == [] and r["outside_bracket"] == []
    assert r["no_bracket"] == [] and all(v == [] for v in r["invalid"].values())
    assert r["p125_over_p25"]["min"] == pytest.approx(2.25 / 1.25)


def test_check_vt_names_each_failure():
    per_t, c2 = synthetic()
    c2["GT_A5_svt_TTG_25C"][("c", "s1")] *= 1.0000001          # check 1: exact, not approximate
    per_t[65][("c", "s2")] = per_t[45][("c", "s2")]           # check 3: flat step
    c2["GT_A5_svt_FFG_125C"][("c", "s2")] = per_t[125][("c", "s2")] * 0.9   # check 4: TT above both corners
    per_t[105][("c", "s1")] = None                            # check 2
    r = c3.check_vt("svt", per_t, c2)
    assert r["parity_mismatch"] == ["c s1"]
    assert len(r["not_rising"]) == 1 and r["not_rising"][0].startswith("c s2: 45 C")
    assert len(r["outside_bracket"]) == 1 and r["outside_bracket"][0].startswith("c s2")
    assert r["invalid"][105] == ["c s1"]


def test_table_mean_is_empty_where_a_state_is_invalid():
    per_t, _ = synthetic()
    per_t[45][("c", "s1")] = None
    cells = c3.table_vt(per_t)
    assert cells["c"]["mean"][1] is None and cells["c"]["mean"][0] == pytest.approx(1.5e-12 * 1.25)
    assert cells["c"]["loglin_worst_rel"] is None
