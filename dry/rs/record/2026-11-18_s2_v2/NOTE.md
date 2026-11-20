# S2 v2 (18 Nov 2026, Kaggle CPU, `rajulkabir/open3d-rs-s2-gcd` version 2): gcd on three techs

Scripts: `scripts/s2_gcd.sh` 3eb97e54..., `scripts/rs_lib.sh` bc86fb1d... (`script.sha256`; extracted from the
notebook as pushed). This rs_lib.sh still has the first status check (`failed=` only), so this record was read by
hand. Flow logs, reports and Pin-3D's run logs are packed in `flow_logs.tgz` (paths below are inside it). The first
download kept only log/txt/json/sha256/md files; GNU time's `<step>.time` reports and Pin-3D's three dispatch
wrappers (`dispatch_wrappers/`) were fetched afterwards from the same kernel version. The session's copy of Pin-3D's
`env.sh` is not kept here: it is the upstream file at the recorded commit (sha256 17e69ba7...).
Per gcd step (`gcd_<tech>.time`): asap7_3D 5:00.43 wall, max RSS 496,236 KiB; nangate45_3D 4:30.49, 371,416 KiB;
asap7_nangate45_3D 23:00.56, 1,310,836 KiB.

- **Build restores as in S2 v1** (`build_identity.txt`: S1's tarball hash and binary hashes); setup 487 s (`steps.log`).
- **gcd per tech** (`steps.log`, `rc.txt`, each `gcd_<tech>.log` ends `[STATUS] failed=1` and
  `[MAIN] All experiments completed.`):

| Tech | Step time | Where it stopped (`flow_run_logs/status/ord__<tech>__gcd.json`) |
|---|---|---|
| asap7_3D | 301 s | run phase: `3_place_upper`, `[ERROR GRT-0029] Pin dpath.b_reg.out\[9\]$_DFFE_PP_/CLK does not have geometries below the max routing layer (M2_m).` (`flow_logs/asap7_3D/gcd/openroad/3_place_upper.log`), as in S2 v1 |
| nangate45_3D | 271 s | run phase: the same error at the same step, pin `.../CK` (`flow_logs/nangate45_3D/gcd/openroad/3_place_upper.log`) |
| asap7_nangate45_3D | 1380 s | **the run phase completed** (`flow_run_logs/asap7_nangate45_3D/ord/run/gcd_run.log`: "flow completed for asap7_nangate45_3D/gcd (openroad)"); the eval phase failed: `[CDS] Final`, `/usr/bin/time: invalid option -- '6'`, `make: *** [Makefile:965: cds-final] Error 125` (`flow_run_logs/asap7_nangate45_3D/ord/eval/gcd_eval.log`) |

- **asap7_nangate45_3D gcd result** (`flow_logs/asap7_nangate45_3D/gcd/openroad/final_summary.txt`): core area
  117.8064, std-cell area 120.05742, total power 7.11e-04, wire length 1549.28, WNS 0.00, TNS 0.00, DRC violations
  14, HB via count 30, cross-tier nets 81 (upper-bottom 27, upper-IO 53, upper-bottom-IO 1). Units as the file
  prints them (none given).
- **Detailed routing dominates:** `5_2_route.log` took 20:27.50 at 100% CPU with peak 1,310,836 KiB although the log
  says "Using 4 thread(s)"; the other 23 stages with a time line took under 31 s each. Machine-wide peak in use
  19,550 MiB (`steps.log`).

So the flow-wide question v1 left open is answered: Pin-3D's OpenROAD run works on the heterogeneous asap7/nangate45
tech and fails at the same upper-tier placement step on both homogeneous techs (cause not shown). Its eval phase calls
a Cadence target, which this toolchain does not have, so S3 runs `--run-only`.

Next (S3 v1, pushed 18 Nov): ibex on asap7_3D (to see whether it fails the same way) and asap7_nangate45_3D.
