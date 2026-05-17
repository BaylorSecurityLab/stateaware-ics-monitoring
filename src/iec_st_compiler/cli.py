"""
IEC 61131-3 Structured Text to XML Compiler.

This command-line interface parses one or more IEC 61131-3 Structured Text
(ST) files and translates the language into an XML Abstract Syntax Tree (AST).
It supports optional features like EPAS pragma handling and pretty-printed XML output.
"""

import argparse
import fileinput
import re
import sys
import time
from typing import List, Optional, Union

from . import core

# --- Static Patterns ---
# Default comment pattern: single level (*...*) or {....}
DEFAULT_COMMENT_PATTERN = re.compile(r"(\(\*.*?\*\))|(\{.*?})", re.S)
PRAGMA_REGEX = re.compile(r"\s*\(\*\s*@(\w+)\s*:=\s*'(.*?)'\s*\*\)\s*")
EMPTY_REGEX = re.compile(r"^\s*$")

# Pattern to ignore
DBG_PREFIX = "(*DBG:"


def get_comment_pattern(
    files_iterator: fileinput.FileInput, enable_epas_pragmas: bool
) -> Union[re.Pattern, List]:
    """
    Determines and returns the correct comment pattern (simple regex or complex
    recursive list) by checking for the NESTEDCOMMENTS pragma at the start of input.

    :param files_iterator: The file-input.FileInput iterator (must be re-opened by caller).
    :param enable_epas_pragmas: Flag from CLI argument.
    :returns: The determined pyPEG comment pattern (re.Pattern or List).
    """
    if not enable_epas_pragmas:
        return DEFAULT_COMMENT_PATTERN

    # Check the first few lines for pragmas
    r = re.compile  # Alias compile locally

    for line in files_iterator:
        # 1. Skip Debug lines
        if line.lstrip().startswith(DBG_PREFIX):
            continue

        # 2. Skip Empty lines
        if EMPTY_REGEX.match(line):
            continue

        m = PRAGMA_REGEX.match(line)
        if m:
            if m.group(1) == "NESTEDCOMMENTS" and m.group(2) == "Yes":
                # If found, build and return the recursive pattern definition
                return [
                    r(r"{.*?}"),
                    (
                        "(*",
                        -1,  # ZeroOrMore/Closure
                        [
                            r(r"[^(*{}]+"),  # Match anything but { (comment start) or (* (comment start)
                            DEFAULT_COMMENT_PATTERN,  # Recurse on the default pattern
                            r(r"(\((?!\*))"),  # Match a '(' not followed by '*'
                            r(r"(\*(?!\)))"),  # Match a '*' not followed by ')'
                        ],
                        "*)",
                    ),
                ]
        else:
            # First non-empty, non-pragma, non-debug line encountered, stop checking
            break

    return DEFAULT_COMMENT_PATTERN  # If loop finishes without finding pragma


def run_cli(args_list: Optional[List[str]] = None) -> int:
    """
    The main entry point for the compiler command-line tool.

    Handles argument parsing, manages file input/output, and orchestrates the
    compilation process via core.py functions.

    :param args_list: Optional list of arguments (used for testing).
    :returns: Exit code (0 on success, 1 on interrupt, 5 on error).
    """

    parser = argparse.ArgumentParser(
        description=__doc__.strip(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-E",
        "--epas-pragmas",
        action="store_true",
        dest="epas_pragmas",
        help="Enable detection and processing of EPAS pragmas (e.g., nested comments).",
        default=False,
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_file",
        metavar="FILE",
        help="Direct output to the specified FILE. Writes to stdout if omitted or FILE is '-'.",
    )
    parser.add_argument(
        "-p",
        "--parse-only",
        action="store_true",
        dest="parse_only",
        help="Parse only, then output the raw Python AST representation to stdout.",
        default=False,
    )

    parser.add_argument(
        "-P",
        "--pretty",
        action="store_true",
        default=False,
        help="Pretty print XML output using lxml for indentation.",
    )

    parser.add_argument(
        "files",
        metavar="FILES",
        nargs="*",
        help="Input source files (reads from stdin if none are provided).",
    )

    parser.add_argument(
        "--analyze",
        action="store_true",
        default=False,
        help="Include PDG and invariant template analysis in output.",
    )

    parser.add_argument(
        "--pdg-only",
        action="store_true",
        default=False,
        help="Include only PDG analysis (no invariants).",
    )

    parser.add_argument(
        "--graphviz",
        dest="graphviz_output",
        metavar="FILE",
        help="Export PDGs to Graphviz DOT format.",
    )

    args = parser.parse_args(args_list)
    start_time = time.time()
    files_iterator = None

    try:
        # Step 1: Determine Comment Pattern and Concatenate Source

        # A. Get comment pattern (requires first pass over files if pragmas enabled)
        files_iterator = fileinput.input(args.files)
        comment_pattern = get_comment_pattern(files_iterator, args.epas_pragmas)
        files_iterator.close()

        # B. Re-open files and concatenate content, filtering out DBG lines
        files_iterator = fileinput.input(args.files)
        source_content = "".join(
            line for line in files_iterator if not line.lstrip().startswith(DBG_PREFIX)
        )

        # C. Select Core Compilation Function
        if args.parse_only:
            # Returns raw Python list (AST)
            output = core.compile_to_ast(
                source_content=source_content,
                comment_pattern=comment_pattern,
            )
            # Output raw AST
            sys.stdout.write(str(output) + "\n")
        else:
            # Determine if we need analysis
            if args.analyze or args.pdg_only:
                xml_output = core.compile_to_xml_with_analysis(
                    source_content=source_content,
                    comment_pattern=comment_pattern,
                    pretty_print=args.pretty,
                    include_pdg=True,
                    include_invariants=args.analyze and not args.pdg_only,
                )
            else:
                # Standard compilation without analysis
                xml_output = core.compile_to_xml(
                    source_content=source_content,
                    comment_pattern=comment_pattern,
                    pretty_print=args.pretty,
                )

            # Write to file or stdout
            if args.output_file and args.output_file != "-":
                with open(args.output_file, "w", encoding="utf-8") as outfile:
                    outfile.write(xml_output)
            else:
                sys.stdout.write(xml_output)

            # Export Graphviz if requested
            if args.graphviz_output:
                from . import pdg as pdg_module
                from .ast_writer import export_pdgs_to_graphviz

                pdgs = pdg_module.build_all_pdgs(
                    core.compile_to_ast(source_content, comment_pattern)
                )
                dot_output = export_pdgs_to_graphviz(pdgs)

                with open(args.graphviz_output, "w", encoding="utf-8") as dotfile:
                    dotfile.write(dot_output)

                sys.stderr.write(f"PDG visualization exported to {args.graphviz_output}\n")

    except KeyboardInterrupt:
        sys.stderr.write("\nProcess interrupted by user.\n")
        return 1
    except SyntaxError as e:
        sys.stderr.write(f"Error: Syntax Error during parsing: {e}\n")
        return 5
    except Exception as e:
        # Re-raise XML runtime errors from core.py as generic error
        sys.stderr.write(f"An unexpected error occurred: {type(e).__name__}: {e}\n")
        return 5
    finally:
        if files_iterator is not None:
            files_iterator.close()

    sys.stderr.write(f"--- Finished in {time.time() - start_time:.4f} seconds ---\n")
    return 0


def main():
    """Main execution function for the CLI, calling run_cli."""
    return run_cli()


if __name__ == "__main__":
    sys.exit(main())