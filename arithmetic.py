"""Restricted arithmetic over CoMER LaTeX; no Python eval or exec."""
import re
from fractions import Fraction


class ArithmeticError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def normalize_latex(text):
    if not isinstance(text, str) or len(text) > 4096:
        raise ArithmeticError("input_limit", "Expression must be a string of at most 4096 characters.")
    text = text.strip()
    for left, right in [("$$", "$$"), ("$", "$"), (r"\(", r"\)"), (r"\[", r"\]")]:
        if text.startswith(left) and text.endswith(right) and len(text) >= len(left) + len(right):
            text = text[len(left):-len(right)]
            break
    text = re.sub(r"\s+", "", text)
    text = text.translate(str.maketrans({"×": "*", "÷": "/", "−": "-", "＋": "+", "＝": "="}))
    text = re.sub(r"\\(?:left|right)(?![a-zA-Z])", "", text)
    for command in [r"\,", r"\;", r"\!", r"\:"]:
        text = text.replace(command, "")
    text = re.sub(r"\\(?:times|cdot)(?![a-zA-Z])", "*", text)
    text = re.sub(r"\\div(?![a-zA-Z])", "/", text)
    text = re.sub(r"\\(?:dfrac|tfrac)(?![a-zA-Z])", r"\\frac", text)
    if len(text) > 512:
        raise ArithmeticError("input_limit", "Normalized expression exceeds 512 characters.")
    return text


def tokenize(text):
    pattern = re.compile(r"\\frac(?![a-zA-Z])|(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)|[+*/(){}-]")
    tokens = []
    pos = 0
    while pos < len(text):
        match = pattern.match(text, pos)
        if not match:
            raise ArithmeticError("unsupported_symbol", "Unsupported symbol at position {}: {!r}".format(pos, text[pos:pos + 16]))
        tokens.append(match.group())
        pos = match.end()
    if len(tokens) > 256:
        raise ArithmeticError("input_limit", "Expression exceeds 256 tokens.")
    return tokens


class Parser:
    def __init__(self, text):
        self.tokens = tokenize(text)
        self.position = 0
        self.depth = 0

    def peek(self):
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self, expected=None):
        token = self.peek()
        if token is None or (expected is not None and token != expected):
            raise ArithmeticError("invalid_expression", "Expected {!r}, found {!r}.".format(expected, token))
        self.position += 1
        return token

    def bounded(self, value):
        if max(value.numerator.bit_length(), value.denominator.bit_length()) > 4096:
            raise ArithmeticError("numeric_limit", "Intermediate value exceeds the arithmetic limit.")
        return value

    def parse(self):
        if not self.tokens:
            raise ArithmeticError("empty_expression", "Expression is empty.")
        value = self.expression()
        if self.peek() is not None:
            raise ArithmeticError("invalid_expression", "Unexpected token {!r}; implicit multiplication is unsupported.".format(self.peek()))
        return value

    def expression(self):
        value = self.term()
        while self.peek() in ("+", "-"):
            operator = self.take()
            right = self.term()
            value = self.bounded(value + right if operator == "+" else value - right)
        return value

    def term(self):
        value = self.factor()
        while self.peek() in ("*", "/"):
            operator = self.take()
            right = self.factor()
            if operator == "/" and right == 0:
                raise ArithmeticError("division_by_zero", "Division by zero.")
            value = self.bounded(value * right if operator == "*" else value / right)
        return value

    def group(self, opening):
        closing = ")" if opening == "(" else "}"
        self.take(opening)
        value = self.expression()
        self.take(closing)
        return value

    def factor(self):
        self.depth += 1
        if self.depth > 32:
            raise ArithmeticError("input_limit", "Nesting depth exceeds 32.")
        try:
            token = self.peek()
            if token in ("+", "-"):
                operator = self.take()
                value = self.factor()
                return value if operator == "+" else -value
            if token in ("(", "{"):
                return self.group(token)
            if token == r"\frac":
                self.take()
                numerator = self.group("{")
                denominator = self.group("{")
                if denominator == 0:
                    raise ArithmeticError("division_by_zero", "Fraction denominator is zero.")
                return self.bounded(numerator / denominator)
            if token is None or not re.fullmatch(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", token):
                raise ArithmeticError("invalid_expression", "Expected a number or a grouped expression.")
            self.take()
            if len(token) > 128:
                raise ArithmeticError("numeric_limit", "Number exceeds 128 characters.")
            return self.bounded(Fraction(token))
        finally:
            self.depth -= 1


def format_value(value):
    return str(value.numerator) if value.denominator == 1 else "{}/{}".format(value.numerator, value.denominator)


def judge_latex(text):
    result = {"recognized_latex": text, "normalized_expression": None,
              "status": "ungradable", "label": "无法判定", "left_value": None,
              "right_value": None, "error": None,
              "basis": "Judgment applies to recognized text; OCR correctness is not independently established."}
    try:
        expression = normalize_latex(text)
        result["normalized_expression"] = expression
        if expression.count("=") > 1:
            raise ArithmeticError("unsupported_equation", "Only one equals sign is supported.")
        if "=" not in expression:
            result["left_value"] = format_value(Parser(expression).parse())
            result.update(status="computed", label="已计算")
        else:
            left, right = expression.split("=")
            left_value, right_value = Parser(left).parse(), Parser(right).parse()
            result["left_value"], result["right_value"] = format_value(left_value), format_value(right_value)
            correct = left_value == right_value
            result.update(status="correct" if correct else "incorrect", label="正确" if correct else "错误")
    except ArithmeticError as error:
        result["error"] = {"code": error.code, "message": str(error)}
    return result
