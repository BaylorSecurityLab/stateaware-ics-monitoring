import json
from pathlib import Path

from gfsm.driver import analyze_topology
from tests.gfsm.test_driver import _stage2


def test_jobs1_vs_jobs4_byte_identical(tmp_path: Path):
    gen = tmp_path / "generated"
    _stage2(gen, "syn")
    a = tmp_path / "a"
    b = tmp_path / "b"
    analyze_topology(generated_dir=gen, topology="syn", out_dir=a, jobs=1)
    analyze_topology(generated_dir=gen, topology="syn", out_dir=b, jobs=4)
    names = sorted(
        p.name for p in a.iterdir()
        if not p.name.endswith("_gfsm_manifest.json")
    )
    assert names
    for name in names:
        assert (a / name).read_text() == (b / name).read_text(), name


def test_resolve_jobs_caps_at_units():
    from gfsm.driver import _resolve_jobs
    assert _resolve_jobs(None, 2) >= 1
    assert _resolve_jobs(None, 2) <= 2
    assert _resolve_jobs(1, 8) == 1
    assert _resolve_jobs(4, 2) == 2  # capped at units
