"""Runtime error / control-flow signal types shared by the interpreter."""

from __future__ import annotations


class RSSRuntimeError(Exception):
    """A Ruby-Shell-Script-level runtime error (raised to the user's script,
    catchable with begin/rescue)."""

    def __init__(self, message: str, line: int = 0):
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self) -> str:
        if self.line:
            return f"{self.message} (line {self.line})"
        return self.message


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class BreakSignal(Exception):
    def __init__(self, value=None):
        self.value = value


class NextSignal(Exception):
    def __init__(self, value=None):
        self.value = value


class ExitSignal(Exception):
    def __init__(self, code: int = 0):
        self.code = code
