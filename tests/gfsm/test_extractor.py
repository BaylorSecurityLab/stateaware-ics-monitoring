import pytest

from gfsm.extractor import FsmExtractor
from gfsm.model import GfsmError
from gfsm.xml_parser import XmlParser

TWO_STATE = """<iec-source><function-block-declaration>
  <derived-function-block-name>FB</derived-function-block-name>
  <case-statement>
    <expression>
      <variable-name>S</variable-name>
    </expression>
    <case-element>
      <case-list><case-list-element>
        <integer-literal>10</integer-literal>
      </case-list-element></case-list>
      <statement-list><if-statement>
        <expression>
          <variable-name>T</variable-name>
          <less-than/>
          <integer-literal>5</integer-literal>
        </expression>
        <statement-list><assignment-statement>
          <variable-name>S</variable-name>
          <expression>
            <integer-literal>20</integer-literal>
          </expression>
        </assignment-statement></statement-list>
      </if-statement></statement-list>
    </case-element>
    <case-element>
      <case-list><case-list-element>
        <integer-literal>20</integer-literal>
      </case-list-element></case-list>
      <statement-list></statement-list>
    </case-element>
  </case-statement>
</function-block-declaration></iec-source>"""

NO_CHECK = """<iec-source><function-block-declaration>
  <derived-function-block-name>FB</derived-function-block-name>
  <case-statement>
    <expression>
      <variable-name>S</variable-name>
    </expression>
    <case-element>
      <case-list><case-list-element>
        <integer-literal>10</integer-literal>
      </case-list-element></case-list>
      <statement-list><if-statement>
        <statement-list><assignment-statement>
          <variable-name>S</variable-name>
          <value>
            <integer-literal>20</integer-literal>
          </value>
        </assignment-statement></statement-list>
      </if-statement></statement-list>
    </case-element>
    <case-element>
      <case-list><case-list-element>
        <integer-literal>20</integer-literal>
      </case-list-element></case-list>
      <statement-list></statement-list>
    </case-element>
  </case-statement>
</function-block-declaration></iec-source>"""

AUTO_CREATE = """<iec-source><function-block-declaration>
  <derived-function-block-name>FB</derived-function-block-name>
  <case-statement>
    <expression>
      <variable-name>S</variable-name>
    </expression>
    <case-element>
      <case-list><case-list-element>
        <integer-literal>10</integer-literal>
      </case-list-element></case-list>
      <statement-list><if-statement>
        <expression>
          <variable-name>T</variable-name>
          <equal/>
          <integer-literal>1</integer-literal>
        </expression>
        <statement-list><assignment-statement>
          <variable-name>S</variable-name>
          <expression>
            <integer-literal>99</integer-literal>
          </expression>
        </assignment-statement></statement-list>
      </if-statement></statement-list>
    </case-element>
  </case-statement>
</function-block-declaration></iec-source>"""


def test_extract_states_and_transition():
    fsm = FsmExtractor(XmlParser(TWO_STATE), "mem.xml").extract()
    fb = fsm.function_blocks[0]
    assert fb.name == "FB"
    assert fb.case_variable == "S"
    assert list(fb.states.keys()) == ["10", "20"]
    assert len(fb.transitions) == 1
    t = fb.transitions[0]
    assert (t.from_state, t.to_state, t.condition) == ("10", "20", "T < 5")
    assert t.id == "10_to_20"
    assert fsm.metadata.total_states == 2
    assert fsm.metadata.total_transitions == 1
    assert fsm.metadata.source_file == "mem.xml"


def test_empty_condition_becomes_no_check():
    fsm = FsmExtractor(XmlParser(NO_CHECK), "m.xml").extract()
    assert fsm.function_blocks[0].transitions[0].condition == "No Check"


def test_missing_target_state_auto_created():
    fsm = FsmExtractor(XmlParser(AUTO_CREATE), "m.xml").extract()
    fb = fsm.function_blocks[0]
    assert list(fb.states.keys()) == ["10", "99"]
    assert fb.states["99"].transitions_in == ["10_to_99"]


def test_no_function_blocks_raises():
    p = XmlParser("<iec-source></iec-source>")
    with pytest.raises(GfsmError, match="No function blocks"):
        FsmExtractor(p, "m.xml").extract()


def test_empty_block_dropped():
    xml = ("<iec-source><function-block-declaration>"
           "<derived-function-block-name>FB</derived-function-block-name>"
           "<case-statement><expression><variable-name>S</variable-name>"
           "</expression></case-statement>"
           "</function-block-declaration></iec-source>")
    fsm = FsmExtractor(XmlParser(xml), "m.xml").extract()
    assert fsm.function_blocks == []
