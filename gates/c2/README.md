# C2: MATRIX-A5 cell leakage, SPICE against the kit's Liberty · VOID (runs 1 and 2)

Registered 16 Nov 2026 (`registration.md`, Amendment 1 after run 1). Neither run gives a verdict: V1 (every case
converges) fails at -40 C in both. Records: `record-run1/`, `record/` (run 2).

## Run 2 (one deck per cell, Amendment 1)

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

(`record/summary.md`; decks that exited 0 per library in `record/ngspice_rc.txt`.)

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
