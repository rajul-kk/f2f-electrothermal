# c6 v3 (20 Nov 2026): backside vs frontside heat path and runaway margin, MATRIX-A5 leakage (dry, no bars)

Design: `../../DESIGN.md` (with Amendment 1). Run: `TAG=v3 PKG=worktree bash dry/c6/run_c6.sh ../open3d-thermal-ext
<opentsense repo>` (container memory cap 1500m, `run_c6.sh`), image ID and package in `inputs.sha256` (package: the OpenTSense
working tree with the runaway fix, `opentsense_pkg.tgz`, `opentsense_status.txt`). `run.log` ends
`docker rc=0 after 3579 s` and `rc=0`; `c6.json` has the end marker and 15 planned stacks. v1 was stopped by hand and
v2 is not used for a verdict (Amendment 1).

## Checks (`summary.md`, from `c6.json`)

| Check | Result |
|---|---|
| a: mean rise within 10% of the 1-D estimate | 15 of 15 (largest 0.03%, the frontside stacks) |
| b: R column against a direct PACT run, max abs difference <= 0.005 K | 0.004998 K: passes, but at the limit, which is half of PACT's 0.01 K output step (`../../DESIGN.md`, check b), so this check cannot resolve a difference below PACT's rounding |
| c: margin located, every probe classified | 90 of 90 cases, all converged at nominal leakage |
| d: one-tile margin against the analytic boundary | -3.7e-8 relative |

## Results (`c6.json`; ratios are backside / frontside at the same k_beol, workload and Vt)

| | Uniform | Hotspot |
|---|---|---|
| Peak rise per W, no leakage | 1.085 to 1.366 x | 1.504 to 2.895 x |
| Runaway margin s_crit | 0.568 to 0.881 x | 0.497 to 0.880 x |

The ranges span all 12 backside stacks and three Vts. For svt:
- **The BEOL conductivity sets most of it.** At k_beol 0.6 the uniform rise is 1.32 to 1.37 x and s_crit is 0.57 to
  0.60 x. At k_beol 3.0 they are 1.09 to 1.13 x and 0.81 to 0.87 x.
- **Under the hotspot, the backside PDN's conductivity matters too.** At k_beol 0.6 and t_c 50 um, k_bs = 10 gives
  2.895 x the frontside peak rise against 2.465 x at k_bs = 71.
- **The thicker carrier (200 um) raises the uniform rise slightly** (1.366 against 1.324 x at k_beol 0.6).

The per-case rows (peak T, rho, s_crit, critical 25 C leakage density) are in `summary.md`.

This record does not set a bar or claim agreement with any other solver. It is PACT only, with the Limits in
DESIGN.md: one VDD, TT only, cell-mean leakage, isotropic BEOL and BSPDN layers, and an adiabatic bottom.

## Cost

3,579 s of Docker wall time for 15 stacks (about 240 s per stack), against DESIGN.md's "minutes" (A10). v1,
before the runaway fix, had finished two stacks and five of the third stack's six cases when it was stopped at 480 s
(`../2026-11-19_c6_v1/run.log`, rc=137), so the estimate was already low then. This record does not split the
time between the operator build and the margin search.
