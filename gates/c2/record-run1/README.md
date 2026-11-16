# C2: MATRIX-A5 cell leakage, SPICE against the kit's Liberty

Registered 16 Nov 2026 (`registration.md`). Run 16 Nov, stopped after 3 of 15 libraries.

**Verdict: VOID** (V1 fails). `GT_A5_lvt_FFG_m40C` exited 1 with no values: the operating point did not converge at
-40 C (gmin stepping, source stepping and transient op all failed). The run was stopped while `GT_A5_lvt_SSG_m40C` had
spent 3 h in transient op, since the verdict could no longer change and the run held the heavy slot. The other 12
libraries were not simulated (`record/ngspice_rc.txt`).

| Library | Cells compared | rN | rP | Ratio range | Class |
|---|---|---|---|---|---|
| lvt FFG 125 C | 64 | 1.0000 | 1.0001 | 0.9997-1.0020 | EXACT |
| lvt SSG 125 C | 64 | 1.0000 | 1.0000 | 1.0000-1.0002 | EXACT |
| lvt FFG -40 C | 0 | - | - | - | no convergence |

Seen, not a verdict: where the operating point converged, every state of every combinational cell matched its Liberty
within 0.2%, so the gmin fix (registration, "Seen") removed the PMOS offset.

Next: find why -40 C does not converge (one deck holds all 756 states, so one hard state blocks the whole library),
fix the harness, and run again under a dated amendment. A VOID gives no verdict, so a rerun after a harness fix is
not a rerun to pass.

The first `evaluate.py` call after stopping raised a JSON decode error; a second call on the same files succeeded.
Not reproduced; recorded here.
