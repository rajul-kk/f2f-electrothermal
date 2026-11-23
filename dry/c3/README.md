# c3: MATRIX-A5 leakage against temperature at TT

Design and checks: `DESIGN.md` (fixed before the run). Record: `record/` (run of 19 Nov 2026, rc 0).

**Result: all four checks pass for all three Vt** (`record/summary.md`, `record/checks.json`).

| Vt | States | 1 parity mismatches | 2 invalid (any T) | 3 not rising | 4 outside SS-FF at 125 °C | P(125)/P(25) median (range) | log-linear fit worst |
|---|---|---|---|---|---|---|---|
| svt | 756 | 0 | 0 | 0 | 0 | 171.80 (90.59-264.92) | 8.9% |
| lvt | 756 | 0 | 0 | 0 | 0 | 93.14 (49.75-130.16) | 6.2% |
| ulvt | 756 | 0 | 0 | 0 | 0 | 55.49 (29.49-90.84) | 6.3% |

- All 18 libraries x 756 decks reached a DC point on the first try; none needed the retry deck
  (`record/ngspice_rc.txt`).
- Check 1 is exact equality with C2 run 5's TT 25 °C values (`gates/c2/runs`), so the `.temp` rewrite changed
  nothing else in the decks.
- Check 4 brackets each state's TT 125 °C power between C2 run 5's SS and FF 125 °C SPICE values; no state needed
  the "no bracket" exception.
- The log-linear fit is description only (DESIGN.md): its worst residual per Vt is the largest over cells, so an
  exponential in T is not used as a substitute for the table.
- The ratios are true device leakage at gmin 1e-18, without the kit's gmin floor (DESIGN.md).

**Use.** `record/tables.json` holds per Vt, cell and state the power in W at 25, 45, 65, 85, 105 and 125 °C
(VDD 0.7 V), plus each cell's mean over its states. Inputs and every deck are hashed in `record/sha256.txt`.

**Run.** `bash dry/c3/run_c3.sh <ext dir>` in a heavy slot (1 GB container), about 1 h on the laptop. `runs/` is local
(gitignored).

**Limits.** TT only, one VDD, sequential cells skipped as in C2, uniform temperature per cell.
