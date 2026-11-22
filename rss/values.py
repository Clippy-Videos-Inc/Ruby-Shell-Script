"""Value formatting & truthiness helpers shared across the interpreter."""

from __future__ import annotations

from typing import Any

from .runtime_values import RSSRange, RSSFunction


def is_truthy(value: Any) -> bool:
    """Ruby semantics: only nil and false are falsy. 0 and "" are truthy."""
    return value is not None and value is not False


def _fmt_number(n) -> str:
    if isinstance(n, float):
        if n == int(n) and abs(n) < 1e16:
            return f"{n:.1f}"
        return repr(n)
    return str(n)


def to_s(value: Any) -> str:
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return _fmt_number(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return inspect(value)
    if isinstance(value, dict):
        return inspect(value)
    if isinstance(value, RSSRange):
        return repr(value)
    if isinstance(value, RSSFunction):
        return repr(value)
    return str(value)


def inspect(value: Any) -> str:
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    if isinstance(value, (int, float)):
        return _fmt_number(value)
    if isinstance(value, list):
        return "[" + ", ".join(inspect(v) for v in value) + "]"
    if isinstance(value, dict):
        items = []
        for k, v in value.items():
            items.append(f"{inspect(k)} => {inspect(v)}")
        return "{" + ", ".join(items) + "}"
    return to_s(value)


def rss_type_name(value: Any) -> str:
    if value is None:
        return "Nil"
    if value is True or value is False:
        return "Boolean"
    if isinstance(value, bool):
        return "Boolean"
    if isinstance(value, int):
        return "Integer"
    if isinstance(value, float):
        return "Float"
    if isinstance(value, str):
        return "String"
    if isinstance(value, list):
        return "Array"
    if isinstance(value, dict):
        return "Hash"
    if isinstance(value, RSSRange):
        return "Range"
    if isinstance(value, RSSFunction):
        return "Function"
    return type(value).__name__
