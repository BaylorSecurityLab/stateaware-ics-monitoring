import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from .pdg import (
    ProgramDependencyGraph,
    PDGNode,
    VariableType
)


@dataclass
class InvariantTemplate:
    """Base class for invariant templates"""
    id: str
    type: str  # "single", "multi", or "inter"
    state_id: str
    variables: List[str]
    structure: str  # Human-readable template structure
    confidence: float = 1.0  # Confidence score

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON/XML export"""
        return {
            "id": self.id,
            "type": self.type,
            "state_id": self.state_id,
            "variables": self.variables,
            "structure": self.structure,
            "confidence": self.confidence
        }


@dataclass
class SingleVariableInvariant(InvariantTemplate):
    """
    Single-variable invariant template

    Example: H_Sensor in range [#, #] -> H_Actuator = TRUE

    The bounds (#) are unresolved and will be filled by trace mining.
    """
    sensing_var: str = ""
    sensing_var_type: VariableType = VariableType.SENSING
    actuation_var: str = ""
    operator: str = ""  # "=", "<", "<=", ">", ">=", "<>"
    actuation_value: Optional[str] = None  # TRUE, FALSE, or numeric value

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "sensing_var": self.sensing_var,
            "sensing_var_type": self.sensing_var_type.value,
            "actuation_var": self.actuation_var,
            "operator": self.operator,
            "actuation_value": self.actuation_value
        })
        return base


@dataclass
class MultiVariableInvariant(InvariantTemplate):
    """
    Multi-variable invariant template

    Example: IF H_Sensor <= (H_Target + H_Offset) THEN H_Actuator := FALSE

    Structure: sensing + configuration -> actuation
    """
    sensing_vars: List[str] = field(default_factory=list)
    configuration_vars: List[str] = field(default_factory=list)
    actuation_var: str = ""
    condition: str = ""  # The parsed condition
    action: str = ""  # The actuation action
    condition_ast: Optional[Any] = None  # Original AST for condition

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "sensing_vars": self.sensing_vars,
            "configuration_vars": self.configuration_vars,
            "actuation_var": self.actuation_var,
            "condition": self.condition,
            "action": self.action
        })
        return base


@dataclass
class InterStateInvariant(InvariantTemplate):
    """
    Interstate invariant template

    Example: IF H_Sensor in [890,910] AND R_Sensor in [695,705]
             AND H_Actuator=FALSE AND R_Actuator=FALSE
             THEN StateVar := 210

    Defines conditions required for a valid state transition
    """
    source_state: str = ""  # Current state
    dest_state: str = ""  # Target state (value assigned to state variable)
    transition_condition: str = ""  # Condition that must be true
    state_variable: str = ""  # Name of the state variable (e.g., "li_StepCase")
    condition_variables: List[str] = field(default_factory=list)  # All variables in condition

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "source_state": self.source_state,
            "dest_state": self.dest_state,
            "transition_condition": self.transition_condition,
            "state_variable": self.state_variable,
            "condition_variables": self.condition_variables
        })
        return base

class InvariantExtractor:
    """Extracts invariant templates from Program Dependency Graphs"""

    def __init__(self, pdg: ProgramDependencyGraph, state_variable: Optional[str] = None):
        self.pdg = pdg
        self.state_id = pdg.state_id
        self.state_variable = state_variable

    def extract_all_templates(self) -> List[InvariantTemplate]:
        """
        Extract all invariant templates (single, multi-variable, and interstate) from the PDG

        Returns:
            List of InvariantTemplate objects
        """
        invariants = []

        # 1. Extract state-based invariants (unconditional assignments)
        state_invs = self._extract_state_invariants()
        invariants.extend(state_invs)

        # 2. Extract interstate invariants (transitions)
        if self.state_variable:
            inter_invs = self._extract_inter_state_invariants()
            invariants.extend(inter_invs)

        # 3. Extract condition-based invariants (Actuation Logic)
        actuation_nodes = self._find_actuation_nodes()

        for act_node_id in actuation_nodes:
            act_node = self.pdg.nodes[act_node_id]
            
            # Skip if this is an assignment to the state variable (handled in step 2)
            if self.state_variable and self.state_variable in act_node.variables_written:
                continue

            # Get the actuation variable being written
            if not act_node.variables_written:
                continue

            act_var = list(act_node.variables_written)[0]

            # Extract single-variable invariants
            single_invs = self._extract_single_variable_invariants(act_node_id, act_var)
            invariants.extend(single_invs)

            # Extract multi-variable invariant
            multi_inv = self._extract_multi_variable_invariant(act_node_id, act_var)
            if multi_inv:
                invariants.append(multi_inv)

        return invariants

    def _extract_inter_state_invariants(self) -> List[InterStateInvariant]:
        """
        Finds assignments to the state_variable to identify transitions.
        """
        invariants = []

        # Find all nodes writing to the state variable
        transition_nodes = []
        for node_id, node in self.pdg.nodes.items():
            if self.state_variable in node.variables_written:
                transition_nodes.append(node_id)

        for node_id in transition_nodes:
            node = self.pdg.nodes[node_id]

            # Extract the target state (the value assigned)
            target_state = self._extract_actuation_value(node)
            if not target_state:
                continue

            # Extract the condition (Guard) - UPGRADED LOGIC
            condition_parts = []
            cond_vars = set()  # Use set to avoid duplicates

            current_node_id = node_id

            # Walk up the control dependency chain to find ALL nested conditions
            while True:
                control_preds = self.pdg.get_predecessors(current_node_id, edge_type="control")

                if not control_preds:
                    break

                # Get the immediate control parent (e.g., the "IF" statement)
                parent_id = control_preds[0]
                parent_node = self.pdg.nodes[parent_id]

                # Extract that specific condition
                part_expr = self._extract_condition_expression(parent_node)
                if part_expr:
                    condition_parts.insert(0, f"({part_expr})")

                # Collect variables from this condition
                cond_vars.update(parent_node.variables_read)

                # Move up to the parent to check for its parent (nested IFs)
                current_node_id = parent_id

            # Combine all parts with AND
            if condition_parts:
                condition_str = " AND ".join(condition_parts)
            else:
                condition_str = "TRUE"

            # Convert set back to list for the template
            cond_vars_list = list(cond_vars)

            # Create the invariant
            inv = InterStateInvariant(
                id=f"inter_{self.state_id}_to_{target_state}",
                type="inter",
                state_id=self.state_id,
                variables=[self.state_variable] + cond_vars_list,
                structure=f"IF {condition_str} THEN {self.state_variable} := {target_state}",
                source_state=self.state_id,
                dest_state=target_state,
                transition_condition=condition_str,
                state_variable=self.state_variable,
                condition_variables=cond_vars_list
            )
            invariants.append(inv)

        return invariants

    def _find_actuation_nodes(self) -> List[int]:
        """
        Find all nodes that write to actuation variables

        Returns:
            List of node IDs
        """
        actuation_nodes = []

        for node_id, node in self.pdg.nodes.items():
            for var in node.variables_written:
                if var in self.pdg.variables:
                    if self.pdg.variables[var].var_type == VariableType.ACTUATION:
                        actuation_nodes.append(node_id)
                        break

        return actuation_nodes

    def _extract_single_variable_invariants(self, act_node_id: int,
                                            act_var: str) -> List[SingleVariableInvariant]:
        """
        Extract single-variable invariants for an actuation node

        Example: H_Sensor <= [#] -> H_Actuator = FALSE

        Args:
            act_node_id: ID of the actuation node
            act_var: Actuation variable name

        Returns:
            List of SingleVariableInvariant templates
        """
        invariants = []
        act_node = self.pdg.nodes[act_node_id]

        # Get the actuation value (what the actuation is set to)
        actuation_value = self._extract_actuation_value(act_node)

        # Trace back through control dependencies to find conditions
        control_predecessors = self.pdg.get_predecessors(act_node_id, edge_type="control")

        for cond_node_id in control_predecessors:
            cond_node = self.pdg.nodes[cond_node_id]

            # Check if this is a condition node
            if cond_node.statement_type != "condition":
                continue

            # Extract sensing variables from the condition
            for var in cond_node.variables_read:
                if var not in self.pdg.variables:
                    continue

                var_obj = self.pdg.variables[var]

                # Only create invariants for sensing variables
                if var_obj.var_type == VariableType.SENSING:
                    # Extract the operator from the condition
                    operator = self._extract_operator_for_variable(cond_node, var)

                    if operator:
                        inv = SingleVariableInvariant(
                            id=f"single_{self.state_id}_{var}_{act_var}",
                            type="single",
                            state_id=self.state_id,
                            variables=[var, act_var],
                            structure=f"IF {var} {operator} [#] THEN {act_var} = {actuation_value}",
                            sensing_var=var,
                            sensing_var_type=var_obj.var_type,
                            actuation_var=act_var,
                            operator=operator,
                            actuation_value=actuation_value
                        )
                        invariants.append(inv)

        return invariants

    def _extract_multi_variable_invariant(self, act_node_id: int,
                                          act_var: str) -> Optional[MultiVariableInvariant]:
        """
        Extract multi-variable invariant for an actuation node

        Example: IF H_Sensor <= (H_Target + H_Offset) THEN H_Actuator := FALSE

        Args:
            act_node_id: ID of the actuation node
            act_var: Actuation variable name

        Returns:
            MultiVariableInvariant template or None
        """
        act_node = self.pdg.nodes[act_node_id]

        # Find all variables that influence this actuation through both
        # control and data dependencies
        sensing_vars = []
        config_vars = []

        # DFS backward through the PDG to find all influencing variables
        visited = set()
        to_visit = [act_node_id]

        while to_visit:
            node_id = to_visit.pop()
            if node_id in visited:
                continue
            visited.add(node_id)

            node = self.pdg.nodes[node_id]

            # Collect variables by type
            for var in node.variables_read:
                if var not in self.pdg.variables:
                    continue

                var_obj = self.pdg.variables[var]

                if var_obj.var_type == VariableType.SENSING:
                    if var not in sensing_vars:
                        sensing_vars.append(var)
                elif var_obj.var_type == VariableType.CONFIGURATION:
                    if var not in config_vars:
                        config_vars.append(var)

            # Continue traversal backward through edges
            predecessors = self.pdg.get_predecessors(node_id)
            to_visit.extend(predecessors)

        # Only create invariant if we found sensing or configuration variables
        if not sensing_vars and not config_vars:
            return None

        # Extract the condition from the controlling condition node
        condition_str = ""
        condition_ast = None
        control_predecessors = self.pdg.get_predecessors(act_node_id, edge_type="control")

        if control_predecessors:
            cond_node = self.pdg.nodes[control_predecessors[0]]
            condition_str = self._extract_condition_expression(cond_node)
            condition_ast = cond_node.ast_node

        # Extract the action
        action_str = self._format_assignment(act_node)

        # Build structure string
        all_vars = sensing_vars + config_vars
        structure = f"IF {condition_str} THEN {action_str}"

        return MultiVariableInvariant(
            id=f"multi_{self.state_id}_{act_var}",
            type="multi",
            state_id=self.state_id,
            variables=all_vars + [act_var],
            structure=structure,
            sensing_vars=sensing_vars,
            configuration_vars=config_vars,
            actuation_var=act_var,
            condition=condition_str,
            action=action_str,
            condition_ast=condition_ast
        )

    def _extract_state_invariants(self) -> List[InvariantTemplate]:
        """
        Extract state-based invariants (unconditional assignments in the state)

        These are assignments that happen at the start of a state without conditions.
        Example: In State 10, PU1_Command = FALSE
        """
        invariants = []

        # Find actuation assignments without control dependencies
        for node_id, node in self.pdg.nodes.items():
            if node.statement_type != "assignment":
                continue
            
            # Skip if this is an assignment to the state variable (handled separately)
            if self.state_variable and self.state_variable in node.variables_written:
                continue

            # Check if this writes to an actuation variable
            for var in node.variables_written:
                if var not in self.pdg.variables:
                    continue

                if self.pdg.variables[var].var_type == VariableType.ACTUATION:
                    # Check if this node has NO control predecessors
                    control_preds = self.pdg.get_predecessors(node_id, edge_type="control")

                    if not control_preds:
                        # This is an unconditional actuation assignment
                        # Extract the value
                        value = self._extract_actuation_value(node)

                        inv = SingleVariableInvariant(
                            id=f"state_{self.state_id}_{var}",
                            type="single",
                            state_id=self.state_id,
                            variables=[var],
                            structure=f"In State {self.state_id}, {var} = {value}",
                            sensing_var="STATE",  # Special marker
                            sensing_var_type=VariableType.INTERNAL,
                            actuation_var=var,
                            operator="=",
                            actuation_value=value
                        )
                        invariants.append(inv)

        return invariants

    @staticmethod
    def _extract_operator_for_variable(cond_node: PDGNode, var: str) -> Optional[str]:
        """
        Extract the comparison operator using AST traversal.
        This finds the specific comparison operation that governs the given variable.
        """
        if not cond_node.ast_node:
            return None

        # Map AST node types
        operator_map = {
            'less_or_equal': '<=',
            'greater_or_equal': '>=',
            'less_than': '<',
            'greater_than': '>',
            'equals': '=',
            'not_equal': '<>',
        }

        found_operator = None

        def traverse(node):
            nonlocal found_operator
            if found_operator: return  # Stop if found

            if isinstance(node, tuple) and len(node) > 0:
                node_type = node[0]

                # If this node is a comparison operator
                if node_type in operator_map:
                    # Check if the variable exists somewhere in this comparison's operands
                    if _contains_variable(node, var):
                        found_operator = operator_map[node_type]
                        return

                # Recurse children
                for child in node[1:]:
                    traverse(child)

            elif isinstance(node, list):
                for item in node:
                    traverse(item)

        # Helper to check if a subtree contains the specific variable text
        def _contains_variable(node, search_var):
            if isinstance(node, str):
                return node == search_var

            if isinstance(node, tuple):
                # Check if this specific node is the variable
                if node[0] == 'variable_name':
                    # Extract the name
                    for child in node[1:]:
                        if isinstance(child, str) and child == search_var:
                            return True
                        if isinstance(child, list):  # deep nested text
                            for item in child:
                                if isinstance(item, str) and item == search_var:
                                    return True

                # Recurse
                for child in node[1:]:
                    if _contains_variable(child, search_var): return True

            elif isinstance(node, list):
                for item in node:
                    if _contains_variable(item, search_var): return True

            return False

        # Start search
        traverse(cond_node.ast_node)
        return found_operator

    @staticmethod
    def _extract_condition_expression(cond_node: PDGNode) -> str:
        """
        Extract the full condition expression from a condition node

        Args:
            cond_node: Condition node

        Returns:
            Condition expression string
        """
        statement = cond_node.statement

        # Remove "IF" prefix if present
        if statement.startswith("IF "):
            return statement[3:].strip()
        elif statement.startswith("ELSIF "):
            return statement[6:].strip()

        return statement

    @staticmethod
    def _extract_actuation_value(act_node: PDGNode) -> Optional[str]:
        """
        Extract the value assigned to the actuation variable

        Args:
            act_node: Actuation assignment node

        Returns:
            Value string (e.g., "TRUE", "FALSE", "100")
        """
        statement = act_node.statement

        # Parse assignment: "var := value"
        match = re.search(r':=\s*(.+?)(?:;|$)', statement)
        if match:
            return match.group(1).strip()

        return None

    @staticmethod
    def _format_assignment(node: PDGNode) -> str:
        """Format an assignment node as a string"""
        return node.statement.replace(";", "").strip()



def extract_invariants_from_pdg(pdg: ProgramDependencyGraph, state_variable: Optional[str] = None) -> List[InvariantTemplate]:
    """
    High-level API to extract invariant templates from a PDG

    Args:
        pdg: Program Dependency Graph for a single state
        state_variable: The name of the state variable (optional)

    Returns:
        List of InvariantTemplate objects
    """
    extractor = InvariantExtractor(pdg, state_variable)
    return extractor.extract_all_templates()


def extract_invariants_from_all_pdgs(pdgs: Dict[str, ProgramDependencyGraph], state_variable: Optional[str] = None) -> Dict[str, List[InvariantTemplate]]:
    """
    Extract invariant templates from multiple PDGs (all states)

    Args:
        pdgs: Dictionary mapping state_id -> ProgramDependencyGraph
        state_variable: The name of the state variable (optional)

    Returns:
        Dictionary mapping state_id -> List[InvariantTemplate]
    """
    invariants_by_state = {}

    for state_id, pdg in pdgs.items():
        invariants = extract_invariants_from_pdg(pdg, state_variable)
        invariants_by_state[state_id] = invariants

    return invariants_by_state
