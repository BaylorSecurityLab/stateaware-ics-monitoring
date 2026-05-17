import json
import subprocess
import sys
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_cli_runs_end_to_end(tmp_path):
    out = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable, "-m", "st_gen",
            "--inp", str(FIXTURE_DIR / "tiny.inp"),
            "--plcs", str(FIXTURE_DIR / "tiny_plcs.yaml"),
            "--out", str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    # topology inferred from --inp basename "tiny"
    assert (out / "tiny_plc1.st").exists()
    assert (out / "tiny_plc2.st").exists()
    manifest = json.loads((out / "tiny_manifest.json").read_text(encoding="utf-8"))
    assert manifest["topology"] == "tiny"
    assert manifest["inp"] == "tiny.inp"
    assert manifest["plcs_yaml"] == "tiny_plcs.yaml"


def test_cli_unsupported_control_exits_2(tmp_path):
    bad = tmp_path / "bad.inp"
    bad.write_text(
        "[CONTROLS]\nLINK PUMP1 OPEN AT TIME 5\n[END]\n",
        encoding="utf-8",
    )
    plcs = tmp_path / "p.yaml"
    plcs.write_text("- name: PLC1\n  actuators: [PUMP1]\n", encoding="utf-8")
    out = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable, "-m", "st_gen",
            "--inp", str(bad),
            "--plcs", str(plcs),
            "--out", str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "AT TIME" in result.stderr
