import pytest

from gfsm.model import GfsmError
from gfsm.xml_parser import XmlParser

PROGRAM_XML = """<iec-source>
  <program-declaration>
    <program-type-name>PLC1</program-type-name>
    <function-block-body><statement-list>
      <case-statement>
        <expression><variable-name>P78_State</variable-name></expression>
        <case-element>
          <case-list><case-list-element>
            <integer-literal>0</integer-literal>
          </case-list-element></case-list>
          <statement-list>
            <if-statement>
              <expression>
                <variable-name>T41</variable-name>
                <less-than/>
                <integer-literal>5</integer-literal>
              </expression>
              <statement-list>
                <assignment-statement>
                  <variable-name>P78_State</variable-name>
                  <expression><integer-literal>1</integer-literal></expression>
                </assignment-statement>
              </statement-list>
            </if-statement>
          </statement-list>
        </case-element>
      </case-statement>
    </statement-list></function-block-body>
  </program-declaration>
</iec-source>"""

FB_XML = """<iec-source>
  <function-block-declaration>
    <derived-function-block-name>FB1</derived-function-block-name>
    <case-statement>
      <expression><variable-name>S</variable-name></expression>
      <case-element>
        <case-list><case-list-element>
          <integer-literal>10</integer-literal>
        </case-list-element></case-list>
      </case-element>
    </case-statement>
  </function-block-declaration>
</iec-source>"""


def test_find_program_declaration():
    p = XmlParser(PROGRAM_XML)
    assert p.find_function_blocks() == ["PLC1"]


def test_find_function_block_declaration():
    p = XmlParser(FB_XML)
    assert p.find_function_blocks() == ["FB1"]


def test_preprocessing_rewrites_literal_expression():
    p = XmlParser(PROGRAM_XML)
    # The assignment value <expression><integer-literal>1 became
    # <value><integer-literal>1 after preprocessing.
    assert "<value><integer-literal>1" in p._content
    # The case variable <expression><variable-name> is untouched.
    assert "<expression><variable-name>P78_State" in p._content


def test_malformed_xml_raises_gfsmerror():
    with pytest.raises(GfsmError):
        XmlParser("<iec-source><unclosed>")
