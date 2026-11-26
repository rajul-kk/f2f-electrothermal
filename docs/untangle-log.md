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

## 20 Nov 2026: dry/rs S8 (add_layers.py --view, s8_direct.sh)

**Changed: the two tech views are data.** `VIEWS` (file suffix) and `a7_files(view, add)` name every input and
output, and `CONFIG_EDITS` holds one edit list per view in file order. The S5-S7 `SRC`/`OUT` tables and the
`edits.insert(4, ...)` index are gone; the `-gcell_size` edit sits in the hbrdl list and is filtered unless
`--drop-gcell`. `--config` and `--config --drop-gcell` on hbrdl print S6's and S7's recorded config.mk hashes
(bb9d5dff, b6a4df9c) byte for byte, now also on Windows (outputs written with LF).
**Kept:** the added layers are still copied from the hybrid platform's LEF, not from the kit's own
`rc_extract/input/asap7_tech_1x_2A6M7M.lef`: S5-S7 used that source, and a real-checkout test proves the two give
identical `*_add` blocks and the same 15 routing layers in order.
**Kept:** `s8_direct.sh` repeats `s7_grt.sh` except for the arguments and the header; both are run records.
**Tests:** none removed; the real-checkout test runs on hbrdl (with and without `--drop-gcell`) and direct.

## 20 Nov 2026: dry/c6 v3 (run_c6.sh, c6.py, test_c6.py; Amendment 1)

**Changed: one integrity check, run three times.** `manifest()` makes the staged tree's full sorted hash list, and
`staged()` compares it with `stage.sha256` before the run, after it and after the summary. The per-path
`sha256sum -c` (which missed added files) and the record-folder copy of the check are gone. The wrapper writes its
own final rc after every check, apart from Docker's rc.
**Changed: check c's population is recorded, not inferred.** `run()` writes `planned` (the stacks it will attempt),
and `check_rows` counts against it and the end marker, instead of against the stacks that happen to be in c6.json.
**Kept: `run(..., only=)`**, used by `measure_c6.sh` for the one-stack timing run.
**Kept: `check_rows` falls back to the stacks keys when `planned` is absent**, so v1/v2 records can still be
summarised as they ran.
**Tests:** none removed; added test_check_c_fails_on_a_stack_that_left_no_case_rows and
test_check_c_fails_on_an_interrupted_run.
