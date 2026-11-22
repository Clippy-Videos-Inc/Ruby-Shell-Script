"""Ruby Shell Script (.rss) -- a Ruby-flavored scripting language for
shell automation, implemented as a tree-walking interpreter in Python.

Public API:
    from rss import run_source, run_file
"""

from .parser import parse
from .interpreter import Interpreter
from .errors import RSSRuntimeError
from .lexer import LexError
from .parser import ParseError

__version__ = "0.1.0"
__all__ = [
    "parse", "Interpreter", "RSSRuntimeError", "LexError", "ParseError",
    "run_source", "run_file", "__version__",
]


def run_source(source: str, argv=None, script_path: str = "main.rss") -> int:
    program = parse(source)
    interp = Interpreter(argv=argv, script_path=script_path)
    return interp.run(program)


def run_file(path: str, argv=None) -> int:
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    return run_source(source, argv=argv, script_path=path)
