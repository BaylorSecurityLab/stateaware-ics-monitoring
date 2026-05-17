import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ANYTOWN = REPO / "data" / "generated" / "anytown"
COMMENT = re.compile(r"(\(\*.*?\*\))|(\{.*?})", re.S)


@pytest.mark.skipif(
    not (ANYTOWN / "anytown_plc1.st").exists(),
    reason="generated data missing; run st-gen / git submodule update --init",
)
def test_analyzer_parses_st_gen_plc1():
    from iec_st_compiler import core, pdg

    src = (ANYTOWN / "anytown_plc1.st").read_text()
    ast = core.compile_to_ast(src, COMMENT)
    assert ast, "analyzer produced empty AST for anytown_plc1.st"

    pdgs, state_var = pdg.build_all_pdgs(ast)
    assert pdgs, "analyzer built no PDGs for a PLC with 2 FSMs"


@pytest.mark.skipif(
    not (ANYTOWN / "anytown_plc2.st").exists(),
    reason="generated data missing",
)
def test_analyzer_parses_empty_plc():
    from iec_st_compiler import core

    src = (ANYTOWN / "anytown_plc2.st").read_text()
    ast = core.compile_to_ast(src, COMMENT)
    assert ast is not None  # empty PROGRAM still parses
