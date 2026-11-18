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
SESSIONS = {"s1_build": {"slug": "open3d-rs-s1-build", "title": "open3d-rs-s1-build", "internet": True}}


def script_text(path):
    """The script as committed: `.gitattributes` keeps *.sh LF in the repository, and a Windows checkout's CRLF are
    undone here, so the sha256 equals `git show HEAD:<path> | sha256sum`."""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return data.decode("utf-8"), hashlib.sha256(data).hexdigest()


def notebook(script_name, text, sha):
    code = (f"import pathlib, subprocess\n"
            f"SCRIPT = {text!r}\n"
            f"p = pathlib.Path('/kaggle/working/{script_name}')\n"
            f"p.write_text(SCRIPT)\n"
            f"pathlib.Path('/kaggle/working/record').mkdir(parents=True, exist_ok=True)\n"
            f"pathlib.Path('/kaggle/working/record/script.sha256').write_text('{sha}  {script_name}\\n')\n"
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
        nb, _ = notebook(f"{name}.sh", text, sha)
        k = Path(a.parent) / s["slug"]
        k.mkdir(parents=True, exist_ok=True)
        (k / f"{name}.ipynb").write_text(json.dumps(nb, indent=1), encoding="utf-8")
        (k / "kernel-metadata.json").write_text(json.dumps({
            "id": f"{a.owner}/{s['slug']}", "title": s["title"], "code_file": f"{name}.ipynb", "language": "python",
            "kernel_type": "notebook", "is_private": True, "enable_gpu": False, "enable_tpu": False,
            "enable_internet": s["internet"], "dataset_sources": [], "competition_sources": [], "kernel_sources": []},
            indent=1), encoding="utf-8")
        print(k, sha)


if __name__ == "__main__":
    main()
