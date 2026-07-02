import math
import pytest
from expr_eval import evaluate


# ---- basic arithmetic & result type ----
@pytest.mark.parametrize("expr,expected", [
    ("1", 1.0),
    ("1+2", 3.0),
    ("2*3", 6.0),
    ("10-2-3", 5.0),          # left-assoc subtraction
    ("100/5/2", 10.0),        # left-assoc division
    ("2+3*4", 14.0),          # precedence
    ("(2+3)*4", 20.0),
    ("2*-3", -6.0),           # unary after binary
    ("-(3+4)", -7.0),
    ("1++2", 3.0),
    ("--5", 5.0),
    ("-5", -5.0),
    ("+5", 5.0),
    ("3.5+1.5", 5.0),
    ("2*(3+4)-5", 9.0),
    ("6/2*3", 9.0),
    ("1-2*3", -5.0),
    ("(1)", 1.0),
    ("((2))", 2.0),
    ("0", 0.0),
    ("00", 0.0),
    ("2*-+-3", 6.0),
    ("  1  +  2  ", 3.0),
    ("\t1\t+\t2\t", 3.0),
])
def test_valid(expr, expected):
    result = evaluate(expr)
    assert isinstance(result, float)
    assert result == expected


# ---- division by zero ----
@pytest.mark.parametrize("expr", [
    "1/0",
    "1/(2-2)",
    "0/0",
    "5/(1-1)",
    "1/-0",
    "10/0.0",
    "1/2/0",
])
def test_zero_division(expr):
    with pytest.raises(ZeroDivisionError):
        evaluate(expr)


# ---- malformed input -> ValueError ----
@pytest.mark.parametrize("expr", [
    "",
    "   ",
    "\t",
    "(1+2",
    "1+2)",
    "()",
    "1+",
    "*5",
    "1+*2",
    "2 3",
    "2&3",
    "5.",
    ".5",
    "1.2.3",
    "1 2",
    "1. 5",
    ".",
    "+",
    "-",
    "(",
    ")",
    "1+()",
    "3*",
    "/5",
    "((1)",
    "(1))",
    "1..2",
    "5.e",
    "2^3",
    "2%3",
    "abc",
    "1+2 3",
    "0x10",
    "1,2",
])
def test_value_error(expr):
    with pytest.raises(ValueError):
        evaluate(expr)


# ---- number rules ----
def test_leading_dot_invalid():
    with pytest.raises(ValueError):
        evaluate(".5")

def test_trailing_dot_invalid():
    with pytest.raises(ValueError):
        evaluate("5.")

def test_decimal_valid():
    assert evaluate("3.14") == pytest.approx(3.14)
    assert evaluate("0.5") == 0.5


# ---- only ValueError / ZeroDivisionError escape ----
@pytest.mark.parametrize("expr", ["", "@@@", "5.", "1/0", "((((1))))", "1+", None if False else "###"])
def test_only_contract_exceptions(expr):
    try:
        evaluate(expr)
    except (ValueError, ZeroDivisionError):
        pass
    except Exception as e:
        pytest.fail("Unexpected exception type: %r" % (e,))


# ---- deep nesting / recursion adversarial ----
def test_deep_nesting():
    depth = 200
    expr = "(" * depth + "1" + ")" * depth
    try:
        assert evaluate(expr) == 1.0
    except (ValueError, ZeroDivisionError):
        # acceptable if it maps recursion overflow to ValueError
        pass

def test_many_unary():
    expr = "-" * 100 + "1"
    result = evaluate(expr)
    assert result == 1.0  # even count of minus


def test_non_string_input():
    # contract says str; must not leak TypeError
    try:
        evaluate(123)
    except (ValueError, ZeroDivisionError):
        pass
    except Exception as e:
        pytest.fail("Leaked %r" % (e,))
