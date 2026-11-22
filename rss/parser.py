"""
Recursive-descent parser for Ruby Shell Script.

Grammar is Ruby-flavored: blocks are closed with `end`, conditions don't
need parentheses, statement modifiers (`do_thing if cond`) are supported,
and `do |x| ... end` blocks attach to method/function calls.
"""

from __future__ import annotations

from typing import List, Optional, Set, Tuple

from .lexer import Token, tokenize
from . import ast_nodes as A


class ParseError(Exception):
    def __init__(self, message: str, token: Optional[Token] = None):
        if token is not None:
            message = f"Parse error at line {token.line}, col {token.col}: {message} (got {token.kind} {token.value!r})"
        super().__init__(message)


ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "%="}
STMT_END_KEYWORDS = {"end", "elsif", "else", "rescue", "ensure", "then"}


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    # ---- token stream helpers ---------------------------------------
    def current(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, offset: int = 1) -> Token:
        i = self.pos + offset
        return self.tokens[i] if i < len(self.tokens) else self.tokens[-1]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.kind != "EOF":
            self.pos += 1
        return tok

    def at_end(self) -> bool:
        return self.current().kind == "EOF"

    def check(self, kind: str, value=None) -> bool:
        tok = self.current()
        if tok.kind != kind:
            return False
        return value is None or tok.value == value

    def check_kw(self, word: str) -> bool:
        return self.check("KEYWORD", word)

    def is_keyword_in(self, words: Set[str]) -> bool:
        tok = self.current()
        return tok.kind == "KEYWORD" and tok.value in words

    def expect(self, kind: str, value=None) -> Token:
        if not self.check(kind, value):
            raise ParseError(f"expected {value or kind}", self.current())
        return self.advance()

    def skip_newlines(self) -> None:
        while self.check("NEWLINE"):
            self.advance()

    def skip_terminators(self) -> None:
        while self.check("NEWLINE") or self.check("OP", ";"):
            self.advance()

    def skip_then(self) -> None:
        self.skip_newlines()
        if self.check_kw("then"):
            self.advance()
            self.skip_newlines()

    def skip_do(self) -> None:
        self.skip_newlines()
        if self.check_kw("do"):
            self.advance()
            self.skip_newlines()

    def at_stmt_end(self) -> bool:
        tok = self.current()
        if tok.kind in ("NEWLINE", "EOF"):
            return True
        if tok.kind == "OP" and tok.value == ";":
            return True
        if tok.kind == "KEYWORD" and tok.value in STMT_END_KEYWORDS:
            return True
        return False

    # ---- entry point --------------------------------------------------
    def parse_program(self) -> A.Program:
        body = self.parse_body(set())
        self.expect("EOF")
        return A.Program(body, line=1)

    def parse_body(self, enders: Set[str]) -> List[A.Node]:
        stmts: List[A.Node] = []
        self.skip_terminators()
        while not self.at_end() and not self.is_keyword_in(enders):
            stmts.append(self.parse_statement())
            self.skip_terminators()
        return stmts

    # ---- statements -----------------------------------------------------
    def parse_statement(self) -> A.Node:
        tok = self.current()
        if tok.kind == "KEYWORD":
            if tok.value == "if":
                return self.apply_modifiers(self.parse_if())
            if tok.value == "unless":
                return self.apply_modifiers(self.parse_unless())
            if tok.value == "while":
                return self.apply_modifiers(self.parse_while())
            if tok.value == "until":
                return self.apply_modifiers(self.parse_until())
            if tok.value == "loop":
                return self.apply_modifiers(self.parse_loop())
            if tok.value == "for":
                return self.apply_modifiers(self.parse_for())
            if tok.value == "def":
                return self.parse_def()
            if tok.value == "begin":
                return self.parse_begin()
            if tok.value == "return":
                line = self.advance().line
                value = None if self.at_stmt_end() else self.parse_expression()
                return self.apply_modifiers(A.Return(value, line=line))
            if tok.value == "break":
                line = self.advance().line
                return self.apply_modifiers(A.Break(line=line))
            if tok.value == "next":
                line = self.advance().line
                return self.apply_modifiers(A.Next(line=line))
            if tok.value == "puts":
                return self.apply_modifiers(self.parse_puts())
            if tok.value == "print":
                return self.apply_modifiers(self.parse_print())
            if tok.value == "require":
                return self.apply_modifiers(self.parse_require())
            if tok.value == "exit":
                line = self.advance().line
                code = None if self.at_stmt_end() else self.parse_expression()
                return self.apply_modifiers(A.Exit(code, line=line))
        expr = self.parse_expression()
        return self.apply_modifiers(expr)

    def apply_modifiers(self, node: A.Node) -> A.Node:
        """Handle Ruby-style statement modifiers: `stmt if cond`, etc."""
        if self.check_kw("if"):
            line = self.advance().line
            cond = self.parse_expression()
            return A.If(cond, [node], [], None, line=line)
        if self.check_kw("unless"):
            line = self.advance().line
            cond = self.parse_expression()
            return A.Unless(cond, [node], None, line=line)
        if self.check_kw("while"):
            line = self.advance().line
            cond = self.parse_expression()
            return A.While(cond, [node], line=line)
        if self.check_kw("until"):
            line = self.advance().line
            cond = self.parse_expression()
            return A.Until(cond, [node], line=line)
        return node

    def parse_if(self) -> A.If:
        line = self.advance().line  # 'if'
        cond = self.parse_expression()
        self.skip_then()
        then_body = self.parse_body({"elsif", "else", "end"})
        elifs: List[Tuple[A.Node, List[A.Node]]] = []
        while self.check_kw("elsif"):
            self.advance()
            c = self.parse_expression()
            self.skip_then()
            b = self.parse_body({"elsif", "else", "end"})
            elifs.append((c, b))
        else_body = None
        if self.check_kw("else"):
            self.advance()
            self.skip_newlines()
            else_body = self.parse_body({"end"})
        self.expect("KEYWORD", "end")
        return A.If(cond, then_body, elifs, else_body, line=line)

    def parse_unless(self) -> A.Unless:
        line = self.advance().line
        cond = self.parse_expression()
        self.skip_then()
        then_body = self.parse_body({"else", "end"})
        else_body = None
        if self.check_kw("else"):
            self.advance()
            self.skip_newlines()
            else_body = self.parse_body({"end"})
        self.expect("KEYWORD", "end")
        return A.Unless(cond, then_body, else_body, line=line)

    def parse_while(self) -> A.While:
        line = self.advance().line
        cond = self.parse_expression()
        self.skip_do()
        body = self.parse_body({"end"})
        self.expect("KEYWORD", "end")
        return A.While(cond, body, line=line)

    def parse_until(self) -> A.Until:
        line = self.advance().line
        cond = self.parse_expression()
        self.skip_do()
        body = self.parse_body({"end"})
        self.expect("KEYWORD", "end")
        return A.Until(cond, body, line=line)

    def parse_loop(self) -> A.Loop:
        line = self.advance().line
        self.skip_do()
        body = self.parse_body({"end"})
        self.expect("KEYWORD", "end")
        return A.Loop(body, line=line)

    def parse_for(self) -> A.ForIn:
        line = self.advance().line
        var_tok = self.expect("IDENT")
        self.expect("KEYWORD", "in")
        iterable = self.parse_expression()
        self.skip_do()
        body = self.parse_body({"end"})
        self.expect("KEYWORD", "end")
        return A.ForIn(var_tok.value, iterable, body, line=line)

    def parse_def(self) -> A.FuncDef:
        line = self.advance().line
        name_tok = self.advance()
        if name_tok.kind not in ("IDENT", "KEYWORD"):
            raise ParseError("expected function name", name_tok)
        name = name_tok.value
        params: List[str] = []
        defaults: List[Optional[A.Node]] = []
        if self.check("OP", "("):
            self.advance()
            self.skip_newlines()
            while not self.check("OP", ")"):
                p_tok = self.expect("IDENT")
                default = None
                if self.check("OP", "="):
                    self.advance()
                    default = self.parse_expression()
                params.append(p_tok.value)
                defaults.append(default)
                self.skip_newlines()
                if self.check("OP", ","):
                    self.advance()
                    self.skip_newlines()
                else:
                    break
            self.expect("OP", ")")
        self.skip_newlines()
        body = self.parse_body({"end"})
        self.expect("KEYWORD", "end")
        return A.FuncDef(name, params, defaults, body, line=line)

    def parse_begin(self) -> A.BeginRescue:
        line = self.advance().line
        self.skip_newlines()
        body = self.parse_body({"rescue", "ensure", "end"})
        rescue_var = None
        rescue_body: List[A.Node] = []
        if self.check_kw("rescue"):
            self.advance()
            if self.check("OP", "=>"):
                self.advance()
                rescue_var = self.expect("IDENT").value
            self.skip_newlines()
            rescue_body = self.parse_body({"ensure", "end"})
        ensure_body = None
        if self.check_kw("ensure"):
            self.advance()
            self.skip_newlines()
            ensure_body = self.parse_body({"end"})
        self.expect("KEYWORD", "end")
        return A.BeginRescue(body, rescue_var, rescue_body, ensure_body, line=line)

    def parse_puts(self) -> A.Puts:
        line = self.advance().line
        args = self._parse_bare_arg_list()
        return A.Puts(args, line=line)

    def parse_print(self) -> A.Print:
        line = self.advance().line
        args = self._parse_bare_arg_list()
        return A.Print(args, line=line)

    def parse_require(self) -> A.Require:
        line = self.advance().line
        tok = self.advance()
        if tok.kind == "STRING":
            name = tok.value
        elif tok.kind == "ISTRING":
            name = "".join(p for p in tok.value if isinstance(p, str))
        else:
            raise ParseError("expected a string after 'require'", tok)
        return A.Require(name, line=line)

    _CONTINUATION_OPS = {
        "+", "-", "*", "/", "%", "**", "==", "!=", "<", ">", "<=", ">=",
        "<=>", "..", "&&", "||", ".", "[",
    }

    def _looks_like_continuation(self) -> bool:
        tok = self.current()
        if tok.kind == "OP" and tok.value in self._CONTINUATION_OPS:
            return True
        if tok.kind == "KEYWORD" and tok.value in ("and", "or"):
            return True
        return False

    def _parse_bare_arg_list(self) -> List[A.Node]:
        """Parse a comma separated list of expressions with no parens,
        used for `puts`/`print` (Ruby allows `puts a, b` without parens).

        `puts(1, 2)` (no space before the paren) is treated as a wrapped
        argument list. `puts (1 + 2) * 3` is treated as a single grouped
        expression, matching Ruby's own space-sensitive disambiguation.
        """
        if self.at_stmt_end():
            return []
        if self.check("OP", "("):
            checkpoint = self.pos
            try:
                self.advance()
                args: List[A.Node] = []
                if not self.check("OP", ")"):
                    args.append(self.parse_expression())
                    while self.check("OP", ","):
                        self.advance()
                        self.skip_newlines()
                        args.append(self.parse_expression())
                self.expect("OP", ")")
                if not self._looks_like_continuation():
                    return args
            except ParseError:
                pass
            self.pos = checkpoint
        args = [self.parse_expression()]
        while self.check("OP", ","):
            self.advance()
            self.skip_newlines()
            args.append(self.parse_expression())
        return args

    # ---- expressions (precedence climbing) -------------------------------
    def parse_expression(self) -> A.Node:
        return self.parse_assignment()

    def parse_assignment(self) -> A.Node:
        left = self.parse_or()
        if self.check("OP") and self.current().value in ASSIGN_OPS:
            op_tok = self.advance()
            value = self.parse_assignment()
            if isinstance(left, (A.Identifier, A.IVar, A.GVar)):
                return A.Assign(left, op_tok.value, value, line=op_tok.line)
            if isinstance(left, A.Index):
                return A.IndexAssign(left.receiver, left.index, op_tok.value, value, line=op_tok.line)
            raise ParseError("invalid assignment target", op_tok)
        return left

    def parse_or(self) -> A.Node:
        left = self.parse_and()
        while (self.check("OP", "||")) or self.check_kw("or"):
            op_tok = self.advance()
            right = self.parse_and()
            left = A.LogicalOp("||", left, right, line=op_tok.line)
        return left

    def parse_and(self) -> A.Node:
        left = self.parse_not()
        while (self.check("OP", "&&")) or self.check_kw("and"):
            op_tok = self.advance()
            right = self.parse_not()
            left = A.LogicalOp("&&", left, right, line=op_tok.line)
        return left

    def parse_not(self) -> A.Node:
        if self.check("OP", "!") or self.check_kw("not"):
            tok = self.advance()
            operand = self.parse_not()
            return A.NotOp(operand, line=tok.line)
        return self.parse_equality()

    def parse_equality(self) -> A.Node:
        left = self.parse_comparison()
        while self.check("OP") and self.current().value in ("==", "!="):
            op_tok = self.advance()
            right = self.parse_comparison()
            left = A.BinOp(op_tok.value, left, right, line=op_tok.line)
        return left

    def parse_comparison(self) -> A.Node:
        left = self.parse_range()
        while self.check("OP") and self.current().value in ("<", ">", "<=", ">=", "<=>"):
            op_tok = self.advance()
            right = self.parse_range()
            left = A.BinOp(op_tok.value, left, right, line=op_tok.line)
        return left

    def parse_range(self) -> A.Node:
        left = self.parse_additive()
        if self.check("OP", ".."):
            tok = self.advance()
            right = self.parse_additive()
            return A.RangeLit(left, right, exclusive=False, line=tok.line)
        return left

    def parse_additive(self) -> A.Node:
        left = self.parse_multiplicative()
        while self.check("OP") and self.current().value in ("+", "-"):
            op_tok = self.advance()
            right = self.parse_multiplicative()
            left = A.BinOp(op_tok.value, left, right, line=op_tok.line)
        return left

    def parse_multiplicative(self) -> A.Node:
        left = self.parse_unary()
        while self.check("OP") and self.current().value in ("*", "/", "%"):
            op_tok = self.advance()
            right = self.parse_unary()
            left = A.BinOp(op_tok.value, left, right, line=op_tok.line)
        return left

    def parse_unary(self) -> A.Node:
        if self.check("OP") and self.current().value in ("-", "+"):
            tok = self.advance()
            operand = self.parse_unary()
            return A.UnaryOp(tok.value, operand, line=tok.line)
        return self.parse_power()

    def parse_power(self) -> A.Node:
        left = self.parse_postfix()
        if self.check("OP", "**"):
            tok = self.advance()
            right = self.parse_unary()
            return A.BinOp("**", left, right, line=tok.line)
        return left

    def parse_postfix(self) -> A.Node:
        expr = self.parse_primary()
        while True:
            if self.check("OP", "."):
                self.advance()
                name_tok = self.advance()
                if name_tok.kind not in ("IDENT", "KEYWORD"):
                    raise ParseError("expected method name after '.'", name_tok)
                args: List[A.Node] = []
                if self.check("OP", "("):
                    args = self.parse_call_args()
                block = self.parse_optional_block()
                expr = A.MethodCall(expr, name_tok.value, args, block, line=name_tok.line)
            elif self.check("OP", "["):
                tok = self.advance()
                idx = self.parse_expression()
                self.expect("OP", "]")
                expr = A.Index(expr, idx, line=tok.line)
            else:
                break
        return expr

    def parse_call_args(self) -> List[A.Node]:
        self.expect("OP", "(")
        self.skip_newlines()
        args: List[A.Node] = []
        if not self.check("OP", ")"):
            args.append(self.parse_expression())
            self.skip_newlines()
            while self.check("OP", ","):
                self.advance()
                self.skip_newlines()
                args.append(self.parse_expression())
                self.skip_newlines()
        self.expect("OP", ")")
        return args

    def parse_optional_block(self) -> Optional[A.Block]:
        if self.check_kw("do"):
            line = self.advance().line
            params: List[str] = []
            if self.check("OP", "|"):
                self.advance()
                while not self.check("OP", "|"):
                    params.append(self.expect("IDENT").value)
                    if self.check("OP", ","):
                        self.advance()
                self.expect("OP", "|")
            self.skip_newlines()
            body = self.parse_body({"end"})
            self.expect("KEYWORD", "end")
            return A.Block(params, body, line=line)
        return None

    def parse_primary(self) -> A.Node:
        tok = self.current()

        if tok.kind == "NUMBER":
            self.advance()
            return A.NumberLit(tok.value, line=tok.line)

        if tok.kind == "STRING":
            self.advance()
            return A.StringLit(tok.value, line=tok.line)

        if tok.kind == "ISTRING":
            self.advance()
            return A.InterpString(self._build_interp_parts(tok.value), line=tok.line)

        if tok.kind == "BACKTICK":
            self.advance()
            return A.Backtick(self._build_interp_parts(tok.value), line=tok.line)

        if tok.kind == "IVAR":
            self.advance()
            return A.IVar(tok.value, line=tok.line)

        if tok.kind == "GVAR":
            self.advance()
            return A.GVar(tok.value, line=tok.line)

        if tok.kind == "OP" and tok.value == ":" and self.peek().kind in ("IDENT", "KEYWORD"):
            # Symbol literal, e.g. :lang -- represented as a plain string,
            # same as the `key:` hash shorthand. A distinct Symbol type is
            # on the roadmap (see README).
            self.advance()
            name_tok = self.advance()
            return A.StringLit(name_tok.value, line=tok.line)

        if tok.kind == "KEYWORD":
            if tok.value == "true":
                self.advance()
                return A.BoolLit(True, line=tok.line)
            if tok.value == "false":
                self.advance()
                return A.BoolLit(False, line=tok.line)
            if tok.value == "nil":
                self.advance()
                return A.NilLit(line=tok.line)
            if tok.value in ("sh", "exec"):
                self.advance()
                self.expect("OP", "(")
                arg = self.parse_expression()
                self.expect("OP", ")")
                return A.ShExec(tok.value, arg, line=tok.line)

        if tok.kind == "IDENT":
            self.advance()
            if self.check("OP", "("):
                args = self.parse_call_args()
                block = self.parse_optional_block()
                return A.Call(tok.value, args, block, line=tok.line)
            # bare identifier used as a command with a block, e.g. user-defined
            # iterator-style helpers: `retry_forever do ... end`
            block = self.parse_optional_block()
            if block is not None:
                return A.Call(tok.value, [], block, line=tok.line)
            return A.Identifier(tok.value, line=tok.line)

        if tok.kind == "OP" and tok.value == "(":
            self.advance()
            self.skip_newlines()
            expr = self.parse_expression()
            self.skip_newlines()
            self.expect("OP", ")")
            return expr

        if tok.kind == "OP" and tok.value == "[":
            return self.parse_array_lit()

        if tok.kind == "OP" and tok.value == "{":
            return self.parse_hash_lit()

        raise ParseError("unexpected token", tok)

    def parse_array_lit(self) -> A.ArrayLit:
        line = self.expect("OP", "[").line
        self.skip_newlines()
        elements: List[A.Node] = []
        while not self.check("OP", "]"):
            elements.append(self.parse_expression())
            self.skip_newlines()
            if self.check("OP", ","):
                self.advance()
                self.skip_newlines()
            else:
                break
        self.expect("OP", "]")
        return A.ArrayLit(elements, line=line)

    def parse_hash_lit(self) -> A.HashLit:
        line = self.expect("OP", "{").line
        self.skip_newlines()
        pairs: List[Tuple[A.Node, A.Node]] = []
        while not self.check("OP", "}"):
            if self.check("IDENT") and self.peek().kind == "OP" and self.peek().value == ":":
                key_tok = self.advance()
                self.advance()  # ':'
                key: A.Node = A.StringLit(key_tok.value, line=key_tok.line)
            else:
                key = self.parse_expression()
                self.expect("OP", "=>")
            value = self.parse_expression()
            pairs.append((key, value))
            self.skip_newlines()
            if self.check("OP", ","):
                self.advance()
                self.skip_newlines()
            else:
                break
        self.expect("OP", "}")
        return A.HashLit(pairs, line=line)

    # ---- interpolation ----------------------------------------------------
    def _build_interp_parts(self, raw_parts: List[object]) -> List[object]:
        built: List[object] = []
        for part in raw_parts:
            if isinstance(part, tuple) and part[0] == "expr":
                built.append(parse_embedded_expression(part[1]))
            else:
                if part != "":
                    built.append(part)
        return built


def parse_embedded_expression(src: str) -> A.Node:
    """Parse the text inside a `#{...}` interpolation as a single expression."""
    tokens = tokenize(src)
    p = Parser(tokens)
    p.skip_newlines()
    expr = p.parse_expression()
    return expr


def parse(source: str) -> A.Program:
    tokens = tokenize(source)
    return Parser(tokens).parse_program()
