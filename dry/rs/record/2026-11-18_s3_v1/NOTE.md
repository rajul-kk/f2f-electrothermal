# S3 v1 (18 Nov 2026, Kaggle CPU, `rajulkabir/open3d-rs-s3-ibex` version 1): ibex on two techs

Scripts: `scripts/s3_ibex.sh` 36fdc1f2..., `scripts/rs_lib.sh` 087e6277... (`script.sha256`; extracted from the
notebook as pushed). These are older than the repository's `s3_ibex.sh` and `rs_lib.sh`, so this record was read by
hand. Flow logs, reports and Pin-3D's run logs are packed in `flow_logs.tgz` (paths below are inside it); Pin-3D's
two dispatch wrappers are in `dispatch_wrappers/`. The session's copy of Pin-3D's `env.sh` is not kept here: it is
the upstream file at the recorded commit (sha256 17e69ba7..., as in S2 v2). The kernel ended in Kaggle state ERROR
because the notebook exited 1 (`notebook_exit_code.txt`).

- **Build restores as in S2** (`build_identity.txt`); setup 543 s (`steps.log`).
- **ibex per tech** (`steps.log`, `rc.txt`). Under either status rule (the old `failed=` check or the current
  `ok=N` rule in `rs_lib.sh`), both are failures:

| Tech | Step time | Where it stopped |
|---|---|---|
| asap7_3D | 1561 s (rc 0, `[STATUS] failed=1`) | run phase, `3_place_upper`: `[ERROR GRT-0029] Pin _39526_/L does not have geometries below the max routing layer (M2_m).` (`flow_logs/asap7_3D/ibex/openroad/3_place_upper.log`), the same error at the same step as gcd in S2 v1 and v2 |
| asap7_nangate45_3D | 35324 s (rc 124, the session deadline) | run phase, detailed routing (`5_2_route`), in its 5th iteration at 60% with 510 violations (`flow_run_logs/asap7_nangate45_3D/ord/run/ibex_run.log`) |

- **asap7_nangate45_3D reaches routing.** Synthesis to global routing completed (the 22 stages with a time line sum
  to 36.1 min; global route ends with clock core_clock slack -0.671 at period 2.205, `5_1_grt.log`).
- **Detailed routing is the cost.** Its iterations (`ibex_run.log`, `DRT-0199` / `DRT-0267`):

| Iteration | Violations after | Wall time | CPU time | Peak (MB) |
|---|---|---|---|---|
| 0 | 12,323 | 2:17:16 | 4:21:56 | 6,234 |
| 1 | 3,505 | 2:13:35 | 4:21:11 | 7,312 |
| 2 | 3,387 | 2:07:08 | 4:06:21 | 8,228 |
| 3 | 578 | 1:46:38 | 2:21:35 | 8,228 |
| 4 | 510 at 60% when stopped | 0:34:36 so far | | |

  CPU time is about twice wall time, so detailed routing used about 2 of the session's cores. Machine-wide peak in
  use 26,478 MiB (`steps.log`), against Kaggle's 30 GB.

So ibex on asap7_nangate45_3D does not finish in one 12 h Kaggle CPU session with this toolchain: routing alone took
8 h 25 min for four iterations and had not converged. asap7_3D fails at upper-tier placement on ibex as on gcd (cause
not shown).

Next: rs-dry is answered for S1-S3 (the flow builds and runs; one tech reaches routing). Finishing ibex needs either
a resume from the routing stage in a second session (DESIGN.md, A17) or fewer violations per iteration; that choice
belongs to G1's design, not to this dry run.
