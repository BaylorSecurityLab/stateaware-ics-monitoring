from pathlib import Path

import pytest

from st_analyze.cli import main


def test_missing_manifest_returns_2(tmp_path: Path, capsys):
    rc = main(["--topology", "nope", "--generated-dir", str(tmp_path)])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_cli_runs_anytown(tmp_path: Path):
    gen = Path(__file__).resolve().parents[2] / "data" / "generated"
    if not (gen / "anytown" / "anytown_manifest.json").exists():
        pytest.skip("generated anytown data missing")
    rc = main([
        "--topology", "anytown",
        "--generated-dir", str(gen),
        "--out", str(tmp_path / "analysis"),
    ])
    assert rc == 0
    assert (tmp_path / "analysis" / "anytown_analysis_manifest.json").exists()
