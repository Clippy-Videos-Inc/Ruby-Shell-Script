"""
CLI entry point for Ruby Shell Script.

Usage:
    rss script.rss [args...]      run a .rss script
    rss -e "puts 1 + 1"           run an inline one-liner
    rss                           start the interactive REPL
    rss -v / --version            print the version
"""

from __future__ import annotations

import sys

from .lexer import LexError
from .parser import parse, ParseError
from .interpreter import Interpreter
from .errors import RSSRuntimeError
from . import __version__


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if argv and argv[0] in ("-v", "--version"):
        print(f"Ruby Shell Script {__version__}")
        return 0

    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    if argv and argv[0] == "-e":
        if len(argv) < 2:
            print("rss: -e needs a script string", file=sys.stderr)
            return 1
        return _run(argv[1], argv[2:], "-e")

    if not argv:
        return repl()

    path = argv[0]
    script_args = argv[1:]
    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"rss: can't read {path}: {e}", file=sys.stderr)
        return 1
    return _run(source, script_args, path)


def _run(source: str, script_args, path: str) -> int:
    try:
        program = parse(source)
    except LexError as e:
        print(f"rss: {e}", file=sys.stderr)
        return 1
    except ParseError as e:
        print(f"rss: {e}", file=sys.stderr)
        return 1
    interp = Interpreter(argv=script_args, script_path=path)
    return interp.run(program)


def repl() -> int:
    print(f"Ruby Shell Script {__version__} -- interactive mode (:exit to quit)")
    interp = Interpreter(argv=[], script_path="(repl)")
    buffer = ""
    depth_openers = {"if", "unless", "while", "until", "for", "def", "begin", "loop", "do"}
    while True:
        try:
            prompt = "rss> " if not buffer else "...> "
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not buffer and line.strip() in (":exit", ":quit", "exit", "quit"):
            return 0
        buffer += line + "\n"
        # naive heuristic: keep reading until `end` count balances out, so
        # multi-line if/while/def blocks can be typed interactively.
        opens = sum(1 for tok in buffer.split() if tok in depth_openers)
        closes = buffer.split().count("end")
        if opens > closes:
            continue
        try:
            program = parse(buffer)
        except (LexError, ParseError) as e:
            print(f"rss: {e}", file=sys.stderr)
            buffer = ""
            continue
        try:
            result = interp.run_block(program.body, interp.globals)
            if result is not None:
                from .values import inspect
                print("=> " + inspect(result))
        except Exception as e:  # keep the REPL alive on runtime errors
            print(f"rss: {e}", file=sys.stderr)
        buffer = ""


if __name__ == "__main__":
    sys.exit(main())
