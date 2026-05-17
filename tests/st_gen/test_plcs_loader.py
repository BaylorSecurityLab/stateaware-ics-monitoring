from pathlib import Path

import pytest

from st_gen.model import ValidationError
from st_gen.plcs_loader import load_plcs

FIXTURE = Path(__file__).parent / "fixtures" / "tiny_plcs.yaml"


def test_load_plcs_happy():
    plcs = load_plcs(FIXTURE)
    assert [p.name for p in plcs] == ["PLC1", "PLC2"]
    assert plcs[0].sensors == ["T1"]
    assert plcs[0].actuators == ["PUMP1"]
    assert plcs[1].sensors == ["T2"]
    assert plcs[1].actuators == []  # missing key -> empty


def test_load_plcs_rejects_duplicate_names(tmp_path):
    f = tmp_path / "dup.yaml"
    f.write_text(
        "- name: PLC1\n"
        "  actuators: [A]\n"
        "- name: PLC1\n"
        "  sensors: [S]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError) as exc:
        load_plcs(f)
    assert "PLC1" in str(exc.value)


def test_load_plcs_rejects_non_list(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text("PLC1: {sensors: [T1]}\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_plcs(f)


def test_load_plcs_rejects_missing_name(tmp_path):
    f = tmp_path / "noname.yaml"
    f.write_text("- sensors: [T1]\n", encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        load_plcs(f)
    assert "name" in str(exc.value).lower()
