# S8 v1: asap7_3D in the direct view (Kaggle CPU, 20 Nov 2026; flow cases 04:21-07:02 UTC, `steps.log` lines 12-17)

Script `scripts/s8_direct.sh` (sha256 c9a1fda8) over `scripts/rs_lib.sh` (43bddc33) and `scripts/add_layers.py`
(ee3ca9c1), as in `script.sha256`, at the commits in `commits.txt` (ORFS-Research 568eb04d, TaiWei-Pin-3D 51a19d6f).
`asap7_3D_config.mk` is the patched platform file as it ran (`add_layers.py --view direct --config`; hashes in
`add_layers.txt`): `ASAP7_HBT_RDL := 0`, the two added layers M2_add and M3_add, the kit's 15-layer 2A6M7M
extraction deck. No environment overrides (`steps.log` line 11). Exit status 0 (`exit_status.txt`); every step rc 0
(`rc.txt`).

**Both cases complete every stage of the flow for the first time.** Earlier runs stopped in floorplan (S5,
EST-0205), upper-tier placement (S3), pin access (S4) or detailed routing (S6, S7); see their NOTEs.

Files below without a folder are in `flow_logs.tgz`, under `flow_logs/asap7_3D/<case>/openroad/`.

| | gcd | ibex | Source |
|---|---|---|---|
| Wall time of the case | 571 s | 9,063 s | `steps.log` lines 13, 17 |
| Maximum single-process RSS | 1,407,404 kB | 5,007,780 kB | `<case>_asap7_3D.time` line 11 |
| Global routing | zero overflow; cap 30 congestion iterations | zero overflow; cap 30 congestion iterations | `5_1_grt.log` gcd 265, 337; ibex 270, 342 |
| Detailed routing | iterations 0-5 (`-droute_end_iter 5`) | iterations 0-20 (`-droute_end_iter 20`), 5,403 s | `5_2_route.log` line 58; ibex 287, 1654, 1761 |
| DRC markers left | 72, all cut spacing on hb_layer | 99, all cut spacing on hb_layer | `5_2_route.log` gcd 594-596, ibex 1675-1677 |
| Core / std-cell area (um^2) | 35.92512 / 55.75392 | 2317.54932 / 2521.87344 | `final_summary.txt` lines 4-5 |
| Total power (W) | 7.78e-04 | 2.13e-02 | `final_summary.txt` line 7 |
| Wirelength (um) | 1000.43 | 92933.19 | `final_summary.txt` line 8 |
| Setup WNS / TNS (ps; unit `time 1ps`, `2_1_floorplan.log` line 36) | -7.10 / -15.47 | -10.93 / -162.89 | `final_summary.txt` lines 9-10 |
| FEP violations | 3 | 44 | `final_summary.txt` line 12 |
| Bond vias / cross-tier nets | 42 / 94 | 399 / 638 | `final_summary.txt` lines 13-14 |
| Wire on M2_add + M3_add | 173 + 162 of 1,002 um | 15,623 + 16,201 of 93,019 um (34%) | `5_2_route.log` gcd 612-613, 598; ibex 1693-1694, 1679 |
| Extraction deck | 15 routing layers, LayerCount check passed | same | `6_report.log` line 64 |

Sampled session-wide peak memory in use: 25,104 MiB (`steps.log` line 22). `flow_reports/.../openroad_eval.json`
repeats a subset of these final metrics (no wirelength).

**What S8 settles.**
- The direct view (bond modelled as the cut layer `hb_layer`, no HBT lattice) gets past S7's DRT-0406 track
  assignment stop. Global routing finishes with zero overflow; detailed routing runs to its last iteration.
- The routing is not clean. In ibex the marker count fell to 65 after iteration 16 and rose to 218 after iteration 17
  (`5_2_route.log` lines 1403, 1469). After iteration 19, 126 of 132 were hb_layer cut spacing, with one marker on
  M4 and five on M6_m (lines 1607-1613); after iteration 20 all 99 were hb_layer cut spacing. Their cause is
  unverified: the marker report `5_route_drc.rpt` is in the Kaggle results archive, not in this record, and is
  needed to compare the marker geometry with the cut rule in the direct LEF.
- Setup fails in both cases. `report_design_area` printed 155% (gcd) and 112% (ibex) utilization (`6_report.log`
  line 88); the floorplan's sizing input was 60.00% (`2_1_floorplan.log` line 25). What the final figure counts per
  tier is unverified.
- `6_report.log` warns that some ibex nets have no detailed route (GRT-0239, from line 109), and the extraction
  config states that physical 3D calibration is not certified (`openrcx_config.txt` line 4).

**What it is not.** One candidate PPA and cost datapoint, not a G1 baseline: run-to-run spread is unmeasured, the
full results archive (`flow_results.sha256`) is outside this record, and the published numbers to compare with are
not here. The kit's `designs/asap7_3D/ibex/rules-base.json` holds ORFS-style regression limits (for example finish
setup WS >= -0.06 and DRC 0), not a published 3D results table; the published values are unverified until read
from the RosettaStone 2.0 paper (arXiv 2601.17520).

**Deviations a G1 built on this flow must state:** (1) two added routing layers on the upper tier carry 34% of
ibex's wire; (2) the bond is the direct view's cut layer, not the kit's default 1 um HBT lattice; (3) extraction on
the 2A6M7M deck; (4) 99 hb_layer cut-spacing markers after the last detailed-routing iteration; (5) negative setup
slack and nets without a detailed route.

Not in this record: `flow_results.tgz` (Kaggle output, not downloaded). Kept local per `.gitignore`: the clone,
checkout and apt logs, `kernel.log` and `shims.txt`.
