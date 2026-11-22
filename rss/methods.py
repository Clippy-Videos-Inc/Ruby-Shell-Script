"""
Built-in method dispatch for Ruby Shell Script's core data types:
String, Array (list), Hash (dict), Integer/Float, Range, nil, and
user-defined Function values.

This is where `receiver.method(args)` / `receiver.method do |x| ... end`
gets resolved for everything that isn't a user-defined function.
"""

from __future__ import annotations

from typing import Any, List, Optional

from .errors import RSSRuntimeError
from .runtime_values import RSSRange, RSSFunction
from .values import is_truthy, to_s, inspect, rss_type_name


def dispatch_method(interp, receiver, name, args, block, env, line) -> Any:
    generic = _try_generic(interp, receiver, name, args, block, env, line)
    if generic is not _MISS:
        return generic

    if isinstance(receiver, bool):
        pass  # bool is a subtype of int in Python; handled by generic / number
    if isinstance(receiver, str):
        result = _string_method(interp, receiver, name, args, block, env, line)
        if result is not _MISS:
            return result
    elif isinstance(receiver, list):
        result = _array_method(interp, receiver, name, args, block, env, line)
        if result is not _MISS:
            return result
    elif isinstance(receiver, dict):
        result = _hash_method(interp, receiver, name, args, block, env, line)
        if result is not _MISS:
            return result
    elif isinstance(receiver, bool):
        pass
    elif isinstance(receiver, (int, float)):
        result = _number_method(interp, receiver, name, args, block, env, line)
        if result is not _MISS:
            return result
    elif isinstance(receiver, RSSRange):
        result = _range_method(interp, receiver, name, args, block, env, line)
        if result is not _MISS:
            return result
    elif isinstance(receiver, RSSFunction):
        result = _function_method(interp, receiver, name, args, block, env, line)
        if result is not _MISS:
            return result
    elif receiver is None:
        result = _nil_method(interp, receiver, name, args, block, env, line)
        if result is not _MISS:
            return result

    raise RSSRuntimeError(
        f"undefined method '{name}' for {inspect(receiver)}:{rss_type_name(receiver)}", line)


_MISS = object()


def _try_generic(interp, receiver, name, args, block, env, line):
    if name == "nil?":
        return receiver is None
    if name == "class":
        return rss_type_name(receiver)
    if name == "to_s":
        return to_s(receiver)
    if name == "inspect":
        return inspect(receiver)
    if name in ("dup", "clone"):
        if isinstance(receiver, list):
            return list(receiver)
        if isinstance(receiver, dict):
            return dict(receiver)
        return receiver
    if name == "freeze":
        return receiver
    if name == "frozen?":
        return not isinstance(receiver, (list, dict))
    if name == "is_a?" or name == "instance_of?":
        if not args:
            return False
        return rss_type_name(receiver).lower() == to_s(args[0]).lower()
    return _MISS


def _block_fn(interp, block, env):
    if block is None:
        return None
    return lambda *a: interp.invoke_block(block, list(a), env)


def _string_method(interp, s: str, name, args, block, env, line):
    if name in ("length", "size"):
        return len(s)
    if name == "upcase":
        return s.upper()
    if name == "downcase":
        return s.lower()
    if name == "capitalize":
        return s[:1].upper() + s[1:].lower() if s else s
    if name == "swapcase":
        return s.swapcase()
    if name == "strip":
        return s.strip()
    if name == "lstrip":
        return s.lstrip()
    if name == "rstrip":
        return s.rstrip()
    if name == "chomp":
        return s[:-1] if s.endswith("\n") else s
    if name == "chop":
        return s[:-1]
    if name == "reverse":
        return s[::-1]
    if name == "chars":
        return list(s)
    if name == "bytes":
        return list(s.encode("utf-8"))
    if name == "lines":
        return s.splitlines(keepends=True)
    if name == "split":
        if not args:
            return s.split()
        sep = args[0]
        limit = args[1] if len(args) > 1 else -1
        return s.split(sep, limit - 1) if limit and limit > 0 else s.split(sep)
    if name == "include?":
        return to_s(args[0]) in s
    if name in ("start_with?",):
        return any(s.startswith(to_s(a)) for a in args)
    if name in ("end_with?",):
        return any(s.endswith(to_s(a)) for a in args)
    if name == "index":
        idx = s.find(to_s(args[0]))
        return None if idx < 0 else idx
    if name == "empty?":
        return len(s) == 0
    if name == "to_i":
        try:
            return int(s.strip().split(".")[0] or "0")
        except ValueError:
            digits = ""
            for ch in s.strip():
                if ch.isdigit() or (ch in "+-" and not digits):
                    digits += ch
                else:
                    break
            return int(digits) if digits and digits not in "+-" else 0
    if name == "to_f":
        try:
            return float(s.strip())
        except ValueError:
            return 0.0
    if name == "to_a":
        return list(s)
    if name == "to_sym":
        return s
    if name == "ord":
        return ord(s[0]) if s else 0
    if name in ("sub", "gsub"):
        if len(args) != 2:
            raise RSSRuntimeError(f"{name} needs 2 arguments", line)
        a, b = to_s(args[0]), to_s(args[1])
        return s.replace(a, b, 1) if name == "sub" else s.replace(a, b)
    if name == "ljust":
        width = args[0]
        pad = to_s(args[1]) if len(args) > 1 else " "
        return s + (pad * width)[: max(0, width - len(s))] if len(s) < width else s
    if name == "rjust":
        width = args[0]
        pad = to_s(args[1]) if len(args) > 1 else " "
        return (pad * width)[: max(0, width - len(s))] + s if len(s) < width else s
    if name == "center":
        width = args[0]
        pad = to_s(args[1]) if len(args) > 1 else " "
        return s.center(width, pad[0] if pad else " ")
    if name == "slice":
        start = args[0]
        length = args[1] if len(args) > 1 else 1
        return s[start:start + length]
    if name == "each_char":
        fn = _block_fn(interp, block, env)
        if fn is None:
            raise RSSRuntimeError("each_char needs a block", line)
        for ch in s:
            fn(ch)
        return s
    if name == "*":
        return s * args[0]
    if name == "+":
        return s + to_s(args[0])
    if name == "==":
        return s == args[0]
    return _MISS


def _array_method(interp, arr: List[Any], name, args, block, env, line):
    fn = _block_fn(interp, block, env)

    if name in ("length", "size"):
        return len(arr)
    if name in ("push", "append"):
        arr.extend(args)
        return arr
    if name == "pop":
        return arr.pop() if arr else None
    if name == "shift":
        return arr.pop(0) if arr else None
    if name in ("unshift", "prepend"):
        for a in reversed(args):
            arr.insert(0, a)
        return arr
    if name == "first":
        if args:
            return arr[: args[0]]
        return arr[0] if arr else None
    if name == "last":
        if args:
            return arr[-args[0]:] if args[0] > 0 else []
        return arr[-1] if arr else None
    if name == "reverse":
        return list(reversed(arr))
    if name == "reverse!":
        arr.reverse()
        return arr
    if name == "sort":
        try:
            return sorted(arr)
        except TypeError:
            raise RSSRuntimeError("can't sort a mixed-type array", line)
    if name == "sort!":
        arr.sort()
        return arr
    if name == "uniq":
        seen = []
        for x in arr:
            if x not in seen:
                seen.append(x)
        return seen
    if name == "uniq!":
        seen = []
        for x in arr:
            if x not in seen:
                seen.append(x)
        arr[:] = seen
        return arr
    if name == "join":
        sep = to_s(args[0]) if args else ""
        return sep.join(to_s(x) for x in arr)
    if name == "include?":
        return args[0] in arr
    if name == "empty?":
        return len(arr) == 0
    if name == "flatten":
        out = []

        def flat(lst):
            for x in lst:
                if isinstance(x, list):
                    flat(x)
                else:
                    out.append(x)
        flat(arr)
        return out
    if name == "compact":
        return [x for x in arr if x is not None]
    if name == "concat":
        for a in args:
            arr.extend(a if isinstance(a, list) else [a])
        return arr
    if name == "delete":
        if args[0] in arr:
            arr[:] = [x for x in arr if x != args[0]]
            return args[0]
        return None
    if name == "delete_at":
        i = args[0]
        if -len(arr) <= i < len(arr):
            return arr.pop(i)
        return None
    if name == "insert":
        i = args[0]
        for offset, v in enumerate(args[1:]):
            arr.insert(i + offset, v)
        return arr
    if name == "clear":
        arr.clear()
        return arr
    if name in ("index", "find_index"):
        for i, x in enumerate(arr):
            if (fn(x) if fn else x == args[0]):
                return i
        return None
    if name == "to_a":
        return list(arr)
    if name == "sum":
        total = args[0] if args else 0
        for x in arr:
            total = total + x
        return total
    if name == "min":
        return min(arr) if arr else None
    if name == "max":
        return max(arr) if arr else None
    if name == "count":
        if fn:
            return sum(1 for x in arr if is_truthy(fn(x)))
        if args:
            return sum(1 for x in arr if x == args[0])
        return len(arr)
    if name == "each":
        if fn is None:
            raise RSSRuntimeError("each needs a block", line)
        for x in arr:
            fn(x)
        return arr
    if name == "each_with_index":
        if fn is None:
            raise RSSRuntimeError("each_with_index needs a block", line)
        for i, x in enumerate(arr):
            fn(x, i)
        return arr
    if name in ("map", "collect"):
        if fn is None:
            raise RSSRuntimeError(f"{name} needs a block", line)
        return [fn(x) for x in arr]
    if name in ("map!", "collect!"):
        if fn is None:
            raise RSSRuntimeError(f"{name} needs a block", line)
        arr[:] = [fn(x) for x in arr]
        return arr
    if name in ("select", "filter"):
        if fn is None:
            raise RSSRuntimeError(f"{name} needs a block", line)
        return [x for x in arr if is_truthy(fn(x))]
    if name == "reject":
        if fn is None:
            raise RSSRuntimeError("reject needs a block", line)
        return [x for x in arr if not is_truthy(fn(x))]
    if name in ("reduce", "inject"):
        if fn is None and (not args or not callable(fn)):
            raise RSSRuntimeError(f"{name} needs a block", line)
        items = list(arr)
        if args and not isinstance(args[0], (int, float, str, list, dict)):
            pass
        if args:
            acc = args[0]
        else:
            if not items:
                return None
            acc = items[0]
            items = items[1:]
        for x in items:
            acc = fn(acc, x)
        return acc
    if name == "any?":
        return any(is_truthy(fn(x)) if fn else is_truthy(x) for x in arr)
    if name == "all?":
        return all(is_truthy(fn(x)) if fn else is_truthy(x) for x in arr)
    if name == "none?":
        return not any(is_truthy(fn(x)) if fn else is_truthy(x) for x in arr)
    if name == "each_slice":
        n = args[0]
        return [arr[i:i + n] for i in range(0, len(arr), n)]
    if name == "take":
        return arr[: args[0]]
    if name == "drop":
        return arr[args[0]:]
    if name == "sample":
        import random
        return random.choice(arr) if arr else None
    if name == "shuffle":
        import random
        copy = list(arr)
        random.shuffle(copy)
        return copy
    if name == "+":
        return arr + (args[0] if isinstance(args[0], list) else [args[0]])
    if name == "-":
        other = args[0]
        return [x for x in arr if x not in other]
    if name == "*":
        if isinstance(args[0], str):
            return to_s(args[0]).join(to_s(x) for x in arr)
        return arr * args[0]
    return _MISS


def _hash_method(interp, h: dict, name, args, block, env, line):
    fn = _block_fn(interp, block, env)

    if name in ("length", "size"):
        return len(h)
    if name == "keys":
        return list(h.keys())
    if name == "values":
        return list(h.values())
    if name in ("has_key?", "key?", "include?"):
        return args[0] in h
    if name in ("has_value?", "value?"):
        return args[0] in h.values()
    if name == "empty?":
        return len(h) == 0
    if name == "merge":
        merged = dict(h)
        merged.update(args[0])
        return merged
    if name == "merge!":
        h.update(args[0])
        return h
    if name == "delete":
        return h.pop(args[0], None)
    if name == "fetch":
        if args[0] in h:
            return h[args[0]]
        if len(args) > 1:
            return args[1]
        raise RSSRuntimeError(f"key not found: {inspect(args[0])}", line)
    if name == "to_a":
        return [[k, v] for k, v in h.items()]
    if name == "clear":
        h.clear()
        return h
    if name == "each":
        if fn is None:
            raise RSSRuntimeError("each needs a block", line)
        for k, v in list(h.items()):
            fn(k, v)
        return h
    if name == "each_key":
        if fn is None:
            raise RSSRuntimeError("each_key needs a block", line)
        for k in list(h.keys()):
            fn(k)
        return h
    if name == "each_value":
        if fn is None:
            raise RSSRuntimeError("each_value needs a block", line)
        for v in list(h.values()):
            fn(v)
        return h
    if name in ("select", "filter"):
        if fn is None:
            raise RSSRuntimeError(f"{name} needs a block", line)
        return {k: v for k, v in h.items() if is_truthy(fn(k, v))}
    if name == "reject":
        if fn is None:
            raise RSSRuntimeError("reject needs a block", line)
        return {k: v for k, v in h.items() if not is_truthy(fn(k, v))}
    if name == "map":
        if fn is None:
            raise RSSRuntimeError("map needs a block", line)
        return [fn(k, v) for k, v in h.items()]
    return _MISS


def _number_method(interp, n, name, args, block, env, line):
    fn = _block_fn(interp, block, env)

    if name == "times":
        if fn is None:
            raise RSSRuntimeError("times needs a block", line)
        for i in range(int(n)):
            fn(i)
        return n
    if name == "upto":
        if fn is None:
            raise RSSRuntimeError("upto needs a block", line)
        i = int(n)
        while i <= args[0]:
            fn(i)
            i += 1
        return n
    if name == "downto":
        if fn is None:
            raise RSSRuntimeError("downto needs a block", line)
        i = int(n)
        while i >= args[0]:
            fn(i)
            i -= 1
        return n
    if name == "step":
        if fn is None:
            raise RSSRuntimeError("step needs a block", line)
        limit, step = args[0], (args[1] if len(args) > 1 else 1)
        i = n
        while (i <= limit if step > 0 else i >= limit):
            fn(i)
            i += step
        return n
    if name == "abs":
        return abs(n)
    if name == "to_i":
        return int(n)
    if name == "to_f":
        return float(n)
    if name == "to_s":
        return to_s(n)
    if name == "even?":
        return int(n) % 2 == 0
    if name == "odd?":
        return int(n) % 2 != 0
    if name == "zero?":
        return n == 0
    if name == "positive?":
        return n > 0
    if name == "negative?":
        return n < 0
    if name == "round":
        if args:
            return round(n, args[0])
        return round(n)
    if name == "ceil":
        import math
        return math.ceil(n)
    if name == "floor":
        import math
        return math.floor(n)
    if name == "between?":
        return args[0] <= n <= args[1]
    if name in ("succ", "next"):
        return n + 1
    if name == "pred":
        return n - 1
    if name == "pow":
        return n ** args[0]
    if name == "divmod":
        return [n // args[0], n % args[0]]
    return _MISS


def _range_method(interp, r: RSSRange, name, args, block, env, line):
    fn = _block_fn(interp, block, env)
    if name == "each":
        if fn is None:
            raise RSSRuntimeError("each needs a block", line)
        for x in r.to_list():
            fn(x)
        return r
    if name == "to_a":
        return r.to_list()
    if name in ("include?", "cover?", "member?"):
        return r.includes(args[0])
    if name in ("size", "length", "count"):
        return len(r.to_list())
    if name == "min":
        return r.start
    if name == "max":
        return r.stop - 1 if r.exclusive else r.stop
    if name == "sum":
        return sum(r.to_list())
    if name == "step":
        n = args[0]
        items = r.to_list()[::n]
        if fn:
            for x in items:
                fn(x)
            return r
        return items
    return _MISS


def _function_method(interp, f: RSSFunction, name, args, block, env, line):
    if name == "call":
        return interp.call_function(f, args, block, env, line)
    if name == "arity":
        return len(f.params)
    if name == "name":
        return f.name
    return _MISS


def _nil_method(interp, n, name, args, block, env, line):
    if name == "to_a":
        return []
    if name == "to_i":
        return 0
    if name == "to_f":
        return 0.0
    return _MISS
