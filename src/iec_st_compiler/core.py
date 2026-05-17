"""
Core Compiler Logic for IEC 61131-3 Structured Text (ST).

This module provides the high-level functions necessary to parse ST source code
 and convert the resulting Abstract Syntax Tree (AST) into XML format.
"""

import re
from typing import List, Union, Any
from lxml import etree
from . import grammar
from .parser import parse
from . import pdg as pdg_module
from . import invariants as inv_module
from .ast_writer import convert_ast_to_xml_with_invariants_and_summary, convert_ast_to_xml
import traceback

# Type aliases for clarity
CommentPattern = Union[re.Pattern, List]


class StringLineSource:
    """Mimics file input.FileInput for parsing strings."""

    def __init__(self, content: str):
        self.lines = content.splitlines(keepends=True)
        self._index = 0
        self._first_line = True

    def __iter__(self):
        return self

    def __next__(self):
        if self._index >= len(self.lines):
            raise StopIteration
        line = self.lines[self._index]
        self._index += 1
        return line

    def isfirstline(self):
        """Returns True on the first line, False afterward."""
        if self._first_line:
            self._first_line = False
            return True
        return False

    @staticmethod
    def filename():
        return "<string>"



def compile_to_xml(
    source_content: str,
    comment_pattern: CommentPattern,
    pretty_print: bool = False,
) -> str:
    """
    Parses Structured Text source content and converts the resulting AST to XML.

    This function coordinates the grammar definition, parsing, and XML conversion.

    :param source_content: The full content of the ST source file(s) as a single string.
    :param comment_pattern: The pyPEG comment pattern (regex or recursive list) to use.
    :param pretty_print: If True, uses lxml to format the final XML output.
    :returns: The generated XML AST string.
    :raises SyntaxError: If the source content fails to parse against the grammar.
    :raises RuntimeError: If lxml is missing or fails during XML post-processing.
    """
    # 1. Prepare Source Input
    source_lines_iterable = StringLineSource(source_content)

    # 2. Parse the Source
    grammar_rule = grammar.iec_source_root

    ast = parse(
        grammar_rule, source_lines_iterable, skip_ws=True, skip_comments=comment_pattern
    )

    # 3. Convert AST to XML
    xml_output = '<?xml version="1.0"?>\n' + convert_ast_to_xml(ast)

    # 4. Pretty Print (Requires lxml)
    if pretty_print:
        try:
            # Use lxml for pretty printing
            xml_output = etree.tostring(
                etree.fromstring(xml_output.encode("utf-8")),
                pretty_print=True,
                encoding="utf-8",
            ).decode("utf-8")
        except etree.XMLSyntaxError as e:
            # If the XML is malformed before pretty printing, raise a runtime error
            raise RuntimeError(
                f"XML post-processing failed due to XML syntax error: {e}"
            ) from e

    return xml_output


def compile_to_ast(source_content: str, comment_pattern: CommentPattern) -> List[Any]:
    """
    Parses Structured Text source content and returns the raw Python AST list.

    :param source_content: The full content of the ST source file(s) as a string.
    :param comment_pattern: The pyPEG comment pattern (regex or recursive list) to use.
    :returns: The raw Python AST list.
    :raises SyntaxError: If the source content fails to parse against the grammar.
    """
    # 1. Prepare Source Input
    source_lines_iterable = StringLineSource(source_content)

    # 2. Parse the Source
    grammar_rule = grammar.iec_source

    ast = parse(
        grammar_rule, source_lines_iterable, skip_ws=True, skip_comments=comment_pattern
    )

    return ast


def compile_to_xml_with_analysis(
        source_content: str,
        comment_pattern: CommentPattern,
        pretty_print: bool = False,
        include_pdg: bool = True,
        include_invariants: bool = True,
) -> str:
    """Parse ST source and convert to XML with PDG and invariant analysis"""



    # 1. Parse the source
    source_lines_iterable = StringLineSource(source_content)
    grammar_rule = grammar.iec_source_root
    ast = parse(
        grammar_rule, source_lines_iterable,
        skip_ws=True, skip_comments=comment_pattern
    )

    # 2. Build PDGs if requested
    pdgs = None
    state_variable = None
    if include_pdg:
        try:
            pdgs, state_variable = pdg_module.build_all_pdgs(ast)
        except Exception as e:
            print(f"DEBUG: ERROR building PDGs: {e}")
            traceback.print_exc()

    # 3. Extract invariants if requested
    invariants = None
    if include_invariants and pdgs:
        try:
            invariants = inv_module.extract_invariants_from_all_pdgs(pdgs, state_variable)  # UPDATED
        except Exception as e:
            print(f"DEBUG: ERROR extracting invariants: {e}")
            traceback.print_exc()

    # 4. Convert to XML
    xml_output = convert_ast_to_xml_with_invariants_and_summary(
        ast, pdgs, invariants, include_summary=True
    )

    # 5. Pretty print if requested
    if pretty_print:
        try:
            xml_output = etree.tostring(
                etree.fromstring(xml_output.encode("utf-8")),
                pretty_print=True,
                encoding="utf-8",
            ).decode("utf-8")
        except etree.XMLSyntaxError as e:
            raise RuntimeError(
                f"XML post-processing failed: {e}"
            ) from e

    return xml_output