# Published ibex F2F results (RosettaStone 2.0) against rs-dry S8

Source: L. Jiang, A. B. Kahng, Z. Wang, Z. Zheng, "Invited: Toward Sustainable and Transparent Benchmarking for
Academic Physical Design Research", Proc. ISPD 2026; arXiv 2601.17520, HTML v1 (https://arxiv.org/html/2601.17520),
read 20 Nov 2026. Values copied as printed; "7+7" is ASAP7 on both tiers (asap7_3D), the first technology is the top
tier.

## Table 2 (3D, Flexible tier strategy), ibex rows

| Stack | Flow | Clock (ns) | Core (um^2) | StdCell (um^2) | Power (mW) | rWL (mm) | WNS (ns) | TNS (ns) | DRVs | FEPs | HBT Cnt |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 7+7 | COMM | 1.000 | 1,340.4 | 1,650.1 | 5.71 | 72.4 | -0.009 | -0.064 | 3,119 | 27 | 1,027 |
| 7+7 | ORD | 1.000 | 1,965.5 | 2,655.7 | 10.99 | 128.4 | -0.449 | -260.812 | 39,311 | 1,371 | 4,466 |
| 45+45 | COMM | 2.200 | 18,295.3 | 22,244.2 | 11.35 | 228.8 | 0.147 | 0.000 | 8 | 0 | 1,072 |
| 45+45 | ORD | 2.200 | 24,022.5 | 30,307.2 | 25.80 | 291.6 | -0.508 | -255.542 | 1 | 1,175 | 2,041 |
| 7+45 | COMM | 2.200 | 2,611.7 | 3,147.0 | 7.69 | 78.8 | -1.264 | -438.321 | 124 | 539 | 257 |
| 7+45 | ORD | 2.200 | 4,501.7 | 4,823.4 | 5.23 | 110.6 | -0.043 | -0.043 | 1,351 | 1 | 671 |

Table 4 compares the Restricted and Flexible tier strategies for 45+45 ORD, 7+7 COMM and 7+45 COMM only (selected
metrics, power and rWL at higher precision); it has no 7+7 ORD row.

## Conditions the paper states

- 60% core utilization target, die outline from the synthesized size; TT corner; vectorless power with default
  switching activity (the numeric activity is not given); detailed routing capped at 20 iterations; HBTs as vias on a
  dedicated cut layer (Table 1: width 0.5 um, spacing 0.5 um, pitch 1.0 um, 0.02 ohm).
- ORD is OpenROAD-Research v2025.11 (no commit given). Timing, power and violations of every row are evaluated with
  Cadence Innovus v21.39.
- Table 2 reports no seed or run-to-run spread for ibex. The paper says its numbers "are shown only to demonstrate
  end-to-end flow completeness and are not intended for any direct comparison".
- The kit's README (TaiWei-Pin-3D 51a19d6f, line 33): "the branch used in the paper differs from the public release".

## S8 against the 7+7 ORD row

S8's setup (kit `designs/asap7_3D/ibex/`): clock 1.200 ns (`constraint.sdc` line 3, `clk_period 1200`; 1,200 ps at
run time, `5_1_grt.log` line 2212); a 60% target for the 2D bootstrap (`config2d.mk` line 18, `2_1_floorplan.log`
line 25) and a 50% max-tier target for the 3D floorplan (`config.mk` line 13, `2_3_floorplan_3d.log` line 54). Logs
are in `record/2026-11-20_s8_v1/flow_logs.tgz`.

| Quantity | Paper 7+7 ORD | S8 (`record/2026-11-20_s8_v1/NOTE.md`) | Comparable? |
|---|---|---|---|
| Clock | 1.000 ns | 1.200 ns | no: different target |
| Utilization target | 60% | 50% max-tier target in 3D (60% in the 2D bootstrap) | no: different sizing |
| Core / std-cell area | 1,965.5 / 2,655.7 um^2 | 2,317.5 / 2,521.9 um^2 | no: different clock and sizing |
| Power | 10.99 mW | 21.3 mW | no: different evaluator; activity matching unverified |
| Routed wirelength | 128.4 mm | 92.9 mm reported detailed-route wirelength; some nets lack detailed routes | no |
| WNS / TNS | -0.449 / -260.812 ns | -0.011 / -0.163 ns | no: different clock and evaluator |
| Violations | 39,311 DRVs (Innovus) | 99 OpenROAD detailed-route markers, all hb_layer cut spacing | no: different checker |
| HBT count | 4,466 | 399 physical bond vias | no |

**What this means for G1.** S8 cannot validate G1 as first written ("reproduce the published PPA within a
tolerance"): the paper's metrics come from a commercial evaluator (not used here), its branch differs from the public
release, and its clock and utilization differ from the kit's ibex setup. The authors also disclaim direct
comparison. The paper's 7+7 ORD row is context, not a target.

**Decision (student, 20 Nov 2026): option A.** G1 gates the repeatability of our own open flow in S8's pinned
setup: 2-3 fresh runs with repeatability bars fixed before the runs, kept separate from route cleanliness (the
hb_layer markers and unrouted nets are reported, not hidden by a spread bar). S8 itself is a dry run, not one of
the gated runs. Cost: about 2.52 h per ibex case on Kaggle CPU (S8: 9,063 s, `steps.log` line 17) plus about 15 min
of clone, checkout and setup per session.

Options considered: B (A plus one 1.000 ns sensitivity run, reported beside the paper's row; its run time is
unmeasured) and C (no G1 reruns; S8's tiers used as G2's input only after its tier DEFs and stack inputs are
recovered from the Kaggle results archive and checked, with a rerun budgeted if they cannot be).
