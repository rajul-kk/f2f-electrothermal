# S4 v1: MAX_ROUTING_LAYER=M1_m on asap7_3D (Kaggle CPU, 18 Nov 2026 19:25-20:05 UTC)

Script `scripts/s4_layer.sh` (sha256 79e2e0f9, as in `script.sha256`) over `scripts/rs_lib.sh` (43bddc33), at
ORFS-Research 568eb04d and TaiWei-Pin-3D 51a19d6f (`commits.txt`). The only change from S3 is the override
(`steps.log`, first line). Exit status 2: both cases fail (`exit_status.txt`, `steps.log`).

| Case | Wall time (`steps.log`) | Furthest step (`flow_logs.tgz`) | Failure | Upper-tier pins | Bottom-tier pins |
|---|---|---|---|---|---|
| gcd | 361 s | `5_1_grt` | DRT-0073 "No access point" | 11 | 0 |
| ibex | 2071 s | `5_1_grt` | DRT-0073 "No access point" | 56 | 0 |

Counts are the DRT-0073 lines in `flow_logs/asap7_3D/<case>/openroad/5_1_grt.log` by the master's `_upper` /
`_bottom` suffix (gcd has one more DRT-0073 line, the stage's summary error). GRT-0029 is gone: both cases pass
`3_place_upper`, CTS and `4_1_cts_post`, and stop at the pin access that `global_route.tcl` runs (line 273). The
failing pins are inner inputs of multi-input cells (AND3/AND4 A or B, OR3 B, AO21 B). Machine peak 22,008 MiB
(`memory.log`). Cause and next step: `../../GRT0029.md`, section "S4".

Kept local (per `.gitignore`): clone, checkout and apt logs, `shims.txt`, the kernel log; `pin3d_env.sh` is not kept.
