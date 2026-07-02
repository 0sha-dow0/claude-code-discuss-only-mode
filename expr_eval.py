"""Arithmetic expression evaluator.

Public surface: ``evaluate(expression: str) -> float``.

A real tokenizer plus recursive-descent parser. No use of
eval/exec/ast.literal_eval/compile and no I/O. The only exception types
that ever escape are ``ValueError`` (all malformed input, lexical or
structural) and ``ZeroDivisionError`` (division by a zero-valued operand,
including zero produced by a sub-expression).

Grammar::

    expr    := term (('+' | '-') term)*
    term    := factor (('*' | '/') factor)*
    factor  := ('+' | '-') factor | primary
    primary := number | '(' expr ')'
    number  := DIGITS ('.' DIGITS)?
"""

import math
from typing import List, NamedTuple, Optional

# ---------------------------------------------------------------------------
# Unit 1 — Token model
# ---------------------------------------------------------------------------

# The eight enumerated token types. Using distinct string constants keeps the
# representation immutable and readable; consumers compare by identity/equality
# against these module-level names.
NUMBER = "NUMBER"
PLUS = "PLUS"
MINUS = "MINUS"
STAR = "STAR"
SLASH = "SLASH"
LPAREN = "LPAREN"
RPAREN = "RPAREN"
EOF = "EOF"


class Token(NamedTuple):
    """An immutable (type, value) token.

    ``type`` is always one of the eight enumerated constants above. For a
    ``NUMBER`` token, ``value`` is a finite Python ``float`` parsed from the
    lexeme. For every other token type, ``value`` is ``None``.
    """

    type: str
    value: Optional[float]


# ---------------------------------------------------------------------------
# Unit 2 — Tokenizer
# ---------------------------------------------------------------------------

# Single-character tokens (operators and parentheses).
_SINGLE_CHAR_TOKENS = {
    "+": PLUS,
    "-": MINUS,
    "*": STAR,
    "/": SLASH,
    "(": LPAREN,
    ")": RPAREN,
}

# Only ASCII space and tab act as separators between tokens.
_SEPARATORS = (" ", "\t")

_DIGITS = "0123456789"


def tokenize(expression: str) -> List[Token]:
    """Scan ``expression`` into a list of tokens terminated by one EOF token.

    Owns all character-level validity: charset, number shape, and separator
    whitespace. Performs no structural judgement (operator ordering, paren
    balance). Raises ``ValueError`` on any lexical violation.
    """
    if not isinstance(expression, str):
        # Defensive: contract says callers pass str; never leak a TypeError.
        raise ValueError("expression must be a string")

    tokens: List[Token] = []
    i = 0
    n = len(expression)

    while i < n:
        ch = expression[i]

        # Separator whitespace: skip.
        if ch in _SEPARATORS:
            i += 1
            continue

        # Single-character operator/paren tokens.
        single = _SINGLE_CHAR_TOKENS.get(ch)
        if single is not None:
            tokens.append(Token(single, None))
            i += 1
            continue

        # Numbers: DIGITS ('.' DIGITS)?  — must begin with a digit, so a
        # leading '.' (e.g. ".5" or a bare ".") is rejected as malformed.
        if ch in _DIGITS:
            start = i
            while i < n and expression[i] in _DIGITS:
                i += 1
            # Optional single fractional part: '.' followed by one or more
            # digits. A trailing dot (e.g. "5.") or a second dot is invalid.
            if i < n and expression[i] == ".":
                i += 1
                if i >= n or expression[i] not in _DIGITS:
                    raise ValueError(
                        "malformed number: '.' must be followed by a digit"
                    )
                while i < n and expression[i] in _DIGITS:
                    i += 1
            lexeme = expression[start:i]
            value = float(lexeme)  # Never raises for a valid decimal literal.
            # Reject astronomically long literals that overflow to inf; the
            # NUMBER contract requires a finite value.
            if not math.isfinite(value):
                raise ValueError("numeric literal out of range: " + lexeme)
            tokens.append(Token(NUMBER, value))
            continue

        # A lone '.' (not preceded by a digit) or any other character is an
        # invalid character.
        if ch == ".":
            raise ValueError("malformed number: unexpected '.'")
        raise ValueError("invalid character: " + repr(ch))

    tokens.append(Token(EOF, None))
    return tokens


# ---------------------------------------------------------------------------
# Unit 3 — Parser cursor
# ---------------------------------------------------------------------------

_EXPECTED_NAME = {
    NUMBER: "number",
    PLUS: "'+'",
    MINUS: "'-'",
    STAR: "'*'",
    SLASH: "'/'",
    LPAREN: "'('",
    RPAREN: "')'",
    EOF: "end of input",
}


class Cursor:
    """A stateful, single-threaded reader over an EOF-terminated token list.

    Never mutates the underlying list. ``peek`` past the last real token keeps
    returning the terminal EOF token; ``advance`` on EOF is a no-op.
    """

    __slots__ = ("_tokens", "_index", "_last")

    def __init__(self, tokens: List[Token]) -> None:
        # Precondition (guaranteed by tokenize): non-empty, EOF-terminated.
        self._tokens = tokens
        self._index = 0
        self._last = len(tokens) - 1

    def peek(self) -> Token:
        """Return the current token without advancing."""
        return self._tokens[self._index]

    def advance(self) -> Token:
        """Return the current token, then move forward by one (EOF stays)."""
        current = self._tokens[self._index]
        if current.type != EOF:
            self._index += 1
        return current

    def expect(self, token_type: str) -> Token:
        """Consume one token of ``token_type`` or raise ValueError (no advance)."""
        current = self._tokens[self._index]
        if current.type != token_type:
            raise ValueError(
                "expected {} but found {}".format(
                    _EXPECTED_NAME[token_type], _EXPECTED_NAME[current.type]
                )
            )
        return self.advance()

    def at_end(self) -> bool:
        """True when the current token is EOF."""
        return self._tokens[self._index].type == EOF


# ---------------------------------------------------------------------------
# Units 4-7 — recursive-descent grammar group
# ---------------------------------------------------------------------------

# Token types that can begin a factor/primary as an operand start.
_FACTOR_START = frozenset({NUMBER, LPAREN, PLUS, MINUS})


def parse_primary(cursor: Cursor) -> float:
    """primary := number | '(' expr ')'."""
    token = cursor.peek()
    if token.type == NUMBER:
        cursor.advance()
        # value is a finite float guaranteed by the tokenizer.
        return token.value  # type: ignore[return-value]
    if token.type == LPAREN:
        cursor.advance()
        value = parse_expr(cursor)
        cursor.expect(RPAREN)
        return value
    raise ValueError(
        "expected number or '(' but found " + _EXPECTED_NAME[token.type]
    )


def parse_factor(cursor: Cursor) -> float:
    """factor := ('+' | '-') factor | primary (unary, right-recursive)."""
    token = cursor.peek()
    if token.type == PLUS:
        cursor.advance()
        return parse_factor(cursor)
    if token.type == MINUS:
        cursor.advance()
        return -parse_factor(cursor)
    return parse_primary(cursor)


def parse_term(cursor: Cursor) -> float:
    """term := factor (('*' | '/') factor)*  (left-associative)."""
    value = parse_factor(cursor)
    while True:
        op = cursor.peek().type
        if op == STAR:
            cursor.advance()
            value = value * parse_factor(cursor)
        elif op == SLASH:
            cursor.advance()
            divisor = parse_factor(cursor)
            if divisor == 0.0:
                raise ZeroDivisionError("division by zero")
            value = value / divisor
        else:
            return value


def parse_expr(cursor: Cursor) -> float:
    """expr := term (('+' | '-') term)*  (left-associative)."""
    value = parse_term(cursor)
    while True:
        op = cursor.peek().type
        if op == PLUS:
            cursor.advance()
            value = value + parse_term(cursor)
        elif op == MINUS:
            cursor.advance()
            value = value - parse_term(cursor)
        else:
            return value


# ---------------------------------------------------------------------------
# Unit 8 — public facade
# ---------------------------------------------------------------------------


def evaluate(expression: str) -> float:
    """Evaluate an arithmetic expression string and return a float.

    Raises ``ValueError`` for all malformed input (empty/whitespace-only,
    unbalanced/empty parens, missing operands, adjacent operands, invalid
    characters, malformed numbers) and ``ZeroDivisionError`` for division by
    a zero-valued operand (including zero from a sub-expression). No other
    exception type escapes. Pure and reentrant: each call builds its own
    token list and cursor.
    """
    try:
        tokens = tokenize(expression)
        cursor = Cursor(tokens)
        result = parse_expr(cursor)
        if not cursor.at_end():
            # Leftover tokens: e.g. "2 3", "1+2)", trailing junk.
            raise ValueError(
                "unexpected trailing token: "
                + _EXPECTED_NAME[cursor.peek().type]
            )
        return float(result)
    except (ValueError, ZeroDivisionError):
        # These are the only two contract exceptions; pass them through.
        raise
    except Exception as exc:  # pragma: no cover - defensive backstop
        # Any other internally-raised exception is re-raised as ValueError so
        # that only {ValueError, ZeroDivisionError} ever cross the boundary.
        raise ValueError("malformed expression") from exc
