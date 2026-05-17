import json
from pathlib import Path

import pytest

from st_gen import emit, load_plcs, parse_inp


REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
GOLDEN = Path(__file__).parent / "golden"


def pytest_addoption(parser):
    parser.addoption(
        "--update-goldens",
        action="store_true",
        default=False,
        help="Overwrite golden files with current emitter output.",
    )


@pytest.fixture
def update_goldens(request):
    return request.config.getoption("--update-goldens")


def run_and_compare(topology: str, tmp_path: Path, update: bool) -> None:
    inp = DATA / topology / f"{topology}.inp"
    yml = DATA / topology / f"{topology}_plcs.yaml"
    if not inp.exists() or not yml.exists():
        pytest.skip(f"submodule data missing for {topology}; run `git submodule update --init`")

    out = tmp_path / "out"
    emit(
        network=parse_inp(inp),
        plcs=load_plcs(yml),
        out_dir=out,
        topology=topology,
        inp_filename=inp.name,
        plcs_filename=yml.name,
    )

    golden_dir = GOLDEN / topology
    if update:
        golden_dir.mkdir(parents=True, exist_ok=True)
        for f in golden_dir.glob("*"):
            f.unlink()
        for f in out.iterdir():
            (golden_dir / f.name).write_bytes(f.read_bytes())
        return

    expected_files = {f.name for f in golden_dir.glob("*")} if golden_dir.exists() else set()
    actual_files = {f.name for f in out.iterdir()}
    assert expected_files == actual_files, (
        f"file list mismatch for {topology}: "
        f"missing={expected_files - actual_files} extra={actual_files - expected_files}"
    )
    for name in sorted(expected_files):
        if name.endswith("_manifest.json"):
            exp = json.loads((golden_dir / name).read_text(encoding="utf-8"))
            act = json.loads((out / name).read_text(encoding="utf-8"))
            exp.pop("generated_at", None)
            act.pop("generated_at", None)
            assert exp == act, f"manifest {name} differs"
        else:
            assert (golden_dir / name).read_bytes() == (out / name).read_bytes(), (
                f"{name} differs from golden"
            )
