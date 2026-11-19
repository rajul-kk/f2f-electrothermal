# S1 v2 (17-18 Nov 2026, Kaggle CPU, `rajulkabir/open3d-rs-s1-build` version 2): build ok

Script: `dry/rs/s1_build.sh`, sha256 1cc93479... (`script.sha256`; the repository's file has the same hash).

- **Every step exited 0** (`rc.txt`, `steps.log`, `exit_status.txt` 0, `notebook_exit_code.txt` 0): clone 85 s,
  checkout with submodules 260 s, Pin-3D clone 10 s, setup 3667 s (61 min), build 11521 s (3 h 12 min), tar 62 s.
  About 4 h 21 min from start to tarball, of the 11 h budget.
- **Commits** (`commits.txt`): ORFS-Research 568eb04d, bundled OpenROAD 305d3ba2 (the README's tested commit, as in
  v1), TaiWei-Pin-3D 51a19d6f.
- **Build:** `./build_openroad.sh --local --threads 4`, 383% CPU, user time 41,674 s (`build.log`, first lines).
- **Memory:** machine-wide peak in use 24,966 MiB (`steps.log`, from `memory.log`, 15 s samples); largest single
  process 2.55 GB in the build and 1.50 GB in setup (`build.log`, `setup.log`, GNU time). The machine figure is close
  to Kaggle's 30 GB, so `--threads 4` should not be raised.
- **Output:** `orfs_install.tgz` (tools/install and dependencies), sha256 b003f6fc... (`tarball.sha256`); about
  291 MB used in `/kaggle/working` at the end (`disk_end.txt`). It stays in the Kaggle output; S2 and S3 attach it.
- **Binaries** (`binaries.sha256`): openroad 5dacbf47..., sta 220c9745..., yosys af7339ba..., and the yosys tools.

## A defect in the record (fixed for S2 and S3, not in this script)

`/usr/bin/time -v -o /dev/stderr` reopens the step's own log (stderr is redirected to it) from the start, so GNU
time's report overwrote the first part of every step log. `versions.log` lost all of `openroad -version` and
`yosys -V` (the step exited 0, so both ran); the other logs lost their first few hundred bytes. The binary hashes and
commits above identify the build instead; S2 prints both versions after restoring the tarball. S2/S3 write the time
report to `<step>.time`.
