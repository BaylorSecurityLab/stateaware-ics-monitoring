"""AST-XML -> raw parsed structures. Faithful port of src/xml_parser.rs.

roxmltree -> lxml.etree mapping:
- Document::parse        -> etree.fromstring(bytes)
- node.descendants()     -> elem.iter()  (self first, then doc-order)
- node.tag_name().name() -> elem.tag     (no namespaces in AST files)
- node.text()            -> elem.text    (Optional[str])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from .model import GfsmError


@dataclass
class Assignment:
    variable: str
    value: str


@dataclass
class IfStatement:
    condition: str
    assignments: list[Assignment] = field(default_factory=list)


@dataclass
class CaseElement:
    state_id: str
    if_statements: list[IfStatement] = field(default_factory=list)


@dataclass
class FunctionBlockData:
    name: str
    case_variable: str
    case_elements: list[CaseElement] = field(default_factory=list)


def _first(root: etree._Element, tag: str) -> etree._Element | None:
    """First descendant (incl. root) whose tag == `tag`, document order.

    Mirrors roxmltree `node.descendants().find(|n| n.tag_name().name()==tag)`.
    """
    for el in root.iter():
        if el.tag == tag:
            return el
    return None


def _text(el: etree._Element | None) -> str | None:
    return None if el is None else el.text


def _preprocess(content: str) -> str:
    """Faithful port of xml_parser.rs:16-18 — opening-tag-only rewrite.

    Rust rewrites ONLY the opening pair `<expression><integer-literal>` /
    `<expression><boolean-literal>` to `<value>...`; the matching
    `</expression>` close tag is deliberately left unchanged (Rust does the
    same). On the real, pretty-printed AST these adjacent substrings never
    occur, so this is a no-op there — byte-for-byte matching Rust. Do NOT
    add a closing-tag rewrite; that would diverge from the Rust port.
    """
    return content.replace(
        "<expression><integer-literal>", "<value><integer-literal>"
    ).replace(
        "<expression><boolean-literal>", "<value><boolean-literal>"
    )


class XmlParser:
    def __init__(self, content: str) -> None:
        # xml_parser.rs:16-18 — raw string replace BEFORE parsing.
        content = _preprocess(content)
        self._content = content
        try:
            self._root = etree.fromstring(content.encode("utf-8"))
        except etree.XMLSyntaxError as exc:
            raise GfsmError(f"XML parsing error: {exc}") from exc

    @classmethod
    def from_path(cls, xml_path: Path) -> "XmlParser":
        return cls(Path(xml_path).read_text())

    def find_function_blocks(self) -> list[str]:
        blocks: list[str] = []
        for node in self._root.iter():
            if node.tag == "function-block-declaration":
                name = _text(_first(node, "derived-function-block-name"))
                if name is not None:
                    blocks.append(name)
            elif node.tag == "program-declaration":
                name = _text(_first(node, "program-type-name"))
                if name is not None:
                    blocks.append(name)
        return blocks

    def _find_block_node(self, name: str) -> etree._Element | None:
        for node in self._root.iter():
            if node.tag == "function-block-declaration":
                cur = _text(_first(node, "derived-function-block-name"))
            elif node.tag == "program-declaration":
                cur = _text(_first(node, "program-type-name"))
            else:
                cur = None
            if cur is not None and cur == name:
                return node
        return None

    def extract_function_block(self, name: str) -> FunctionBlockData:
        # Implemented incrementally in B2/B3/B4; raises until then.
        raise NotImplementedError
