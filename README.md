# open3d-thermal

An open electrothermal evaluation for face-to-face 3D ICs. Given a two-tier design placed and routed by an open 3D
flow and a set of real programs, it reports per-tier power from simulated activity, temperature from three
independent thermal solvers, the leakage-temperature feedback loop with a certified runaway margin, and timing slack
and IR drop at each tier's own temperature. Everything runs on open tools in pinned containers.

Separate from the FYP (OpenTSense), started 13 Nov 2026; it reuses OpenTSense as an installed package.

## The 3D flow

The physical design comes from TaiWei-Pin-3D (github.com/CODA-Team/TaiWei-Pin-3D, BSD-3), the open Pin-3D-style
face-to-face flow of RosettaStone 2.0 (Jiang, Kahng et al., ISPD 2026, arXiv 2601.17520), on ORFS-Research and
OpenROAD-Research (BSD-3). Only its open `ord` flow is used. The first case is Ibex on ASAP7-ASAP7.

Open3DBench (Shi et al., arXiv 2503.12946; `lamda-bbo/Open3DBench`) was the original target. Its repository states
no licence, so it is cited and compared by its published numbers only, not run or modified (decided 17 Nov 2026).

## What this project adds to an open 3D flow

| Usual open-flow practice | What this project adds | Reused from OpenTSense |
|---|---|---|
| Vectorless (default) activity | Gate-level simulation of real programs, VCD into OpenSTA, per window and tier | the G72/G81/G100 simulation flow; `opentsense.power` |
| Leakage at one temperature (shipped Liberty) | Per-temperature leakage from SPICE (ASAP7 BSIM-CMG) | `opentsense.power.leaklib` (G92e) |
| No leakage-temperature feedback | The electrothermal loop and a certified runaway margin per tier | `opentsense.thermal.electrothermal`, `runaway` (G95, G101) |
| One thermal solver, die-sized stack | 3D-ICE, PACT and HotSpot on one stack description with BEOL, bond and package layers | `opentsense.stack`, `opentsense.thermal.run` (G93a, G94) |
| Sign-off at 25 C | Timing derated and IR drop with metal resistance at each tier's temperature | goal 14's derating and PDNSim scripts (G97) |
| No sensing | Sensor placement and per-tier temperature recovery, including failed sensors | `opentsense.bench`, `opentsense.estimate` (G86) |

## How OpenTSense is reused

As an installed package, never copied: `pip install -e ../FYP-search/fyp/opentsense`, pinned to a recorded commit in
each result's manifest (`opentsense.manifest`). Changes OpenTSense needs go into OpenTSense through its own review
and commit process, not into a fork here. Every result is a registered gate with its bars fixed before the run.

## Status (17 Nov 2026)

Gate C2 (CFET leakage, SPICE against Liberty) ran twice, VOID both times on a -40 C convergence problem; see
`gates/c2/`. The 3D flow work (gates G1 to G6) starts with a dry run of TaiWei-Pin-3D on Ibex.
