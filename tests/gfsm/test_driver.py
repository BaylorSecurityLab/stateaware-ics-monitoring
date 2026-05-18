import json
import pickle
from pathlib import Path

import pytest

from gfsm.worker import extract_plc


def test_worker_is_picklable():
    pickle.dumps(extract_plc)  # function ref must pickle (top-level)


def test_worker_returns_serializable_dict(tmp_path):
    xml = tmp_path / "p.ast.xml"
    xml.write_text(
        "<iec-source><function-block-declaration>"
        "<derived-function-block-name>FB</derived-function-block-name>"
        "<case-statement>"
        "<expression><variable-name>S</variable-name></expression>"
        "<case-element><case-list><case-list-element>"
        "<integer-literal>10</integer-literal>"
        "</case-list-element></case-list>"
        "<statement-list><if-statement>"
        "<expression><variable-name>T</variable-name><less-than/>"
        "<integer-literal>5</integer-literal></expression>"
        "<statement-list><assignment-statement>"
        "<variable-name>S</variable-name>"
        "<expression>\n<integer-literal>20</integer-literal>\n</expression>"
        "</assignment-statement></statement-list>"
        "</if-statement></statement-list></case-element>"
        "</case-statement></function-block-declaration></iec-source>"
    )
    res = extract_plc("PLC1", str(xml))
    pickle.dumps(res)  # whole result must pickle
    assert res["name"] == "PLC1"
    assert res["status"] == "ok"
    assert res["counts"]["function_blocks"] == 1
    assert res["counts"]["states"] == 2
    # The LocalFSM is carried as a plain dict (output.fsm_to_dict shape).
    # Identity is the CASE selector (Task 2 contract): name == case_variable.
    assert res["fsm"]["function_blocks"][0]["name"] == "S"


def test_worker_records_error_on_bad_xml(tmp_path):
    bad = tmp_path / "b.ast.xml"
    bad.write_text("<iec-source><unclosed>")
    res = extract_plc("PLC1", str(bad))
    assert res["status"] == "error"
    assert res["errors"]


# ---------------------------------------------------------------------------
# H3 driver tests
# ---------------------------------------------------------------------------

from gfsm.driver import analyze_topology  # noqa: E402
from gfsm.model import GfsmError  # noqa: E402


def _stage2(gen: Path, topo: str):
    ad = gen / topo / "analysis"
    ad.mkdir(parents=True)
    for n, sa, sb in [("PLC1", "10", "20"), ("PLC2", "30", "40")]:
        (ad / f"{topo}_{n.lower()}.ast.xml").write_text(
            "<iec-source><function-block-declaration>"
            f"<derived-function-block-name>FB{n}</derived-function-block-name>"
            "<case-statement>"
            "<expression><variable-name>S</variable-name></expression>"
            f"<case-element><case-list><case-list-element>"
            f"<integer-literal>{sa}</integer-literal>"
            "</case-list-element></case-list>"
            "<statement-list><if-statement>"
            "<expression><variable-name>T</variable-name><equal/>"
            "<integer-literal>1</integer-literal></expression>"
            "<statement-list><assignment-statement>"
            "<variable-name>S</variable-name>"
            f"<expression>\n<integer-literal>{sb}</integer-literal>\n</expression>"
            "</assignment-statement></statement-list>"
            "</if-statement></statement-list></case-element>"
            "</case-statement></function-block-declaration></iec-source>"
        )
    (ad / f"{topo}_analysis_manifest.json").write_text(json.dumps({
        "schema": "st_analyze/v1",
        "topology": topo,
        "plcs": [
            {"name": "PLC1", "st_file": f"{topo}_plc1.st", "status": "ok",
             "artifacts": {"ast_xml": f"{topo}_plc1.ast.xml"},
             "st_gen_fsms": ["FBPLC1"]},
            {"name": "PLC2", "st_file": f"{topo}_plc2.st", "status": "ok",
             "artifacts": {"ast_xml": f"{topo}_plc2.ast.xml"},
             "st_gen_fsms": ["FBPLC2"]},
        ],
    }))
    return ad


def test_driver_writes_all_artifacts(tmp_path: Path):
    gen = tmp_path / "generated"
    _stage2(gen, "syn")
    out = tmp_path / "gfsm"
    m = analyze_topology(generated_dir=gen, topology="syn", out_dir=out)
    assert (out / "syn_gfsm_manifest.json").exists()
    assert (out / "syn.gfsm.json").exists()
    assert (out / "syn.gfsm.dot").exists()
    assert (out / "syn.gfsm.analysis.json").exists()
    assert (out / "syn_plc1.fsm.json").exists()
    assert (out / "syn_plc1.fsm.dot").exists()
    assert m["topology"] == "syn"
    assert len(m["plcs"]) == 2
    g = json.loads((out / "syn.gfsm.json").read_text())
    assert g["initial"] == "PLC1.S:10|PLC2.S:30"


def test_driver_missing_source_manifest_raises(tmp_path: Path):
    with pytest.raises(GfsmError, match="manifest not found"):
        analyze_topology(
            generated_dir=tmp_path, topology="nope", out_dir=tmp_path
        )


def test_driver_deterministic(tmp_path: Path):
    gen = tmp_path / "generated"
    _stage2(gen, "syn")
    a = tmp_path / "a"
    b = tmp_path / "b"
    analyze_topology(generated_dir=gen, topology="syn", out_dir=a)
    analyze_topology(generated_dir=gen, topology="syn", out_dir=b)
    for name in ["syn.gfsm.json", "syn.gfsm.dot", "syn.gfsm.analysis.json",
                 "syn_plc1.fsm.json"]:
        assert (a / name).read_text() == (b / name).read_text(), name


def test_driver_skips_legitimate_no_fsm_plc(tmp_path: Path):
    # Mirrors real anytown: PLC1 has an FSM; PLC2 legitimately has none
    # (empty st_gen_fsms, AST with no function-block declaration).
    gen = tmp_path / "generated"
    ad = gen / "syn" / "analysis"
    ad.mkdir(parents=True)
    (ad / "syn_plc1.ast.xml").write_text(
        "<iec-source><function-block-declaration>"
        "<derived-function-block-name>FB1</derived-function-block-name>"
        "<case-statement>"
        "<expression><variable-name>S</variable-name></expression>"
        "<case-element><case-list><case-list-element>"
        "<integer-literal>10</integer-literal>"
        "</case-list-element></case-list>"
        "<statement-list><if-statement>"
        "<expression><variable-name>T</variable-name><equal/>"
        "<integer-literal>1</integer-literal></expression>"
        "<statement-list><assignment-statement>"
        "<variable-name>S</variable-name>"
        "<expression>\n<integer-literal>20</integer-literal>\n</expression>"
        "</assignment-statement></statement-list>"
        "</if-statement></statement-list></case-element>"
        "</case-statement></function-block-declaration></iec-source>"
    )
    # No function-block declaration -> extractor raises GfsmError.
    (ad / "syn_plc2.ast.xml").write_text("<iec-source></iec-source>")
    (ad / "syn_analysis_manifest.json").write_text(json.dumps({
        "schema": "st_analyze/v1", "topology": "syn",
        "plcs": [
            {"name": "PLC1", "st_file": "syn_plc1.st", "status": "ok",
             "artifacts": {"ast_xml": "syn_plc1.ast.xml"},
             "st_gen_fsms": ["FB1"]},
            {"name": "PLC2", "st_file": "syn_plc2.st", "status": "ok",
             "artifacts": {"ast_xml": "syn_plc2.ast.xml"},
             "st_gen_fsms": []},
        ],
    }))
    out = tmp_path / "gfsm"
    m = analyze_topology(generated_dir=gen, topology="syn", out_dir=out)
    by = {e["name"]: e for e in m["plcs"]}
    assert by["PLC1"]["status"] == "ok"
    assert by["PLC2"]["status"] == "skipped"
    assert by["PLC2"]["errors"] == []
    assert m["all_ok"] is True  # a legitimate no-FSM PLC must not fail topo
    g = json.loads((out / "syn.gfsm.json").read_text())
    # GFSM composed from PLC1 only; PLC2 absent from the global tuple.
    assert "PLC2" not in g["initial"]
    assert g["initial"] == "PLC1.S:10"
