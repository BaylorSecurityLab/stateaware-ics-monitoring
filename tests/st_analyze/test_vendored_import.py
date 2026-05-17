def test_analyzer_submodules_import():
    from iec_st_compiler import core, pdg, invariants, ast_writer

    assert hasattr(core, "compile_to_ast")
    assert hasattr(core, "compile_to_xml")
    assert hasattr(pdg, "build_all_pdgs")
    assert hasattr(invariants, "extract_invariants_from_all_pdgs")
    assert hasattr(ast_writer, "export_pdgs_to_graphviz")
