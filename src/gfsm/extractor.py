"""Parsed XML -> LocalFSM. Faithful port of src/fsm/extractor.rs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .model import FunctionBlock, GfsmError, LocalFSM, Metadata, State, Transition
from .xml_parser import FunctionBlockData, XmlParser


class FsmExtractor:
    def __init__(self, parser: XmlParser, source_path: str) -> None:
        self._parser = parser
        self._source_path = source_path

    @classmethod
    def from_path(cls, xml_path: Path) -> "FsmExtractor":
        p = Path(xml_path)
        return cls(XmlParser.from_path(p), str(p))

    def extract(self) -> LocalFSM:
        names = self._parser.find_function_blocks()
        if not names:
            raise GfsmError("No function blocks found in XML")

        function_blocks: list[FunctionBlock] = []
        total_states = 0
        total_transitions = 0

        for name in names:
            try:
                fb_data_list = self._parser.extract_function_blocks(name)
            except GfsmError:
                continue  # Rust `if let Ok(...)` — skip on error.
            for fb_data in fb_data_list:
                try:
                    fb = self._build_function_block(fb_data)
                except GfsmError:
                    continue
                if fb.state_count() > 0 or fb.transition_count() > 0:
                    total_states += fb.state_count()
                    total_transitions += fb.transition_count()
                    function_blocks.append(fb)

        metadata = Metadata(
            source_file=self._source_path,
            extraction_date=datetime.now(timezone.utc).isoformat(),
            total_states=total_states,
            total_transitions=total_transitions,
        )
        return LocalFSM(function_blocks=function_blocks, metadata=metadata)

    def _build_function_block(self, fb_data: FunctionBlockData) -> FunctionBlock:
        # Identity is the actuator CASE selector — unique within a PLC and
        # stable across runs, so compose._ordered_components sorts
        # per-actuator deterministically.
        fb = FunctionBlock.new(fb_data.case_variable, fb_data.case_variable)

        # First pass: create all states.
        for element in fb_data.case_elements:
            fb.add_state(State.new(element.state_id))

        # Second pass: extract transitions.
        for element in fb_data.case_elements:
            current_state = element.state_id
            if not element.if_statements:
                continue
            for if_stmt in element.if_statements:
                for assignment in if_stmt.assignments:
                    if assignment.variable == fb_data.case_variable:
                        next_state = assignment.value
                        condition = (
                            "No Check"
                            if if_stmt.condition == ""
                            else if_stmt.condition
                        )
                        transition = Transition.new(
                            current_state, next_state, condition
                        )
                        if next_state not in fb.states:
                            fb.add_state(State.new(next_state))
                        fb.add_transition(transition)
        return fb
