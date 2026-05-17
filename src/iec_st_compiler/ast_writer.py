from xml.sax.saxutils import escape
from typing import Union, List, Tuple, Any, Dict, Optional

AST_Element = Union[str, Tuple[str, Any, ...], List[Any]]


def convert_ast_to_xml(ast: AST_Element) -> str:
    """
    Recursively converts a Structured Text (ST) Abstract Syntax Tree (AST)
    represented by tuples and strings into a basic XML string.

    The conversion logic is as follows:
    1. String: Escapes special characters and returns as XML content.
    2. Tuple: Interpreted as an XML element, where the first element is the
       tag name (underscores replaced by hyphens) and subsequent elements are children.
    3. Other Iterable (e.g., List): Interpreted as a sequence of sibling
       elements, which are processed sequentially.

    Args:
        ast: The AST element to convert. Can be a string (content), a tuple
             (XML element/node), or an iterable (list of sibling elements).

    Returns:
        The resulting XML fragment as a string.
    """
    # 1. Handle String (Content)
    if isinstance(ast, str):
        # Escape special characters (<, >, &, ", ') for safe inclusion in XML
        return escape(ast)

    # 2. Handle Tuple (XML Element/Node)
    if isinstance(ast, tuple):
        # The first element is the tag name. Replace underscores with hyphens.
        tag_name = ast[0].replace("_", "-")
        result = "<" + tag_name + ">"

        # Recursively process children (elements after the tag name)
        for child in ast[1:]:
            result += convert_ast_to_xml(child)

        # Close the XML element
        result += "</" + tag_name + ">"
        return result

    # 3. Handle Other Iterable (Sibling Container, e.g., List)
    else:
        result = ""
        for sibling_element in ast:
            result += convert_ast_to_xml(sibling_element)
        return result


def convert_ast_to_xml_with_invariants(
        ast: AST_Element,
        pdgs: Optional[Dict] = None,
        invariants: Optional[Dict] = None
) -> str:
    """
    Enhanced XML output with PDG and invariant data

    Args:
        ast: The AST element to convert
        pdgs: Dictionary mapping state_id -> ProgramDependencyGraph
        invariants: Dictionary mapping state_id -> List[InvariantTemplate]

    Returns:
        Complete XML document with AST, PDG analysis, and invariant templates
    """
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<iec-source>\n'

    # Add the original AST
    xml += '  <program>\n'
    xml += _indent(convert_ast_to_xml(ast), 2)
    xml += '  </program>\n'

    # Add PDG section if provided
    if pdgs:
        xml += '  <pdg-analysis>\n'
        for state_id, pdg in sorted(pdgs.items()):
            xml += serialize_pdg(state_id, pdg)
        xml += '  </pdg-analysis>\n'

    # Add invariant templates if provided
    if invariants:
        xml += '  <invariant-templates>\n'
        for state_id, inv_list in sorted(invariants.items()):
            xml += f'    <state id="{state_id}">\n'
            for inv in inv_list:
                xml += serialize_invariant(inv)
            xml += '    </state>\n'
        xml += '  </invariant-templates>\n'

    xml += '</iec-source>'
    return xml


def serialize_pdg(state_id: str, pdg: Any) -> str:
    """
    Serialize a Program Dependency Graph to XML

    Args:
        state_id: State identifier
        pdg: ProgramDependencyGraph object

    Returns:
        XML string representation of the PDG
    """
    xml = f'    <state id="{state_id}">\n'

    # Serialize variables
    xml += '      <variables>\n'
    for var_name, var in sorted(pdg.variables.items()):
        xml += f'        <variable name="{escape(var_name)}" '
        xml += f'type="{var.var_type.value}" '
        xml += f'data-type="{escape(var.data_type)}" '
        xml += f'scope="{escape(var.scope)}"'
        if var.initial_value:
            xml += f' initial-value="{escape(var.initial_value)}"'
        xml += '/>\n'
    xml += '      </variables>\n'

    # Serialize nodes
    xml += '      <nodes>\n'
    for node_id, node in sorted(pdg.nodes.items()):
        xml += f'        <node id="{node_id}" type="{escape(node.statement_type)}">\n'
        xml += f'          <statement>{escape(node.statement)}</statement>\n'

        if node.variables_read:
            xml += '          <reads>\n'
            for var in sorted(node.variables_read):
                xml += f'            <variable>{escape(var)}</variable>\n'
            xml += '          </reads>\n'

        if node.variables_written:
            xml += '          <writes>\n'
            for var in sorted(node.variables_written):
                xml += f'            <variable>{escape(var)}</variable>\n'
            xml += '          </writes>\n'

        xml += '        </node>\n'
    xml += '      </nodes>\n'

    # Serialize edges
    xml += '      <edges>\n'
    for edge in pdg.edges:
        xml += f'        <edge from="{edge.from_node}" to="{edge.to_node}" '
        xml += f'type="{escape(edge.edge_type)}"'
        if edge.variable:
            xml += f' variable="{escape(edge.variable)}"'
        if edge.label:
            xml += f' label="{escape(edge.label)}"'
        xml += '/>\n'
    xml += '      </edges>\n'

    xml += '    </state>\n'
    return xml


def serialize_invariant(inv: Any) -> str:
    """
    Serialize an invariant template to XML format

    Args:
        inv: InvariantTemplate object to serialize

    Returns:
        XML string
    """
    xml = f'      <invariant id="{escape(inv.id)}" type="{escape(inv.type)}">\n'

    # Variables
    xml += '        <variables>\n'
    for var in inv.variables:
        xml += f'          <variable>{escape(var)}</variable>\n'
    xml += '        </variables>\n'

    # Structure
    xml += f'        <structure>{escape(inv.structure)}</structure>\n'

    # Type-specific fields
    if inv.type == "single":
        xml += f'        <sensing-var>{escape(inv.sensing_var)}</sensing-var>\n'
        xml += f'        <sensing-var-type>{escape(inv.sensing_var_type.value)}</sensing-var-type>\n'
        xml += f'        <actuation-var>{escape(inv.actuation_var)}</actuation-var>\n'
        xml += f'        <operator>{escape(inv.operator)}</operator>\n'
        if inv.actuation_value:
            xml += f'        <actuation-value>{escape(inv.actuation_value)}</actuation-value>\n'

    elif inv.type == "multi":
        if inv.sensing_vars:
            xml += '        <sensing-vars>\n'
            for var in inv.sensing_vars:
                xml += f'          <variable>{escape(var)}</variable>\n'
            xml += '        </sensing-vars>\n'

        if inv.configuration_vars:
            xml += '        <configuration-vars>\n'
            for var in inv.configuration_vars:
                xml += f'          <variable>{escape(var)}</variable>\n'
            xml += '        </configuration-vars>\n'

        xml += f'        <actuation-var>{escape(inv.actuation_var)}</actuation-var>\n'
        xml += f'        <condition>{escape(inv.condition)}</condition>\n'
        xml += f'        <action>{escape(inv.action)}</action>\n'

    elif inv.type == "inter":
        xml += f'        <source-state>{escape(inv.source_state)}</source-state>\n'
        xml += f'        <dest-state>{escape(inv.dest_state)}</dest-state>\n'
        xml += f'        <state-variable>{escape(inv.state_variable)}</state-variable>\n'
        xml += f'        <transition-condition>{escape(inv.transition_condition)}</transition-condition>\n'

        if inv.condition_variables:
            xml += '        <condition-variables>\n'
            for var in inv.condition_variables:
                xml += f'          <variable>{escape(var)}</variable>\n'
            xml += '        </condition-variables>\n'

    # Confidence
    xml += f'        <confidence>{inv.confidence}</confidence>\n'

    xml += '      </invariant>\n'
    return xml


def _indent(text: str, levels: int) -> str:
    """
    Add indentation to multi-line text

    Args:
        text: Text to indent
        levels: Number of indentation levels (2 spaces each)

    Returns:
        Indented text
    """
    indent = '  ' * levels
    lines = text.split('\n')
    return '\n'.join(indent + line if line.strip() else line for line in lines)


def convert_to_json(
        ast: AST_Element,
        pdgs: Optional[Dict] = None,
        invariants: Optional[Dict] = None
) -> dict:
    """
    Convert AST, PDGs, and invariants to JSON-serializable dictionary

    Args:
        ast: The AST element
        pdgs: Dictionary mapping state_id -> ProgramDependencyGraph
        invariants: Dictionary mapping state_id -> List[InvariantTemplate]

    Returns:
        Dictionary suitable for JSON serialization
    """
    result = {
        "program": _ast_to_dict(ast)
    }

    if pdgs:
        result["pdg_analysis"] = {
            state_id: pdg.to_dict()
            for state_id, pdg in pdgs.items()
        }

    if invariants:
        result["invariant_templates"] = {
            state_id: [inv.to_dict() for inv in inv_list]
            for state_id, inv_list in invariants.items()
        }

    return result


def _ast_to_dict(ast: AST_Element) -> Any:
    """
    Convert AST to dictionary representation

    Args:
        ast: AST element

    Returns:
        Dictionary or primitive value
    """
    if isinstance(ast, str):
        return ast
    elif isinstance(ast, tuple):
        tag_name = ast[0]
        children = [_ast_to_dict(child) for child in ast[1:]]
        return {
            "type": tag_name,
            "children": children
        }
    elif isinstance(ast, list):
        return [_ast_to_dict(elem) for elem in ast]
    else:
        return str(ast)


def export_pdgs_to_graphviz(pdgs: Dict) -> str:
    """
    Export all PDGs to a single Graphviz DOT file with subgraphs

    Args:
        pdgs: Dictionary mapping state_id -> ProgramDependencyGraph

    Returns:
        DOT format string
    """
    dot = 'digraph PDGs {\n'
    dot += '  rankdir=TB;\n'
    dot += '  compound=true;\n'
    dot += '  node [shape=box];\n\n'

    for state_id, pdg in sorted(pdgs.items()):
        dot += f'  subgraph cluster_state_{state_id} {{\n'
        dot += f'    label="State {state_id}";\n'
        dot += '    style=dashed;\n'
        dot += '    color=blue;\n\n'

        # Add nodes
        for node_id, node in pdg.nodes.items():
            label = node.statement.replace('"', '\\"').replace('\n', '\\n')
            color = {
                'assignment': 'lightblue',
                'condition': 'lightyellow',
                'if_block': 'lightgreen'
            }.get(node.statement_type, 'white')

            dot += f'    s{state_id}_n{node_id} [label="{label}", '
            dot += f'fillcolor={color}, style=filled];\n'

        # Add edges within this state
        for edge in pdg.edges:
            style = 'solid' if edge.edge_type == 'control' else 'dashed'
            color = 'red' if edge.edge_type == 'control' else 'blue'
            label = edge.label or edge.variable or ''

            dot += f'    s{state_id}_n{edge.from_node} -> s{state_id}_n{edge.to_node} '
            dot += f'[style={style}, color={color}, label="{label}"];\n'

        dot += '  }\n\n'

    dot += '}\n'
    return dot


# ============================================================================
# STATISTICS AND SUMMARY
# ============================================================================

def generate_xml_summary(
        pdgs: Optional[Dict] = None,
        invariants: Optional[Dict] = None
) -> str:
    """
    Generate a summary XML section with statistics

    Args:
        pdgs: Dictionary of PDGs
        invariants: Dictionary of invariants

    Returns:
        XML summary section
    """
    xml = '  <analysis-summary>\n'

    if pdgs:
        total_nodes = sum(len(pdg.nodes) for pdg in pdgs.values())
        total_edges = sum(len(pdg.edges) for pdg in pdgs.values())
        total_vars = sum(len(pdg.variables) for pdg in pdgs.values())

        xml += '    <pdg-statistics>\n'
        xml += f'      <total-states>{len(pdgs)}</total-states>\n'
        xml += f'      <total-nodes>{total_nodes}</total-nodes>\n'
        xml += f'      <total-edges>{total_edges}</total-edges>\n'
        xml += f'      <total-variables>{total_vars}</total-variables>\n'
        xml += '    </pdg-statistics>\n'

    if invariants:
        total_invs = sum(len(inv_list) for inv_list in invariants.values())
        single_invs = sum(
            len([inv for inv in inv_list if inv.type == "single"])
            for inv_list in invariants.values()
        )
        multi_invs = sum(
            len([inv for inv in inv_list if inv.type == "multi"])
            for inv_list in invariants.values()
        )

        xml += '    <invariant-statistics>\n'
        xml += f'      <total-states>{len(invariants)}</total-states>\n'
        xml += f'      <total-invariants>{total_invs}</total-invariants>\n'
        xml += f'      <single-variable-invariants>{single_invs}</single-variable-invariants>\n'
        xml += f'      <multi-variable-invariants>{multi_invs}</multi-variable-invariants>\n'
        xml += '    </invariant-statistics>\n'

    xml += '  </analysis-summary>\n'
    return xml


def convert_ast_to_xml_with_invariants_and_summary(
        ast: AST_Element,
        pdgs: Optional[Dict] = None,
        invariants: Optional[Dict] = None,
        include_summary: bool = True
) -> str:
    """
    Complete XML output with AST, PDG, invariants, and optional summary

    Args:
        ast: The AST element to convert
        pdgs: Dictionary mapping state_id -> ProgramDependencyGraph
        invariants: Dictionary mapping state_id -> List[InvariantTemplate]
        include_summary: Whether to include statistics summary

    Returns:
        Complete XML document
    """
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<iec-source>\n'

    # Summary (at top for quick reference)
    if include_summary and (pdgs or invariants):
        xml += generate_xml_summary(pdgs, invariants)

    # Program AST
    xml += '  <program>\n'
    xml += _indent(convert_ast_to_xml(ast), 2)
    xml += '  </program>\n'

    # PDG Analysis
    if pdgs:
        xml += '  <pdg-analysis>\n'
        for state_id, pdg in sorted(pdgs.items()):
            xml += serialize_pdg(state_id, pdg)
        xml += '  </pdg-analysis>\n'

    # Invariant Templates
    if invariants:
        xml += '  <invariant-templates>\n'
        for state_id, inv_list in sorted(invariants.items()):
            xml += f'    <state id="{state_id}">\n'
            for inv in inv_list:
                xml += serialize_invariant(inv)
            xml += '    </state>\n'
        xml += '  </invariant-templates>\n'

    xml += '</iec-source>'
    return xml