# c4 dry, step b: PDNSim's model, read from its source (18 Nov 2026)

Source: OpenROAD `src/psm/src` at 5bbad751ba283c4721ef15358c98b9e518e6f68d (2026-10-20 23:39 UTC), the last commit
before G97's image (`openroad/orfs@sha256:55266bc7...`, created 2026-10-21). That image holds no source and prints
version "unknown", so this commit is the nearest by date, not a proven match. File:line below are at that commit.

| # | PDNSim does | Where | c4's solver |
|---|---|---|---|
| 1 | Sources: if the net has block pins (BTerms), their shapes' nodes are the sources and `-source_type` is not used; only a net without BTerms gets FULL (every top-layer node), STRAPS or BUMPS | `ir_solver.cpp` 1073-1085, 1109-1135 | copy; the export records the BTerm count per net |
| 2 | Shapes: special wires, instance pin shapes and BTerm shapes are merged per layer into polygons, then cut into rectangles | `ir_network.cpp` 658-770 | copy the merge (overlapping straps become one shape) |
| 3 | Nodes: on both layers at every via, at every terminal, plus top-layer fillers every min(10 um, 10 x layer pitch) along each top shape | `ir_network.cpp` 78-100, 880-945; `shape.cpp` 121-153; `ir_network.h` 227-228 | copy |
| 4 | Wire edges: within a shape, each node to its nearest not-yet-used node; R = (length / width) x R_sq, parallel edges merged by adding width | `shape.cpp` 78-109; `connection.cpp` 145-182 | copy |
| 5 | R_sq of a routing layer = OpenROAD's estimated resistance per metre (`layerRC`, i.e. the platform's `set_layer_rc`) x the layer's default width; the tech LEF's value only if that is 0 | `ir_solver.cpp` 981-1041 | export both per layer and use PDNSim's |
| 6 | Vias: R = R_cut of the cut layer above node0's layer / number of cuts (layerRC, else the LEF) | `connection.cpp` 184-205; `ir_solver.cpp` 1001-1005 | copy |
| 7 | Instances: one base node per pin at the pin's average XY on the first front-side routing layer, joined to each pin-shape node by a 1 mOhm terminal edge; current P / VDD split equally over the instance's base nodes | `ir_network.cpp` 275-340; `connection.h` 134-170; `ir_solver.cpp` 1414-1440 | copy, including the 1 mOhm edges |
| 8 | Backside: the network already places nodes on backside routing layers (`firstBacksideRoutingLayer`, `isBackside`) and links them through "backside bridge" cells | `ir_network.cpp` 275-340 | not needed for G97; see below |

## What changes for c4

- **Row 1 likely explains G97's Amendment 1** ("BUMPS and FULL wrote byte-identical voltage files"): if G99's Ibex
  has VDD/VSS BTerms, both runs used the BTerms as sources. Confirmed by the export (step c, `export.log`:
  `NET VDD bterms 1`, `NET VSS bterms 1`; 14 M6 block-pin shapes per net in `geom_*.tsv`). So G97's FULL is really
  "the block pins as sources", and its README's source note should say so (an FYP note, not changed here).
- **Row 8 weakens c4's reason.** `ambitions.md` 7 (15 Nov) read OpenROAD's docs, which never mention backside, and
  concluded PDNSim likely cannot represent a backside grid. Its source at this commit can. The blocker for MATRIX-A5
  is still the P&R port (no OpenROAD platform for it), not PDNSim. c4 stays useful as an independent check of
  PDNSim (A21: a second solver that agrees on a frontside grid makes a backside result from either more credible),
  and its node model now copies PDNSim's instead of inventing one.
