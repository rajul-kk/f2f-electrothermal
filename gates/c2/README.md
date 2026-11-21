# C2: MATRIX-A5 cell leakage, SPICE against the kit's Liberty · VOID (runs 1-4); run 4 has one FAIL, from the floor

Registered 16 Nov 2026 (`registration.md`, Amendments 1-3). No run has given a valid verdict: V1 (every case reaches
a DC point) fails in each. Records: `record-run1/` to `record-run4/`; `record/` holds the latest run (run 4).
Waiting on the student (registration.md, "Result of run 4").

## Run 4 (Amendment 3)

| Library | Scored | Listed (below cut) | Ratio range (scored) | Verdict |
|---|---|---|---|---|
| 11 libraries (all at 25 and 125 C, lvt and ulvt FFG -40 C) | 756 each | 0 | 0.9988-1.0056 | EXACT |
| ulvt SSG -40 C | 702 | 54 | 0.9931-1.0001 | EXACT |
| svt SSG -40 C | 0 | 743 | - | LISTED ONLY |
| svt FFG -40 C | 163 | 579 | - | VOID: one above-cut state (nand2_x3, A * !B * Y) hit the 2 min cap |
| lvt SSG -40 C | 25 | 718 | 0.9590-1.0001 | FAIL |

(`record-run4/summary.md`.) The lvt SSG -40 C FAIL comes from the floor. Every scored state below 0.98 is short of
its Liberty value by 2 to 12 floors (7.0e-15 A x 0.7 V each, within 0.03 of a whole number). These are the
multi-finger cells, one floor per off PMOS finger, while the cut allows for only one. The states without such a gap
read 1.0000-1.0001. Run 4 also answers the run 3 probe's open question: only one above-cut state lacks a DC point.

## Run 3 (one deck per state, Amendment 2)

VOID in 13 of 15 libraries (`record-run3/summary.md`). 636 states have no DC point, 495 of them above the floor cut,
including 111 in svt SSG 125 C and 44 in svt TTG 25 C, which converged in run 2. ulvt FFG -40 C is EXACT (ratios
0.9998-1.0000) and svt SSG -40 C is LISTED ONLY. Cause, from the probe (`diag/a3_probe.py`, `diag/a3/report.json`):
Amendment 2's `gminsteps=200 srcsteps=200`. Rerunning run 3's decks without both options, 602 of the 636 states
reach a DC point, every state above the cut among them, and 150 states that already converged keep their current
exactly. Amendment 3 removes the two options, and run 4 reruns all 15 libraries.
The probe's limit: of run 3's 11,340 states, 10,517 reached their DC point by Newton, which the change cannot affect,
and 187 by gmin stepping with `gminsteps=200`. Only 5 of those 187 were among the probe's controls (145 of the 150
were Newton states). Run 4 is the first test of the other 182 under ngspice's default stepping.

## Run 2 (one deck per cell, Amendment 1; `record-run2/`)

| Library | Cells compared | rN | rP | Ratio range | Class |
|---|---|---|---|---|---|
| svt TTG 25 C | 64 | 1.0000 | 0.9988 | 0.9988-215.6 | FAIL class (finding 2) |
| svt SSG 125 C | 64 | 1.0000 | 1.0000 | 1.0000-1.0001 | EXACT |
| svt FFG 125 C | 64 | 1.0000 | 1.0000 | 1.0000-1.0002 | EXACT |
| lvt TTG 25 C | 64 | 1.0000 | 0.9999 | 0.9999-1.0000 | EXACT |
| lvt SSG 125 C | 64 | 1.0000 | 1.0000 | 1.0000-1.0002 | EXACT |
| lvt FFG 125 C | 64 | 1.0000 | 1.0001 | 0.9997-1.0020 | EXACT |
| ulvt TTG 25 C | 64 | 1.0000 | 1.0000 | 1.0000-1.0001 | EXACT |
| ulvt SSG 125 C | 64 | 1.0000 | 1.0000 | 0.9999-1.0007 | EXACT |
| ulvt FFG -40 C | 64 | 1.0000 | 0.9998 | 0.9998-1.0000 | EXACT |
| ulvt FFG 125 C | 64 | 1.0002 | 1.0002 | 0.9991-1.0056 | EXACT |
| svt SSG -40 C | 40 converged | | | | VOID (V1) |
| svt FFG -40 C | 42 converged | | | | VOID (V1) |
| lvt SSG -40 C | 40 converged | | | | VOID (V1) |
| lvt FFG -40 C | 63 converged | | | | VOID (V1) |
| ulvt SSG -40 C | 54 converged | | | | VOID (V1) |

(`record-run2/summary.md`; decks that exited 0 per library in `record-run2/ngspice_rc.txt`.)

## Findings, not a verdict

1. **-40 C does not converge cell by cell either.** In svt SSG -40 C, 456 cases end with NaN (exit 1) and 64 hit
   the 2 min cap, mostly cells with series stacks (aoi, oai, nor3, xor2, nand2/nor2 x2-x4). One deck per cell helped
   (lvt FFG -40 C: 0 to 63 cells) but is not the whole cause. Candidate causes, untested: gmin = abstol = 1e-18 at
   currents of about 1e-14 A leave floating stack nodes ill-conditioned at low temperature; the card's behaviour at
   -40 C. Two harness fixes have been tried; the next step is a diagnosis, not a third rerun (task c2-diag).
2. **svt aoi33_x1 and oai211_x1 at TT 25 C read 2.5 to 215 times their Liberty** in output-high states, with clean
   convergence (exit 0, outputs within 7 uV). The same cells match in lvt and ulvt (ratio about 1), which reuse the
   svt netlist with renamed models. So the svt card or the svt Liberty for these two cells differs from the others;
   to diagnose before any claim.
3. Where everything converged and the cells are not those two, every state of every combinational cell matches its
   Liberty within 0.6% at 25 and 125 C in all three Vt: the gmin fix removed the PMOS offset.

## Run 1 (one deck per library)

VOID: `GT_A5_lvt_FFG_m40C` did not converge; stopped after 3 of 15 libraries (lvt FFG and SSG 125 C were EXACT).
Cause of the stop: one deck held all 756 states, so one hard state blocked the library (Amendment 1).
