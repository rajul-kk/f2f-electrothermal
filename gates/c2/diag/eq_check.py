"""A15 for the c2diag.py rewrite: the regenerated state decks equal the originals apart from the first (comment) line
and line endings. Usage: python eq_check.py <old dir> <new dir>"""
import argparse
import glob
import os
from pathlib import Path


def body(path):
    return Path(path).read_text(encoding="utf-8").replace("\r\n", "\n").split("\n", 1)[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    a = ap.parse_args()
    old = sorted(os.path.basename(p) for p in glob.glob(f"{a.old}/s*.cir"))
    new = sorted(os.path.basename(p) for p in glob.glob(f"{a.new}/s*.cir"))
    diff = [n for n in old if n not in new or body(f"{a.old}/{n}") != body(f"{a.new}/{n}")]
    print(f"old {len(old)} new {len(new)} differing {len(diff)} {diff[:3]}")


if __name__ == "__main__":
    main()
