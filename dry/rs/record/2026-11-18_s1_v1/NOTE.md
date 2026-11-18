# S1 v1 (18 Nov 2026, Kaggle CPU, `rajulkabir/open3d-rs-s1-build` version 1): stopped in setup

- Machine (`machine.txt`): Ubuntu 24.04.5 LTS. Clone 78 s, checkout with submodules 248 s, Pin-3D clone 8 s
  (`steps.log`).
- Commits (`commits.txt`): ORFS-Research 568eb04d; bundled OpenROAD 305d3ba2, the README's tested commit (match);
  TaiWei-Pin-3D 51a19d6ffa8e4483a1a3357fb69c5038d720b0b8.
- Stopped: `setup` rc 1 after 257 s, `./setup.sh: line 30: SUDO_USER: unbound variable` (`setup.log`, last line).
  ORFS's setup.sh expects to be started through sudo and reads $SUDO_USER as the user for the `-common` dependency
  install; the session is root and sets no SUDO_USER. Fixed in the script for v2 (`SUDO_USER=root`, listed in
  shims.txt), which also saves `dependencies/` in the tarball (the `-common` libraries the binaries load).
- Peak machine memory in use during these steps: 8671 MiB (`steps.log`, from `memory.log`).
