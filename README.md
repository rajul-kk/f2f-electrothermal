# open3d-thermal

Electrothermal and workload-aware extensions for Open3DBench, the open 3D-IC backend benchmark
(Shi et al., arXiv 2503.12946; repository `lamda-bbo/Open3DBench`). Separate from the FYP (OpenTSense): started
13 Nov 2026 at the student's request, as its own project.

## What Open3DBench does, and what this project adds

Open3DBench splits one design across two tiers bonded face to face (memory-on-logic, `Place-MoL`, and logic-on-logic,
`Place-LoL`), places and routes it with an OpenROAD fork (`OpenROAD-3D`), and evaluates PPA and temperature (HotSpot).
It emulates two tiers in NanGate45 by duplicating the metal stack.

| Gap (from its README, 13 Nov; to confirm in its code) | What this project adds | Reused from OpenTSense |
|---|---|---|
| Power activity: the README does not say whether it is workload-driven | Gate-level simulation of real programs, VCD into OpenSTA, per window | the G72/G81 simulation flow; `opentsense.power` (`maps`, OpenSTA scripts) |
| Leakage at one temperature (shipped Liberty) | Per-temperature libraries built from SPICE for NanGate45 / FreePDK45 | `opentsense.power.leaklib` (G92e's generator) |
| No leakage-temperature feedback | The electrothermal loop and the runaway margin per tier | `opentsense.thermal.electrothermal`, `opentsense.thermal.runaway` (G92e, G95) |
| One thermal solver (HotSpot) | The same stack through 3D-ICE, PACT and HotSpot | `opentsense.stack` (stack format, converters), `opentsense.thermal.run`, `response` (G93a) |
| No sensing | Sensor placement and per-tier power/temperature recovery | `opentsense.bench`, `opentsense.estimate` (G77b's regularised inversion) |

## How OpenTSense is reused

As an installed package, never copied: `pip install -e ../FYP-search/fyp/opentsense`, pinned to a recorded commit in
each result's manifest (`opentsense.manifest`). Changes OpenTSense needs go into OpenTSense through its own loop
(code review, untangle, commit), not into a fork here. Gate protocol, job scheduling (heavy lock, slots) and the
commit queue are the same as the FYP's.

## Status

Not started. Blocked on the licence question (goals.md, decision 1): the Open3DBench repository has no LICENSE file.

Files: `goals.md` (what to do next, in order), `ambitions.md` (the most this could become).
