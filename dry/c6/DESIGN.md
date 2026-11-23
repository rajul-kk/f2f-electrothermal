# c6: the heat path of a backside-power stack and its runaway margin (dry, no bars, 19 Nov 2026)

**Question.** With MATRIX-A5's leakage against temperature (c3) on a 1 x 1 mm block, how much does a backside-power
(BSPDN) stack change the peak temperature rise per watt and the leakage loop's runaway margin, against a frontside
stack with the same sink, for svt, lvt and ulvt, under uniform power and a hotspot?

**Why it differs.** In a frontside flip-chip die the devices sit at the bottom of 50 um or more of bulk silicon whose
far face meets the sink, so heat spreads laterally in silicon before it reaches the sink. In a BSPDN wafer the
frontside BEOL is bonded to a carrier wafer, the device silicon is thinned to reach the backside rails, and the die
is flipped: heat leaves through the BEOL and the bond oxide, both poor conductors, before the carrier spreads it.
Chen et al. (imec, arXiv 2508.02284) report BSPDN cooler under uniform maps and hotter under localised ones; the
"up to 14 C" local penalty they cite is from a 2D SoC study. Neither couples leakage to temperature.

## Stacks (OpenTSense YAML, `stack.model`; top = sink side, bottom face adiabatic in both)

| Layer | Frontside (FS) | Backside (BS) | Source of the value |
|---|---|---|---|
| spreader | Cu 500 um, k 400 | same | OpenTSense `single_die.yaml` |
| TIM | 25 um, k 4 | same | same |
| carrier | - | Si t_c = 50 (nominal) or 200 um, k 130 | silicon as OpenTSense; t_c swept |
| bond oxide | - | 1 um, k 1.4 | SiO2 bulk value; no published bond-layer k found (sweep b) |
| frontside BEOL | 5 um, k_beol, below the die (no heat path down) | 5 um, k_beol, between bond and devices | Chen et al. Table I, interposer BEOL k 1.2; k_beol swept 0.6 / 1.2 / 3.0 |
| die (devices) | Si 50 um, sources in its bottom 2 um | Si 0.5 um, sources in its top 0.1 um (next to the BEOL) | thinned to reach the rails |
| backside PDN | - | 2 um, k_bs = 71 (nominal) or 10 | Chen et al. (BSPDN layer, 71 W/m K); BSM1-3 are 0.2 + 0.5 + 1.0 um thick in the kit's ICT (c5), so 2 um |

Heat sink: the spreader's top face at htc 5e4 W/(m^2 K), ambient 300 K (OpenTSense default). Grid 32 x 32 tiles of
31.25 um. Sweeps: k_beol in {0.6, 1.2, 3.0}; for BS also t_c in {50, 200} and k_bs in {71, 10}: 3 FS + 12 BS stacks.

## Power

- Dynamic: uniform 0.5 W/mm^2 (`uniform`), or the same total with a 4 x 4-tile square (125 um) at the centre at 10x
  the density of the rest (`hotspot`).
- Leakage at 25 C, nominal: per Vt, the mean over c3's cells (`record/tables.json`, each cell's mean over its
  states) divided by the mean cell area from the same TT 25 C Liberty, times utilisation 0.7, as W/mm^2, the same
  in every tile. Its temperature curve is the matching per-Vt cell-mean curve from c3 at 25-125 C, log-linear
  between points and along the end segments beyond (`electrothermal.LeakModel`, one instance per tile).
- The margin is a scale on the leakage, so the nominal mix sets only where 1.0 sits; the critical leakage density at
  25 C (scale x nominal) is reported too, and does not depend on the mix.

## Per case (stack x workload x Vt)

1. R: the tile operator from PACT's conductance matrix (`thermal.response.build`, one basis pattern per tile, the
   die's sources only).
2. The loop at nominal leakage: `runaway.classify` (status, T, rho, iterations, monotone).
3. The margin: `runaway.critical_scale` (scale bracket [1e-3, 1e3], rtol 1e-4).
4. Reported: peak and mean rise per W with leakage off (R alone), loop peak T at nominal leakage, rho, s_crit, and
   critical 25 C leakage density; then BS / FS ratios at matching k_beol, workload and Vt.

## Checks (fixed before the run; failures reported, not hidden)

| # | Check | Why |
|---|---|---|
| a | Each stack's uniform-load mean rise per W is within 10% of a 1-D series estimate (layers in series from the sources to the sink, plus 1/(htc A)) | the stack and the operator are what the table says (A21) |
| b | For one stack (FS, k_beol 1.2), R's column for the centre tile equals a direct PACT run of that one tile's power to within 0.005 K everywhere (half of PACT's 0.01 K output step; first set at 1e-6 of the peak, changed after the 8 x 8 smoke run showed PACT writes two decimals) | `response.build` is used as G93a validated it (A15) |
| c | `critical_scale` brackets close (s_hi / s_lo - 1 <= 1e-4) in every case, and every probe converges (else listed) | the margin is located, not assumed |
| d | For a one-tile case, `critical_scale_1tile` and `critical_scale` on a 1 x 1 R agree to 1e-3 | the boundary method on the same leakage form |

## Limits

One VDD; TT only; cell-mean leakage, not a placement; no bumps, package or board below (adiabatic bottom, same in
both stacks); BEOL and backside PDN as uniform isotropic layers (the striped BSM layers are anisotropic: a later
variant can set k_lateral); PACT only (no cross-solver check here: G2 does that); the 0.5 um die is one sublayer
of sources plus bulk, as `stack.model` allows.

Architecture lints: A3 (um and W in the YAML, K internally, converted in `stack.model` only), A4 (FS and BS share
footprint, sink, grid, power and leakage; only the listed layers differ), A6 (c6.py is a thin CLI over OpenTSense's
`stack`, `thermal.response`, `electrothermal`, `runaway`), A9 (leakage from c3's record, not recomputed), A10 (15
stacks x 1,024 basis solves on a 32 x 32 grid, G101's timings: minutes), A11 (detached, in a slot), A14 (record/
append-only), A25 (README numbers cite record/).
