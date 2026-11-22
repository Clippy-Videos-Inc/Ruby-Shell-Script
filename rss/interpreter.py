"""
Tree-walking interpreter for Ruby Shell Script.

Everything in the language is an expression that evaluates to a Python
value: nil -> None, true/false -> bool, integers/floats -> int/float,
strings -> str, arrays -> list, hashes -> dict, ranges -> RSSRange,
functions -> RSSFunction.
"""

from __future__ import annotations

import os
import random
import subprocess
import sys
import time
from typing import Any, List, Optional

from . import ast_nodes as A
from .errors import RSSRuntimeError, ReturnSignal, BreakSignal, NextSignal, ExitSignal
from .runtime_values import Environment, RSSFunction, RSSRange
from .values import is_truthy, to_s, inspect, rss_type_name


class Interpreter:
    def __init__(self, argv: Optional[List[str]] = None, script_path: str = "main.rss"):
        self.globals = Environment()
        self.ivars = {}  # script-level @instance variables (see README)
        self.argv = argv or []
        self.script_path = script_path
        self.last_status = 0
        self.globals.define("ARGV", list(self.argv))
        self.globals.define("SCRIPT_NAME", script_path)

    # ---- entry point --------------------------------------------------
    def run(self, program: A.Program) -> int:
        try:
            self.run_block(program.body, self.globals)
        except ExitSignal as e:
            sys.stdout.flush()
            return e.code
        except ReturnSignal:
            pass
        except (BreakSignal, NextSignal):
            pass
        except RSSRuntimeError as e:
            sys.stdout.flush()
            print(f"rss: {e}", file=sys.stderr)
            return 1
        return 0

    # ---- statement list ------------------------------------------------
    def run_block(self, body: List[A.Node], env: Environment) -> Any:
        result = None
        for stmt in body:
            result = self.ev(stmt, env)
        return result

    # ---- dispatch ---------------------------------------------------------
    def ev(self, node: A.Node, env: Environment) -> Any:
        method = getattr(self, "n_" + type(node).__name__, None)
        if method is None:
            raise RSSRuntimeError(f"no evaluator for node {type(node).__name__}", getattr(node, "line", 0))
        return method(node, env)

    # ---- literals -----------------------------------------------------
    def n_Program(self, node: A.Program, env):
        return self.run_block(node.body, env)

    def n_NumberLit(self, node: A.NumberLit, env):
        return node.value

    def n_StringLit(self, node: A.StringLit, env):
        return node.value

    def n_BoolLit(self, node: A.BoolLit, env):
        return node.value

    def n_NilLit(self, node: A.NilLit, env):
        return None

    def n_InterpString(self, node: A.InterpString, env):
        out = []
        for part in node.parts:
            if isinstance(part, str):
                out.append(part)
            else:
                out.append(to_s(self.ev(part, env)))
        return "".join(out)

    def n_ArrayLit(self, node: A.ArrayLit, env):
        return [self.ev(e, env) for e in node.elements]

    def n_HashLit(self, node: A.HashLit, env):
        result = {}
        for k, v in node.pairs:
            result[self.ev(k, env)] = self.ev(v, env)
        return result

    def n_RangeLit(self, node: A.RangeLit, env):
        start = self.ev(node.start, env)
        stop = self.ev(node.stop, env)
        return RSSRange(start, stop, node.exclusive)

    # ---- references -----------------------------------------------------
    def n_Identifier(self, node: A.Identifier, env):
        if node.name == "ENV":
            return dict(os.environ)
        if env.has(node.name):
            return env.get(node.name, node.line)
        raise RSSRuntimeError(f"undefined local variable or method '{node.name}'", node.line)

    def n_IVar(self, node: A.IVar, env):
        return self.ivars.get(node.name)

    def n_GVar(self, node: A.GVar, env):
        name = node.name[1:]  # strip '$'
        return os.environ.get(name)

    # ---- operators ----------------------------------------------------
    def n_UnaryOp(self, node: A.UnaryOp, env):
        val = self.ev(node.operand, env)
        if node.op == "-":
            if not isinstance(val, (int, float)):
                raise RSSRuntimeError("unary '-' needs a number", node.line)
            return -val
        return val

    def n_NotOp(self, node: A.NotOp, env):
        return not is_truthy(self.ev(node.operand, env))

    def n_LogicalOp(self, node: A.LogicalOp, env):
        left = self.ev(node.left, env)
        if node.op == "&&":
            return self.ev(node.right, env) if is_truthy(left) else left
        return left if is_truthy(left) else self.ev(node.right, env)

    def n_BinOp(self, node: A.BinOp, env):
        left = self.ev(node.left, env)
        right = self.ev(node.right, env)
        return self.apply_binop(node.op, left, right, node.line)

    def apply_binop(self, op: str, left, right, line: int):
        try:
            if op == "+":
                if isinstance(left, list) and isinstance(right, list):
                    return left + right
                if isinstance(left, dict) and isinstance(right, dict):
                    merged = dict(left)
                    merged.update(right)
                    return merged
                if isinstance(left, str) or isinstance(right, str):
                    if isinstance(left, str) and isinstance(right, str):
                        return left + right
                    raise RSSRuntimeError(
                        f"can't coerce {rss_type_name(right)} to String for '+' "
                        f"(use #{{}} interpolation or .to_s)", line)
                return left + right
            if op == "-":
                if isinstance(left, list) and isinstance(right, list):
                    return [x for x in left if x not in right]
                return left - right
            if op == "*":
                if isinstance(left, str) and isinstance(right, int):
                    return left * right
                if isinstance(left, list) and isinstance(right, int):
                    return left * right
                return left * right
            if op == "/":
                if isinstance(left, int) and isinstance(right, int):
                    if right == 0:
                        raise RSSRuntimeError("divided by 0", line)
                    return left // right  # Ruby integer division floors, like Python's //
                if right == 0:
                    raise RSSRuntimeError("divided by 0", line)
                return left / right
            if op == "%":
                if isinstance(left, str):
                    return left % (right if isinstance(right, tuple) else (right,))
                return left % right
            if op == "**":
                return left ** right
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            if op == "<":
                return left < right
            if op == ">":
                return left > right
            if op == "<=":
                return left <= right
            if op == ">=":
                return left >= right
            if op == "<=>":
                if left == right:
                    return 0
                return -1 if left < right else 1
        except TypeError as e:
            raise RSSRuntimeError(
                f"can't apply '{op}' to {rss_type_name(left)} and {rss_type_name(right)}", line)
        except ZeroDivisionError:
            raise RSSRuntimeError("divided by 0", line)
        raise RSSRuntimeError(f"unknown operator '{op}'", line)

    # ---- assignment -----------------------------------------------------
    def n_Assign(self, node: A.Assign, env):
        if node.op == "=":
            value = self.ev(node.value, env)
        else:
            current = self.ev(node.target, env)
            value = self.apply_binop(node.op[0], current, self.ev(node.value, env), node.line)
        if isinstance(node.target, A.Identifier):
            env.assign(node.target.name, value)
        elif isinstance(node.target, A.IVar):
            self.ivars[node.target.name] = value
        elif isinstance(node.target, A.GVar):
            os.environ[node.target.name[1:]] = to_s(value)
        else:
            raise RSSRuntimeError("invalid assignment target", node.line)
        return value

    def n_IndexAssign(self, node: A.IndexAssign, env):
        receiver = self.ev(node.receiver, env)
        index = self.ev(node.index, env)
        new_val = self.ev(node.value, env)
        if node.op != "=":
            current = self._do_index(receiver, index, node.line)
            new_val = self.apply_binop(node.op[0], current, new_val, node.line)
        self._do_index_set(receiver, index, new_val, node.line)
        return new_val

    # ---- indexing -------------------------------------------------------
    def n_Index(self, node: A.Index, env):
        receiver = self.ev(node.receiver, env)
        index = self.ev(node.index, env)
        return self._do_index(receiver, index, node.line)

    def _do_index(self, receiver, index, line):
        try:
            if isinstance(receiver, dict):
                return receiver.get(index)
            if isinstance(receiver, (list, str)):
                if isinstance(index, int):
                    length = len(receiver)
                    if index < 0:
                        index += length
                    if index < 0 or index >= length:
                        return None if isinstance(receiver, list) else ""
                    return receiver[index]
                raise RSSRuntimeError("array/string index must be an Integer", line)
            if isinstance(receiver, RSSRange):
                return receiver.to_list()[index]
        except IndexError:
            return None
        raise RSSRuntimeError(f"can't index into {rss_type_name(receiver)}", line)

    def _do_index_set(self, receiver, index, value, line):
        if isinstance(receiver, dict):
            receiver[index] = value
            return
        if isinstance(receiver, list):
            if not isinstance(index, int):
                raise RSSRuntimeError("array index must be an Integer", line)
            length = len(receiver)
            if index < 0:
                index += length
            while index >= len(receiver):
                receiver.append(None)
            receiver[index] = value
            return
        raise RSSRuntimeError(f"can't assign into {rss_type_name(receiver)}", line)

    # ---- control flow ---------------------------------------------------
    def n_If(self, node: A.If, env):
        if is_truthy(self.ev(node.cond, env)):
            return self.run_block(node.then_body, env.child())
        for cond, body in node.elifs:
            if is_truthy(self.ev(cond, env)):
                return self.run_block(body, env.child())
        if node.else_body is not None:
            return self.run_block(node.else_body, env.child())
        return None

    def n_Unless(self, node: A.Unless, env):
        if not is_truthy(self.ev(node.cond, env)):
            return self.run_block(node.then_body, env.child())
        if node.else_body is not None:
            return self.run_block(node.else_body, env.child())
        return None

    def n_While(self, node: A.While, env):
        result = None
        while is_truthy(self.ev(node.cond, env)):
            try:
                result = self.run_block(node.body, env.child())
            except BreakSignal as b:
                return b.value
            except NextSignal:
                continue
        return result

    def n_Until(self, node: A.Until, env):
        result = None
        while not is_truthy(self.ev(node.cond, env)):
            try:
                result = self.run_block(node.body, env.child())
            except BreakSignal as b:
                return b.value
            except NextSignal:
                continue
        return result

    def n_Loop(self, node: A.Loop, env):
        while True:
            try:
                self.run_block(node.body, env.child())
            except BreakSignal as b:
                return b.value
            except NextSignal:
                continue

    def n_ForIn(self, node: A.ForIn, env):
        iterable = self.ev(node.iterable, env)
        items = self._iterable_items(iterable, node.line)
        result = None
        for item in items:
            child = env.child()
            child.define(node.var, item)
            try:
                result = self.run_block(node.body, child)
            except BreakSignal as b:
                return b.value
            except NextSignal:
                continue
        return result

    def _iterable_items(self, value, line):
        if isinstance(value, list):
            return value
        if isinstance(value, RSSRange):
            return value.to_list()
        if isinstance(value, dict):
            return list(value.items())
        if isinstance(value, str):
            return list(value)
        raise RSSRuntimeError(f"{rss_type_name(value)} is not iterable", line)

    def n_FuncDef(self, node: A.FuncDef, env):
        defaults = node.defaults
        func = RSSFunction(node.name, node.params, defaults, node.body, env)
        env.define(node.name, func)
        return None

    def n_Return(self, node: A.Return, env):
        value = self.ev(node.value, env) if node.value is not None else None
        raise ReturnSignal(value)

    def n_Break(self, node: A.Break, env):
        raise BreakSignal(None)

    def n_Next(self, node: A.Next, env):
        raise NextSignal(None)

    def n_Exit(self, node: A.Exit, env):
        code = self.ev(node.code, env) if node.code is not None else 0
        if code is True:
            code = 0
        elif code is False:
            code = 1
        elif not isinstance(code, int):
            code = 0
        raise ExitSignal(code)

    def n_Require(self, node: A.Require, env):
        # Module system is a roadmap item (see README) -- no-op for now so
        # scripts that plan ahead for it still parse and run.
        return None

    def n_BeginRescue(self, node: A.BeginRescue, env):
        try:
            try:
                return self.run_block(node.body, env.child())
            except RSSRuntimeError as e:
                child = env.child()
                if node.rescue_var:
                    child.define(node.rescue_var, e.message)
                if node.rescue_body:
                    return self.run_block(node.rescue_body, child)
                raise
        finally:
            if node.ensure_body is not None:
                self.run_block(node.ensure_body, env.child())

    # ---- output ---------------------------------------------------------
    def n_Puts(self, node: A.Puts, env):
        if not node.args:
            print()
            return None
        for arg in node.args:
            self._puts_value(self.ev(arg, env))
        return None

    def _puts_value(self, value):
        if isinstance(value, list):
            if not value:
                return
            for item in value:
                self._puts_value(item)
            return
        print(to_s(value))

    def n_Print(self, node: A.Print, env):
        for arg in node.args:
            sys.stdout.write(to_s(self.ev(arg, env)))
        return None

    # ---- shell integration ------------------------------------------------
    def n_Backtick(self, node: A.Backtick, env):
        cmd = self._render_parts(node.parts, env)
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        except OSError as e:
            raise RSSRuntimeError(f"failed to run command: {e}", node.line)
        self.last_status = proc.returncode
        out = proc.stdout
        if out.endswith("\n"):
            out = out[:-1]
        return out

    def n_ShExec(self, node: A.ShExec, env):
        cmd_val = self.ev(node.command, env)
        cmd = to_s(cmd_val)
        try:
            proc = subprocess.run(cmd, shell=True)
        except OSError as e:
            raise RSSRuntimeError(f"failed to run command: {e}", node.line)
        self.last_status = proc.returncode
        if node.kind == "exec":
            raise ExitSignal(proc.returncode)
        return proc.returncode

    def _render_parts(self, parts, env) -> str:
        out = []
        for part in parts:
            if isinstance(part, str):
                out.append(part)
            else:
                out.append(to_s(self.ev(part, env)))
        return "".join(out)

    # ---- calls --------------------------------------------------------
    def n_Call(self, node: A.Call, env):
        args = [self.ev(a, env) for a in node.args]
        if env.has(node.name):
            callee = env.get(node.name, node.line)
            if isinstance(callee, RSSFunction):
                return self.call_function(callee, args, node.block, env, node.line)
        if node.name in BUILTIN_FUNCTIONS:
            return BUILTIN_FUNCTIONS[node.name](self, args, node.block, env, node.line)
        raise RSSRuntimeError(f"undefined method '{node.name}'", node.line)

    def call_function(self, func: RSSFunction, args: List[Any], block, call_env, line) -> Any:
        call_scope = Environment(func.closure)
        n_required = len(func.params)
        if len(args) > n_required:
            raise RSSRuntimeError(
                f"wrong number of arguments for '{func.name}' "
                f"(given {len(args)}, expected {n_required})", line)
        for i, pname in enumerate(func.params):
            if i < len(args):
                call_scope.define(pname, args[i])
            elif func.defaults[i] is not None:
                call_scope.define(pname, self.ev(func.defaults[i], call_scope))
            else:
                raise RSSRuntimeError(
                    f"wrong number of arguments for '{func.name}' "
                    f"(given {len(args)}, expected {n_required})", line)
        if block is not None:
            call_scope.define("__block__", (block, call_env))
        try:
            return self.run_block(func.body, call_scope)
        except ReturnSignal as r:
            return r.value

    def n_MethodCall(self, node: A.MethodCall, env):
        receiver = self.ev(node.receiver, env)
        args = [self.ev(a, env) for a in node.args]
        from .methods import dispatch_method
        return dispatch_method(self, receiver, node.method, args, node.block, env, node.line)

    def invoke_block(self, block: A.Block, args: List[Any], env: Environment) -> Any:
        if block is None:
            raise RSSRuntimeError("no block given", 0)
        child = env.child()
        for i, pname in enumerate(block.params):
            child.define(pname, args[i] if i < len(args) else None)
        try:
            return self.run_block(block.body, child)
        except NextSignal as n:
            return n.value

    def yield_block(self, env: Environment, args: List[Any], line: int):
        """Used by user-defined functions that call `yield`-like semantics
        via the implicit block passed when the function itself was called
        with a `do...end` block. Exposed as the builtin function block_call()."""
        if not env.has("__block__"):
            raise RSSRuntimeError("no block given (yield)", line)
        block, def_env = env.get("__block__")
        return self.invoke_block(block, args, def_env)


# ----------------------------------------------------------------------
# Built-in global (Kernel-style) functions
# ----------------------------------------------------------------------

def _b_len(interp, args, block, env, line):
    if len(args) != 1:
        raise RSSRuntimeError("len() takes exactly 1 argument", line)
    v = args[0]
    if isinstance(v, (list, str, dict)):
        return len(v)
    if isinstance(v, RSSRange):
        return len(v.to_list())
    raise RSSRuntimeError(f"len() doesn't work on {rss_type_name(v)}", line)


def _b_range(interp, args, block, env, line):
    if len(args) == 1:
        return RSSRange(0, args[0] - 1, False)
    if len(args) == 2:
        return RSSRange(args[0], args[1], False)
    raise RSSRuntimeError("range() takes 1 or 2 arguments", line)


def _b_rand(interp, args, block, env, line):
    if not args:
        return random.random()
    n = args[0]
    if isinstance(n, int):
        return random.randrange(n)
    if isinstance(n, RSSRange):
        lo, hi = n.start, (n.stop - 1 if n.exclusive else n.stop)
        return random.randint(lo, hi)
    raise RSSRuntimeError("rand() expects an Integer or Range", line)


def _b_sleep(interp, args, block, env, line):
    time.sleep(args[0] if args else 0)
    return None


def _b_gets(interp, args, block, env, line):
    try:
        line_in = sys.stdin.readline()
    except (EOFError, OSError):
        return None
    if line_in == "":
        return None
    return line_in.rstrip("\n")


def _b_Integer(interp, args, block, env, line):
    v = args[0]
    try:
        if isinstance(v, str):
            return int(v.strip())
        return int(v)
    except (ValueError, TypeError):
        raise RSSRuntimeError(f"invalid value for Integer(): {inspect(v)}", line)


def _b_Float(interp, args, block, env, line):
    v = args[0]
    try:
        if isinstance(v, str):
            return float(v.strip())
        return float(v)
    except (ValueError, TypeError):
        raise RSSRuntimeError(f"invalid value for Float(): {inspect(v)}", line)


def _b_String(interp, args, block, env, line):
    return to_s(args[0])


def _b_Array(interp, args, block, env, line):
    v = args[0] if args else None
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, RSSRange):
        return v.to_list()
    return [v]


def _b_typeof(interp, args, block, env, line):
    return rss_type_name(args[0])


def _b_p(interp, args, block, env, line):
    for a in args:
        print(inspect(a))
    return args[-1] if args else None


def _b_min(interp, args, block, env, line):
    if len(args) == 1 and isinstance(args[0], list):
        return min(args[0]) if args[0] else None
    return min(args)


def _b_max(interp, args, block, env, line):
    if len(args) == 1 and isinstance(args[0], list):
        return max(args[0]) if args[0] else None
    return max(args)


def _b_format(interp, args, block, env, line):
    fmt = args[0]
    rest = tuple(args[1:])
    try:
        return fmt % rest
    except (TypeError, ValueError) as e:
        raise RSSRuntimeError(f"format() error: {e}", line)


def _b_puts(interp, args, block, env, line):
    if not args:
        print()
    for a in args:
        interp._puts_value(a)
    return None


def _b_print(interp, args, block, env, line):
    for a in args:
        sys.stdout.write(to_s(a))
    return None


def _b_exit(interp, args, block, env, line):
    raise ExitSignal(args[0] if args else 0)


def _b_last_status(interp, args, block, env, line):
    return interp.last_status


def _b_env_get(interp, args, block, env, line):
    return os.environ.get(args[0])


def _b_env_set(interp, args, block, env, line):
    os.environ[args[0]] = to_s(args[1])
    return args[1]


def _b_block_call(interp, args, block, env, line):
    """yield(...) equivalent: calls the block passed to the enclosing
    user-defined function."""
    return interp.yield_block(env, args, line)


def _b_has_block(interp, args, block, env, line):
    return env.has("__block__")


BUILTIN_FUNCTIONS = {
    "len": _b_len,
    "range": _b_range,
    "rand": _b_rand,
    "sleep": _b_sleep,
    "gets": _b_gets,
    "Integer": _b_Integer,
    "Float": _b_Float,
    "String": _b_String,
    "Array": _b_Array,
    "typeof": _b_typeof,
    "p": _b_p,
    "min": _b_min,
    "max": _b_max,
    "format": _b_format,
    "sprintf": _b_format,
    "puts": _b_puts,
    "print": _b_print,
    "exit": _b_exit,
    "last_status": _b_last_status,
    "env_get": _b_env_get,
    "env_set": _b_env_set,
    "yield": _b_block_call,
    "block_given?": _b_has_block,
}
