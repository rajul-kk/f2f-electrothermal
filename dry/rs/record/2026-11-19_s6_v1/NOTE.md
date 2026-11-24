# S6 v1: asap7_3D with M2_add/M3_add, scoped to the platform's config.mk (Kaggle CPU, 19 Nov 2026 08:44-09:19 UTC)

Script `scripts/s6_add.sh` (sha256 44ba2b32) over `scripts/rs_lib.sh` (43bddc33) and `scripts/add_layers.py`
(d658f9f4), as in `script.sha256`, at the commits in `commits.txt` (ORFS-Research 568eb04d, TaiWei-Pin-3D 51a19d6f).
`add_layers.txt` lists every input and output hash. `asap7_3D_config.mk` is the patched platform file as it ran
(sha256 bb9d5dff, the same as in `add_layers.txt`). Exit status 2 (`exit_status.txt`). Peak machine memory 13,443 MiB
(`steps.log`).

| Case | Wall time (`steps.log`) | Furthest step (`flow_logs.tgz`) | Failure |
|---|---|---|---|
| gcd | 271 s | `5_2_route` | "Global routing failed" (`detail_route.tcl`, line 55) |
| ibex | 1,770 s | `5_2_route` | the same |

**What S6 settles.**
- **S5's failure is fixed.** Changing asap7_3D's config.mk instead of the environment leaves Pin-3D's 2D asap7
  stages alone. Both cases pass `2_1_floorplan` and every later stage up to `5_1_grt`.
- **Pin access now completes.** `5_1_grt.log` has no DRT-0073, where S4 had it on 11 upper-tier pins for gcd and 56
  for ibex (inner inputs of multi-input cells; `../2026-11-19_s4_v1/NOTE.md`), plus one summary error line each. It reports "Complete pin access" (DRT-0166, line
  275 for gcd and 280 for ibex).
- **Which change fixed it is not separated.** Against S4, S6 changed the tech LEF (the two added layers and their
  vias), the track script (their tracks), the RC script, MAX_ROUTING_LAYER (M1_m in S4, M3_add here), and emptied
  the extraction deck (`add_layers.txt`, `asap7_3D_config.mk`). The record does not show which via any upper-tier
  pin used.

**Why it still stops.** In both cases `5_1_grt.log` (line 278 for gcd, 283 for ibex) has `[ERROR STA-0562]
global_route -gcell_size is not a known keyword or flag`.
- **The flag comes from the kit.** asap7_3D's `config.mk` adds `GLOBAL_ROUTE_ARGS += -gcell_size
  $(ASAP7_HBT_RDL_GCELL_SIZE_UM)` (1.1 um) whenever ASAP7_HBT_RDL is on, which is its default (`asap7_3D_config.mk`,
  lines 12-13 and 24).
- **The pinned OpenROAD has no such flag.** OpenROAD-Research 305d3ba2 defines `global_route`'s arguments in
  `src/grt/src/GlobalRouter.tcl`, lines 143-156, and `-gcell_size` is not among them. Source:
  https://raw.githubusercontent.com/ieee-ceda-datc/OpenROAD-Research/305d3ba2/src/grt/src/GlobalRouter.tcl, fetched
  19 Nov, sha256 270f4c38.
- **Pin-3D carries on past the error.** Its `global_route_helper` (`scripts_openroad/global_route.tcl`, lines
  223-235) catches the error. Unless GENERATE_ARTIFACTS_ON_FAILURE is set to 0, it writes the stage outputs and
  returns normally; set to 0, it re-raises. The record does not show the variable's value, but `5_1_grt.log` ends
  normally, which fits the first case. So `5_1_grt` ends without a route, and `5_2_route`
  stops.
- **S4 never reached this command**, because pin access failed first. What the record shows is that the kit's
  asap7_3D config.mk passes a global-route flag the pinned OpenROAD rejects. Whether routing succeeds once the flag
  is dropped is S7's question.

**Next (S7).** The same patch, plus dropping that line (`add_layers.py --config --drop-gcell`), so global routing
uses OpenROAD's default gcell size: a stated deviation from the kit's 1.1 um, beside the two added layers and the
emptied extraction deck.

Not in this record: `flow_results.tgz` (Kaggle output, not downloaded into the record) and `pin3d_env.sh`. Kept
local per `.gitignore`: the clone, checkout and apt logs, and `shims.txt`.
