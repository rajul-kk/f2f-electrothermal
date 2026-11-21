# c5-dry: static IR drop on MATRIX-A5's backside power grid · done (dry, no bars)

Design and checks: `DESIGN.md`. Record: `record/2026-11-18_c5_v3.json` (sha256 9662c2c0...). The kit's file hashes
are in its `kit_sha256` and the generator's and solver's in its `code_sha256`. `record/2026-11-18_c5_v2.json`, made
before the round-3 review fixes, has the same drops in every case (largest difference 0.0 mV). `record/2026-11-18_c5_v1.json`
is superseded: it had a bump-placement bug, wrong rail polarity, and vias from the non-DEFAULT rules.

All drops are mV per A/mm^2 of uniform load (the mesh is linear, so they scale with power density). The cores have
one cell per 10 sites, the BPR rails use the ICT resistivity, and sources are the ring or bumps (DESIGN.md, step 3).

## Results

| Case | Worst VDD | Median VDD | Worst VSS | Median VSS | Nodes per net (VDD) | Seconds per net |
|---|---|---|---|---|---|---|
| ring, L = 25 um | 0.121 | 0.072 | 0.154 | 0.110 | 15,930 | 1.3-1.4 |
| ring, L = 50 um | 0.399 | 0.222 | 0.459 | 0.283 | 62,684 | 5.5-6.0 |
| ring, L = 100 um | 1.475 | 0.785 | 1.597 | 0.906 | 250,496 | 25-27 |
| ring, L = 50, TSV capped at 1 cut | 0.405 | 0.228 | 0.465 | 0.288 | 62,684 | 4.8-5.5 |
| ring, L = 50, BPR at the ITF resistivity | 0.397 | 0.221 | 0.457 | 0.282 | 62,684 | 6.9-8.0 |
| ring, L = 50, 10x hotspot (10 x 10 um, centre) | 1.200 | 0.308 | 1.295 | 0.390 | 62,684 | 6.8-6.9 |
| bumps, L = 50, pitch 10 um (25 bumps) | 0.146 | 0.084 | 0.147 | 0.083 | 62,684 | 6.7 |
| bumps, L = 50, pitch 20 um (9) | 0.359 | 0.255 | 0.426 | 0.290 | 62,684 | 9.0-9.2 |
| bumps, L = 100, pitch 20 um (25) | 0.536 | 0.398 | 0.539 | 0.398 | 250,496 | 24-25 |
| bumps, L = 100, pitch 40 um (9) | 1.811 | 1.350 | 1.832 | 1.367 | 250,496 | 31-33 |

The seconds are v2's, measured with tracemalloc running, so they are upper bounds (`seconds_note`). v3 ran while C2's
run 4 shared the machine and took 1.5-3.2x as long per net (for example 15.4 s at L = 50, 64.4 s at L = 100).
tracemalloc peak over all ten cases: 1,291 MB in both.

## What the record shows

- **BSM2 carries most of the drop.** In the hand estimate (`hand_estimate_vdd_mv`) the BSM2 term is 0.117 of 0.139 mV
  at L = 25 and 1.665 of 1.692 mV at L = 100; BPR adds 0.012, BSM1 0.006, and every via together under 0.01 mV. In the
  grid, the worst node drop on BSM2 is within 0.025 mV of the worst BPR drop in every uniform-load ring case
  (`worst_node_drop_by_layer_mv`).
- **Check c, hand estimate against grid (VDD, ring):** 0.139 / 0.121 at L = 25, 0.457 / 0.399 at L = 50, and 1.692 /
  1.475 at L = 100. The estimate is 14-15% higher in all three, as expected from a sum of 1-D straps that ignores 2-D
  spreading.
- **The drop grows as about L^2** for ring feed: 0.121, 0.399 and 1.475 mV for L = 25, 50 and 100. Bumps at a 20 um
  pitch cut the L = 100 worst drop from 1.475 to 0.536 mV; at 40 um it is 1.811 mV, worse than ring feed.
- **VSS reads higher than VDD under ring feed** (0.459 against 0.399 at L = 50). This is consistent with VSS's ring
  being the outer one, so its BSM2 stripes are longer. Between ring centres the spans are 56.2 and 52.0 um, so the
  ratio squared is 1.17, against a drop ratio of 1.15.
- **TSV and BPR resistivity matter little here.** One TSV cut instead of ten raises the L = 50 worst VDD drop by 1.5%
  (0.399 to 0.405). The ITF BPR resistivity, 6.8% below the ICT's, lowers it by 0.5%.
- **Vias** (`grid.ohm_per_cut`, `vias_by_rule`): ViaTSVArray, 10 cuts of 23.1 ohm per rail crossing; fixed VBSV1_0
  (0.231 ohm) and VBSV2_0 (0.0371 ohm), one per crossing. The non-DEFAULT ViaBSV1Array and ViaBSV2Array are not
  used (DESIGN.md quirks).

## Not covered

See DESIGN.md: no placed design or real load map, no frontside path, no electromigration, no rho(T). The bump pitch is
a sweep, not a kit number.

## Reproduce

`python -I run_c5.py <MATRIX_A5_CFET_base> gen record/<new name>.json` (refuses an existing record). Tests:
`python -m pytest -q test_bsgrid.py ../c4/`.
