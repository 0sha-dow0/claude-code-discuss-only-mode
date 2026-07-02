import math
import pytest

from expr_eval import evaluate


# --- basic values & float return type ---
@pytest.mark.parametrize("expr,expected", [
    ("1", 1.0),
    ("42", 42.0),
    ("3.14", 3.14),
    ("0", 0.0),
    ("007", 7.0),
    ("10.0", 10.0),
])
def test_numbers(expr, expected):
    r = evaluate(expr)
    assert r == expected
    assert isinstance(r, float)


# --- precedence ---
@pytest.mark.parametrize("expr,expected", [
    ("2+3*4", 14.0),
    ("2*3+4", 10.0),
    ("2+3-1", 4.0),
    ("2*3/6", 1.0),
    ("1+2*3-4/2", 5.0),
    ("(2+3)*4", 20.0),
    ("2*(3+4)", 14.0),
])
def test_precedence(expr, expected):
    assert evaluate(expr) == expected


# --- left associativity ---
@pytest.mark.parametrize("expr,expected", [
    ("10-2-3", 5.0),
    ("100/5/2", 10.0),
    ("20/2*5", 50.0),
    ("8-3+1", 6.0),
])
def test_left_assoc(expr, expected):
    assert evaluate(expr) == expected


# --- unary ---
@pytest.mark.parametrize("expr,expected", [
    ("-5", -5.0),
    ("+5", 5.0),
    ("2*-3", -6.0),
    ("-(3+4)", -7.0),
    ("1++2", 3.0),
    ("1--2", 3.0),
    ("--5", 5.0),
    ("2*-+-3", 6.0),
    ("-2*-3", 6.0),
    ("3+-2", 1.0),
    ("(-3)", -3.0),
])
def test_unary(expr, expected):
    assert evaluate(expr) == expected


# --- whitespace ---
@pytest.mark.parametrize("expr,expected", [
    ("  1 + 2 ", 3.0),
    ("\t2\t*\t3", 6.0),
    (" ( 1 + 2 ) * 3 ", 9.0),
])
def test_whitespace(expr, expected):
    assert evaluate(expr) == expected


# --- division by zero ---
@pytest.mark.parametrize("expr", [
    "1/0",
    "1/(2-2)",
    "0/0",
    "5/0.0",
    "1/-0",
    "(4+6)/(5-5)",
])
def test_div_zero(expr):
    with pytest.raises(ZeroDivisionError):
        evaluate(expr)


# --- malformed -> ValueError ---
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
    "+",
    "-",
    "(",
    ")",
    "1 2 3",
    "3*",
    "/5",
    "1..2",
    "1.",
    ".",
    "3.+2",
    "2)(3",
    "((1)",
    "1 .5",
    "1. 5",
    "a",
    "2^3",
    "2%3",
    "1e5",
])
def test_malformed(expr):
    with pytest.raises(ValueError):
        evaluate(expr)


# --- whitespace inside number is invalid ---
@pytest.mark.parametrize("expr", ["1 2", "3 . 5", "12 34"])
def test_ws_in_number(expr):
    with pytest.raises(ValueError):
        evaluate(expr)


# --- exact exception types are distinct ---
def test_zero_not_valueerror_hierarchy():
    # ZeroDivisionError must be raised, and ValueError must NOT be raised
    # for a well-formed div-by-zero (they are unrelated types).
    with pytest.raises(ZeroDivisionError):
        evaluate("1/0")


def test_no_eval_import():
    import expr_eval, inspect, ast
    tree = ast.parse(inspect.getsource(expr_eval))
    # Strip the module docstring which legitimately names these APIs.
    banned = {"eval", "exec", "compile", "literal_eval"}
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                called.add(f.id)
            elif isinstance(f, ast.Attribute):
                called.add(f.attr)
    assert not (banned & called)


# --- nested / deep ---
def test_deep_nesting():
    assert evaluate("((((5))))") == 5.0
    assert evaluate("-(-(-(3)))") == -3.0


# --- fractional math ---
def test_fractions():
    assert evaluate("0.1+0.2") == pytest.approx(0.3)
    assert evaluate("1/4") == 0.25
    assert evaluate("3/2") == 1.5


# --- non-str input should be ValueError not TypeError ---
@pytest.mark.parametrize("bad", [None, 5, 3.2, ["1+1"]])
def test_non_str(bad):
    with pytest.raises(ValueError):
        evaluate(bad)


# --- large integer literal (grammar-valid) ---
def test_large_literal():
    # A 400-digit integer is grammatically valid. Spec says always return a
    # float. Record actual behavior.
    big = "9" * 400
    try:
        r = evaluate(big)
        assert isinstance(r, float)
    except ValueError:
        pytest.fail("grammar-valid large literal raised ValueError instead of returning a float")
