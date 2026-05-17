"""
pdg.py - Program Dependency Graph Construction for IEC 61131-3 Structured Text

This module builds Program Dependency Graphs (PDGs) from parsed AST to support
invariant template extraction for the SAIN (State-Aware Invariants) approach.

Key Components:
- Variable classification (sensing, configuration, actuation)
- Control dependency analysis
- Data dependency analysis (use-def chains)
- PDG construction per state (case element)
"""

from dataclasses import dataclass, field
from typing import Set, Dict, List, Optional, Tuple, Any
from enum import Enum
import re


# ============================================================================
# DATA STRUCTURES
# ============================================================================


class VariableType(Enum):
    """Classification of PLC variables based on their role"""
    SENSING = "sensing"  # Input from sensors (e.g., H_Sensor, L_T1)
    CONFIGURATION = "configuration"  # Parameters (e.g., H_Target, PU1_LowLevel)
    ACTUATION = "actuation"  # Output to actuators (e.g., H_Actuator, PU1_Command)
    INTERNAL = "internal"  # Internal state/logic variables


@dataclass
class Variable:
    """Represents a PLC program variable with its classification"""
    name: str
    var_type: VariableType
    data_type: str  # BOOL, REAL, INT, etc.
    scope: str  # "input", "output", "var", "var_temp"
    initial_value: Optional[str] = None

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if not isinstance(other, Variable):
            return False
        return self.name == other.name


@dataclass
class PDGNode:
    """Represents a statement node in the Program Dependency Graph"""
    id: int
    statement: str  # Human-readable statement
    statement_type: str  # "assignment", "condition", "if_block"
    variables_read: Set[str] = field(default_factory=set)
    variables_written: Set[str] = field(default_factory=set)
    ast_node: Optional[Any] = None  # Reference to original AST node
    line_number: Optional[int] = None

    def __hash__(self):
        return hash(self.id)


@dataclass
class PDGEdge:
    """Represents a dependency edge in the PDG"""
    from_node: int
    to_node: int
    edge_type: str  # "control" or "data"
    variable: Optional[str] = None  # For data edges, which variable creates dependency
    label: Optional[str] = None  # Human-readable label


class ProgramDependencyGraph:
    """Complete Program Dependency Graph for a single state"""

    def __init__(self, state_id: str):
        self.state_id = state_id
        self.nodes: Dict[int, PDGNode] = {}
        self.edges: List[PDGEdge] = []
        self.variables: Dict[str, Variable] = {}
        self.next_node_id: int = 0

    def add_node(self, node: PDGNode) -> int:
        """Add a node to the PDG and return its ID"""
        self.nodes[node.id] = node
        return node.id

    def add_edge(self, edge: PDGEdge):
        """Add an edge to the PDG"""
        self.edges.append(edge)

    def create_node(self, statement: str, stmt_type: str,
                    reads: Set[str] = None, writes: Set[str] = None,
                    ast_node: Any = None) -> PDGNode:
        """Factory method to create and add a node"""
        node = PDGNode(
            id=self.next_node_id,
            statement=statement,
            statement_type=stmt_type,
            variables_read=reads or set(),
            variables_written=writes or set(),
            ast_node=ast_node
        )
        self.next_node_id += 1
        self.add_node(node)
        return node

    def get_predecessors(self, node_id: int, edge_type: Optional[str] = None) -> List[int]:
        """Get all predecessor nodes (nodes with edges pointing to this node)"""
        predecessors = []
        for edge in self.edges:
            if edge.to_node == node_id:
                if edge_type is None or edge.edge_type == edge_type:
                    predecessors.append(edge.from_node)
        return predecessors

    def get_successors(self, node_id: int, edge_type: Optional[str] = None) -> List[int]:
        """Get all successor nodes (nodes this node points to)"""
        successors = []
        for edge in self.edges:
            if edge.from_node == node_id:
                if edge_type is None or edge.edge_type == edge_type:
                    successors.append(edge.to_node)
        return successors

    def find_defining_node(self, variable: str, before_node: Optional[int] = None) -> Optional[int]:
        """Find the most recent node that defines (writes to) a variable"""
        # Search backwards from before_node
        candidates = []
        for node_id, node in self.nodes.items():
            if before_node is not None and node_id >= before_node:
                continue
            if variable in node.variables_written:
                candidates.append(node_id)

        # Return the most recent (highest ID)
        return max(candidates) if candidates else None

    def to_dict(self) -> dict:
        """Serialize PDG to dictionary for JSON/XML export"""
        return {
            "state_id": self.state_id,
            "nodes": [
                {
                    "id": node.id,
                    "statement": node.statement,
                    "type": node.statement_type,
                    "reads": list(node.variables_read),
                    "writes": list(node.variables_written)
                }
                for node in self.nodes.values()
            ],
            "edges": [
                {
                    "from": edge.from_node,
                    "to": edge.to_node,
                    "type": edge.edge_type,
                    "variable": edge.variable,
                    "label": edge.label
                }
                for edge in self.edges
            ],
            "variables": {
                name: {
                    "type": var.var_type.value,
                    "data_type": var.data_type,
                    "scope": var.scope
                }
                for name, var in self.variables.items()
            }
        }


# ============================================================================
# VARIABLE CLASSIFICATION
# ============================================================================

class VariableClassifier:
    """Classifies PLC variables based on naming conventions and declaration context"""

    # Heuristic patterns for variable classification
    SENSING_PATTERNS = [
        r'.*sensor.*',
        r'.*_sensor$',
        r'.*input.*',
        r'^l_.*',  # Level variables (e.g., L_T1)
        r'.*level$',
        r'.*position$',
        r'.*_actual.*',  # Actual readings (e.g., H_ActualPositioning)
        r'.*reading$',
        r'.*detected$'
    ]

    ACTUATION_PATTERNS = [
        r'^s_.*',  # Signal variables (e.g., S_PU1)
        r'.*actuator.*',
        r'.*_actuator$',
        r'.*command$',
        r'.*_command$',
        r'.*output$',
        r'.*_start.*',  # Start signals (e.g., H_StartPositioning)
        r'.*motor$',
        r'.*valve$',
        r'.*pump$'
    ]

    CONFIGURATION_PATTERNS = [
        r'.*target.*',
        r'.*_target$',
        r'.*level$',  # Threshold levels (e.g., PU1_LowLevel)
        r'.*threshold$',
        r'.*offset$',
        r'.*_offset$',
        r'.*limit$',
        r'.*setpoint$',
        r'.*tolerance$',
        r'.*tol$'
    ]

    @classmethod
    def classify_variable(cls, var_name: str, scope: str) -> VariableType:
        """
        Classify a variable based on its name, scope, and type

        Args:
            var_name: Variable name (e.g., "H_Sensor", "PU1_Command")
            scope: Declaration scope ("input", "output", "var")

        Returns:
            Classified VariableType
        """
        var_lower = var_name.lower()

        # Scope-based classification (strong signal)
        if scope == "input":
            # Most inputs are sensing, unless they're clearly configuration
            if cls._matches_patterns(var_lower, cls.CONFIGURATION_PATTERNS):
                return VariableType.CONFIGURATION
            return VariableType.SENSING

        if scope == "output":
            # Most outputs are actuation
            return VariableType.ACTUATION

        # For VAR section, use pattern matching
        if cls._matches_patterns(var_lower, cls.SENSING_PATTERNS):
            return VariableType.SENSING

        if cls._matches_patterns(var_lower, cls.ACTUATION_PATTERNS):
            return VariableType.ACTUATION

        if cls._matches_patterns(var_lower, cls.CONFIGURATION_PATTERNS):
            return VariableType.CONFIGURATION

        # Default to internal
        return VariableType.INTERNAL

    @staticmethod
    def _matches_patterns(text: str, patterns: List[str]) -> bool:
        """Check if text matches any regex pattern in the list"""
        return any(re.match(pattern, text, re.IGNORECASE) for pattern in patterns)


def extract_variables_from_ast(ast: Any) -> Dict[str, Variable]:
    """
    Extract and classify all variables from the program AST

    Args:
        ast: Parsed AST from iec_st_compiler

    Returns:
        Dictionary mapping variable names to Variable objects
    """
    variables = {}

    # Helper to extract variables from declarations
    def extract_from_decl_section(section_ast: Any, scope: str):
        if section_ast is None:
            return

        # Look for var-init-decl nodes
        for item in _iterate_ast_list(section_ast):

            if _is_node_type(item, 'var_init_decl'):
                var_name = _extract_variable_name(item)
                data_type = _extract_data_type(item)
                initial_value = _extract_initial_value(item)


                if var_name:
                    var_type = VariableClassifier.classify_variable(
                        var_name, scope
                    )

                    variables[var_name] = Variable(
                        name=var_name,
                        var_type=var_type,
                        data_type=data_type,
                        scope=scope,
                        initial_value=initial_value
                    )

    # Extract from different declaration sections
    input_nodes = _find_all_nodes(ast, 'input_declarations')
    for node in input_nodes:
        extract_from_decl_section(node, "input")

    output_nodes = _find_all_nodes(ast, 'output_declarations')
    for node in output_nodes:
        extract_from_decl_section(node, "output")

    var_nodes = _find_all_nodes(ast, 'var_declarations')

    for node in var_nodes:
        extract_from_decl_section(node, "var")

    return variables


class PDGBuilder:
    """Builds Program Dependency Graphs from case statement AST"""

    def __init__(self, variables: Dict[str, Variable]):
        self.variables = variables

    def build_pdg_for_state(self, state_id: str, case_element_ast: Any) -> ProgramDependencyGraph:
        """
        Build a complete PDG for a single case element (state)

        Args:
            state_id: State identifier (e.g., "10", "20")
            case_element_ast: AST node for the case-element

        Returns:
            Complete ProgramDependencyGraph with nodes and edges
        """
        pdg = ProgramDependencyGraph(state_id)
        pdg.variables = self.variables

        # Extract statement list from case element
        statement_list = self._extract_statement_list(case_element_ast)

        if not statement_list:
            return pdg

        # Step 1: Create nodes for all statements
        self._create_nodes_from_statements(pdg, statement_list)

        # Step 2: Add control dependencies
        self._add_control_dependencies(pdg)

        # Step 3: Add data dependencies
        self._add_data_dependencies(pdg)

        return pdg

    @staticmethod
    def _extract_statement_list(case_element_ast: Any) -> List[Any]:
        """Extract the statement-list from a case-element node"""
        # Look for statement-list child
        for item in _iterate_ast_list(case_element_ast):
            if _is_node_type(item, 'statement_list'):
                return _get_children(item)
        return []

    def _create_nodes_from_statements(self, pdg: ProgramDependencyGraph,
                                      statements: List[Any]):
        """
        Create PDG nodes from a list of statements

        Args:
            pdg: The PDG being built
            statements: List of statement AST nodes
        """
        for stmt in statements:
            if _is_node_type(stmt, 'assignment_statement'):
                self._create_assignment_node(pdg, stmt)

            elif _is_node_type(stmt, 'if_statement'):
                self._create_if_statement_nodes(pdg, stmt)

    def _create_assignment_node(self, pdg: ProgramDependencyGraph, stmt_ast: Any) -> PDGNode:
        """Create a node for an assignment statement"""
        # Extract LHS (variable being written)
        lhs_var = self._extract_assignment_lhs(stmt_ast)

        # Extract RHS (variables being read)
        rhs_vars = self._extract_expression_variables(stmt_ast)

        # Create human-readable statement
        statement_str = self._format_assignment_statement(stmt_ast, lhs_var)

        node = pdg.create_node(
            statement=statement_str,
            stmt_type="assignment",
            reads=rhs_vars,
            writes={lhs_var} if lhs_var else set(),
            ast_node=stmt_ast
        )

        return node

    def _create_if_statement_nodes(self, pdg: ProgramDependencyGraph,
                                   if_stmt_ast: Any) -> int:
        """
        Create nodes for an if-statement (condition + body)

        Returns:
            ID of the condition node
        """
        # Create condition node
        condition_vars = self._extract_condition_variables(if_stmt_ast)
        condition_str = self._format_condition(if_stmt_ast)

        condition_node = pdg.create_node(
            statement=f"IF {condition_str}",
            stmt_type="condition",
            reads=condition_vars,
            writes=set(),
            ast_node=if_stmt_ast
        )

        # Process THEN block statements
        then_statements = self._extract_then_statements(if_stmt_ast)
        then_start_id = pdg.next_node_id
        self._create_nodes_from_statements(pdg, then_statements)
        then_end_id = pdg.next_node_id - 1

        # Add control edges from condition to THEN block
        for node_id in range(then_start_id, then_end_id + 1):
            pdg.add_edge(PDGEdge(
                from_node=condition_node.id,
                to_node=node_id,
                edge_type="control",
                label="then"
            ))

        # Process ELSIF blocks if present
        elsif_conditions = self._extract_elsif_blocks(if_stmt_ast)
        for elsif_condition_ast, elsif_statements in elsif_conditions:
            elsif_vars = self._extract_condition_variables(elsif_condition_ast)
            elsif_str = self._format_condition_ast(elsif_condition_ast)

            elsif_node = pdg.create_node(
                statement=f"ELSIF {elsif_str}",
                stmt_type="condition",
                reads=elsif_vars,
                writes=set(),
                ast_node=elsif_condition_ast
            )

            elsif_start_id = pdg.next_node_id
            self._create_nodes_from_statements(pdg, elsif_statements)
            elsif_end_id = pdg.next_node_id - 1

            for node_id in range(elsif_start_id, elsif_end_id + 1):
                pdg.add_edge(PDGEdge(
                    from_node=elsif_node.id,
                    to_node=node_id,
                    edge_type="control",
                    label="elsif"
                ))

        # Process ELSE block if present
        else_statements = self._extract_else_statements(if_stmt_ast)
        if else_statements:
            else_start_id = pdg.next_node_id
            self._create_nodes_from_statements(pdg, else_statements)
            else_end_id = pdg.next_node_id - 1

            for node_id in range(else_start_id, else_end_id + 1):
                pdg.add_edge(PDGEdge(
                    from_node=condition_node.id,
                    to_node=node_id,
                    edge_type="control",
                    label="else"
                ))

        return condition_node.id

    @staticmethod
    def _add_control_dependencies(pdg: ProgramDependencyGraph):
        """
        Refine control dependency edges.

        During node creation, nested structures (like IF blocks) add edges from the
        condition to *all* nested nodes. This results in transitive dependencies
        (e.g., IF A -> IF B -> Stmt X results in edges A->X and B->X).

        This method prunes these transitive edges to ensure each node only depends
        on its immediate controller (the innermost predicate), forming a proper
        Control Dependence Graph.
        """
        # We iterate over all nodes in the PDG to prune edges
        for node_id in pdg.nodes:
            preds = pdg.get_predecessors(node_id, edge_type="control")
            if len(preds) <= 1:
                continue

            # Identify predecessors that are ancestors of other predecessors.
            # If P1 -> P2 exists (control edge) and both P1, P2 -> Node,
            # then P1 is the ancestor and should be removed for Node.
            to_remove = set()
            for p1 in preds:
                for p2 in preds:
                    if p1 == p2:
                        continue

                    # Check if p1 is a direct parent of p2
                    is_parent = False
                    for edge in pdg.edges:
                        if edge.from_node == p1 and edge.to_node == p2 and edge.edge_type == "control":
                            is_parent = True
                            break

                    if is_parent:
                        # p1 dominates p2, so p1's influence on current node is transitive via p2.
                        # We remove the direct edge p1 -> node to keep only the immediate parent.
                        to_remove.add(p1)

            # Remove the redundant edges
            if to_remove:
                new_edges = []
                for edge in pdg.edges:
                    # Keep edge if it's NOT one of the redundant ones targeting this node
                    if edge.to_node == node_id and edge.from_node in to_remove and edge.edge_type == "control":
                        continue
                    new_edges.append(edge)
                pdg.edges = new_edges


    @staticmethod
    def _add_data_dependencies(pdg: ProgramDependencyGraph):
        """
        Add data dependency edges based on use-def chains

        For each variable read in a node, add an edge from the most recent
        node that wrote to that variable.
        """
        # Build def-use chains
        last_def: Dict[str, int] = {}  # variable -> node_id of last definition

        # Process nodes in order
        for node_id in sorted(pdg.nodes.keys()):
            node = pdg.nodes[node_id]

            # For each variable read, add edge from its definition
            for var in node.variables_read:
                if var in last_def:
                    pdg.add_edge(PDGEdge(
                        from_node=last_def[var],
                        to_node=node_id,
                        edge_type="data",
                        variable=var,
                        label=f"def-use: {var}"
                    ))

            # Update definitions for variables written
            for var in node.variables_written:
                last_def[var] = node_id


    @staticmethod
    def _extract_assignment_lhs(assignment_ast: Any) -> Optional[str]:
        """Extract the left-hand side variable name from assignment"""
        for item in _iterate_ast_list(assignment_ast):
            if _is_node_type(item, 'variable_name'):
                return _extract_text(item)
        return None

    @staticmethod
    def _extract_expression_variables(expr_ast: Any) -> Set[str]:
        """Extract all variable names from an expression"""
        variables = set()

        def traverse(node):
            if _is_node_type(node, 'variable_name'):
                var_name = _extract_text(node)
                if var_name:
                    variables.add(var_name)

            # Recursively traverse children
            for child in _iterate_ast_list(node):
                traverse(child)

        traverse(expr_ast)
        return variables

    def _extract_condition_variables(self, if_stmt_ast: Any) -> Set[str]:
        """Extract variables from the condition of an if-statement"""
        # Find the first expression node (the condition)
        for item in _iterate_ast_list(if_stmt_ast):
            if _is_node_type(item, 'expression'):
                return self._extract_expression_variables(item)
        return set()

    @staticmethod
    def _extract_then_statements(if_stmt_ast: Any) -> List[Any]:
        """Extract statements from the THEN block"""
        # Find the first statement-list after the condition
        found_expression = False
        for item in _iterate_ast_list(if_stmt_ast):
            if _is_node_type(item, 'expression'):
                found_expression = True
            elif found_expression and _is_node_type(item, 'statement_list'):
                return _get_children(item)
        return []

    @staticmethod
    def _extract_elsif_blocks(if_stmt_ast: Any) -> List[Tuple[Any, List[Any]]]:
        """
        Extract ELSIF conditions and their statement blocks.

        This iterates through the AST children of the IF statement. Since the
        grammar defines ELSIF blocks sequentially (ELSIF -> expr -> THEN -> stmt_list),
        we use a state machine approach to capture pairs of (condition, statements).
        """
        elsif_blocks = []

        # Get all children of the IF statement node
        children = _get_children(if_stmt_ast)

        current_condition = None
        looking_for_condition = False
        looking_for_stmt = False

        for child in children:
            # Check if this child is the "ELSIF" keyword
            # This resets the state machine to look for a new block
            text = _extract_text(child)
            if text == "ELSIF":
                looking_for_condition = True
                looking_for_stmt = False
                current_condition = None
                continue

            # If we passed an ELSIF keyword, the next expression is the condition
            if looking_for_condition:
                if _is_node_type(child, 'expression'):
                    current_condition = child
                    looking_for_condition = False
                    looking_for_stmt = True
                    continue

            # If we have a condition, the next statement_list is the body
            if looking_for_stmt:
                if _is_node_type(child, 'statement_list'):
                    # We found a complete ELSIF block.
                    # statement_list node contains the actual statements as children.
                    stmts = _get_children(child)
                    if current_condition is not None:
                        elsif_blocks.append((current_condition, stmts))

                    # Reset state to wait for the next ELSIF (if any)
                    current_condition = None
                    looking_for_stmt = False

        return elsif_blocks

    @staticmethod
    def _extract_else_statements(if_stmt_ast: Any) -> List[Any]:
        """
        Extract statements from the ELSE block.

        The AST for an IF statement is a flattened sequence of nodes.
        Structure:
          - Child 0: Expression (IF condition)
          - Child 1: StatementList (THEN block)
          - Subsequent nodes are either:
             a) Expression (ELSIF condition) followed by StatementList (ELSIF block)
             b) StatementList (ELSE block) - appearing at the end
        """
        children = _get_children(if_stmt_ast)

        # Verify we have at least the initial IF structure
        if len(children) < 2:
            return []

        # Start scanning after the initial IF condition and THEN block
        idx = 2
        while idx < len(children):
            node = children[idx]

            if _is_node_type(node, 'expression'):
                idx += 2
            elif _is_node_type(node, 'statement_list'):
                return _get_children(node)
            else:
                idx += 1

        return []

    def _format_assignment_statement(self, stmt_ast: Any, lhs: Optional[str]) -> str:
        """Create a human-readable assignment statement"""
        # FIX: Find the expression node specifically, don't format the whole statement
        rhs_ast = None
        for child in _iterate_ast_list(stmt_ast):
            if _is_node_type(child, 'expression'):
                rhs_ast = child
                break

        # Fallback: if no expression node found
        if rhs_ast is None:
            for child in _iterate_ast_list(stmt_ast):
                if _is_node_type(child, 'boolean_literal') or \
                        _is_node_type(child, 'integer_literal') or \
                        _is_node_type(child, 'real_literal'):
                    rhs_ast = child
                    break

        if lhs and rhs_ast:
            rhs_str = self._format_expression_ast(rhs_ast)
            return f"{lhs} := {rhs_str}"

        return f"{lhs} := UNKNOWN"

    def _format_condition(self, if_stmt_ast: Any) -> str:
        """Format the condition of an if-statement"""
        for item in _iterate_ast_list(if_stmt_ast):
            if _is_node_type(item, 'expression'):
                return self._format_expression_ast(item)
        return "UNKNOWN CONDITION"

    def _format_condition_ast(self, expr_ast: Any) -> str:
        """Format an expression AST node as a string"""
        return self._format_expression_ast(expr_ast)

    @staticmethod
    def _format_expression_ast(expr_ast: Any) -> str:
        """
        Format an expression AST node as a human-readable string.

        This implementation recursively traverses the AST to reconstruct the
        expression, ensuring that all operators, parentheses, and nested structures
        (like function calls or array access) are preserved exactly as parsed.
        """
        parts = []

        # Map AST node types to their string representation
        operator_map = {
            'less_or_equal': '<=',
            'greater_or_equal': '>=',
            'less_than': '<',
            'greater_than': '>',
            'equals': '=',
            'not_equal': '<>',
            'adding': '+',
            'subtracting': '-',
            'multiply_with': '*',
            'divide_by': '/',
            'logical_and': 'AND',
            'logical_or': 'OR',
            'logical_not': 'NOT',
            'modulo': 'MOD',
            'assign': ':=',
        }

        def traverse(node):
            # 1. Base case: String literal (leaf)
            if isinstance(node, str):
                parts.append(node)
                return

            # 2. Tuple node: (Type, Children...)
            if isinstance(node, tuple):
                node_type = node[0]

                # FIX: Check if this node IS an operator
                if node_type in operator_map:
                    parts.append(operator_map[node_type])

                # Traverse children
                for child in node[1:]:
                    traverse(child)
                return

            # 3. List of nodes
            if isinstance(node, list):
                for item in node:
                    traverse(item)
                return

        traverse(expr_ast)

        # Join parts. The AST leaves are the raw tokens.
        text = " ".join(parts)

        # Formatting cleanup to make the output valid ST code
        text = text.replace(" (", "(").replace("( ", "(")
        text = text.replace(" )", ")")
        text = text.replace(" [", "[").replace("[ ", "[")
        text = text.replace(" ]", "]")
        text = text.replace(" . ", ".")
        text = text.replace(" ,", ",")

        return text


def _is_node_type(node: Any, node_type: str) -> bool:
    """Check if an AST node is of a specific type"""
    if isinstance(node, tuple) and len(node) > 0:
        return node[0] == node_type
    return False


def _iterate_ast_list(node: Any):
    """Iterate over children of an AST node"""
    if isinstance(node, tuple):
        for item in node[1:]:
            # If the child is a list, iterate through it
            if isinstance(item, list):
                for list_item in item:
                    yield list_item
            else:
                yield item
    elif isinstance(node, list):
        for item in node:
            yield item


def _get_children(node: Any) -> List[Any]:
    """Get all children of an AST node as a list"""
    return list(_iterate_ast_list(node))


def _find_all_nodes(ast: Any, node_type: str) -> List[Any]:
    """Find all nodes of a specific type in the AST"""
    results = []

    def traverse(node):
        if _is_node_type(node, node_type):
            results.append(node)

        for child in _iterate_ast_list(node):
            traverse(child)

    traverse(ast)
    return results


def _extract_text(node: Any) -> Optional[str]:
    """Extract text content from a leaf node"""

    if isinstance(node, str):
        return node
    elif isinstance(node, tuple) and len(node) > 1:
        for child in node[1:]:
            if isinstance(child, str):
                return child
            elif isinstance(child, list):
                for list_item in child:
                    if isinstance(list_item, str):
                        return list_item

    return None


def _extract_variable_name(var_init_decl: Any) -> Optional[str]:
    """Extract variable name from var-init-decl node"""
    for child in _iterate_ast_list(var_init_decl):
        if _is_node_type(child, 'variable_name'):
            return _extract_text(child)
    return None


def _extract_data_type(var_init_decl: Any) -> str:
    """Extract data type from var-init-decl node"""

    # Type category nodes (contain the actual type)
    type_category_nodes = {
        'real_type_name': 'REAL',
        'integer_type_name': 'INT',
        'bit_string_type_name': 'BOOL'
    }

    # Specific type nodes
    specific_type_nodes = {
        'type_bool': 'BOOL',
        'type_int': 'INT',
        'type_dint': 'DINT',
        'type_sint': 'SINT',
        'type_real': 'REAL',
        'type_lreal': 'LREAL',
        'type_word': 'WORD',
        'type_dword': 'DWORD',
        'type_uint': 'UINT',
        'type_ulint': 'ULINT'
    }

    # Recursive search function
    def search_for_type(node, depth=0):
        if depth > 5:  # Prevent infinite recursion
            return None

        # Check if this node is a type category
        if isinstance(node, tuple) and len(node) > 0:
            node_name = node[0]

            # Check for type category nodes
            if node_name in type_category_nodes:
                # Look inside for specific type
                for child in _iterate_ast_list(node):
                    result = search_for_type(child, depth + 1)
                    if result:
                        return result
                # If no specific type found, return the category default
                return type_category_nodes[node_name]

            # Check for specific type nodes
            if node_name in specific_type_nodes:
                return specific_type_nodes[node_name]

        # Recursively search children
        for child in _iterate_ast_list(node):
            result = search_for_type(child, depth + 1)
            if result:
                return result

        return None

    result = search_for_type(var_init_decl)
    return result if result else "UNKNOWN"


def _extract_initial_value(var_init_decl: Any) -> Optional[str]:
    """Extract initial value from var-init-decl node"""
    for child in _iterate_ast_list(var_init_decl):
        if _is_node_type(child, 'expression'):
            # Find literal value
            for expr_child in _iterate_ast_list(child):
                if _is_node_type(expr_child, 'integer_literal'):
                    return _extract_text(expr_child)
                elif _is_node_type(expr_child, 'real_literal'):
                    return _extract_text(expr_child)
                elif _is_node_type(expr_child, 'boolean_literal'):
                    return _extract_text(expr_child)

    return None



def build_pdg_from_ast(program_ast: Any, state_id: str,
                       case_element_ast: Any) -> ProgramDependencyGraph:
    """
    High-level API to build a PDG from AST components

    Args:
        program_ast: Full program AST (for variable extraction)
        state_id: State identifier
        case_element_ast: Case element AST node

    Returns:
        Complete ProgramDependencyGraph
    """
    # Step 1: Extract and classify variables
    variables = extract_variables_from_ast(program_ast)

    # Step 2: Build PDG
    builder = PDGBuilder(variables)
    pdg = builder.build_pdg_for_state(state_id, case_element_ast)

    return pdg


def _extract_state_variable(case_stmt_ast: Any) -> Optional[str]:
    """
    Extract the state variable name from a CASE statement.
    Structure: CASE <expression> OF ...
    """

    # Helper to recursively find the first variable_name
    def find_first_var(node: Any) -> Optional[str]:
        if _is_node_type(node, 'variable_name'):
            return _extract_text(node)

        for child in _iterate_ast_list(node):
            res = find_first_var(child)
            if res:
                return res
        return None

    # Iterate through CASE statement children to find the governing expression
    for child in _iterate_ast_list(case_stmt_ast):
        if _is_node_type(child, 'expression'):
            return find_first_var(child)

    return None

def build_all_pdgs(program_ast: Any) -> Tuple[Dict[str, ProgramDependencyGraph], Optional[str]]:
    """
    Build PDGs for all states in a program

    Args:
        program_ast: Complete program AST

    Returns:
        Tuple of (Dictionary mapping state_id -> ProgramDependencyGraph, state_variable_name)
    """
    pdgs = {}
    state_variable = None

    # Extract variables once
    variables = extract_variables_from_ast(program_ast)
    builder = PDGBuilder(variables)

    # Find case statement
    case_statements = _find_all_nodes(program_ast, 'case_statement')

    if not case_statements:

        # Try to find what nodes exist
        def find_node_types(node, depth=0):
            if depth > 3:  # Limit depth
                return
            if isinstance(node, tuple) and len(node) > 0:
                for child in node[1:]:
                    find_node_types(child, depth + 1)
            elif isinstance(node, list):
                for item in node:
                    find_node_types(item, depth)

        find_node_types(program_ast)

    for case_stmt in case_statements:

        if state_variable is None:
            state_variable = _extract_state_variable(case_stmt)

        # Find all case elements
        case_elements = _find_all_nodes(case_stmt, 'case_element')

        for case_elem in case_elements:
            # Extract state ID
            state_id = _extract_state_id(case_elem)

            if state_id:
                pdg = builder.build_pdg_for_state(state_id, case_elem)
                pdgs[state_id] = pdg

    return pdgs, state_variable


def _extract_state_id(case_element: Any) -> Optional[str]:
    """Extract the state ID from a case-element node"""
    # Look for case-list -> case-list-element -> integer-literal
    for child in _iterate_ast_list(case_element):
        if _is_node_type(child, 'case_list'):
            for list_child in _iterate_ast_list(child):
                if _is_node_type(list_child, 'case_list_element'):
                    for elem_child in _iterate_ast_list(list_child):
                        if _is_node_type(elem_child, 'integer_literal'):
                            text = _extract_text(elem_child)
                            return text
    return None

def _get_node_name(node: Any) -> str:
    """Helper to get node name for debugging"""
    if isinstance(node, tuple) and len(node) > 0:
        return str(node[0])
    elif isinstance(node, str):
        return f"STRING: '{node}'"
    elif isinstance(node, list):
        return f"LIST (len={len(node)})"
    else:
        return str(type(node))


def pdg_to_graphviz(pdg: ProgramDependencyGraph) -> str:
    """
    Generate a Graphviz DOT representation of the PDG

    Args:
        pdg: Program Dependency Graph

    Returns:
        DOT format string
    """
    dot = f'digraph "PDG_State_{pdg.state_id}" {{\n'
    dot += '    rankdir=TB;\n'
    dot += '    node [shape=box];\n\n'

    # Add nodes
    for node_id, node in pdg.nodes.items():
        label = node.statement.replace('"', '\\"')
        color = {
            'assignment': 'lightblue',
            'condition': 'lightyellow',
            'if_block': 'lightgreen'
        }.get(node.statement_type, 'white')

        dot += f'    node{node_id} [label="{label}", fillcolor={color}, style=filled];\n'

    dot += '\n'

    # Add edges
    for edge in pdg.edges:
        style = 'solid' if edge.edge_type == 'control' else 'dashed'
        color = 'red' if edge.edge_type == 'control' else 'blue'
        label = edge.label or edge.variable or ''

        dot += f'    node{edge.from_node} -> node{edge.to_node} '
        dot += f'[style={style}, color={color}, label="{label}"];\n'

    dot += '}\n'
    return dot