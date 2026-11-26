"""Check one downloaded G1 replicate against what was shipped, before any scoring.

  python gates/g1/check_download.py <kernel dir with launch.json> <download dir>

The download dir is `kaggle kernels output` of that kernel. Checked: the run id; the shipped runner and sidecar
hashes (both the notebook's list and the runner's own); the notebook exit code; the runner's end marker
(record/complete.txt), which binds the run id to both archives and every record file; that the environment and
scoring evidence is present and non-empty; that flow_results.tgz holds each case's final ODB, DEF, Verilog and SDC
once, with the hashes in final_outputs.sha256; that flow_logs.tgz holds each case's final summary and route log,
whose DRC counts equal final_route_drc.tsv, and the route DRC report, whose complete markers number the same (required
where the count is not zero). Both archives are read through to the gzip trailer. Writes <download dir>/check.json
and exits 1 on any problem; a failed attempt keeps its files and is replaced by a new run id, never re-checked into
a pass. Download with kaggle 2.x (WSL ~/kgl), which fetches every output page; if files the end marker lists are
absent, the download is incomplete: exit 2, nothing recorded, download again.
"""
import gzip
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path

ARCHIVES = ("flow_results.tgz", "flow_logs.tgz")
CASES = ("gcd", "ibex")
FINALS = tuple(f"results/asap7_3D/{c}/openroad/6_final.{x}" for c in CASES for x in ("odb", "def", "v", "sdc"))
# What run_g1.sh and rs_lib.sh write into record/ and the scorer or the environment comparison reads.
EVIDENCE = ("run_id.txt", "script.sha256", "complete.txt", "final_outputs.sha256", "final_route_drc.tsv",
            "flow_results.sha256", "flow_logs.sha256", "sidecars_check.txt", "patched_config_check.txt", "cpu.txt",
            "machine.txt", "commits.txt", "build_identity.txt", "packages_before_setup.tsv",
            "packages_after_setup.tsv", "linked_libraries.sha256", "steps.log")
SUMMARY_DRC = re.compile(r"^DRC Violations\s+(\d+)\s*$", re.MULTILINE)      # as run_g1.sh's collect_case
ROUTE_DRC = re.compile(r"Number of violations = (\d+)\.")
# One marker in OpenROAD's detailed-route report (Pin-3D's final summary counts the first line of each):
#   violation type: Cut Spacing / <tab>srcs: net:a net:b / <tab>bbox = (x, y) - (x, y) on Layer hb_layer
DRC_HEAD = re.compile(r"^violation type:", re.MULTILINE)
DRC_BLOCK = re.compile(r"^violation type: .+\n[ \t]*srcs: .*\n[ \t]*bbox = .* on Layer \S+[ \t]*\n", re.MULTILINE)
# (the box line must end in its newline: a copy cut inside the last layer name is not a complete marker)


def logs(case):
    return {"summary": f"flow_logs/asap7_3D/{case}/openroad/final_summary.txt",
            "route": f"flow_logs/asap7_3D/{case}/openroad/5_2_route.log",
            "drc_report": f"flow_reports/asap7_3D/{case}/openroad/5_route_drc.rpt"}


def text(path):
    """A small text file's content, or None if it is missing or not UTF-8."""
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def read_hashes(content, base_names=True):
    """{name: sha256} from a sha256sum listing (names reduced to their base name unless base_names is False); None
    if the content is missing, a line is not `<64 hex>  <name>`, or a name repeats."""
    if content is None:
        return None
    out = {}
    for line in content.splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64 or any(c not in "0123456789abcdef" for c in parts[0]):
            return None
        name = parts[1].strip().lstrip("*")
        name = Path(name).name if base_names else name
        if name in out:
            return None
        out[name] = parts[0]
    return out


def sha256_stream(fh):
    h = hashlib.sha256()
    for block in iter(lambda: fh.read(1 << 20), b""):
        h.update(block)
    return h.hexdigest()


def sha256(path):
    with path.open("rb") as fh:
        return sha256_stream(fh)


def read_tgz(path, wanted):
    """{member: (sha256, size, content)} for the wanted members (content kept only where wanted[member] is true),
    reading the whole gzip stream so a cut or corrupt archive raises. Raises ValueError on a repeated or non-file
    wanted member."""
    out = {}
    with gzip.open(path, "rb") as gz:
        with tarfile.open(fileobj=gz, mode="r|") as tar:
            for m in tar:
                if m.name not in wanted:
                    continue
                if m.name in out or not m.isfile():
                    raise ValueError(f"{m.name} repeats or is not a regular file")
                data = tar.extractfile(m).read() if wanted[m.name] else None
                digest = hashlib.sha256(data).hexdigest() if data is not None else sha256_stream(tar.extractfile(m))
                out[m.name] = (digest, m.size, data)
        while gz.read(1 << 20):     # past tar's end blocks to the gzip trailer (CRC and length)
            pass
    return out


def archive_problems(d, finals, drc):
    bad = []
    try:
        got = read_tgz(d / "flow_results.tgz", dict.fromkeys(FINALS, False))
        wrong = sorted(n for n in FINALS if n not in got or got[n][1] == 0 or got[n][0] != finals[n])
        if wrong:
            bad.append(f"flow_results.tgz final outputs missing, empty or differing from final_outputs.sha256: "
                       f"{wrong}")
    except (tarfile.TarError, OSError, EOFError, ValueError) as e:
        bad.append(f"flow_results.tgz is unreadable or ambiguous: {e}")
    try:
        got = read_tgz(d / "flow_logs.tgz", {n: True for c in CASES for n in logs(c).values()})
    except (tarfile.TarError, OSError, EOFError, ValueError) as e:
        return bad + [f"flow_logs.tgz is unreadable or ambiguous: {e}"]
    for c in CASES:
        names = logs(c)
        needed = ("summary", "route") + (("drc_report",) if drc[c] != 0 else ())
        absent = [names[k] for k in needed if names[k] not in got or got[names[k]][1] == 0]
        if absent:
            bad.append(f"flow_logs.tgz lacks {absent}")
            continue
        summary = SUMMARY_DRC.findall(got[names["summary"]][2].decode("utf-8", "replace"))
        route = ROUTE_DRC.findall(got[names["route"]][2].decode("utf-8", "replace"))
        if summary != [str(drc[c])] or not route or route[-1] != str(drc[c]):
            bad.append(f"{c}: final_route_drc.tsv count {drc[c]} differs from the summary {summary} or the route "
                       f"log's last count {route[-1:]}")
        if names["drc_report"] in got:      # optional at zero markers, but then it must hold none
            report = got[names["drc_report"]][2].decode("utf-8", "replace")
            heads, blocks = len(DRC_HEAD.findall(report)), len(DRC_BLOCK.findall(report))
            if not heads == blocks == drc[c]:
                bad.append(f"{c}: the DRC report has {heads} markers, {blocks} complete (type, sources, box and "
                           f"layer), not the {drc[c]} in final_route_drc.tsv")
    return bad


def drc_counts(content):
    """{case: count} from final_route_drc.tsv, or None unless it is exactly one integer row per case."""
    rows = [line.split("\t") for line in (content or "").splitlines()]
    if len(rows) != len(CASES) or any(len(r) != 2 or not r[1].isdigit() for r in rows):
        return None
    out = {r[0]: int(r[1]) for r in rows}
    return out if set(out) == set(CASES) else None


def problems(launch, d):
    """Every reason this download cannot be scored (empty list: it can)."""
    rec, notes = d / "record", d / "notebook"
    need = [rec / n for n in EVIDENCE] + [notes / "script.sha256", notes / "notebook_exit_code.txt"] + \
        [d / a for a in ARCHIVES]
    missing = [str(p.relative_to(d)) for p in need if not p.is_file() or p.stat().st_size == 0]
    if missing:
        return [f"missing or empty: {', '.join(missing)}"]
    bad = []
    run_id = launch["env"].get("G1_RUN_ID")
    got = (text(rec / "run_id.txt") or "").strip()
    if got != run_id:
        bad.append(f"run id {got!r}, launched {run_id!r}")
    for listing in (notes / "script.sha256", rec / "script.sha256"):
        if read_hashes(text(listing)) != launch["sha256"]:
            bad.append(f"{listing.relative_to(d)} differs from what was shipped or is malformed")
    code = (text(notes / "notebook_exit_code.txt") or "").strip()
    if code != "0":
        bad.append(f"notebook exit code {code!r}")
    marker = (text(rec / "complete.txt") or "").splitlines()
    bound = read_hashes("\n".join(marker[1:]), base_names=False)
    must_bind = {*ARCHIVES, *(f"record/{n}" for n in EVIDENCE if n != "complete.txt")}
    if marker[:1] != [f"G1 artifacts complete: {run_id}"] or bound is None or not must_bind <= set(bound):
        return bad + ["end marker is not this run's or does not bind the archives and every evidence file"]
    changed = sorted(n for n, h in bound.items() if not (d / n).is_file() or sha256(d / n) != h)
    if changed:
        return bad + [f"files differ from the end marker (edited, cut or from another replicate): {changed}"]
    unreadable = [n for n in EVIDENCE if text(rec / n) is None]
    if unreadable:
        bad.append(f"evidence files are not UTF-8 text: {unreadable}")
    for a in ARCHIVES:
        if (read_hashes(text(rec / a.replace(".tgz", ".sha256"))) or {}).get(a) != bound[a]:
            bad.append(f"record/{a.replace('.tgz', '.sha256')} does not match {a}")
    finals = read_hashes(text(rec / "final_outputs.sha256"), base_names=False)
    if finals is None or set(finals) != set(FINALS):
        bad.append(f"record/final_outputs.sha256 does not list exactly {list(FINALS)}")
    drc = drc_counts(text(rec / "final_route_drc.tsv"))
    if drc is None:
        bad.append("record/final_route_drc.tsv does not give one DRC count per case")
    if bad:
        return bad
    return archive_problems(d, finals, drc)


def not_downloaded(d):
    """Files this download should hold but lacks, which says nothing about the run: the notebook's exit code
    (always written), the end marker when that exit code is 0 (run_g1.sh exits 0 only after writing it), and every
    file the end marker binds."""
    code = d / "notebook" / "notebook_exit_code.txt"
    if not code.is_file():
        return ["notebook/notebook_exit_code.txt"]
    marker = d / "record" / "complete.txt"
    if not marker.is_file():
        return ["record/complete.txt"] if (text(code) or "").strip() == "0" else []
    bound = read_hashes("\n".join((text(marker) or "").splitlines()[1:]), base_names=False)
    return sorted(n for n in bound or {} if not (d / n).is_file())


def main(kernel_dir, download_dir):
    launch = json.loads((Path(kernel_dir) / "launch.json").read_text(encoding="utf-8"))
    d = Path(download_dir)
    old = d / "check.json"
    if old.is_file() and not json.loads(old.read_text(encoding="utf-8")).get("ok"):
        print(f"{old} already records a failed check; this attempt stays failed (rerun under a new run id)")
        return 1
    absent = not_downloaded(d)
    if absent:
        print(f"download incomplete, nothing recorded: {len(absent)} files the end marker lists are absent, e.g. "
              f"{absent[:3]}. Download again with a CLI that fetches every output page (kaggle 2.x).")
        return 2
    bad = problems(launch, d)
    (d / "check.json").write_text(json.dumps({"kernel": launch["kernel"], "run_id": launch["env"].get("G1_RUN_ID"),
                                              "ok": not bad, "problems": bad}, indent=1) + "\n", encoding="utf-8")
    for b in bad:
        print("PROBLEM", b)
    print("ok" if not bad else f"{len(bad)} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
