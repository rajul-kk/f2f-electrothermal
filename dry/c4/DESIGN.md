# c4-dry: an own resistive-mesh IR solver, checked against PDNSim on G97's frontside Ibex grid (design)

Drafted 18 Nov 2026. A dry run, not a gate: no bars. Why own: the CFET side track needs static IR drop on a backside
power grid, which OpenROAD's PDNSim does not represent (`ambitions.md` 7). An own solver is only credible once it
matches PDNSim where PDNSim works, on a frontside grid with a published result: the FYP's G97 (OpenTSense
`gates/g97`, valid 16 Nov: Ibex ASAP7 at 1,400 ps, TT, windows k0-k4, worst VDD drop 1.01-1.44 mV, FULL sources).

## What it does

1. **Export (ORFS image G97 used, `openroad/orfs@sha256:55266bc7...`, same `load_routed.tcl` and k0's VCD):** one
   OpenROAD session writes, from G99's `6_final.odb`:
   - every special-net shape of VDD and VSS: layer, rectangle, and each via (cut layer, location, cut count);
   - each routing layer's sheet resistance and each via's resistance, as the tech LEF in the ODB holds them;
   - per-instance power from `report_power` for k0 (the instances and power G97's PDNSim used), and each instance's
     power-pin locations;
   - the same session's `analyze_power_grid` voltage files (VDD, VSS, FULL), so reference and inputs share one
     session (A4).
2. **Solve (Python, `scipy.sparse`):** nodes at every strap crossing and via, and along each strap where a pin taps
   it; conductances from sheet resistance x length / width, vias in parallel per cut; current sinks at the nearest
   node of the lowest layer per instance pin, I = P / VDD (the same assumption PDNSim makes, to be confirmed in its
   source, A19); FULL: every node of the top grid layer pinned to VDD (or 0 V). One sparse solve per net.
3. **Compare:** per instance terminal (G97's voltage file keys: instance, terminal), our voltage against PDNSim's:
   worst drop, the error distribution, and the error map on G100's 32 x 32 tiles.

## Steps (each recorded under `dry/c4/record/<date>_<step>/`)

| Step | Does | Shows |
|---|---|---|
| a. analytic | one strap of length L, uniform load, both ends held: drop L^2 i / (8 sigma) at the middle, and a 2-D mesh with a point load against a direct dense solve | the solver's own error before any PDNSim number (A21: which side is right) |
| b. PDNSim's model | read `src/psm` of the OpenROAD in that image (commit from the image if it records one, else the nearest by build date, stated): node placement, via model, how instance current is attached, what FULL fixes | every modelling choice in 2 copies PDNSim's or is named as different (A19) |
| c. export | the session in 1, k0 only | file sizes, shape and via counts per layer, instance count = G100's located instances (A2) |
| d. compare k0 | solve and compare as in 3 | how close an independent solver gets, and where it differs |

k1-k4 stay for the gate; the dry only uses k0 (G97's k0 numbers are already published, so they are not unseen).

## Lints checked (architecture-lints.md read in full 18 Nov; code-lints titles)

| Lint | What the design does |
|---|---|
| A2 inventory | shape, via and instance counts checked against the ODB's own counts and G100's instance list before solving |
| A3 one unit system | export in DBU and ohms; converted once to um, ohm, A, V at load |
| A4 like with like | reference voltages and inputs come from one OpenROAD session on one activity |
| A5 identities | instance and terminal names kept end to end; the comparison joins on them, unmatched rows counted |
| A6 / A7 | the solver is one module (`irmesh.py`) with tests; the export TCL and the CLI stay thin |
| A10 cost | node count and solve time recorded in step d; the backside grid later is bigger, so cost per node is the figure |
| A19 tool quirks | step b: PDNSim's node, via and current models read from its source, mirrored or named |
| A21 ours vs theirs | step a decides the solver's own accuracy independently of PDNSim |
| A25 cite outputs | the dry README quotes only recorded numbers |
| L11 | the export's peak RAM measured (G97 ran in 2 GB) |

## Machine time

The export is one OpenROAD session like G97's (about 2 GB, minutes), on the laptop under a slot once C2 run 3
releases the heavy slot; the solve is a few seconds of Python. Nothing here needs Kaggle.

## Open questions (none blocks step a or b)

- Whether the ODB holds per-layer resistance (ASAP7's tech LEF does give RESISTANCE RPERSQ for routing layers; via
  resistance may be missing, in which case PDNSim's own default is what step b must find).
- The gate's bars (decision 5) are fixed by the student after this dry.
