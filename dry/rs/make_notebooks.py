"""Write the rs-dry Kaggle notebooks and kernel folders from the session scripts in this folder (DESIGN.md).

The notebook runs the script unchanged (embedded as text, written to disk, run with bash) and keeps its exit code,
so what runs on Kaggle is exactly the reviewed file; its sha256 is printed in the notebook and kept in the record.

  python make_notebooks.py <kernel dir parent> [--owner OWNER]
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SESSIONS = {   # libs: files the script sources, shipped beside it; kernels: earlier sessions' outputs attached
    "s1_build": {"slug": "open3d-rs-s1-build", "title": "open3d-rs-s1-build", "internet": True, "libs": [],
                 "kernels": []},
    "s2_gcd": {"slug": "open3d-rs-s2-gcd", "title": "open3d-rs-s2-gcd", "internet": True, "libs": ["rs_lib.sh"],
               "kernels": ["open3d-rs-s1-build"]},
    "s3_ibex": {"slug": "open3d-rs-s3-ibex", "title": "open3d-rs-s3-ibex", "internet": True, "libs": ["rs_lib.sh"],
                "kernels": ["open3d-rs-s1-build"]},
    "s4_layer": {"slug": "open3d-rs-s4-layer", "title": "open3d-rs-s4-layer", "internet": True, "libs": ["rs_lib.sh"],
                 "kernels": ["open3d-rs-s1-build"]},
    "s5_add": {"slug": "open3d-rs-s5-add", "title": "open3d-rs-s5-add", "internet": True,
               "libs": ["rs_lib.sh", "add_layers.py"], "kernels": ["open3d-rs-s1-build"]},
}


def script_text(path):
    """The script as committed: `.gitattributes` keeps *.sh LF in the repository, and a Windows checkout's CRLF are
    undone here, so the sha256 equals `git show HEAD:<path> | sha256sum`."""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return data.decode("utf-8"), hashlib.sha256(data).hexdigest()


def notebook(script_name, text, sha, libs=()):
    """libs: [(name, text, sha)] written beside the script (it sources them); every hash goes in script.sha256."""
    files = {script_name: text, **{n: t for n, t, _ in libs}}
    hashes = "".join(f"{h}  {n}\n" for n, h in [(script_name, sha)] + [(n, h) for n, _, h in libs])
    code = (f"import pathlib, subprocess\n"
            f"FILES = {files!r}\n"
            f"for name, body in FILES.items():\n"
            f"    pathlib.Path('/kaggle/working', name).write_text(body)\n"
            f"p = pathlib.Path('/kaggle/working/{script_name}')\n"
            f"pathlib.Path('/kaggle/working/record').mkdir(parents=True, exist_ok=True)\n"
            f"pathlib.Path('/kaggle/working/record/script.sha256').write_text({hashes!r})\n"
            f"print('script sha256 {sha}')\n"
            f"rc = subprocess.run(['bash', str(p)]).returncode\n"
            f"pathlib.Path('/kaggle/working/record/notebook_exit_code.txt').write_text(f'{{rc}}\\n')\n"
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parent")
    ap.add_argument("--owner", default="rajulkabir")
    a = ap.parse_args()
    for name, s in SESSIONS.items():
        text, sha = script_text(HERE / f"{name}.sh")
        libs = [(n, *script_text(HERE / n)) for n in s["libs"]]
        nb, _ = notebook(f"{name}.sh", text, sha, libs)
        k = Path(a.parent) / s["slug"]
        k.mkdir(parents=True, exist_ok=True)
        (k / f"{name}.ipynb").write_text(json.dumps(nb, indent=1), encoding="utf-8")
        (k / "kernel-metadata.json").write_text(json.dumps({
            "id": f"{a.owner}/{s['slug']}", "title": s["title"], "code_file": f"{name}.ipynb", "language": "python",
            "kernel_type": "notebook", "is_private": True, "enable_gpu": False, "enable_tpu": False,
            "enable_internet": s["internet"], "dataset_sources": [], "competition_sources": [],
            "kernel_sources": [f"{a.owner}/{src}" for src in s["kernels"]]},
            indent=1), encoding="utf-8")
        print(k, sha)


if __name__ == "__main__":
    main()
