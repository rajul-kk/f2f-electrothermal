# c5-dry: static IR drop on MATRIX-A5's backside power grid, with c4's solver (design)

Drafted 18 Nov 2026, revised after review the same day. A dry run, not a gate: no bars. It needs c4 (the solver,
checked against PDNSim on a frontside grid, `dry/c4/README.md`) and c1 (the kit runs). OpenROAD has no MATRIX-A5
P&R port, so there is no placed design and no PDNSim reference here (`ambitions.md` 7); c5 builds the grid the kit's
own Innovus variables describe and reports drop per unit load. That is what the kit fixes; a placed design would add
only the load map.

## Inputs (MATRIX-PDK-CFET-A5-V1 at 56b46714, `MATRIX_A5_CFET_base`; sparse clone in `open3d-thermal-ext/matrix-a5-lef`)

| File | sha256 | Gives |
|---|---|---|
| `PDK_PATHS.tcl` | a7d032d5... | the grid: BSM1 vertical stripes 0.2 wide, VDD-VSS spacing 0.8, set-to-set 2.0, offset 0; BSM2 horizontal 0.5 wide, spacing 1.1, set-to-set 3.2, offset 2.4; ring on BSM2 (horizontal sides) and BSM3 (vertical), width 1.0, spacing 1.1, offset 0.5; core pins on BPR; site 0.039 x 0.072 um; 0.7 V |
| `lef/gtA5_cfet.tlef` | b0513aea... | layer widths: BPR 0.024, BSM1 0.2, BSM2 0.5, BSM3 1.0 um; the backside via generate rules (cut size, centre-to-centre pitch, enclosures, DEFAULT flag) and fixed DEFAULT vias; **no RESISTANCE on any layer** |
| `lef/gtA5_cfet_macros.lef` | (hashed in the record) | the cells' power pins on BPR: VSS at the row's bottom (y -0.012..0.012), VDD at its top (0.06..0.084), so VDD is on odd row boundaries |
| `qrc/GTA5_cfet.ict` | 2024b454... | resistances: BSM1-3 resistivity 0.1 ohm.um, thickness = LEF width, so 0.5, 0.2, 0.1 ohm/sq; BPR 0.132257 ohm.um over 0.032 um; vias (ohm per cut of the stated area, um^2): TSV 23.1 (0.0004), VBSM1 0.231 (0.04), VBSM2 0.058 (0.16), VBPR 44.0 (0.00012) |
| `starrc/GTA5cfet.itf` | 13589680... | BPR's width-dependent resistivity, 0.123214 ohm.um at 24 nm by interpolation (the ICT uses the 9 nm value 0.132257, 7.3% higher); states that BSM/TSV/BSV are not in it ("StarRC never sees them") |

Quirks the converter owns (A19):
- The tech LEF names the backside vias BSV1/BSV2, the ICT VBSM1/VBSM2: each LEF cut layer is matched to the ICT via
  joining the same two layers, and a missing or ambiguous match is refused.
- Candidate vias are those a router may use without a non-default rule: the DEFAULT generate rules (`ViaTSVArray`,
  `viaTSV`, `viaBSV1`, `viaBSV2`) and the fixed DEFAULT vias (`VTSV_0`, `VBSV1_0`, `VBSV2_0`). `ViaBSV1Array` and
  `ViaBSV2Array` lack DEFAULT and are skipped (listed in the record). Each crossing gets the candidate with the lowest
  via resistance among those that fit, with each metal's enclosure measured from its own edges. On this grid that is
  `ViaTSVArray` for TSV (`VTSV_0`'s 0.09 um cut is wider than the 0.024 um rail), `VBSV1_0` for BSV1 and `VBSV2_0`
  for BSV2 (`viaBSV1`/`viaBSV2`'s enclosures do not fit the 0.2 / 0.5 um stripes).
- The ICT quotes each via's ohms for its own cut area, so R per cut is scaled to the LEF cut's area: VBSV1_0's 0.2 um
  cut matches (0.231 ohm); VBSV2_0's 0.5 um cut gives 0.058 x 0.16 / 0.25 = 0.0371 ohm.
- `ViaTSVArray`'s pitch equals its cut size, so its 0.02 um cuts abut: 10 per 0.2 x 0.024 crossing, 9 where the rail
  ends at the stripe (BPR's 0.004 enclosure along the rail).
- c4's format has one resistance per cut layer name, so each (cut layer, via) pair is written as its own name,
  `<cut>@<via>`, with its resistance in the generated `export.log`.
- BPR resistivity: the ICT value is the one Innovus top-level RC uses, so it is the default; the ITF value is a variant.

## What it does

1. **Grid generator (`bsgrid.py`):** from the files above, for a square core of side L (25, 50, 100 um), writes the
   geometry table c4's builder reads (`geom_<net>.tsv`: wires, vias with their cut boxes, sources), so c4's builder and
   solver run unchanged on it (A6, one mesh builder). BPR rails at every row boundary (pitch 0.072, VDD on odd
   boundaries, rows alternately flipped); BSM1 VDD/VSS stripe pairs and BSM2 pairs, each to its own net's ring; the
   rings outside the core, VDD inner. A via wherever two adjacent backside layers of one net overlap, cuts per the chosen
   via. c4's builder takes the rail layer as a parameter (BPR here, M1 for c4).
2. **Loads:** one cell per 10 sites in every row, drawing J x cell area with J = 1 A/mm^2, its VDD and VSS pins on its
   row's rails. The mesh is linear, so results are mV per A/mm^2 and scale to any power density. A second load puts
   10x J in a 10 x 10 um square at the core centre.
3. **Sources:** (i) ring-fed: every node on both ring layers of the net held at 0.7 V (or 0 V); (ii) area-fed: a bump
   array at pitch P (10, 20, 40 um) centred in the core, each bump holding the BSM1 x BSM2 crossing nearest it; BSM3
   above the bumps is taken as ideal, since the kit has no bump plan. P is a sweep, not a kit number.
4. **Solve and report:** worst and median drop per net (per instance, its worst pin), the worst node drop on each layer
   (how much of the drop is reached by BSM2, BSM1, BPR), the same with the TSV array capped at 1 cut and with BPR at
   the ITF resistivity, node counts, seconds.

## Checks (A21: there is no tool reference, so the parts are checked one by one)

| Check | Against |
|---|---|
| a. generated geometry | hand counts in the tests: rails = floor(L / 0.072) + 1 split by polarity, stripes, vias and cuts per via type |
| b. the whole pipeline on one layer | with all backside metal and vias ~1e-6 of BPR's, every pin voltage equals an independent dense 1-D solve of its rail held at the TSV columns (test) |
| c. ring-fed square, uniform load | a hand estimate as straps in series: BPR between TSV columns, TSV, BSM1 between BSM2 stripes, BSV1, BSM2 between the ring sides, BSV2 at each BSM2 stripe end (half the stripe's load), each strap uniformly loaded and held at both ends (i L^2 R / 8), each via carrying its share; vias from the same choice the grid makes; it ignores 2-D spreading, so it should read somewhat high |
| d. c4's solver on this mesh | irmesh's conservation check and refinement step (L66) run in every solve |

## Architecture lints that apply

A3 (one unit: um and ohm, converted once from the LEF/ICT), A6/A7 (the generator writes c4's geometry format, no second
mesh builder), A9 (all kit numbers read from the files: layers, rules, pins, resistances), A19 (the quirks above),
A21 (checks above), A25 (every README number cites a record), A14 (records append-only, dated names).

## Not covered

No placement, no real load map, no frontside path (the cells' VBPR is inside the cell, left to PEX as the kit says),
no electromigration, no temperature dependence of resistivity (goal 14's stretch).

## Decision for the student

None blocks the dry run. Its bump-pitch sweep is a stand-in: if c5 becomes a gate, the bump pitch and the power
density come from a placed design or a cited package.

## Cost

Measured in the cited record (README); the superseded first run took 12 s per net at L = 50 um and about 50 s at
L = 100 um.
