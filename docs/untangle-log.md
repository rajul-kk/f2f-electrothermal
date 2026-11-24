# Untangle decision log

Additions (asked once for this repository): Comments and Tests both run, as in the sibling OpenTSense repository.

## 19 Nov 2026: dry/rs (add_layers.py, s6_add.sh, make_notebooks.py, rs_lib.sh)

**Fix: derive each session's lib files, kernel slug and title instead of listing them.**
`make_notebooks.py` reads the lib files from the script itself (every `"$(dirname "$0")/<file>"` it sources or runs),
names the kernel `open3d-rs-<stem>`, and keeps only the attached earlier sessions per entry.
- Hidden link: each SESSIONS entry's `libs` had to match the files its script calls, and nothing checked it; a missed
  `add_layers.py` would only show up as a missing file on Kaggle.
- Surplus: `title` always equalled `slug`, `internet` was always True, `slug` always followed from the stem.
Behaviour unchanged: checked by hand on 19 Nov by building all six sessions' kernel folders before and after and
comparing them with `diff -r` (no difference); the folders and the output were not kept.

**Fix (code review round 1): add_layers.py computes every output before writing, and writes config.mk last.**
- Hidden order: `config.mk.orig` and the outputs were written as they were computed, so a failed step left a
  half-patched clone that a re-run refused.

**Kept:**
- `CONFIG_EDITS` replacements follow from `OUT`, so there is no copy of a path.
- `patch_lef` and `append_lines` each have one caller per output kind; inlining them would only lengthen `build`.
- `s5_add.sh` and `s6_add.sh` repeat a few lines of setup. s5 is a run record and must stay as it ran.
- `rs_lib.sh` was read only for its links: it calls no file from its own folder, which `make_notebooks.py` now
  checks. It was not changed or reviewed for anything else here.

**Comments:** none removed (the comments in these files point at outside facts: Pin-3D's stages, FlexPA, Kaggle).
**Tests:** `test_lef_refuses_a_second_application` removed. It tested a guard `main` could never reach, which was
deleted. The config tests that only checked `CONFIG_EDITS` against itself are now backed by tests on the real
checkout.

## 19 Nov 2026: dry/rs S7 (add_layers.py --drop-gcell, s7_grt.sh)

**Kept: a separate `--drop-gcell` flag instead of adding the edit to `CONFIG_EDITS`.** It looks like a parameter for
one caller (S7), but each session's record must stay rebuildable as it ran: with the edit folded into `--config`, a
rebuilt S6 notebook would no longer reproduce S6's STA-0562 (code review round 1). `--config` alone still prints
the same hashes as S6's recorded `add_layers.py` (checked by hand on 19 Nov, not kept).
**Kept:** `s7_grt.sh` repeats `s6_add.sh` except for the flag and the header; both are run records.
**Tests:** none removed; the real-checkout test now runs with and without `--drop-gcell`.
