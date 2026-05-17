import pickle

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
    assert res["fsm"]["function_blocks"][0]["name"] == "FB"


def test_worker_records_error_on_bad_xml(tmp_path):
    bad = tmp_path / "b.ast.xml"
    bad.write_text("<iec-source><unclosed>")
    res = extract_plc("PLC1", str(bad))
    assert res["status"] == "error"
    assert res["errors"]
