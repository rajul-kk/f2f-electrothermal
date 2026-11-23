# S5 v1: asap7_3D with M2_add/M3_add above M1_m, by environment overrides (Kaggle CPU, 19 Nov 2026 06:53-08:06 UTC)

Script `scripts/s5_add.sh` (sha256 5a86035d) over `scripts/rs_lib.sh` (43bddc33) and `scripts/add_layers.py`
(f9c72c7d), as in `script.sha256`, at the commits in `commits.txt`. `add_layers.txt` holds the sha256 of the patch's
six inputs and its three `*_add` outputs. `steps.log` has no "add_layers.py failed" line, so the patch ran. Exit
status 2 (`exit_status.txt`). The two flow cases ran from 08:04 to 08:06 (`steps.log`); clone, checkout and setup
took the session's first 72 minutes (06:53:20 to 08:04:59).

| Case | Wall time (`steps.log`) | Furthest step (`flow_logs.tgz`) | Failure |
|---|---|---|---|
| gcd | 30 s | `2_1_floorplan` | EST-0205 "via V_HB_B not found" (`floorplan.tcl`, line 3) |
| ibex | 61 s | `2_1_floorplan` | the same |

**Cause.** `2_1_floorplan.log` (line 17, both cases, and the same line in S4's record) loads the plain 2D
`platforms/asap7` tech LEF: Pin-3D runs synthesis and the first floorplan on the 2D platform before it switches to
asap7_3D. The script exported TECH_LEF, MAKE_TRACKS, SET_RC_TCL and MAX_ROUTING_LAYER. The 2D platform's
`config.mk` (Pin-3D 51a19d6f) sets TECH_LEF (line 11) and MAX_ROUTING_LAYER (line 123) with `=`, which overrides
the environment; that is why line 17 shows the 2D LEF. It sets SET_RC_TCL (lines 35 and 105) and MAKE_TRACKS (line
104) with `?=`, which keeps an exported value. So the 2D stage would have used the exported 3D RC script, whose
`set_layer_rc -via V_HB_B` (`setRC_2A6M7M_hbrdl.tcl`, line 22) names a via the 2D tech LEF does not have. This
matches the error; no log line names the RC script the stage sourced, so this is inferred from the config files. The
added layers were never reached, and S5 says nothing about whether they fix S4's pin access.

**Next (S6).** The same added layers, scoped to the platform: patch asap7_3D's `config.mk` in the session's clone
(its three hbrdl file pointers to the `*_add` copies, MAX_ROUTING_LAYER to M3_add) instead of the environment, and
empty `ASAP7_HBT_RDL_RCX_RULES` so the final report does not extract the two new layers with 15-layer rules (code
review, 19 Nov). (Written before S6 ran; see `../2026-11-19_s6_v1/NOTE.md`.)

Kept local (per `.gitignore`): the clone, checkout and apt logs, and `shims.txt`. `pin3d_env.sh` is not kept.
