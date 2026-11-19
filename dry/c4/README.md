# c4 dry: an own IR solver against PDNSim on G97's Ibex grid (18 Nov 2026)

Design: `DESIGN.md`. A dry, not a gate: it fixes no bars. Every number below is from the file cited beside it;
`record/` is short for `dry/c4/record/`.

## What ran

| Step | Code | Record |
|---|---|---|
| a. closed forms | `irmesh.py`, `test_irmesh.py` | 4 tests: a chain of equal loads, a uniformly loaded strap, a dense solve, refusals |
| b. PDNSim's model | read from its source at 5bbad751 | `record/2026-11-18_b_pdnsim_model.md` |
| c. export | `export.tcl`, `export.sh` (G97's image, G99's Ibex, G100's k0) | `record/2026-11-18_c_export/` (`export.log`, `inputs.sha256`; the large files stay local, hashed in `large_files.sha256`) |
| d1. PDNSim's own network, our solver | `pgspice.py`, `test_pgspice.py` | `d1v2_VDD.json`, `d1v2_VSS.json` in the export folder |
| d2. our network from the geometry | `irbuild.py`, `test_irbuild.py`, `asap7_cutclass.tsv` | `record/2026-11-18_d2_explore_v2.json` (`explore_d2.py`) |
| d2 cause | `rail_ladder.py` | `record/2026-11-18_d2_rail_v2.json` |

All the v2 records come from `records_v2.sh`, which ran after the second review. Its log line reported success
unconditionally then; it now counts failed steps, and all four records exist. The earlier files (`d1_*.json` and
`d2_*.json` in the export folder, `2026-11-18_d2_explore.json`, `2026-11-18_d2_rail.json`) are kept but superseded:
those builds averaged an instance's pins and split its current over all their nodes. They also had no x check on rails
and a d1 pin-node counter that could only read 0.

## Results

- **The export reproduces G97's k0** (`export.log`): total power 4.45e-03 W, worst VDD drop 1.37e-03 V. Each net has
  one block pin (`NET VDD bterms 1`, `NET VSS bterms 1`). PDNSim therefore took its sources from that pin and ignored
  `-source_type` (step b, row 1), which is why G97's BUMPS and FULL runs were identical (its Amendment 1).
- **d1, same network:** irmesh on PDNSim's own `write_pg_spice` network puts every one of 48,798 terminals within
  0.63 uV (VDD) and 0.67 uV (VSS) of PDNSim's voltage file, which prints 1 uV steps (`d1v2_*.json`). The VDD network
  has 144,053 nodes and solves in 2.7 s with a 57.9 MB tracemalloc peak; VSS has 144,762 nodes and takes 3.2 s
  (`2026-11-18_d2_explore_v2.json`, `d1`). These times were measured with tracemalloc running, so they are upper
  bounds.
- **d2, independent network** (pins spread along the rail, cut classes on; `2026-11-18_d2_explore_v2.json`, `variants`):

| Net | PDNSim worst (instance) | Ours worst | Ours at PDNSim's worst instance | Median per-instance difference | 99th percentile | Max | Nodes | Time |
|---|---|---|---|---|---|---|---|---|
| VDD drop | 1.372 mV (place4109) | 1.554 mV (+13%) | 1.550 mV | 5.5 uV | 68.5 uV | 217 uV | 587,592 | 12.8 s |
| VSS rise | 1.241 mV (clkbuf_2_1__f__07890_) | 1.298 mV (+5%) | 1.264 mV | 4.4 uV | 69.8 uV | 157 uV | 591,689 | 13.1 s |

  All 48,798 instances matched by name. The total current applied, 6.3528 mA on VDD, equals report_power's
  4.44693e-03 W / 0.7 V (`export.log`). At node positions the two networks share, voltages differ by a median of 2.6-4.8 uV per layer
  on M1-M5 for VDD; M6 nodes are the sources, so their difference is 0.

## Why our worst drop is higher

1. **Cut classes (fixed in ours).** Counting each via cut shape as one cut gives a VDD median difference of 203 uV
   and a worst drop of 1.874 mV; with cut classes it is 5.5 uV and 1.554 mV. ASAP7's tech LEF makes a 24 x 288 nm V5
   bar count as 8 cuts (`asap7_cutclass.tsv`), and PDNSim applies this (`getEffectiveNumberOfCuts`).
2. **PDNSim's via edges conduct along the rail (the rest of the VDD gap).** On a VDD rail both networks have the same
   metal: M1 70.42 and M2 29.71 ohm per um. These figures are PDNSim's R_sq in `export.log` (1.2675 and 0.5348 ohm
   per square) divided by the 18 nm rail width in `geom_VDD.tsv`; `rail_ladder.py` assumes that width. But PDNSim joins each lumped M1 node to M2 nodes up to 180 nm away along
   the rail (`v1_edge_x_offset_nm_pdnsim`), so via resistance also carries current sideways
   (`2026-11-18_d2_rail_v2.json`):

| Rail ladder (M1 + M2 + V1), no loads | y 15.93 um | y 14.31 um (PDNSim's worst instance) |
|---|---|---|
| M1 parallel M2, from the layer resistances | 20.90 ohm/um | 20.90 ohm/um |
| ours | 20.91 ohm/um | 20.91 ohm/um |
| PDNSim's | 16.78 ohm/um (-20%) | 17.51 ohm/um (-16%) |
| PDNSim's, each V1 edge made vertical | 22.46 ohm/um | 21.52 ohm/um |

   The ladder alone accounts for the gap at the worst instance. On y 14.31 um, PDNSim's ladder and ours were solved
   with the same M3 voltages (PDNSim's) and the same loads on the rail. At place4109's rail node they give 0.69865 and
   0.69843 V, a 0.22 mV difference. The full grids give 0.69863 and 0.69842 V there (point pins), a 0.20 mV difference.
   On y 15.93 um (VSS's worst instance sits at x 58.6 um on the VDD rail there) the ladders differ by 0.26 mV and the
   full grids by 0.27 mV. So PDNSim's worst drop reads low because its network makes the rails 16-20% less resistive
   than the metal. The vertical variant is a rough bound, not a fix: it leaves some M2 nodes without a via.
   Ruled out by measurement (`2026-11-18_d2_explore_v2.json`):
   - **Pin ties.** Every PDNSim pin node has exactly one 1 mOhm partner (`pin_ties`, zero-tie nodes counted). The
     48,798 VDD terminals sit on 45,688 pin nodes (`terminals_on_an_already_used_pin_node` 3,110).
   - **Our node density.** Coarser cut grouping raises our drop: 1.575, 1.582 and 1.642 mV at 1, 4 and 16 cuts per
     node (point pins).

   A tie from every rail node under a pin (`ties`) shorts the rail and gives 0.43 mV, so it is not PDNSim's model.

G97's decision does not change: its worst squeeze is far below its threshold even if PDNSim's drop is raised by 20%.
That comparison uses G97's own README numbers and was not recomputed here.

## Limits

- One grid, one window (G97's k0). The mechanism is shown on two VDD rails. The VSS gap (+5%) is assumed to have the
  same cause; that is not shown.
- `export.tcl` runs `analyze_power_grid` once per net with the default source type. That is moot here, because with a
  block pin PDNSim ignores the source type. It also does not guard against instance names STA cannot find; there were
  none on this design (all 48,798 matched). It is kept as it ran, since its hash is in `inputs.sha256`.
- irbuild does not merge overlapping same-layer wires as PDNSim does; it counts them instead (0 on this grid).

## What this means for c4

- The solver is exact on a given network (a, d1). An independent network built from the same geometry agrees with
  PDNSim to a median of 4-6 uV per instance, with a 99th percentile near 70 uV and a maximum of 0.22 mV (about 15% of
  the worst drop). Its worst drop is 5-13% higher, and the VDD part of that is explained by PDNSim's discretisation.
- PDNSim already models backside routing layers at this commit (step b), so a backside IR result can come from
  PDNSim once there is a placed backside design. c4's builder is the independent check beside it, and it reads higher
  wherever PDNSim's lumped vias shorten the rails.
- If this becomes a gate (bars set by the student, decision 5), the natural bars are d2's median and 99th-percentile
  agreement plus a stated worst-case band, on G97's other windows k1-k4 (not used here).

## Cost

The export took 127 s in G97's image (`export.log`). d1 takes about 3 s per net. d2 takes 6-15 s per net at
130k-633k nodes, in Python and SciPy (`2026-11-18_d2_explore_v2.json`).
