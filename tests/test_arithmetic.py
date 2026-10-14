import json
import subprocess
import sys
import unittest
from pathlib import Path

from arithmetic import judge_latex


class ArithmeticTests(unittest.TestCase):
    def test_valid_equations(self):
        cases = ["2+3=5", "-2+3=1", "2+3*4=14", "(2+3)*4=20",
                 "0.1+0.2=0.3", "-(-2)=2", "1/3+1/6=1/2", "2×3=6",
                 "12÷3=4", r"\frac{1}{2}+\frac{1}{3}=\frac{5}{6}",
                 r"\frac{\frac{1}{2}}{3}=\frac{1}{6}",
                 r"\left(2+3\right)\times4=20", "$2+3=5$", "2 + 3 = 5",
                 r"\dfrac{1}{2}=.5", "1 2 + 8 = 2 0", "1.0=1"]
        for expression in cases:
            with self.subTest(expression=expression):
                self.assertEqual(judge_latex(expression)["status"], "correct")

    def test_incorrect_equations(self):
        for expression in ["2+3=6", "0.1+0.2=0.3000000001", "2+3*4=20", "1/3=0.333"]:
            with self.subTest(expression=expression):
                self.assertEqual(judge_latex(expression)["status"], "incorrect")

    def test_expression_without_equals(self):
        result = judge_latex("1/3+1/6")
        self.assertEqual((result["status"], result["left_value"]), ("computed", "1/2"))

    def test_invalid_or_out_of_scope(self):
        cases = ["", " ", "2+=3", "=3", "3=", "1=1=1", "2(3)=6",
                 "x+2=4", "2^3=8", r"\sqrt{4}=2", r"\sum_{i=1}^{3}i=6",
                 r"\frac12=.5", "(2+3=5", "2//3=0", "2**3=8",
                 "__import__('os').system('echo UNSAFE')", "[1][0]=1", "1<2",
                 r"\timesfoo=2", "$2=2", "2e3=2000"]
        for expression in cases:
            with self.subTest(expression=expression):
                self.assertEqual(judge_latex(expression)["status"], "ungradable")

    def test_zero_division(self):
        for expression in ["1/0=1", r"\frac{1}{0}=1", "1/(2-2)=0"]:
            result = judge_latex(expression)
            self.assertEqual(result["status"], "ungradable")
            self.assertEqual(result["error"]["code"], "division_by_zero")

    def test_resource_limits(self):
        for expression in ["9" * 129, "(" * 33 + "1" + ")" * 33, "1" * 513, " " * 4097]:
            self.assertEqual(judge_latex(expression)["status"], "ungradable")

    def test_text_cli_does_not_require_torch(self):
        script = Path(__file__).resolve().parents[1] / "recognize_math.py"
        completed = subprocess.run([sys.executable, str(script), "--latex", "2+3=5"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "correct")


if __name__ == "__main__":
    unittest.main()
