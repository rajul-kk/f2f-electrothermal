# S7 v1: S6 plus the kit's -gcell_size flag dropped (Kaggle CPU, 19 Nov 2026; flow cases 10:03-10:42 UTC)

Script `scripts/s7_grt.sh` (sha256 5775117f) over `scripts/rs_lib.sh` (43bddc33) and `scripts/add_layers.py`
(1bf733f5), as in `script.sha256`, at the commits in `commits.txt` (ORFS-Research 568eb04d, TaiWei-Pin-3D 51a19d6f).
`asap7_3D_config.mk` is the patched platform file as it ran (sha256 b6a4df9c, as in `add_layers.txt`). Its
`-gcell_size` line is replaced by a comment. Exit status 2 (`exit_status.txt`). Peak machine memory 18,784 MiB
(`steps.log`).

| Case | Wall time (`steps.log`) | Furthest step (`flow_logs.tgz`) | First error in any stage log |
|---|---|---|---|
| gcd | 301 s | `5_2_route` | DRT-0406 "No vertical tracks found in (0.027, 0.569) for layer HBM_T" (`5_2_route.log` line 300) |
| ibex | 2,011 s | `5_2_route` | DRT-0406, the same for HBM_T, from (37.05, 37.619) (`5_2_route.log` line 304) |

**What S7 settles.**
- **Global routing now runs and finishes in both cases.** `5_1_grt.log` has no ERROR line in either case. It
  reports a total wirelength of 1,739 um for gcd (line 357) and 121,818 um for ibex (line 362), with 4,115 and
  172,259 vias.
- **Detailed routing stops at track assignment.** The global route left guides on HBM_T, the kit's hbrdl bonding
  layer: `5_2_route.log` gives "HBM_T guide region query size" as 46 for gcd (line 279) and 418 for ibex (line 283).
  The region named in the gcd error, x 0.027 to 0.569 um, is 0.542 um wide and holds no HBM_T track (the nearest
  tracks are at x 0.016 and 1.016).

**Why.**
- **HBM_T's tracks are 1 um apart.** `make_tracks.2A6M7M_hbrdl.tcl` puts them on a 1 um lattice with origin 0.016
  um (line 6), and the LEF gives HBM_T a pitch of 1.0. A global-routing cell narrower than 1 um can hold no HBM_T
  track.
- **The pinned OpenROAD makes its cells narrower than that.** OpenROAD-Research 305d3ba2's
  `dbBlock::getGCellTileSize` (`src/odb/src/db/dbBlock.cpp`, lines 2513-2553) sets the cell size to 15 times the
  median track spacing of routing layers 2 to 4. It takes no setting, and it ignores any existing GCell grid. Source:
  https://raw.githubusercontent.com/ieee-ceda-datc/OpenROAD-Research/305d3ba2/src/odb/src/db/dbBlock.cpp, fetched 20
  Nov 2026.
- **That is what the kit's `-gcell_size 1.1` was for**: cells wider than HBM_T's pitch. That build has no flag for
  it (S6, STA-0562), and `global_route` has no other setting for the cell size (`src/grt/src/GlobalRouter.tcl`,
  `GlobalRouter.i`). One route around it exists but was not tried: `read_guides` (GlobalRouter.tcl line 347) loads
  route guides made elsewhere, and `GlobalRouter::computeGCellGridPatternFromGuides` (`GlobalRouter.cpp` line 2647)
  then sets the cell grid from the guides' geometry.
- **This is Pin-3D's own bundled OpenROAD.** Pin-3D's README (line 31) gives the same commit, 305d3ba2, as its
  bundled OpenROAD. The kit enabled HBT_RDL as asap7_3D's default on 14 Oct 2026 (Pin-3D commit b55050a, "config:
  enable ASAP7 HBT RDL"). With its own bundled router's `global_route`, the HBT_RDL view as configured does not get
  through detailed routing.

**Next (S8).** asap7_3D's direct view (ASAP7_HBT_RDL off): `asap7_tech_1x_2A6M7M.lef`, whose bonding layer
`hb_layer` is a cut layer between M7 and M6_m with no tracks of its own. The same two added layers go on top of
M1_m, their tracks and RC are appended to `make_tracks.2A6M7M.tcl` and `setRC_2A6M7M.tcl`, and extraction uses the
kit's `asap7_tech_1x_2A6M7M.rcx_patterns.rules` (LayerCount 15, made from `rc_extract/input/asap7_tech_1x_2A6M7M.lef`,
whose four `*_add` layer blocks are byte-identical to the ones added), with Pin-3D's own LayerCount check
(`final_report.tcl` line 79, `PIN3D_REQUIRE_RCX_LAYER_MATCH`) turned on. A G1 baseline built on it must state that the bond is
modelled as a cut layer, not the 1 um HBT lattice.

Not in this record: `flow_results.tgz` (Kaggle output, not downloaded into the record) and `pin3d_env.sh`. Kept
local per `.gitignore`: the clone, checkout and apt logs, and `shims.txt`.
