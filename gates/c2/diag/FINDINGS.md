# c2-diag: why C2 runs 1 and 2 were VOID, and what the kit's Liberty contains

Exploratory diagnosis, 17 Nov 2026, after run 2 (not a gate: no bars, nothing here is a verdict). Inputs are run 2's
own generated files in `../runs/` (models, subcircuits, options, stimulus), split or with one option changed; the
scripts below say which. All runs in `opentsense:g93a` (ngspice 45.2, the registered image).

## Finding 2 (svt aoi33_x1 / oai211_x1 at TT 25 C, 2.5-215x): the transient-op fallback, not the model

- In run 2's per-cell deck, Newton, gmin stepping and source stepping all failed and ngspice fell back to its
  transient op, which exits 0 (`../runs/GT_A5_svt_TTG_25C/gtA5_cfet_11_aoi33_x1_svt.log`: "Transient op finished
  successfully"). Its point is not a DC solution: the leaky stack nodes are still charging, so the supply current
  includes capacitor current. aoi33's all-low state reads -3.62e-10 A there.
- The same state alone (`c2diag.py f2`; `f2/svt_aoi33_x1/*.log`) converges by Newton to -1.680e-12 A, i.e.
  1.18e-12 W, the Liberty's value, under the registered options, reltol 1e-9, gmin 1e-15 and both nodesets (5
  variants, -1.68003e-12 to -1.68009e-12 A). Controls in the same way: lvt aoi33 and svt aoi22 alone (`f2/`).
- Physical check: in run 2, svt SPICE for the output-high states read above lvt and ulvt (aoi33 all-low: svt 2.53e-10
  W, lvt 1.28e-11, ulvt 1.02e-10); the svt Liberty keeps svt < lvt < ulvt.
- In run 2, 53 per-cell decks used the transient op (`grep -l "Transient op finished successfully"`): exactly these
  two at svt TT 25 C and 51 in the -40 C libraries. V1 ("exit 0") accepted all of them.

## Finding 1 (-40 C non-convergence): iteration limits, and a matrix with almost no conductance at floating nodes

svt SSG -40 C, the worst library (42 cells needing it, 700 states; `c2diag.py states`, one deck per state):

Counts from `c2diag.py summary <dir> [--prefix P]` on the logs in the directory named, saved in `record/summaries.txt` (failed = nonzero exit,
including the 120 s cap; source stepping: 0 except where stated):

| Change from run 2 (rest as registered) | Newton | gmin stepping | transient op (not DC) | failed | Logs |
|---|---|---|---|---|---|
| one deck per state (700) | 356 (+2 source stepping) | 199 | 122 | 21 | `f1/svt_SSG_m40C/` |
| + 25 C solution as `.nodeset` (143 hard states) | 23 | 21 | 83 | 16 | `f1/svt_SSG_m40C/nodeset/`, `p2_` |
| + `pivtol=1e-30` (143 hard) | 0 | 0 | 121 | 22 | `f1/svt_SSG_m40C/pivtol/`, `h_` |
| + `itl1=50000 gminsteps=200 srcsteps=200` (143 hard) | 120 | 7 | 10 | 6 | `f1/svt_SSG_m40C/itl/`, `i50k_` |
| gmin `1e-14` + those limits (all 700) | 626 | 11 | 11 | 52 | `f1/svt_SSG_m40C/gmin14/` |

Sample of 24 hard states (every 6th): `itl1=5000 gminsteps=50 srcsteps=50` gave 18 Newton, 3 gmin stepping, 3
transient op (`options/`, `itl_h_`); abstol 1e-16 gave 8, 8, 8 (`abs16_h_`). Controls (30 Newton-converged states):
pivtol and the iteration limits left their currents unchanged; abstol 1e-16 or 1e-17 moved them 0.3%, so abstol stays.
(The control comparisons were printed by the scripts of the first pass, since folded into `c2diag.py`; the logs are
kept under `pivtol/` and `options/` as `c_*`.)

## Finding 3 (new): the kit's Liberty carries a 7.0e-15 A floor per off PMOS (gmin = 1e-14)

- inv_x1's off-PMOS state `(A * !Y)`: Liberty minus SPICE is 6.99e-15 to 7.14e-15 A in every library at 25 and -40 C
  (`record/floor.txt`). At 125 C the off-PMOS leakage is 3e-10 to 7e-8 W, rounded in the Liberty at its 4th digit (1e-13 to 1e-11 W), so the
  floor cannot be resolved there (svt SSG 125 C shows 6.4e-15 A, the others -2.2e-11 to -3.6e-14 A). 7.0e-15 A =
  0.7 V x 1e-14 S,
  consistent with a characterisation at gmin = 1e-14 acting through BSIM-CMG's BULKMOD junction term (dry c1 found
  that term at `bsimcmg_body.include:2823`); the kit does not state its gmin. The off-NMOS state (bulkmod = 0) is
  within 0.25% everywhere (run 2 `result.json`, `(!A * Y)`).
- So C2's gmin = 1e-18 removes a floor the Liberty contains. Where real leakage is small the floor dominates: svt SSG
  -40 C inv_x1 off-PMOS is 7.99e-15 W in the Liberty and 3.09e-15 W in SPICE (ratio 0.39, rP in run 2).
- With gmin = 1e-14 (and the raised limits) the 637 svt SSG -40 C single-term states that reach DC have SPICE /
  Liberty median 1.0047 for the 626 Newton states and 0.9999 for the 11 gmin-stepping ones, range 0.958-4.59 over
  both, none rejected by the value checks (`record/ratios_gmin14.txt`, from `c2diag.py ratios
  f1/svt_SSG_m40C/gmin14 ../runs/GT_A5_svt_SSG_m40C`). The states outside [0.98, 1.02] are mostly in oa33, oai33,
  oai32 and oa32. Untested hypothesis: these cells have series PMOS stacks, so how a gmin floor adds up depends on
  where the kit's simulator places gmin.

## What this means for C2 and c3

- V1 as registered cannot detect finding 2: an exit code is not a DC solution. A run 3 must reject any case whose log
  shows the transient op (or any fallback that is not a converged DC point).
- Whether to compare at gmin = 1e-14 (reproduce the Liberty, floor included) or 1e-18 (device leakage without the
  floor, and state the floor as a known Liberty offset) is a choice of question for Amendment 2, for the student.
- For c3: at -40 C the kit's svt and lvt SSG leakage is partly the 7 fA-per-off-PMOS floor, not device physics; a
  leakage-temperature table must say whether it includes it.

## Scripts

`c2diag.py` (decks: `states`, `variant`, `nodeset`, `f2`; reports: `summary`, `ratios`, `floor`), `run_decks.sh`
(ngspice in the image), `test_c2diag.py`, `eq_check.py` (the rewrite into `c2diag.py` reproduces the first pass's 700
state decks, apart from the comment line and CRLF endings). Generated decks and logs under `f1/` and `f2/` are not
tracked.
