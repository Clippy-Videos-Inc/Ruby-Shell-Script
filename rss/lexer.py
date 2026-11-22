"""
Lexer for Ruby Shell Script (.rss)

Converts raw source text into a flat list of Token objects that the
parser consumes. The lexer is hand-written (no regex-based tokenizer
libraries) so that error messages can carry accurate line/column info.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


KEYWORDS = {
    "def", "end", "if", "elsif", "else", "unless", "while", "until",
    "for", "in", "do", "then", "return", "break", "next", "true", "false",
    "nil", "and", "or", "not", "begin", "rescue", "ensure", "class",
    "puts", "print", "require", "sh", "exec", "exit", "loop",
}

# Multi-character operators must be listed longest-first so the lexer
# greedily matches them before falling back to single characters.
MULTI_CHAR_OPS = [
    "<=>", "**=", "==", "!=", "<=", ">=", "&&", "||", "+=", "-=",
    "*=", "/=", "%=", "..", "=>", "->", "::", "**",
]

SINGLE_CHAR_OPS = set("+-*/%=<>!&|().,[]{}:;?#@$\n")


@dataclass
class Token:
    kind: str           # NUMBER, STRING, IDENT, KEYWORD, OP, NEWLINE, EOF, ...
    value: object        # parsed value (str, float, int, ...)
    line: int
    col: int

    def __repr__(self) -> str:
        return f"Token({self.kind!r}, {self.value!r}, L{self.line}:{self.col})"


class LexError(Exception):
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"Lex error at line {line}, col {col}: {message}")
        self.line = line
        self.col = col


class Lexer:
    def __init__(self, source: str):
        self.src = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.length = len(source)
        self.tokens: List[Token] = []

    # ---- low level helpers -------------------------------------------------
    def _peek(self, offset: int = 0) -> str:
        i = self.pos + offset
        return self.src[i] if i < self.length else ""

    def _advance(self) -> str:
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _match(self, text: str) -> bool:
        if self.src.startswith(text, self.pos):
            for _ in text:
                self._advance()
            return True
        return False

    # ---- main entry ---------------------------------------------------------
    def tokenize(self) -> List[Token]:
        while self.pos < self.length:
            ch = self._peek()

            if ch in " \t\r":
                self._advance()
                continue

            if ch == "\\" and self._peek(1) == "\n":
                # line continuation
                self._advance()
                self._advance()
                continue

            if ch == "#":
                # comment runs to end of line
                while self.pos < self.length and self._peek() != "\n":
                    self._advance()
                continue

            if ch == "\n":
                line, col = self.line, self.col
                self._advance()
                self._emit_newline(line, col)
                continue

            if ch == "`":
                self._read_backtick()
                continue

            if ch == '"':
                self._read_string('"', interpolate=True)
                continue

            if ch == "'":
                self._read_string("'", interpolate=False)
                continue

            if ch.isdigit() or (ch == "." and self._peek(1).isdigit()):
                self._read_number()
                continue

            if ch.isalpha() or ch == "_":
                self._read_ident()
                continue

            if ch == "@":
                self._read_at_ident()
                continue

            if ch == "$":
                self._read_env_ident()
                continue

            self._read_operator()

        self.tokens.append(Token("EOF", None, self.line, self.col))
        return self.tokens

    def _emit_newline(self, line: int, col: int) -> None:
        # Collapse consecutive blank-line tokens so the parser doesn't have
        # to special-case runs of empty lines.
        if self.tokens and self.tokens[-1].kind == "NEWLINE":
            return
        self.tokens.append(Token("NEWLINE", None, line, col))

    # ---- literals -------------------------------------------------------
    def _read_number(self) -> None:
        line, col = self.line, self.col
        start = self.pos
        is_float = False
        while self._peek().isdigit():
            self._advance()
        if self._peek() == "." and self._peek(1).isdigit():
            is_float = True
            self._advance()
            while self._peek().isdigit():
                self._advance()
        if self._peek() in ("e", "E") and (self._peek(1).isdigit() or
                                            (self._peek(1) in ("+", "-") and self._peek(2).isdigit())):
            is_float = True
            self._advance()
            if self._peek() in "+-":
                self._advance()
            while self._peek().isdigit():
                self._advance()
        text = self.src[start:self.pos]
        value = float(text) if is_float else int(text)
        self.tokens.append(Token("NUMBER", value, line, col))

    def _read_string(self, quote: str, interpolate: bool) -> None:
        line, col = self.line, self.col
        self._advance()  # opening quote
        parts: List[object] = []  # list of str (literal) or ("expr", src) markers
        buf: List[str] = []
        while True:
            if self.pos >= self.length:
                raise LexError("unterminated string literal", line, col)
            ch = self._peek()
            if ch == quote:
                self._advance()
                break
            if ch == "\\":
                self._advance()
                esc = self._advance() if self.pos < self.length else ""
                buf.append(self._escape_char(esc, interpolate))
                continue
            if interpolate and ch == "#" and self._peek(1) == "{":
                parts.append("".join(buf))
                buf = []
                self._advance()
                self._advance()
                depth = 1
                expr_start = self.pos
                while depth > 0:
                    if self.pos >= self.length:
                        raise LexError("unterminated interpolation", line, col)
                    c = self._peek()
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    self._advance()
                expr_src = self.src[expr_start:self.pos]
                self._advance()  # closing }
                parts.append(("expr", expr_src))
                continue
            buf.append(self._advance())
        parts.append("".join(buf))
        if interpolate and any(isinstance(p, tuple) for p in parts):
            self.tokens.append(Token("ISTRING", parts, line, col))
        else:
            literal = "".join(p for p in parts if isinstance(p, str))
            self.tokens.append(Token("STRING", literal, line, col))

    @staticmethod
    def _escape_char(ch: str, interpolate: bool) -> str:
        if not interpolate:
            # single-quoted strings only understand \\ and \'
            return {"\\": "\\", "'": "'"}.get(ch, "\\" + ch)
        return {
            "n": "\n", "t": "\t", "r": "\r", "\\": "\\",
            '"': '"', "0": "\0", "#": "#", "a": "\a", "e": "\x1b",
        }.get(ch, ch)

    def _read_backtick(self) -> None:
        line, col = self.line, self.col
        self._advance()
        parts: List[object] = []
        buf: List[str] = []
        while True:
            if self.pos >= self.length:
                raise LexError("unterminated backtick command", line, col)
            ch = self._peek()
            if ch == "`":
                self._advance()
                break
            if ch == "\\":
                self._advance()
                buf.append(self._escape_char(self._advance(), interpolate=True))
                continue
            if ch == "#" and self._peek(1) == "{":
                parts.append("".join(buf))
                buf = []
                self._advance()
                self._advance()
                depth = 1
                expr_start = self.pos
                while depth > 0:
                    if self.pos >= self.length:
                        raise LexError("unterminated interpolation", line, col)
                    c = self._peek()
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    self._advance()
                expr_src = self.src[expr_start:self.pos]
                self._advance()
                parts.append(("expr", expr_src))
                continue
            buf.append(self._advance())
        parts.append("".join(buf))
        self.tokens.append(Token("BACKTICK", parts, line, col))

    # ---- identifiers / keywords ------------------------------------------
    def _read_ident(self) -> None:
        line, col = self.line, self.col
        start = self.pos
        while self._peek().isalnum() or self._peek() == "_":
            self._advance()
        # Ruby-style trailing ? or ! on method names (e.g. empty?, exit!)
        if self._peek() != "" and self._peek() in "?!":
            self._advance()
        text = self.src[start:self.pos]
        if text in KEYWORDS:
            self.tokens.append(Token("KEYWORD", text, line, col))
        else:
            self.tokens.append(Token("IDENT", text, line, col))

    def _read_at_ident(self) -> None:
        line, col = self.line, self.col
        self._advance()  # @
        start = self.pos
        while self._peek().isalnum() or self._peek() == "_":
            self._advance()
        name = "@" + self.src[start:self.pos]
        self.tokens.append(Token("IVAR", name, line, col))

    def _read_env_ident(self) -> None:
        line, col = self.line, self.col
        self._advance()  # $
        if self._peek() == "{":
            # $ENV style not used; reserved for future global vars
            pass
        start = self.pos
        while self._peek().isalnum() or self._peek() == "_":
            self._advance()
        name = "$" + self.src[start:self.pos]
        self.tokens.append(Token("GVAR", name, line, col))

    # ---- operators --------------------------------------------------------
    def _read_operator(self) -> None:
        line, col = self.line, self.col
        for op in MULTI_CHAR_OPS:
            if self.src.startswith(op, self.pos):
                for _ in op:
                    self._advance()
                self.tokens.append(Token("OP", op, line, col))
                return
        ch = self._advance()
        if ch in "+-*/%=<>!&|().,[]{}:;?":
            self.tokens.append(Token("OP", ch, line, col))
            return
        if ch == "\n":
            self._emit_newline(line, col)
            return
        raise LexError(f"unexpected character {ch!r}", line, col)


def tokenize(source: str) -> List[Token]:
    return Lexer(source).tokenize()
