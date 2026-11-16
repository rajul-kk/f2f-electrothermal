# C2: MATRIX-A5 cell leakage from open SPICE equals the kit's Liberty

Registered 16 Nov 2026, before any library other than svt TTG 25 C was simulated for values, and before any cell
other than the three listed under "Seen" was simulated. One unseen deck (svt SSG -40 C, the smallest currents) was run
only to check that the chosen solver options converge: the count of currents was read, no value.

## Question

Does open ngspice with Berkeley's BSIM-CMG 111.2.1 (compiled with OpenVAF-Reloaded) reproduce MATRIX-A5's own
Liberty leakage per state, across Vt (svt, lvt, ulvt), corners and temperatures (TTG 25 C; SSG and FFG at -40 C and
125 C)? Gap 2's per-temperature leakage (c3) rests on this: the kit gives TT only at 25 C.

## Seen before registration (dry c1, `dry/c1/NOTES.md`)

svt TTG 25 C: inv_x1, inv_x4 and nand2_x1. At ngspice's default options every off-NMOS state matched to 1e-4 and
every off-PMOS state was 1.1222 times the Liberty. Cause found: the model adds V(e, di) x gmin to its junction current
when BULKMOD != 0 (`bsimcmg_body.include:2823`); the PMOS cards have bulkmod = 1, the NMOS cards 0, so default gmin
(1e-12 S) adds 0.7 pA to each off PMOS. With gmin = 1e-18 (the options below) the off-PMOS states are 0.9988 and the
off-NMOS states unchanged.

## Method

- `leak.py deck` per library: every cell, every VDD `leakage_power` state with a `when`, every product term of a
  sum-of-products `when` (the state scored as the mean of its terms), one instance each with its own supply; inputs at 0 or VDD; operating point at the Liberty's
  `nom_temperature` and `nom_voltage`; the corner's card (`GT_A5_<corner>.inc`). lvt and ulvt reuse the svt CDL with
  the model and cell names swapped. `leak.py compare`: SPICE power = -I(VDD) x VDD. Options `.option gmin=1e-18 abstol=1e-18 reltol=1e-5` (defaults
are not small next to ~1e-15 A states; 1e-21 did not converge); vntol stays at its default, 1e-6 V.
- Card handling: `devtype` becomes `TYPE`; every name not declared in `bsimcmg_parameters.include` is dropped and
  listed. Thermal node grounded (shmod = 0 in every card).
- Skipped by rule only, each with its reason listed: a cell whose Liberty has an `ff` or `latch` group, or with no
  svt CDL, no input, no VDD state, or a state that cannot be set from its input ports. (Edited 16 Nov after code
  review, before the run: the first rule, "a state naming a non-port node", missed flops, whose states name `Q`.)
- Inputs (`run.sh` refuses to run if the commit or a hash differs): MATRIX-PDK-CFET-A5-V1 at 56b467142c870284eb0cec1e89a680522e7a171d; OSDI sha256 ce7b25c8…acac; parameters
  file 33eed640…0697; cards TTG 16918dc1…2669, SSG 40d8eb01…b5e6, FFG 9eb5e23a…b4b7; ngspice 45.2 in `opentsense:g93a`.
  `run.sh` records in `record/sha256.txt` the image id, the kit commit, and the hashes of the OSDI, the parameters
  file, the cards, every Liberty and CDL, the scripts and every generated deck.

## Validity (all must hold, else the gate is void, not failed)

- V1 ngspice exits 0, every case has finite current and output voltages in the log, and every supply sources
  current.
- V2 every output pin named in a `when` is within 10% of VDD of its literal (G92e's bar; checks the cell's function and
  the svt-to-lvt/ulvt netlist swap).
- V3 the dropped names (card names not declared in the parameters file) are the same in every library, and every
  skipped cell has one of the registered skip reasons.
- All 15 libraries are present.
- V4 at least 50 cells per library have at least one scored state.

## Bars, per library

References from the same library: rN = ratio of inv_x1's `(!A * Y)` state (off NMOS), rP = ratio of its `(A * !Y)`
state (off PMOS). Ratio = SPICE / Liberty; states with Liberty value 0 or below are listed, not scored.

- **EXACT**: every ratio within [0.98, 1.02].
- **DEVICE OFFSET**: not EXACT, and every ratio within [min(rN, rP) - 0.02, max(rN, rP) + 0.02]: each cell's error is
  bounded by the two single-device errors.
- **FAIL**: otherwise.

Why 2%: the NMOS path reproduced to 1e-4, so 2% leaves room only for solver tolerance and Liberty rounding (5-6
digits), not for a model difference.

## Decision

- C2 passes if every library is EXACT or DEVICE OFFSET and V1-V4 hold.
- Use in c3: SPICE gives the shape of leakage against temperature, anchored to the Liberty's own values. If, at one
  corner and Vt, |rP(125 C) - rP(-40 C)| / min of the two (or the same for rN) is above 2%, the offset depends on temperature and c3
  must carry that difference as a stated error on its temperature ratios.
- A FAIL stops c3 on SPICE; the fallback is interpolating the kit's -40/25/125 C Liberties, stated as such.

## Limits

- The card names V3 lists are dropped: binning bounds (lmin, lmax), version, devtype (mapped to TYPE), switches
  111.2.1 does not have (coremod = 1 and capmod = 0 in every card; 111.2.1 has a single core model), and names from
  the card's commercial-simulator origin. The dry's 1e-4 NMOS match suggests the kit was characterised with the same
  code, but that is not shown for every name.
- The result depends on gmin through the BULKMOD junction term; the options are fixed above.
- Combinational cells only; flops and latches are skipped by the rule above.
- Leakage only; no delays or capacitances.

## Amendment 1 (16 Nov 2026, after run 1; post-run)

Run 1 (`record-run1/`) is VOID: in `GT_A5_lvt_FFG_m40C` the operating point did not converge (gmin stepping, source
stepping and transient op all failed), and it was stopped after 3 of 15 libraries. Cause, shown before this change:
the whole library was one deck, and ngspice's stepping acts on the whole matrix; the two cells it named singular
(nand3_x1, aoi33_x1) converge alone in about a second with the same options. Change: one deck per cell sharing one
models file, each with a 2 min cap (exit 124 is invalid under V1). Options, bars, validity and skip rules unchanged.

Seen before run 2, so not unseen: every value of lvt FFG 125 C and lvt SSG 125 C (all 64 cells EXACT, ratios
0.9997-1.0020), and at lvt FFG -40 C the states of inv_x1, nand2_x1 and nand3_x1 (ratios 0.9989-1.0000; the harness
check). Run 2 reruns all 15 libraries; nothing from run 1 is reused.

## Result of run 2 (16 Nov 2026, post-run)

VOID again on V1 (five -40 C libraries have non-converged cells). No further rerun under this registration until the
cause is found (task c2-diag); see README.md for the findings.
