"""G1 packaging: replicate kernels ship the runner byte-exact with its run id, and a download passes only when every
shipped hash, the end marker and both archives check out."""
import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mk = load("make_notebooks", HERE.parent.parent / "dry" / "rs" / "make_notebooks.py")
chk = load("check_download", HERE / "check_download.py")


def test_replicate_kernels_carry_their_run_id_and_leave_record_to_the_runner(tmp_path):
    mk.g1_kernels(tmp_path, "owner", ["g1-v1-r1", "g1-v1-r2"])
    for r in ("r1", "r2"):
        k = tmp_path / f"open3d-g1-v1-{r}"
        launch = json.loads((k / "launch.json").read_text(encoding="utf-8"))
        assert launch["env"] == {"G1_RUN_ID": f"g1-v1-{r}"}
        assert set(launch["sha256"]) == {"run_g1.sh", "rs_lib.sh", "add_layers.py"}
        assert launch["sha256"]["run_g1.sh"] == hashlib.sha256(
            (HERE / "run_g1.sh").read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        code = json.loads((k / "run_g1.ipynb").read_text(encoding="utf-8"))["cells"][1]["source"]
        assert "Path('/kaggle/working/record" not in code      # run_g1.sh refuses an existing record/
        assert "Path('/kaggle/working/notebook')" in code
        assert f"'G1_RUN_ID': 'g1-v1-{r}'" in code
        meta = json.loads((k / "kernel-metadata.json").read_text(encoding="utf-8"))
        assert meta["kernel_sources"] == ["owner/open3d-rs-s1-build"]


@pytest.mark.parametrize("ids", [["g1-a", "g1-a"], ["G1-bad"], ["g1-"], ["g1-a.b", "g1-a-b"], ["g1-A", "g1-a"],
                                 ["g1-v1-r1\n"]])
def test_bad_or_colliding_run_ids_are_refused(tmp_path, ids):
    with pytest.raises(SystemExit):
        mk.g1_kernels(tmp_path, "owner", ids)
    assert not list(tmp_path.iterdir())


def test_the_g1_command_line_builds_kernels_without_a_session(tmp_path):
    mk.main([str(tmp_path), "--g1", "g1-v1-r1"])
    assert [p.name for p in tmp_path.iterdir()] == ["open3d-g1-v1-r1"]


def test_sidecars_that_differ_from_the_runners_pins_are_refused(tmp_path, monkeypatch):
    real = mk.script_text

    def edited(path):
        text, sha = real(path)
        return (text + "\n# edited\n", "0" * 64) if path.name == "rs_lib.sh" else (text, sha)
    monkeypatch.setattr(mk, "script_text", edited)
    with pytest.raises(SystemExit, match="pins"):
        mk.g1_kernels(tmp_path, "owner", ["g1-v1-r1"])


def test_a_second_call_cannot_overwrite_an_existing_replicate(tmp_path):
    mk.g1_kernels(tmp_path, "owner", ["g1-a.b"])
    before = (tmp_path / "open3d-g1-a-b" / "launch.json").read_bytes()
    with pytest.raises(SystemExit, match="already exist"):
        mk.g1_kernels(tmp_path, "owner", ["g1-x", "g1-a-b"])
    assert (tmp_path / "open3d-g1-a-b" / "launch.json").read_bytes() == before
    assert not (tmp_path / "open3d-g1-x").exists()


def tgz(path, members):
    with tarfile.open(path, "w:gz") as tar:
        for name, data in (members.items() if isinstance(members, dict) else members):   # a list may repeat names
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def seal(d, run_id):
    """Write the runner's listings and end marker for whatever archives and final listing are in d."""
    for a in chk.ARCHIVES:
        (d / "record" / a.replace(".tgz", ".sha256")).write_text(
            f"{sha(d / a)}  /kaggle/working/{a}\n", encoding="utf-8")
    names = [*chk.ARCHIVES] + sorted(f.relative_to(d).as_posix() for f in (d / "record").rglob("*")
                                     if f.is_file() and f.name != "complete.txt")
    bound = "".join(f"{sha(d / n)}  {n}\n" for n in names)
    (d / "record" / "complete.txt").write_text(f"G1 artifacts complete: {run_id}\n{bound}", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


MARKER = (b"violation type: Cut Spacing\n\tsrcs: net:a net:clk\n"
          b"\tbbox = (5.4720, 4.4480) - (6.0160, 4.9920) on Layer hb_layer\n")


def with_report(case, content):
    """The passing logs archive, with this case's DRC report replaced."""
    members = logs_members({"gcd": 0, "ibex": 99})
    members[chk.logs(case)["drc_report"]] = content
    return lambda d: tgz(d / "flow_logs.tgz", members)


def logs_members(drc, salt=b""):
    """Each case's final summary and route log with these DRC counts, and the DRC report where the count is not 0."""
    out = {}
    for c, n in drc.items():
        m = chk.logs(c)
        out[m["summary"]] = f"Core Area 1\nDRC Violations             {n}\n".encode() + salt
        out[m["route"]] = f"Number of violations = 132.\nNumber of violations = {n}.\n".encode()
        if n:
            out[m["drc_report"]] = MARKER * n
    return out


def fake_replicate(d, launch, run_id, salt=b""):
    (d / "record").mkdir(parents=True)
    (d / "notebook").mkdir()
    listing = "".join(f"{h}  /kaggle/working/{n}\n" for n, h in launch["sha256"].items())
    (d / "record" / "script.sha256").write_text(listing, encoding="utf-8")
    (d / "notebook" / "script.sha256").write_text(listing.replace("/kaggle/working/", ""), encoding="utf-8")
    (d / "notebook" / "notebook_exit_code.txt").write_text("0\n", encoding="utf-8")
    (d / "record" / "run_id.txt").write_text(f"{run_id}\n", encoding="utf-8")
    for n in chk.EVIDENCE:
        if not (d / "record" / n).exists():
            (d / "record" / n).write_text("evidence\n", encoding="utf-8")
    (d / "record" / "final_route_drc.tsv").write_text("gcd\t0\nibex\t99\n", encoding="utf-8")
    finals = {n: n.encode() + salt for n in chk.FINALS}
    (d / "record" / "final_outputs.sha256").write_text(
        "".join(f"{hashlib.sha256(b).hexdigest()}  {n}\n" for n, b in finals.items()), encoding="utf-8")
    tgz(d / "flow_results.tgz", {**finals, "objects/asap7_3D/ibex/x": b"obj"})
    tgz(d / "flow_logs.tgz", logs_members({"gcd": 0, "ibex": 99}, salt))
    seal(d, run_id)


@pytest.fixture
def download(tmp_path):
    """A kernel folder and a download that passes every check, with small real archives."""
    mk.g1_kernels(tmp_path / "k", "owner", ["g1-v1-r1"])
    k = tmp_path / "k" / "open3d-g1-v1-r1"
    launch = json.loads((k / "launch.json").read_text(encoding="utf-8"))
    d = tmp_path / "dl"
    fake_replicate(d, launch, "g1-v1-r1")
    return k, d


def test_a_complete_download_passes(download):
    k, d = download
    assert chk.main(k, d) == 0
    assert json.loads((d / "check.json").read_text(encoding="utf-8"))["ok"] is True


def resealed(change):
    """Break one thing, then rewrite the runner's listings and marker so only the archive content check can see it."""
    def apply(d):
        change(d)
        seal(d, "g1-v1-r1")
    return apply


def swap_from_other_replicate(d):
    """Another replicate's results archive and its own sidecar, moved into this run's folder."""
    launch = {"sha256": {}}
    other = d.parent / "other"
    fake_replicate(other, launch, "g1-v1-r2", salt=b"2")
    for n in ("flow_results.tgz", "record/flow_results.sha256"):
        (d / n).write_bytes((other / n).read_bytes())


@pytest.mark.parametrize("break_it, word", [
    (lambda d: ((d / "record" / "complete.txt").unlink(),         # a failed run: nonzero exit and no marker
                (d / "notebook" / "notebook_exit_code.txt").write_text("1\n", encoding="utf-8")), "missing"),
    (lambda d: (d / "flow_logs.tgz").write_bytes(b"changed"), "flow_logs.tgz"),
    (lambda d: (d / "record" / "run_id.txt").write_text("g1-v1-r9\n", encoding="utf-8"), "run id"),
    (lambda d: (d / "notebook" / "notebook_exit_code.txt").write_text("1\n", encoding="utf-8"), "exit code"),
    (lambda d: (d / "record" / "script.sha256").write_text("0" * 64 + "  run_g1.sh\n", encoding="utf-8"),
     "differs"),
    (lambda d: (d / "record" / "script.sha256").write_text(
        "0" * 64 + "  run_g1.sh\n" + (d / "record" / "script.sha256").read_text(encoding="utf-8"),
        encoding="utf-8"), "differs"),
    (lambda d: (d / "record" / "script.sha256").write_bytes(b"\xff\xfe"), "differs"),
    (lambda d: (d / "flow_results.tgz").write_bytes(b"changed"), "flow_results.tgz"),
    (lambda d: (d / "notebook" / "script.sha256").write_text(
        (d / "notebook" / "script.sha256").read_text(encoding="utf-8").replace(
            next(line for line in (d / "notebook" / "script.sha256").read_text(encoding="utf-8").splitlines()
                 if line.endswith("add_layers.py"))[:64], "f" * 64), encoding="utf-8"), "notebook"),
    (lambda d: (d / "record" / "flow_results.sha256").write_text("5217f622\n", encoding="utf-8"), "flow_results"),
    (lambda d: (d / "record" / "complete.txt").write_text(
        (d / "record" / "complete.txt").read_text(encoding="utf-8").replace("g1-v1-r1", "g1-v1-r2"),
        encoding="utf-8"), "end marker"),
    (lambda d: (d / "record" / "complete.txt").write_text("G1 artifacts complete: g1-v1-r1\n", encoding="utf-8"),
     "end marker"),
    (swap_from_other_replicate, "end marker"),
    (resealed(lambda d: tgz(d / "flow_results.tgz", {n: n.encode() for n in chk.FINALS[:-1]})), "final outputs"),
    (resealed(lambda d: tgz(d / "flow_results.tgz", {n: b"other" for n in chk.FINALS})), "final outputs"),
    (resealed(lambda d: tgz(d / "flow_logs.tgz", {"flow_logs/asap7_3D/gcd/openroad/a.log": b"x"})), "lacks"),
    (resealed(lambda d: tgz(d / "flow_logs.tgz", {k: v for k, v in logs_members({"gcd": 0, "ibex": 99}).items()
                                                  if not k.endswith("5_route_drc.rpt")})), "lacks"),
    (resealed(lambda d: tgz(d / "flow_logs.tgz", logs_members({"gcd": 0, "ibex": 98}))), "differs from the summary"),
    (resealed(lambda d: (d / "record" / "final_route_drc.tsv").write_text("gcd\t0\nibex\t98\n",
                                                                         encoding="utf-8")), "differs from the summary"),
    (lambda d: (d / "record" / "machine.txt").write_text("", encoding="utf-8"), "empty"),
    (resealed(with_report("ibex", MARKER)), "complete"),
    (resealed(with_report("ibex", MARKER * 98 + b"violation type: Cut Spacing\n")), "complete"),
    (resealed(with_report("gcd", MARKER)), "complete"),
    (resealed(with_report("ibex", (MARKER * 99)[:-len(b"ayer\n")])), "complete"),   # cut inside the last layer name
    (lambda d: (d / "record" / "final_route_drc.tsv").write_text("gcd\t0\nibex\t98\n", encoding="utf-8"),
     "differ from the end marker"),
    (resealed(lambda d: (d / "record" / "linked_libraries.sha256").write_bytes(b"\xff\xfe")), "not UTF-8"),
    (resealed(lambda d: tgz(d / "flow_results.tgz", [*((n, n.encode()) for n in chk.FINALS), (chk.FINALS[0], b"")])),
     "repeats"),
    (resealed(lambda d: (d / "flow_results.tgz").write_bytes((d / "flow_results.tgz").read_bytes()[:-8])),
     "unreadable"),
    (resealed(lambda d: (d / "flow_results.tgz").write_bytes(b"not a tar")), "unreadable"),
    (resealed(lambda d: (d / "record" / "final_route_drc.tsv").write_text("gcd\t0\n", encoding="utf-8")), "DRC"),
])
def test_each_broken_piece_fails_the_check(download, break_it, word):
    k, d = download
    break_it(d)
    assert chk.main(k, d) == 1
    report = json.loads((d / "check.json").read_text(encoding="utf-8"))
    assert not report["ok"] and any(word in p for p in report["problems"]), report["problems"]


def test_a_failed_attempt_is_not_rechecked_into_a_pass(download):
    k, d = download
    run_id = (d / "record" / "run_id.txt").read_text(encoding="utf-8")
    (d / "record" / "run_id.txt").write_text("g1-v1-r9\n", encoding="utf-8")
    assert chk.main(k, d) == 1
    (d / "record" / "run_id.txt").write_text(run_id, encoding="utf-8")   # "repaired" in place
    assert chk.main(k, d) == 1
    assert json.loads((d / "check.json").read_text(encoding="utf-8"))["ok"] is False


@pytest.mark.parametrize("name", ["record/cpu.txt", "record/linked_libraries.sha256", "record/final_outputs.sha256",
                                  "flow_logs.tgz", "record/complete.txt", "notebook/notebook_exit_code.txt"])
def test_an_incomplete_download_is_not_recorded_as_a_failed_run(download, name):
    k, d = download
    (d / name).unlink()        # e.g. a CLI that fetched only the first output page
    assert chk.main(k, d) == 2
    assert not (d / "check.json").exists()


def test_the_report_pattern_counts_real_s8_reports():
    s8 = HERE.parent.parent / "dry" / "rs" / "record" / "2026-11-20_s8_v1" / "route_drc"
    for case, n in (("gcd", 72), ("ibex", 99)):
        text = (s8 / f"{case}_5_route_drc.rpt").read_text(encoding="utf-8")
        assert len(chk.DRC_HEAD.findall(text)) == len(chk.DRC_BLOCK.findall(text)) == n
