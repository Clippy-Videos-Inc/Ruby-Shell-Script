"""
AST node definitions for Ruby Shell Script.

Every node is a lightweight dataclass. The interpreter dispatches on
``type(node).__name__`` so adding a new node only requires: (1) define it
here, (2) build it in parser.py, (3) add a visit_<Name> method in
interpreter.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any


@dataclass
class Node:
    line: int = field(default=0, kw_only=True)


# ---------------------------------------------------------------- literals
@dataclass
class Program(Node):
    body: List[Node]


@dataclass
class NumberLit(Node):
    value: float | int


@dataclass
class StringLit(Node):
    value: str


@dataclass
class InterpString(Node):
    # parts: list of str (literal) or Node (expression)
    parts: List[Any]


@dataclass
class BoolLit(Node):
    value: bool


@dataclass
class NilLit(Node):
    pass


@dataclass
class ArrayLit(Node):
    elements: List[Node]


@dataclass
class HashLit(Node):
    pairs: List[Tuple[Node, Node]]


@dataclass
class RangeLit(Node):
    start: Node
    stop: Node
    exclusive: bool


# ------------------------------------------------------------- references
@dataclass
class Identifier(Node):
    name: str


@dataclass
class IVar(Node):
    name: str


@dataclass
class GVar(Node):
    name: str


# --------------------------------------------------------------- operators
@dataclass
class BinOp(Node):
    op: str
    left: Node
    right: Node


@dataclass
class UnaryOp(Node):
    op: str
    operand: Node


@dataclass
class LogicalOp(Node):
    op: str  # '&&' / '||'
    left: Node
    right: Node


@dataclass
class NotOp(Node):
    operand: Node


@dataclass
class Assign(Node):
    target: Node
    op: str  # '=', '+=', '-=', '*=', '/=', '%='
    value: Node


# ------------------------------------------------------------------- calls
@dataclass
class Block(Node):
    params: List[str]
    body: List[Node]


@dataclass
class Call(Node):
    name: str
    args: List[Node]
    block: Optional[Block] = None


@dataclass
class MethodCall(Node):
    receiver: Node
    method: str
    args: List[Node]
    block: Optional[Block] = None


@dataclass
class Index(Node):
    receiver: Node
    index: Node


@dataclass
class IndexAssign(Node):
    receiver: Node
    index: Node
    op: str
    value: Node


# -------------------------------------------------------------- statements
@dataclass
class If(Node):
    cond: Node
    then_body: List[Node]
    elifs: List[Tuple[Node, List[Node]]]
    else_body: Optional[List[Node]]


@dataclass
class Unless(Node):
    cond: Node
    then_body: List[Node]
    else_body: Optional[List[Node]]


@dataclass
class While(Node):
    cond: Node
    body: List[Node]


@dataclass
class Until(Node):
    cond: Node
    body: List[Node]


@dataclass
class Loop(Node):
    body: List[Node]


@dataclass
class ForIn(Node):
    var: str
    iterable: Node
    body: List[Node]


@dataclass
class FuncDef(Node):
    name: str
    params: List[str]
    defaults: List[Optional[Node]]
    body: List[Node]


@dataclass
class Return(Node):
    value: Optional[Node]


@dataclass
class Break(Node):
    pass


@dataclass
class Next(Node):
    pass


@dataclass
class Puts(Node):
    args: List[Node]


@dataclass
class Print(Node):
    args: List[Node]


@dataclass
class Backtick(Node):
    # command: str or InterpString-like list of parts for interpolation
    parts: List[Any]


@dataclass
class ShExec(Node):
    """sh(...) / exec(...) builtin — runs a command, streaming output."""
    kind: str  # 'sh' or 'exec'
    command: Node


@dataclass
class Exit(Node):
    code: Optional[Node]


@dataclass
class Require(Node):
    name: str


@dataclass
class BeginRescue(Node):
    body: List[Node]
    rescue_var: Optional[str]
    rescue_body: List[Node]
    ensure_body: Optional[List[Node]]
