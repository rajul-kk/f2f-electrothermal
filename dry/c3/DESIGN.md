# c3: MATRIX-A5 leakage against temperature at TT (dry, 19 Nov 2026)

**Why.** The kit's Liberty has TT only at 25 °C (SS and FF at -40 and 125 °C), and the electrothermal loop needs
leakage at each tile's temperature. C2 passed (run 5, `gates/c2/registration.md`): the same SPICE decks reproduce the
kit's Liberty to within 2% in every scored state, at TT 25 °C and at both temperatures of SS and FF. c3 runs those
decks on the TT card at the temperatures the thermal solvers need.

**What runs.** C2's harness, unchanged (`gates/c2/leak.py`, `ngspice_states.sh`, same image, card, OSDI and pinned
hashes). For each Vt (svt, lvt, ulvt), `leak.py deck` writes the 756 state decks from the TT 25 °C Liberty, and
`c3.py retemp` changes only each deck's `.temp` line (exactly one per deck, checked) to T, for
T = 25, 45, 65, 85, 105, 125 °C. 18 libraries x 756 decks; run 5 took 2 h 15 min for 15 libraries on the laptop.
Values are true device leakage at gmin 1e-18 (the student's decision, 18 Nov), without the kit's gmin floor.

**Checks** (fixed before the run; a failed check is reported, not hidden):

| # | Check | Why |
|---|---|---|
| 1 | At 25 °C every state's SPICE power equals C2 run 5's TT 25 °C value exactly | the retemp step changes nothing else (A15) |
| 2 | Every state has a DC point at every T (else listed, and its row is empty at that T) | as C2's V1 |
| 3 | Each state's power rises with T at every step | physics; a fall is named |
| 4 | At 125 °C each state's TT power lies between C2 run 5's SS and FF 125 °C SPICE values (state-wise) | an independent bracket from the corners |

**Output.** `record/tables.json`: per Vt, per cell, per state the power (W) at each T, and the cell's mean over its
states (how the kit's `cell_leakage_power` relates to its states is not assumed; both are given). `record/summary.md`:
the checks, and per Vt the median and range of P(125 °C) / P(25 °C). A log-linear fit per cell is reported as a
description only (its worst relative residual), not used.

**Limits.** TT only; one VDD (the Liberty's, 0.7 V); sequential cells skipped as in C2; the decks see a uniform
temperature per cell.

Architecture lints: A1 (each state a deck, its own row), A4 (the population is C2's, from the same Liberty), A5
(states keep their (cell, when) key through every stage), A9 (deck rules live in `leak.py` only), A10 (cost from run
5), A11 (detached, in a slot), A14 (record/ append-only), A15 (check 1), A25 (README numbers cite `record/`).
