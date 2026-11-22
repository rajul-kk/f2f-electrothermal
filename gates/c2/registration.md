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

## Amendment 2 (18 Nov 2026, after run 2 and the diagnosis `diag/FINDINGS.md`; post-run)

The question is unchanged. The student chose (18 Nov) to measure device leakage: gmin stays 1e-18, and the floor the
kit's Liberty carries is stated and cut out of the scoring (option A of the three the student was shown). Changes,
each from a diagnosis finding:

1. **One deck per state** (`s<i>.cir`), was one per cell. Run 2's per-cell decks fell back to the transient op where
   the same states alone converged (finding 2).
2. **Options:** `.option gmin=1e-18 abstol=1e-18 reltol=1e-5 itl1=50000 gminsteps=200 srcsteps=200`; only the
   iteration limits are raised (finding 1: 120 of 143 hard svt SSG -40 C states then converge by Newton, and 30 states
   that already converged keep their currents).
3. **V1 also requires a DC point:** a case is invalid unless its log shows Newton, gmin stepping or source stepping
   (`leak.method`, the one classifier, also used by `diag/c2diag.py`). "Transient op finished" is invalid even with
   exit 0 (finding 2: 53 run-2 decks passed V1 that way).
4. **Floor cut:** the kit's Liberty is 7.0e-15 A per off PMOS above SPICE at 25 and -40 C (finding 3). A state is
   scored only if its Liberty value is at least 100 x 7.0e-15 A x VDD (4.9e-13 W at 0.7 V): the floor is then at most
   1% of it per off PMOS. States below are listed with their ratios in `summary.json` (`below_floor`), not scored.
   - EXACT and DEVICE OFFSET apply to the scored states, bars unchanged. An rN or rP whose inv_x1 state is below the
     cut is not a reference: that library can then be EXACT or FAIL, not DEVICE OFFSET.
   - A library with no state above the cut is **LISTED ONLY**: it neither passes nor fails C2, and the result says so.
   - V4 counts cells with a valid comparison, scored or listed (the cut is a scoring rule, not a coverage loss).
   - Share listed, from run 2's cases (`diag/threshold_share.py runs`, of 756 per library): svt SSG -40 C 756 (100%),
     lvt SSG -40 C 731 (96.7%), svt FFG -40 C 592 (78.3%), ulvt SSG -40 C 54 (7.1%), none in the other 11. So C2
     says nothing scored about svt SSG -40 C, and little about lvt SSG and svt FFG at -40 C.
   - The c3 temperature check uses only rN and rP above the cut.
5. **V1 and V2 cover states at or above the cut** (decided by the student on 18 Nov after the cost probe below, so
   not blind to it): a state below the cut that does not reach a DC point is named in `invalid_below_floor`, not
   voiding, and so is a below-cut state whose output misses V2 (`out_err_below_floor`). Reason: such a state carries
   no claim under 4. The probe (`diag/record/a2_cost_svt_SSG_m40C.txt`, run 3's
   exact decks at svt SSG -40 C): 710 of 756 reach a DC point; 46 do not (17 transient op, 29 failed), all with Liberty
   at most 2.74e-14 W; 1052 s for the library.

Decision, amended: C2 passes if V1-V4 hold (V1 and V2 as in 5) and no library FAILs; LISTED ONLY libraries and invalid
states below the cut are named in the result.
Everything else is unchanged: cells, skip rules, V2, V3, references, cards, image and pinned hashes.

Seen before run 3, so not unseen: at svt SSG -40 C, the 143 hard states at these options and 700 states at gmin 1e-14
(diagnosis), then all 756 at exactly run 3's decks and options (this amendment's cost probe,
`diag/record/a2_cost_svt_SSG_m40C.txt`); svt aoi33_x1's all-low state and lvt aoi33_x1's and svt aoi22_x1's all-low
states at TT 25 C; all of run 2's values. Run 3 reruns all 15 libraries.

## Result of run 3 (18 Nov 2026, post-run)

VOID (`record-run3/`): V1 fails in 13 of the 15 libraries. 636 states have no DC point, 495 of them above the floor
cut, including 111 in svt SSG 125 C and 44 in svt TTG 25 C, where run 2 converged every state. ulvt FFG -40 C is
EXACT and svt SSG -40 C is LISTED ONLY. The failures are new with Amendment 2's options: Newton goes to NaN, then
gmin and source stepping both fail.

## Amendment 3 (18 Nov 2026, after run 3 and the probe `diag/a3_probe.py`; post-run)

The question, cells, bars, floor cut and validity rules are unchanged. One change:

1. **Options:** `.option gmin=1e-18 abstol=1e-18 reltol=1e-5 itl1=50000`. `gminsteps=200 srcsteps=200` are removed,
   and the raised Newton limit stays. The probe (`diag/a3/report.json`, `diag/a3_run.log`) reran run 3's own decks
   for all 636 states without a DC point, plus 10 per library that had one, in three variants:

   | Variant | States reaching a DC point | Above the cut, still without one | Valid controls' current change |
   |---|---|---|---|
   | without srcsteps | 578 / 636 | 1 | 0 |
   | without gminsteps | 566 / 636 | 7 | 0 |
   | **without both** | **602 / 636** | **0** | 0 |

   The 34 states still without a DC point are all below the cut (lvt SSG -40 C 12, svt FFG -40 C 10, svt SSG -40 C
   12). Under Amendment 2's item 5 they are named in the result and do not void it. The above/below split was counted
   against run 3's `summary.json` lists (`below_floor`, `invalid_below_floor`).

Seen before run 4, so not unseen: every value of run 3 (`record-run3/`), and the 602 + 150 probe states above. Run 4
reruns all 15 libraries.

## Result of run 4 (18 Nov 2026, post-run)

VOID (`record-run4/`). V1 fails in one library, on one state: svt FFG -40 C, `nand2_x3_svt (A * !B * Y)`, which is
above the cut and hit the 2 min cap (exit 124). Twelve libraries are EXACT and svt SSG -40 C is LISTED ONLY. 39
states below the cut have no DC point (13 each in svt SSG, svt FFG and lvt SSG at -40 C); under item 5 they do not
void the run.

**lvt SSG -40 C is FAIL:** 25 scored states, ratios 0.9590-1.0001. Its inv_x1 states are below the cut, so it can be
only EXACT or FAIL (item 4). In every state below 0.98, the gap Liberty - SPICE is within 0.03 of a whole multiple of the floor
(7.0e-15 A x 0.7 V), 2 to 12 times (`runs/GT_A5_lvt_SSG_m40C/result.json`; for example inv_x12 (A * !Y) is 12.00
times). These are the multi-finger cells, with one floor per off PMOS finger. The cut assumed the floor is at most 1%
of a scored state, which holds only for one off PMOS. The four states without an off PMOS gap read 1.0000-1.0001.

So under these rules C2 does not pass. The FAIL comes from the stated Liberty floor, not from a device mismatch shown
by these states. No further run or amendment is made without the student's decision (scale the cut, or subtract the
floor, by the number of off PMOS; or accept the FAIL and use the c3 fallback).

## Amendment 4 (18 Nov 2026, after run 4 and the probe `diag/a4_probe.sh`; post-run)

The student chose (18 Nov) to scale the cut by the floor each state carries, and to fix the state that voided run 4.
The question, cells, skip rules, bars, references, cards, image and pinned hashes are unchanged. Changes:

1. **Floor cut per state.** A state is scored only if its Liberty value is at least 100 x its own kit floor, and
   never below Amendment 2's one-floor cut (4.9e-13 W at 0.7 V). The kit floor is the current the kit's gmin
   (1e-14 S, finding 3) adds through BSIM-CMG's BULKMOD junction terms (`bsimcmg_body.include:2823-2824`),
   computed from the state's own operating point: 1e-14 S x m x (V(e) - V(di) + V(e) - V(si)), summed over the PMOS,
   times VDD (`leak.kit_floor_w`; the decks add `print all` for the junction voltages).
   - The floor is computed from our operating point at gmin 1e-18, not the kit's at 1e-14. In the probe it is an
     **upper bound**: over the 557 (lvt SSG -40 C) and 485 (svt FFG -40 C) states whose floor exceeds 1% of their
     Liberty value, (SPICE + floor) / Liberty is 0.9997-1.3528 and 0.9995-1.3255 (`diag/a4/summary.json`,
     `floor_check`). 304 and 249 of them read 0.98-1.02. The high ones are PMOS stacks (nor3, oai33, aoi211), where
     mid-stack nodes sit differently at the kit's gmin (`diag/a4/floor_check.json`, `outside`). An upper bound makes
     the cut conservative: a scored state's floor is at most 1% of it. The cost is that more states are listed.
   - A state without an operating point (invalid) keeps the one-floor cut, so a state that does not converge is
     never excused by an estimate. A valid state whose junction voltages are missing from its log is invalid
     ("junction voltage missing (kit floor)"), not given the one-floor cut.
   - `floor_check` is reported per library and is not a bar.
2. **Retry deck.** A deck that may lack a DC point (nonzero exit, or "transient op" in its log) runs once more with
   Amendment 2's options, `.option gmin=1e-18 abstol=1e-18 reltol=1e-5 itl1=50000 gminsteps=200 srcsteps=200`
   (`ngspice_states.sh`). If the first deck has no DC point (`leak.method`), the retry's log is used; the first
   method and exit code are kept in `result.json` (`first_method`, `first_rc`). The DC point does not depend on
   how it was reached: in the Amendment 3 probe, valid controls kept their current under every option set
   (`diag/a3/report.json`). The 2 min cap is unchanged. Run 4's voiding state, `nand2_x3_svt (A * !B * Y)` at
   svt FFG -40 C, had failed Newton, gmin and source stepping and was in the transient op when it hit the cap
   (`diag/a4/run4_s0373_nand2_x3_svt_FFG_m40C.log`), so a longer cap would not have made it valid. With the retry
   it reaches a DC point by gmin stepping. Run 4's per-state logs are kept outside the repository
   (`open3d-thermal-ext/c2_run4_runs`), as run 3's are.

Probe (`diag/a4_probe.sh`, `diag/a4/summary.md`): Amendment 4's decks for lvt SSG -40 C and svt FFG -40 C.

| Library | Retried | Retry reached a DC point | Invalid above cut | Invalid below cut | Scored | Listed | Ratio range (scored) | Verdict |
|---|---|---|---|---|---|---|---|---|
| svt FFG -40 C | 14 | 4 (nand2_x3 among them) | 0 | 10 | 112 | 634 | 0.9902-1.0001 | EXACT |
| lvt SSG -40 C | 13 | 1 | 0 | 12 | 4 | 740 | 1.0000-1.0001 | EXACT |

The probe's last deck in svt FFG -40 C (s0755) was cut short when `ngspice_states.sh` was edited while it ran. It
was rerun alone with the same decks and steps, then compared again; the table includes the rerun.

Limits added: in lvt SSG and svt FFG at -40 C most states are listed, not scored (lvt SSG -40 C scores 4 states,
run 4 scored 25), because the floor bound is high in stacks. A floor from the kit's own operating point (a second
deck at gmin 1e-14 per state) would list fewer; it is not used here.

Seen before run 5, so not unseen: every value of run 4 (`record-run4/`) and every value of the probe above. Run 5
reruns all 15 libraries.

## Result of run 5 (18 Nov 2026, post-run)

**PASS** (`record-run5/`; `record/` holds the same run). V1-V4 hold in all 15 libraries, with the same dropped cells
in each and no unregistered skips. 14 libraries are EXACT and svt SSG -40 C is LISTED ONLY (no state at or above
its cut), which under Amendment 2 neither passes nor fails C2. No library FAILs and none is DEVICE OFFSET.

| Library | Scored | Listed (below cut) | Ratio range (scored) | Retried | Invalid (all below cut) | Verdict |
|---|---|---|---|---|---|---|
| 8 of the 9 libraries at 25 and 125 C, and ulvt FFG -40 C | 756 each | 0 | 0.9991-1.0056 | 0 | 0 | EXACT |
| svt TTG 25 C | 753 | 3 | 0.9988-1.0000 | 0 | 0 | EXACT |
| lvt FFG -40 C | 753 | 3 | 0.9989-1.0001 | 0 | 0 | EXACT |
| ulvt SSG -40 C | 547 | 209 | 0.9931-1.0001 | 0 | 0 | EXACT |
| svt FFG -40 C | 112 | 634 | 0.9902-1.0001 | 14 | 10 | EXACT |
| lvt SSG -40 C | 4 | 740 | 1.0000-1.0001 | 13 | 12 | EXACT |
| svt SSG -40 C | 0 | 744 | - | 13 | 12 | LISTED ONLY |

(`record-run5/summary.md`, `record-run5/summary.json`; exit codes and retries per library in
`record-run5/ngspice_rc.txt`.) svt FFG -40 C and lvt SSG -40 C repeat the Amendment 4 probe exactly (scored states,
ratio ranges and floor checks). The 34 invalid states are all below their cut and are named in `summary.json`
(`invalid_below_floor`); none voids the run (Amendment 2, item 5).

The floor check (not a bar) reads 0.9894-4.7715 over 561 states in svt SSG -40 C and 1.0040-1.0589 over 195 in ulvt
SSG -40 C. Its minimum in every library is above 0.98, so the floor is not undercounted by more than the tolerance.

For c3: inv_x1's ratios at -40 C and at 125 C are both scored in three Vt and corner pairs (lvt FFG, ulvt SSG,
ulvt FFG); rN changes by at most 0.02% and rP by at most 0.69% (ulvt SSG) between them (`offset_change_m40_to_125C`).
None is above 2%, so no offset is shown to depend on temperature. In the other three pairs inv_x1 is below the cut at
-40 C, so the comparison is not available there.

Limits of this PASS: svt SSG -40 C is not tested at all, and lvt SSG -40 C rests on 4 states. Both follow from
the floor cut (Amendment 4, limits), not from a mismatch shown by any state.
