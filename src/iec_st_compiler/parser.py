import re


class Keyword(str):
    """
    Marker class used to distinguish literal strings that must be matched
    as whole keywords (respecting word boundaries), not just substrings.
    """

    pass


class Code(str):
    """
    Marker class used for code segments (currently unused in the provided code).
    """

    pass


class Ignore(object):
    """
    Represents a pattern (typically a regular expression) whose match
    result should be ignored/discarded from the resulting AST.
    """

    def __init__(self, regex_text):
        """
        Initializes the Ignore object by compiling the regex.

        :param regex_text: The regular expression string to ignore.
        """
        self.regex = re.compile(regex_text)


class _And(object):
    """
    Implements the positive lookahead (&) operator.
    Checks if a pattern matches without consuming input.
    """

    def __init__(self, something):
        """
        Initializes the _And lookahead operator.

        :param something: The pattern to check.
        """
        self.obj = something


class _Not(_And):
    """
    Implements the negative lookahead (!) operator.
    Checks if a pattern does NOT match without consuming input.
    """

    pass


# Global regex objects and sentinel values
word_regex = re.compile(r"\w+")
rest_regex = re.compile(r".*")
ignoring = Ignore("")


def skip(skipper, text, skip_ws=True, skip_comments=None):
    """
    Skips whitespace and comments at the beginning of the text.

    :param skipper: The internal parser instance used for parsing comments.
    :param text: The text string to process.
    :param skip_ws: Flag if whitespace should be skipped.
    :param skip_comments: A function returning a pyPEG pattern for matching comments.
    :returns: The text after skipping leading whitespace and comments.
    """
    if skip_ws:
        t = text.strip()
    else:
        t = text

    if skip_comments:
        # Loop until no more comments are found
        try:
            while True:
                # Use the skipper to parse the comment pattern
                skip_ast, t = skipper.parse_line(t, skip_comments, [], skip_ws, None, 0)
                if skip_ws:
                    t = t.strip()
        except SyntaxError:
            # Breaks the loop if comment parsing fails (no comment found)
            pass

    return t


class Parser(object):
    """
    The core recursive descent parser engine for pyPEG.
    Manages state and performs the pattern matching recursively.
    """

    def __init__(self, another=False):
        """
        Initializes the Parser.

        :param another: Internal flag; True for the auxiliary skipper parser.
        """
        self.rest_length = -1
        # The parser owns a reference to an internal 'skipper' parser used for comments
        if not another:
            self.skipper = Parser(True)
        else:
            self.skipper = self

    def parse_line(
        self,
        text_line,
        pattern,
        result_so_far=None,
        skip_ws=True,
        skip_comments=None,
        input_length=0,
    ):
        """
        Parses a single line of text against a pyPEG pattern recursively.

        :param text_line: The text to parse.
        :param pattern: The pyPEG language description (function, string, tuple, or list).
        :param result_so_far: The parsing result accumulated so far (list of AST nodes).
        :param skip_ws: Flag if whitespace should be skipped.
        :param skip_comments: Python function returning pyPEG for matching comments.
        :param input_length: Original length of text (used for position tracking).
        :returns: (pyAST, text_rest) - The updated AST and the remaining unparsed text.
        :raises: SyntaxError if the text does not match the pattern.
        """
        if result_so_far is None:
            result_so_far = []
        name = None
        position = 0

        # Inner helper function to finalize the result (r = result_builder)
        def r(_result, _text):
            """Handles packaging the match result into the final AST structure."""

            # Track the minimum remaining text length for error reporting
            if self.rest_length == -1:
                self.rest_length = len(_text)
            else:
                self.rest_length = min(self.rest_length, len(_text))

            res = result_so_far

            # Non-terminal rule with a result: create a node (name, result)
            if name and _result:
                if input_length:
                    res.append(position)
                res.append((name, _result))
            # Non-terminal rule that matched empty or only literals: create an empty node
            elif name:
                if input_length:
                    res.append(position)
                res.append((name, []))
            # Terminal/Sequence/Loop result: extend the existing list
            elif _result:
                # Check if the result is already a list (e.g., from Sequence or loops)
                if type(_result) is type([]):
                    res.extend(_result)
                else:
                    if input_length:
                        res.append(position)
                    res.extend([_result])

            return res, _text

        # 1. Lazy evaluation and naming (if pattern is a function)
        if type(pattern) is type(lambda x: 0):
            if pattern.__name__[0] != "_":
                name = pattern.__name__
            pattern = pattern()
            if type(pattern) is type(lambda x: 0):
                pattern = (pattern,)

        # 2. Skip initial comments and whitespace
        text = skip(self.skipper, text_line, skip_ws, skip_comments)

        if input_length:
            position = input_length - len(text) - 1

        pattern_type = type(pattern)

        # 3. Pattern Matching Logic

        # 3a. String Literal Match
        if pattern_type is type(""):
            if text[: len(pattern)] == pattern:
                text = skip(self.skipper, text[len(pattern) :], skip_ws, skip_comments)
                return r(None, text)
            else:
                raise SyntaxError()

        # 3b. Keyword Match (checks word boundary)
        elif pattern_type is type(Keyword("")):
            m = word_regex.match(text)
            if m:
                if m.group(0) == pattern:
                    text = skip(
                        self.skipper,
                        text[len(pattern) :],
                        skip_ws,
                        skip_comments,
                    )
                    return r(None, text)
                else:
                    raise SyntaxError()
            else:
                raise SyntaxError()

        # 3c. Not Match (Negative Lookahead)
        elif pattern_type is type(_Not("")):
            try:
                # Attempt to parse the inner object
                self.parse_line(
                    text, pattern.obj, [], skip_ws, skip_comments, input_length
                )
            except SyntaxError:
                # Success: Inner object did NOT match, return original text
                return result_so_far, text_line

            # Failure: Inner object matched, raise error
            raise SyntaxError()

        # 3d. And Match (Positive Lookahead)
        elif pattern_type is type(_And("")):
            # Parse the inner object
            self.parse_line(text, pattern.obj, [], skip_ws, skip_comments, input_length)
            # Success: return original results and text (consumes nothing)
            return result_so_far, text_line

        # 3e. Regex or Ignore Match
        elif pattern_type is type(word_regex) or pattern_type is type(ignoring):
            if pattern_type is type(ignoring):
                pattern = pattern.regex

            m = pattern.match(text)
            if m:
                text = skip(
                    self.skipper, text[len(m.group(0)) :], skip_ws, skip_comments
                )
                if pattern_type is type(ignoring):
                    return r(None, text)  # Ignore match result
                else:
                    return r(m.group(0), text)  # Return the matched string
            else:
                raise SyntaxError()

        # 3f. Sequence/Quantifier Match (Tuple)
        elif pattern_type is type((None,)):
            result = []
            n = 1  # Current quantifier (-2, -1, 0, 1, 2, ...)
            for p in pattern:
                # Quantifier definition (must be type(0))
                if type(p) is type(0):
                    n = p
                else:
                    if n > 0:
                        # Required or Fixed Repetition (n times)
                        for _ in range(n):
                            result, text = self.parse_line(
                                text, p, result, skip_ws, skip_comments, input_length
                            )
                    elif n == 0:
                        # Optional Repetition (0 or 1 time)
                        try:
                            new_result, new_text = self.parse_line(
                                text, p, result, skip_ws, skip_comments, input_length
                            )
                            result, text = new_result, new_text
                        except SyntaxError:
                            pass  # Optional failed, continue with old result/text
                    elif n < 0:
                        # ZeroOrMore (-1) or OneOrMore (-2) Loop
                        found = False
                        while True:
                            try:
                                new_result, new_text = self.parse_line(
                                    text,
                                    p,
                                    result,
                                    skip_ws,
                                    skip_comments,
                                    input_length,
                                )
                                result, text, found = new_result, new_text, True
                            except SyntaxError:
                                break  # Loop terminates when parse fails

                        # OneOrMore (-2) failed if nothing was found
                        if n == -2 and not found:
                            raise SyntaxError()
                    n = 1  # Reset quantifier for the next pattern
            return r(result, text)

        # 3g. Choice Match (List)
        elif pattern_type is type([]):
            result = []
            found = False
            for p in pattern:
                try:
                    # Attempt to parse with the current choice pattern
                    result, text = self.parse_line(
                        text, p, result, skip_ws, skip_comments, input_length
                    )
                    found = True
                except SyntaxError:
                    pass
                if found:
                    break  # Success, stop checking choices

            if found:
                return r(result, text)
            else:
                raise SyntaxError()

        # 3h. Illegal Pattern
        else:
            raise SyntaxError("illegal type in grammar: " + str(pattern_type))


# --- Plain Module API ---


def parse_line(
    text_line,
    pattern,
    result_so_far=None,
    skip_ws=True,
    skip_comments=None,
    output_pos=False,
):
    """
    Parses a single line of text against a pyPEG pattern.

    This function initializes a new Parser instance for a single operation.

    :param text_line: Text to parse.
    :param pattern: pyPEG language description.
    :param result_so_far: Initial list of AST nodes.
    :param skip_ws: Flag if whitespace should be skipped (default: True).
    :param skip_comments: Python function returning pyPEG for matching comments.
    :param output_pos: Flag whether to insert position information into the pyAST.
    :returns: (pyAST, text_rest) - The resulting AST and the remaining unparsed text.
    """
    if result_so_far is None:
        result_so_far = []
    p = Parser()
    if output_pos:
        length = len(text_line)
    else:
        length = 0

    text = skip(p.skipper, text_line, skip_ws, skip_comments)
    ast, text = p.parse_line(
        text, pattern, result_so_far, skip_ws, skip_comments, length
    )

    return ast, text


def parse(language, line_source, skip_ws=True, skip_comments=None, output_pos=False):
    """
    Parses an entire source (multiple lines) against a pyPEG language definition.

    :param language: The top-level pyPEG language function or structure.
    :param line_source: A file_input.FileInput object (or iterable yielding lines).
    :param skip_ws: Flag if whitespace should be skipped (default: True).
    :param skip_comments: Python function returning pyPEG for matching comments.
    :param output_pos: Flag whether to insert position information into the pyAST.
    :returns: pyAST - The final Abstract Syntax Tree.
    :raises: SyntaxError if the source is not fully parsed or contains errors.
    """
    lines, text_len, line_no = [], 0, 0
    p = None  # Initialize p in the outer scope to avoid the shadowing warning

    # Resolve lazy top-level language function if necessary
    while type(language) is type(lambda x: 0):
        language = language()

    # Concatenate all input lines into a single string
    orig = ""
    ld = 0
    for line in line_source:
        if line_source.isfirstline():
            ld = 1
        else:
            ld += 1
        lines.append((len(orig), ld))
        orig += line
    text_len = len(orig)

    try:
        p = Parser()
        if output_pos:
            length = len(orig)
        else:
            length = 0

        text = skip(p.skipper, orig, skip_ws, skip_comments)
        result, text = p.parse_line(text, language, [], skip_ws, skip_comments, length)

        # Final check: did we consume all non-whitespace/comment text?
        if text:
            raise SyntaxError()
        text_len = 0

    except SyntaxError:
        # Check if p was initialized before the error (it should be, unless memory failed earlier)
        if p is None:
            raise  # Re-raise if parser wasn't even initialized

        # Calculate error position for reporting using p.rest_length
        parsed = text_len - p.rest_length

        for n, ld in lines:
            if n >= parsed:
                if n == parsed:
                    line_no += 1
                break
            else:
                line_no = ld

        line_cont = orig.splitlines()[line_no - 1]

        raise SyntaxError(
            f"syntax error in {line_source.filename()}:{line_no}: {line_cont}"
        )

    return result
