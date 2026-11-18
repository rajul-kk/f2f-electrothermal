# rs-dry: TaiWei-Pin-3D's open flow on Ibex ASAP7-ASAP7, once, on Kaggle CPU (design)

Drafted 18 Nov 2026. A dry run, not a gate: no bars. It measures what G1 needs (PPA of one run, peak RAM, wall time,
toolchain identity) and whether the flow runs at all outside its authors' machines. Decision 2 (17 Nov): the laptop
stays with the FYP; this runs on Kaggle CPU sessions (4 cores, about 30 GB RAM, 12 h per session).

## What runs

- **Flow:** TaiWei-Pin-3D (github.com/CODA-Team/TaiWei-Pin-3D, BSD-3), `ord` flow only, on ORFS-Research
  568eb04da9173695d6bfc1b10ba868e0b6b8a9fa with its bundled OpenROAD 305d3ba2ddfd00591924cc586ad408179f566afe
  (the commits the README says were tested). The `cds` flow (Innovus/Genus) and any TCL file carrying a Cadence
  notice are not used.
- **Case:** `python3 run_experiments.py --flow ord --tech asap7_3D --case ibex`. The README shows this command only
  for `gcd`; the ibex form is our extrapolation, checked first with `--list`.
- **Pin-3D's commit:** recorded at clone time (the README pins ORFS-Research, not itself).

## Sessions (each one a Kaggle CPU notebook, internet on, outputs saved as files)

| Session | Does | Records | Stops if |
|---|---|---|---|
| S1 build | clone ORFS-Research at the commit, then its submodules; dependency installer; `build_openroad.sh --local`; tar the install tree | wall time per step; machine-wide memory in use every 15 s (`memory.log`, the build's real peak) and, where `/usr/bin/time` exists, each step's largest single process; disk used; `openroad -version`, `yosys -V`; sha256 of the binaries; OS and compiler versions; the exit status | a step fails, or the one deadline is reached: 11 h from the start for all steps, of which the last 30 min are kept for saving the (possibly partial) tarball and record |
| S2 smoke | restore S1's tarball (attached as a private dataset); `--list`; run `gcd` | per-stage time and peak RSS, gcd's final summary | gcd fails: the toolchain, not ibex, is the problem |
| S3 ibex | restore S1's tarball; run `ibex` stage by stage (`run_stage.sh`) | per-stage time and peak RSS; the final PPA summary (area, WNS/TNS, power, wirelength, per tier where reported); per-tier DEF/ODB, SPEF, reports and logs in the output | a stage fails: its log is the result |

Why three sessions: the build is the unknown cost (OpenROAD from source is typically an hour or more on 4 cores, but
not measured here), and reusing it keeps S2 and S3 inside 12 h each.

## Lints checked (architecture-lints.md, read in full 17 Nov; code-lints titles 17-18 Nov)

| Lint | What the design does |
|---|---|
| A10 cost per unit at full size | S1 and S2 measure the build and a small case before ibex; S3 records time and RAM per stage, so G1's cost is known per stage |
| A11 long jobs detached | Kaggle sessions run on their own; nothing waits on this shell |
| A13 external services | each session checks its own outputs exist and are non-empty before it ends, and records the commits it actually checked out (`git rev-parse`), not the ones asked for |
| A14 append-only | on Kaggle every run is a new notebook version with an empty `/kaggle/working`, so a run's record is never mixed with another's; each downloaded record goes into a new folder `dry/rs/record/<date>_<session>_v<version>/`, never over an existing one |
| A16 / A17 fail per unit, resume per unit | ibex runs stage by stage; S3 can restart from the last finished stage; the build is reused only if its recorded commit and binary hashes match |
| A18 offloaded compute proves parity | there is no local image of this fork to compare against. The reference is the S1 build itself (commits plus binary hashes); any later laptop or Kaggle run must show the same hashes or rerun gcd and match S2's summary |
| A21 name what is ours | every edit to their files (only `env.sh` paths are expected) is a recorded patch in `dry/rs/` |
| A25 cite outputs | the dry's README quotes only numbers from the saved logs and reports |
| L11 sizes from measured peaks | peak RSS from `/usr/bin/time -v`, not from the README |
| L50 exact launch commands | the notebooks hold the exact commands; the README copies them from there |

## Outputs (tracked, small)

`dry/rs/notebooks/` (the three notebooks), `dry/rs/record/<date>_<session>/` (summary JSON, the PPA summary, per-stage
time and RAM, commits and hashes), `dry/rs/README.md` (what it showed, with paths). Large outputs (the build tarball,
ODB/DEF/SPEF) stay in Kaggle outputs and datasets; their sha256 goes in the record.

## Open questions (none blocks S1)

- Does the Kaggle image's Ubuntu match what ORFS's dependency installer supports? S1 records it; if not, S1 fails fast
  in the installer and the fallback is ORFS's own Dockerfile commands run by hand.
- Peak RAM of ibex 3D placement and routing is unknown; Kaggle's 30 GB is the cap. If S3 is killed for memory, that is
  the dry's finding (and the laptop could not run it either).
- G1's tolerance (decision 5) is fixed by the student after this dry.
