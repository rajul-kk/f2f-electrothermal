# C2: MATRIX-A5 cell leakage, SPICE against the kit's Liberty

Registered 16 Nov 2026 (`registration.md`). Run 16 Nov, stopped after 3 of 15 libraries.

**Run 1 verdict: VOID** (V1 fails; record in `record-run1/`). Run 2 under Amendment 1 follows. `GT_A5_lvt_FFG_m40C` exited 1 with no values: the operating point did not converge at
-40 C (gmin stepping, source stepping and transient op all failed). The run was stopped while `GT_A5_lvt_SSG_m40C` had
spent 3 h in transient op, since the verdict could no longer change and the run held the heavy slot. The other 12
libraries were not simulated (`record-run1/ngspice_rc.txt`).

| Library | Cells compared | rN | rP | Ratio range | Class |
|---|---|---|---|---|---|
| lvt FFG 125 C | 64 | 1.0000 | 1.0001 | 0.9997-1.0020 | EXACT |
| lvt SSG 125 C | 64 | 1.0000 | 1.0000 | 1.0000-1.0002 | EXACT |
| lvt FFG -40 C | 0 | - | - | - | no convergence |

Seen, not a verdict: where the operating point converged, every state of every combinational cell matched its Liberty
within 0.2%, so the gmin fix (registration, "Seen") removed the PMOS offset.

Cause (Amendment 1): one deck held all 756 states, and ngspice's stepping acts on the whole matrix; the failing
cells converge alone. Run 2 uses one deck per cell. A VOID gives no verdict, so a rerun after a harness fix is not a
rerun to pass.

The first `evaluate.py` call after stopping raised a JSON decode error; a second call on the same files succeeded.
Not reproduced; recorded here.
