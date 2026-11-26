"""Write the rs-dry Kaggle notebooks and kernel folders from the session scripts in this folder (DESIGN.md).

The notebook runs the script unchanged (embedded as text, written to disk, run with bash) and keeps its exit code,
so what runs on Kaggle is exactly the reviewed file; its sha256 is printed in the notebook and kept in the record.

  python make_notebooks.py <kernel dir parent> <session...> [--owner OWNER]
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SESSIONS = {   # session script stem: the earlier sessions whose output is attached
    "s1_build": [], "s2_gcd": ["s1_build"], "s3_ibex": ["s1_build"], "s4_layer": ["s1_build"],
    "s5_add": ["s1_build"], "s6_add": ["s1_build"], "s7_grt": ["s1_build"], "s8_direct": ["s1_build"],
}
LIB = re.compile(r'"\$\(dirname "\$0"\)/([\w.]+)"')   # files a script sources or runs from its own folder


def slug(name):
    return "open3d-rs-" + name.replace("_", "-")


def script_text(path):
    """The script as committed: `.gitattributes` keeps *.sh LF in the repository, and a Windows checkout's CRLF are
    undone here, so the sha256 equals `git show HEAD:<path> | sha256sum`."""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return data.decode("utf-8"), hashlib.sha256(data).hexdigest()


def notebook(script_name, text, sha, libs=(), env=None, notes="record"):
    """libs: [(name, text, sha)] written beside the script (it sources them); every hash goes in script.sha256.
    env: variables set for the script (G1_RUN_ID). notes: the /kaggle/working folder for the notebook's own hash and
    exit-code files; G1 needs it outside record/, which its runner must create fresh."""
    files = {script_name: text, **{n: t for n, t, _ in libs}}
    hashes = "".join(f"{h}  {n}\n" for n, h in [(script_name, sha)] + [(n, h) for n, _, h in libs])
    code = (f"import os, pathlib, subprocess\n"
            f"os.environ.update({dict(env or {})!r})\n"
            f"FILES = {files!r}\n"
            f"for name, body in FILES.items():\n"
            f"    pathlib.Path('/kaggle/working', name).write_text(body)\n"
            f"p = pathlib.Path('/kaggle/working/{script_name}')\n"
            f"pathlib.Path('/kaggle/working/{notes}').mkdir(parents=True, exist_ok=True)\n"
            f"pathlib.Path('/kaggle/working/{notes}/script.sha256').write_text({hashes!r})\n"
            f"print('script sha256 {sha}')\n"
            f"rc = subprocess.run(['bash', str(p)]).returncode\n"
            f"pathlib.Path('/kaggle/working/{notes}/notebook_exit_code.txt').write_text(f'{{rc}}\\n')\n"
            f"print('exit code', rc)\n"
            f"if rc:\n"
            f"    raise SystemExit(f'{script_name} exited {{rc}}')\n")
    compile(code, script_name, "exec")
    return {"cells": [{"cell_type": "markdown", "metadata": {},
                       "source": f"# rs-dry {script_name}\n\nRuns `dry/rs/{script_name}` unchanged "
                                 f"(sha256 {sha}). See `dry/rs/DESIGN.md`."},
                      {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": code}],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 5}, sha


G1_SCRIPT = HERE.parent.parent / "gates" / "g1" / "run_g1.sh"
G1_LIBS = ("rs_lib.sh", "add_layers.py")   # run_g1.sh reads them as "$bundle/<name>" and checks S8's hashes itself
G1_RUN_ID = re.compile(r"g1-[A-Za-z0-9][A-Za-z0-9_.-]*")   # run_g1.sh's own rule, used with fullmatch
PINNED = re.compile(r"'([0-9a-f]{64})  ([\w.]+)'")           # the sidecar hashes run_g1.sh checks on Kaggle


def g1_slug(run_id):
    return "open3d-" + re.sub(r"[_.]", "-", run_id).lower()


def write_kernel(parent, owner, kernel_slug, script_name, text, sha, libs, attach, env=None, notes="record"):
    """One kernel folder: the notebook, kernel-metadata.json, and launch.json (what was shipped, for the download
    check). Returns the folder."""
    nb, _ = notebook(script_name, text, sha, libs, env, notes)
    k = Path(parent) / kernel_slug
    k.mkdir(parents=True, exist_ok=True)
    (k / f"{Path(script_name).stem}.ipynb").write_text(json.dumps(nb, indent=1), encoding="utf-8")
    (k / "kernel-metadata.json").write_text(json.dumps({
        "id": f"{owner}/{kernel_slug}", "title": kernel_slug, "code_file": f"{Path(script_name).stem}.ipynb",
        "language": "python", "kernel_type": "notebook", "is_private": True, "enable_gpu": False,
        "enable_tpu": False, "enable_internet": True, "dataset_sources": [], "competition_sources": [],
        "kernel_sources": [f"{owner}/{slug(src)}" for src in attach]}, indent=1), encoding="utf-8")
    (k / "launch.json").write_text(json.dumps({
        "kernel": f"{owner}/{kernel_slug}", "env": dict(env or {}),
        "sha256": {script_name: sha, **{n: h for n, _, h in libs}},
        "attached": [f"{owner}/{slug(src)}" for src in attach]}, indent=1), encoding="utf-8")
    return k


def g1_kernels(parent, owner, run_ids):
    """One kernel per G1 replicate (a fresh session each), the runner and S8's two sidecars byte-exact."""
    text, sha = script_text(G1_SCRIPT)
    libs = [(n, *script_text(HERE / n)) for n in G1_LIBS]
    for n in G1_LIBS:
        if f'"$bundle/{n}"' not in text:
            raise SystemExit(f"run_g1.sh no longer reads {n} from its bundle; update G1_LIBS")
    pinned = {n: h for h, n in PINNED.findall(text) if n in G1_LIBS}
    shipped = {n: h for n, _, h in libs}
    if pinned != shipped:      # run_g1.sh would stop on Kaggle with exit 2 and use up the run id
        raise SystemExit(f"sidecars differ from the hashes run_g1.sh pins: pinned {pinned}, local {shipped}")
    if not all(G1_RUN_ID.fullmatch(r) for r in run_ids):
        raise SystemExit(f"run ids must match {G1_RUN_ID.pattern}: {run_ids}")
    if len({g1_slug(r) for r in run_ids}) != len(run_ids):   # distinct ids can share a slug ('.', '_', case)
        raise SystemExit(f"run ids must give distinct kernel names: {run_ids}")
    taken = [g1_slug(r) for r in run_ids if (Path(parent) / g1_slug(r)).exists()]
    if taken:     # a replicate's kernel is never rewritten, also not by a later call with a colliding id
        raise SystemExit(f"G1 kernel folders already exist, use new run ids: {taken}")
    for r in run_ids:
        k = write_kernel(parent, owner, g1_slug(r), "run_g1.sh", text, sha, libs, ["s1_build"], {"G1_RUN_ID": r},
                         notes="notebook")
        print(k, sha)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("parent")
    ap.add_argument("sessions", nargs="*", metavar="SESSION",
                    help=f"the sessions to build, of {sorted(SESSIONS)}: a session that has run keeps the libs it "
                         "ran with, so it is not rebuilt")
    ap.add_argument("--g1", nargs="+", metavar="RUN_ID", default=[],
                    help="G1 replicate kernels, one per run id (e.g. g1-v1-r1 g1-v1-r2 g1-v1-r3)")
    ap.add_argument("--owner", default="rajulkabir")
    a = ap.parse_args(argv)
    if not a.sessions and not a.g1:
        ap.error("name at least one session or --g1 run id")
    unknown = sorted(set(a.sessions) - set(SESSIONS))    # checked here: argparse rejects an empty list with choices
    if unknown:
        ap.error(f"unknown session(s) {unknown}; choose from {sorted(SESSIONS)}")
    for name in a.sessions:
        text, sha = script_text(HERE / f"{name}.sh")
        libs = [(n, *script_text(HERE / n)) for n in dict.fromkeys(LIB.findall(text))]
        if any(LIB.search(t) for _, t, _ in libs):     # libs are written flat beside the script, one level only
            raise SystemExit(f"{name}: a lib calls another file from its folder; ship it from the script instead")
        print(write_kernel(a.parent, a.owner, slug(name), f"{name}.sh", text, sha, libs, SESSIONS[name]), sha)
    g1_kernels(a.parent, a.owner, a.g1)


if __name__ == "__main__":
    main()
