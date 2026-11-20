# S2 v1 (18 Nov 2026, Kaggle CPU, `rajulkabir/open3d-rs-s2-gcd` version 1): toolchain ok, gcd fails in placement

Scripts: `dry/rs/s2_gcd.sh` b14844ed..., `dry/rs/rs_lib.sh` 3b2cf4d9... (`script.sha256`). The download kept only log/txt/json/sha256/md files, so GNU time's `<step>.time` reports are not here; Kaggle keeps only a kernel's latest version, and v2 replaced them.

- **The S1 build restores** (`build_identity.txt`): the attached tarball's sha256 equals S1 v2's (b003f6fc...), and
  openroad and yosys hash as in S1. Before ORFS's `setup.sh` the two binaries lacked 6 system libraries
  (libtclreadline-2.3.8, libQt5Charts/Widgets/Gui/Core, libyaml-cpp 0.8); after it, none. With S1's dependencies
  restored, setup took 468 s (`steps.log`), against S1's 3667 s.
- **Versions** (`versions.log`): OpenROAD 305d3ba2ddfd00591924cc586ad408179f566afe (the README's tested commit),
  Yosys 0.61+0 (git sha1 77005b69a). Commits (`commits.txt`): ORFS-Research 568eb04d, TaiWei-Pin-3D 51a19d6f.
- **`--list`** (`list.log`): 19 ord runs over asap7_3D, asap7_nangate45_3D and nangate45_3D; `ibex` is listed for all
  three, so the design's `--case ibex` form exists.
- **gcd on asap7_3D fails** in `3_place_upper` (`flow_logs.tgz`: `flow_logs/asap7_3D/gcd/openroad/3_place_upper.log`, last lines):
  `[ERROR GRT-0029] Pin dpath.b_reg.out\[9\]$_DFFE_PP_/CLK does not have geometries below the max routing layer
  (M2_m).` raised by `global_placement -routability_driven -timing_driven` (place_upper.tcl line 53) on its first
  routability iteration. Pin-3D's platform sets `MIN_ROUTING_LAYER ?= M2`, `MAX_ROUTING_LAYER ?= M2_m`
  (`platforms/asap7_3D/config.mk` at 51a19d6f). Cause not shown; the likely one is that the upper tier's mirrored
  stack puts M1_m (where upper-tier cell pins are) above M2_m, outside the routing range.
- **The run reported success.** `run_experiments.py` exited 0 and printed `[STATUS] failed=1` (`gcd.log`, last
  lines), so the script logged "gcd ok". `rs_lib.sh` now passes a run only if "All experiments completed" follows the last status line and that
  line is exactly "ok=N" with N > 0 (an allow-list; A13).
- Stage times (`flow_logs.tgz`, `flow_logs/.../*.log`): the 15 stages with a GNU time line took 2-8 s each, the largest peak among them
  495,760 KiB (`3_place_upper`). `2_tritonpart` and `1_0_synth_env` print no such line; tritonpart's own timestamps
  run 22:52:30 to 22:56:02, about 212 s of the 301 s gcd step, and its memory is not measured. Machine-wide peak in
  use 17,617 MiB (`steps.log`). Results tarball `flow_results.tgz` cc529691... (`flow_results.sha256`), in the Kaggle
  output. The run's own scripts are in `scripts/` (hashes as in `script.sha256`).
- S2 v2 was pushed before that review and checks only `failed=`; its record is read by hand.

Next (S2 v2): the same gcd on all three ord techs, to tell an asap7_3D configuration problem from a flow-wide one,
and keep `run_logs/`.
