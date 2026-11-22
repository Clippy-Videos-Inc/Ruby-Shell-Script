"""Runtime value types and the lexically-scoped Environment used by the
tree-walking interpreter."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .errors import RSSRuntimeError


class Environment:
    """A chained scope. Lookups walk up to parent scopes (closures);
    assignment to an already-declared name mutates it wherever it lives,
    Ruby-block style. A brand new name is declared in the current scope."""

    __slots__ = ("vars", "parent")

    def __init__(self, parent: Optional["Environment"] = None):
        self.vars: Dict[str, Any] = {}
        self.parent = parent

    def get(self, name: str, line: int = 0) -> Any:
        env: Optional[Environment] = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise RSSRuntimeError(f"undefined local variable or method '{name}'", line)

    def has(self, name: str) -> bool:
        env: Optional[Environment] = self
        while env is not None:
            if name in env.vars:
                return True
            env = env.parent
        return False

    def define(self, name: str, value: Any) -> None:
        self.vars[name] = value

    def assign(self, name: str, value: Any) -> None:
        env: Optional[Environment] = self
        while env is not None:
            if name in env.vars:
                env.vars[name] = value
                return
            env = env.parent
        self.vars[name] = value

    def child(self) -> "Environment":
        return Environment(self)


class RSSFunction:
    __slots__ = ("name", "params", "defaults", "body", "closure")

    def __init__(self, name: str, params: List[str], defaults: List[Any],
                 body: List[Any], closure: Environment):
        self.name = name
        self.params = params
        self.defaults = defaults
        self.body = body
        self.closure = closure

    def __repr__(self) -> str:
        return f"#<Function:{self.name}>"


class RSSRange:
    """Ruby-style inclusive range, e.g. 1..10."""

    __slots__ = ("start", "stop", "exclusive")

    def __init__(self, start, stop, exclusive: bool = False):
        self.start = start
        self.stop = stop
        self.exclusive = exclusive

    def to_list(self) -> List[Any]:
        if isinstance(self.start, int) and isinstance(self.stop, int):
            end = self.stop if self.exclusive else self.stop + 1
            return list(range(self.start, end))
        # fallback for non-integer ranges: not iterable term by term
        raise RSSRuntimeError("range is not iterable (non-integer bounds)")

    def __iter__(self):
        return iter(self.to_list())

    def includes(self, value) -> bool:
        try:
            if self.exclusive:
                return self.start <= value < self.stop
            return self.start <= value <= self.stop
        except TypeError:
            return False

    def __repr__(self) -> str:
        op = "..." if self.exclusive else ".."
        return f"{self.start}{op}{self.stop}"

    def __eq__(self, other):
        return (isinstance(other, RSSRange) and self.start == other.start
                and self.stop == other.stop and self.exclusive == other.exclusive)
