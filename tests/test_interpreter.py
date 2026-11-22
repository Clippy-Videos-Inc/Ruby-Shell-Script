"""
Automated tests for the Ruby Shell Script interpreter.

Run with: python3 -m pytest tests/  (or: python3 tests/test_interpreter.py)
"""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rss import run_source, RSSRuntimeError
from rss.parser import ParseError
from rss.lexer import LexError


def run(src, argv=None):
    buf = io.StringIO()
    with redirect_stdout(buf):
        run_source(src, argv=argv)
    return buf.getvalue()


class TestLiteralsAndArithmetic(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(run("puts 1 + 2 * 3"), "7\n")
        self.assertEqual(run("puts (1 + 2) * 3"), "9\n")
        self.assertEqual(run("puts 10 / 3"), "3\n")
        self.assertEqual(run("puts 10.0 / 4"), "2.5\n")
        self.assertEqual(run("puts 2 ** 10"), "1024\n")
        self.assertEqual(run("puts -5 + 3"), "-2\n")
        self.assertEqual(run("puts 7 % 3"), "1\n")

    def test_strings_and_interpolation(self):
        self.assertEqual(run('puts "hi " + "there"'), "hi there\n")
        self.assertEqual(run('x = 3\nputs "x is #{x}"'), "x is 3\n")
        self.assertEqual(run('puts "a#{1+1}b#{2+2}c"'), "a2b4c\n")

    def test_truthiness(self):
        self.assertEqual(run('puts "yes" if 0'), "yes\n")   # 0 is truthy
        self.assertEqual(run('puts "yes" if ""'), "yes\n")  # "" is truthy
        self.assertEqual(run('puts "no" if nil'), "")
        self.assertEqual(run('puts "no" if false'), "")


class TestControlFlow(unittest.TestCase):
    def test_if_elsif_else(self):
        src = """
        x = 5
        if x > 10
          puts "big"
        elsif x > 3
          puts "medium"
        else
          puts "small"
        end
        """
        self.assertEqual(run(src), "medium\n")

    def test_while_and_break_next(self):
        src = """
        i = 0
        out = []
        while i < 10
          i += 1
          next if i % 2 == 0
          break if i > 7
          out.push(i)
        end
        puts out.inspect
        """
        self.assertEqual(run(src), "[1, 3, 5, 7]\n")

    def test_for_in_range(self):
        self.assertEqual(run("for i in 1..3\n  print i\nend"), "123")

    def test_statement_modifiers(self):
        self.assertEqual(run('puts "hi" unless false'), "hi\n")
        self.assertEqual(run('puts "hi" if true'), "hi\n")


class TestFunctions(unittest.TestCase):
    def test_basic_function(self):
        src = """
        def add(a, b)
          return a + b
        end
        puts add(2, 3)
        """
        self.assertEqual(run(src), "5\n")

    def test_default_args(self):
        src = """
        def greet(name, greeting = "Hi")
          return "#{greeting}, #{name}"
        end
        puts greet("Sam")
        puts greet("Sam", "Yo")
        """
        self.assertEqual(run(src), "Hi, Sam\nYo, Sam\n")

    def test_recursion(self):
        src = """
        def fact(n)
          return 1 if n <= 1
          return n * fact(n - 1)
        end
        puts fact(6)
        """
        self.assertEqual(run(src), "720\n")

    def test_implicit_last_expression_return(self):
        src = """
        def square(n)
          n * n
        end
        puts square(7)
        """
        self.assertEqual(run(src), "49\n")


class TestCollections(unittest.TestCase):
    def test_array_methods(self):
        src = """
        a = [3, 1, 2]
        puts a.sort.inspect
        puts a.map do |x| x * 10 end
        puts a.select do |x| x > 1 end .inspect
        puts a.sum
        """
        out = run(src)
        self.assertIn("[1, 2, 3]", out)
        self.assertIn("30\n10\n20", out)
        self.assertIn("[3, 2]", out)
        self.assertIn("6", out)

    def test_hash_methods(self):
        src = """
        h = {a: 1, b: 2}
        puts h.keys.inspect
        puts h["a"]
        h["c"] = 3
        puts h.size
        """
        self.assertEqual(run(src), '["a", "b"]\n1\n3\n')

    def test_range(self):
        self.assertEqual(run("puts (1..5).to_a.inspect"), "[1, 2, 3, 4, 5]\n")
        self.assertEqual(run("puts (1..5).sum"), "15\n")


class TestBlocksAndClosures(unittest.TestCase):
    def test_each(self):
        self.assertEqual(run('[1,2,3].each do |x| print x end'), "123")

    def test_closure_over_outer_var(self):
        src = """
        total = 0
        [1,2,3].each do |x|
          total += x
        end
        puts total
        """
        self.assertEqual(run(src), "6\n")


class TestErrorHandling(unittest.TestCase):
    def test_rescue_catches_runtime_error(self):
        src = """
        begin
          x = 1 / 0
        rescue => e
          puts "caught"
        end
        """
        self.assertEqual(run(src), "caught\n")

    def test_ensure_always_runs(self):
        src = """
        begin
          puts "try"
        ensure
          puts "ensure"
        end
        """
        self.assertEqual(run(src), "try\nensure\n")

    def test_undefined_variable_raises(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = run_source("puts nope_not_defined")
        self.assertEqual(code, 1)


class TestShellIntegration(unittest.TestCase):
    def test_backtick_capture(self):
        self.assertEqual(run('puts `echo hi`'), "hi\n")

    def test_env_vars(self):
        src = """
        $RSS_TEST_VAR = "hello-env"
        puts $RSS_TEST_VAR
        """
        self.assertEqual(run(src), "hello-env\n")
        self.assertEqual(os.environ.get("RSS_TEST_VAR"), "hello-env")


class TestArgv(unittest.TestCase):
    def test_argv_passed_through(self):
        self.assertEqual(run("puts ARGV.join(',')", argv=["a", "b"]), "a,b\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
