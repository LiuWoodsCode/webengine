from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .parser import (
    ArrayLiteral,
    AssignmentExpression,
    BinaryExpression,
    BlockStatement,
    CallExpression,
    ConditionalExpression,
    ExpressionStatement,
    ForStatement,
    FunctionDeclaration,
    FunctionExpression,
    Identifier,
    IfStatement,
    Literal,
    MemberExpression,
    ObjectLiteral,
    Program,
    ReturnStatement,
    SequenceExpression,
    ThrowStatement,
    TryCatchStatement,
    UnaryExpression,
    UpdateExpression,
    VarDeclaration,
    WhileStatement,
    JSParseError,
    parse_js,
)


class JSError(Exception):
    def __init__(
        self,
        message: str,
        *,
        source_name: str | None = None,
        source_text: str | None = None,
        pos: int | None = None,
        stack: list["JSStackFrame"] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.source_name = source_name
        self.source_text = source_text
        self.pos = pos
        self.stack = stack or []

    def __str__(self) -> str:
        return self.message

    def format_for_console(self) -> str:
        lines = [f"Uncaught {self.message}"]
        for frame in self.stack:
            location = f"{frame.source_name}:{frame.line}"
            if frame.column is not None:
                location = f"{location}:{frame.column}"
            lines.append(f"    {frame.function_name} {location}")
        excerpt = _format_source_excerpt(self.source_text, self.pos)
        if excerpt:
            lines.extend(["", excerpt])
        return "\n".join(lines)


@dataclass
class JSStackFrame:
    function_name: str
    source_name: str
    line: int
    column: int | None = None


@dataclass
class _ExecutionFrame:
    function_name: str
    source_name: str
    source_text: str
    node_stack: list[object] = field(default_factory=list)


class JSReturn(Exception):
    def __init__(self, value: Any):
        super().__init__("return")
        self.value = value


class JSThrow(Exception):
    def __init__(self, value: Any):
        super().__init__("throw")
        self.value = value


@dataclass
class Scope:
    parent: "Scope | None" = None
    bindings: dict[str, Any] = field(default_factory=dict)
    const_bindings: set[str] = field(default_factory=set)

    def declare(self, name: str, value: Any, is_const: bool = False):
        self.bindings[name] = value
        if is_const:
            self.const_bindings.add(name)

    def resolve(self, name: str) -> "Scope | None":
        scope: Scope | None = self
        while scope:
            if name in scope.bindings:
                return scope
            scope = scope.parent
        return None

    def get(self, name: str) -> Any:
        scope = self.resolve(name)
        if not scope:
            raise JSError(f"ReferenceError: {name} is not defined")
        return scope.bindings[name]

    def assign(self, name: str, value: Any):
        scope = self.resolve(name)
        if not scope:
            raise JSError(f"ReferenceError: {name} is not defined")
        if name in scope.const_bindings:
            raise JSError(f"TypeError: Assignment to constant variable '{name}'")
        scope.bindings[name] = value


@dataclass
class JSObject:
    props: dict[str, Any] = field(default_factory=dict)

    def get(self, name: str) -> Any:
        return self.props.get(name)

    def set(self, name: str, value: Any):
        self.props[name] = value


@dataclass
class NativeFunction:
    fn: Callable[..., Any]
    name: str = "<native>"

    def __call__(self, *args):
        return self.fn(*args)


@dataclass
class JSFunction:
    params: list[str]
    body: object
    closure: Scope
    is_arrow: bool = False
    impl: Callable[["JSRuntime", Scope], Any] | None = None
    name: str = "<anonymous>"
    source_name: str | None = None
    source_text: str | None = None

    def call(self, runtime: "JSRuntime", args: list[Any]) -> Any:
        call_scope = Scope(parent=self.closure)
        for i, param in enumerate(self.params):
            call_scope.declare(param, args[i] if i < len(args) else None)
        runtime._push_frame(
            self.name or "<anonymous>",
            self.source_name or runtime._current_source_name or "<anonymous>",
            self.source_text or runtime._current_source_text or "",
        )
        try:
            if self.impl is not None:
                return self.impl(runtime, call_scope)
            if isinstance(self.body, BlockStatement):
                return runtime._eval_block(self.body, call_scope)
            return runtime._eval_expression(self.body, call_scope)
        except JSReturn as ret:
            return ret.value
        finally:
            runtime._pop_frame()


@dataclass
class CompiledProgram:
    program: Program
    python_source: str
    entrypoint: Callable[["JSRuntime", Scope], Any]


def _truthy(value: Any) -> bool:
    return bool(value)


def _js_value_to_error_text(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _line_col_from_pos(source: str | None, pos: int | None) -> tuple[int, int | None]:
    if source is None or pos is None:
        return 1, None
    bounded = max(0, min(pos, len(source)))
    line = source.count("\n", 0, bounded) + 1
    last_newline = source.rfind("\n", 0, bounded)
    column = bounded + 1 if last_newline == -1 else bounded - last_newline
    return line, column


def _format_source_excerpt(source: str | None, pos: int | None, *, context_lines: int = 1) -> str:
    if source is None or pos is None:
        return ""

    lines = source.splitlines()
    if not lines:
        lines = [source]

    line_no, column = _line_col_from_pos(source, pos)
    start = max(1, line_no - context_lines)
    end = min(len(lines), line_no + context_lines)
    gutter_width = len(str(end))
    excerpt: list[str] = ["Source context:"]

    for current_line in range(start, end + 1):
        marker = ">" if current_line == line_no else " "
        excerpt.append(f"{marker} {current_line:>{gutter_width}} | {lines[current_line - 1]}")
        if current_line == line_no and column is not None:
            caret_pad = max(column - 1, 0)
            excerpt.append(f"  {' ' * gutter_width} | {' ' * caret_pad}^")

    return "\n".join(excerpt)


def _to_number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        if value == "":
            return 0.0
        try:
            return float(value)
        except ValueError:
            return float("nan")
    return float("nan")


def _is_stringy(value: Any) -> bool:
    return isinstance(value, str)


def _to_primitive(value: Any) -> Any:
    if isinstance(value, JSObject):
        return value.props
    return value


def _js_type_tag(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return "object"


def _js_strict_eq(left: Any, right: Any) -> bool:
    if _js_type_tag(left) != _js_type_tag(right):
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(left) == float(right)
    return left == right


def _js_loose_eq(left: Any, right: Any) -> bool:
    left = _to_primitive(left)
    right = _to_primitive(right)

    if _js_type_tag(left) == _js_type_tag(right):
        return _js_strict_eq(left, right)

    if left is None and right is None:
        return True

    if isinstance(left, bool):
        return _js_loose_eq(_to_number(left), right)
    if isinstance(right, bool):
        return _js_loose_eq(left, _to_number(right))

    if isinstance(left, (int, float)) and isinstance(right, str):
        return _js_loose_eq(left, _to_number(right))
    if isinstance(left, str) and isinstance(right, (int, float)):
        return _js_loose_eq(_to_number(left), right)

    return left == right


def _to_property_key(value: Any) -> Any:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _get_property(obj: Any, prop: Any) -> Any:
    if obj is None:
        raise JSError("TypeError: Cannot read properties of null")

    key = _to_property_key(prop)

    if isinstance(obj, JSObject):
        return obj.get(str(key))
    if isinstance(obj, dict):
        return obj.get(str(key), obj.get(key))
    if isinstance(obj, list):
        if isinstance(key, int) and 0 <= key < len(obj):
            return obj[key]
        return None
    if hasattr(obj, str(key)):
        return getattr(obj, str(key))
    return None


def _set_property(obj: Any, prop: Any, value: Any):
    if obj is None:
        raise JSError("TypeError: Cannot set properties of null")

    key = _to_property_key(prop)

    if isinstance(obj, JSObject):
        obj.set(str(key), value)
        return
    if isinstance(obj, dict):
        obj[str(key)] = value
        return
    if isinstance(obj, list):
        if not isinstance(key, int) or key < 0:
            raise JSError(f"TypeError: Invalid array index '{key}'")
        while len(obj) <= key:
            obj.append(None)
        obj[key] = value
        return
    if hasattr(obj, str(key)):
        setattr(obj, str(key), value)
        return
    raise JSError(f"TypeError: Cannot set property '{key}'")


def _apply_unary(op: str, arg: Any) -> Any:
    if op == "!":
        return not _truthy(arg)
    if op == "-":
        return -_to_number(arg)
    if op == "+":
        return _to_number(arg)
    raise JSError(f"Unsupported unary operator: {op}")


def _apply_binary(op: str, left: Any, right: Any) -> Any:
    if op == "+":
        if _is_stringy(left) or _is_stringy(right):
            return f"{left}{right}"
        return _to_number(left) + _to_number(right)
    if op == "-":
        return _to_number(left) - _to_number(right)
    if op == "*":
        return _to_number(left) * _to_number(right)
    if op == "/":
        return _to_number(left) / _to_number(right)
    if op == "&":
        return int(_to_number(left)) & int(_to_number(right))
    if op == "^":
        return int(_to_number(left)) ^ int(_to_number(right))
    if op == "|":
        return int(_to_number(left)) | int(_to_number(right))
    if op == "==":
        return _js_loose_eq(left, right)
    if op == "!=":
        return not _js_loose_eq(left, right)
    if op == "===":
        return _js_strict_eq(left, right)
    if op == "!==":
        return not _js_strict_eq(left, right)
    if op == "<":
        return _to_number(left) < _to_number(right)
    if op == "<=":
        return _to_number(left) <= _to_number(right)
    if op == ">":
        return _to_number(left) > _to_number(right)
    if op == ">=":
        return _to_number(left) >= _to_number(right)
    raise JSError(f"Unsupported binary operator: {op}")


class _JITCompiler:
    def __init__(self):
        self._counter = 0
        self._helper_defs: list[str] = []

    def compile(self, program: Program) -> CompiledProgram:
        program_lines = self._emit_callable("__js_program", program.body)
        python_source = "\n".join(self._helper_defs + program_lines) + "\n"
        namespace: dict[str, Any] = {
            "JSFunction": JSFunction,
            "JSReturn": JSReturn,
            "JSThrow": JSThrow,
            "Scope": Scope,
        }
        code = compile(python_source, "<medrano-jit>", "exec")
        exec(code, namespace, namespace)
        entrypoint = namespace["__js_program"]
        return CompiledProgram(program=program, python_source=python_source, entrypoint=entrypoint)

    def _next_name(self, prefix: str) -> str:
        self._counter += 1
        return f"__js_{prefix}_{self._counter}"

    def _indent(self, lines: list[str], level: int = 1) -> list[str]:
        prefix = "    " * level
        return [f"{prefix}{line}" if line else "" for line in lines]

    def _emit_callable(self, name: str, body: list[object]) -> list[str]:
        lines = [f"def {name}(__rt, __scope):", "    __result = None"]
        stmt_lines = self._compile_statements(body, "__scope")
        if stmt_lines:
            lines.extend(self._indent(stmt_lines))
        lines.append("    return __result")
        return lines

    def _compile_function_impl(self, body: object) -> str:
        name = self._next_name("fn")
        if isinstance(body, BlockStatement):
            lines = self._emit_callable(name, body.body)
        else:
            expr = self._compile_expression(body, "__scope")
            lines = [
                f"def {name}(__rt, __scope):",
                f"    return {expr}",
            ]
        self._helper_defs.extend(lines)
        self._helper_defs.append("")
        return name

    def _compile_block_impl(self, block: BlockStatement) -> str:
        name = self._next_name("block")
        lines = self._emit_callable(name, block.body)
        self._helper_defs.extend(lines)
        self._helper_defs.append("")
        return name

    def _compile_statements(self, statements: list[object], scope_name: str) -> list[str]:
        lines: list[str] = []
        for stmt in statements:
            lines.extend(self._compile_statement(stmt, scope_name))
        return lines

    def _compile_statement(self, stmt: object, scope_name: str) -> list[str]:
        if isinstance(stmt, BlockStatement):
            block_name = self._compile_block_impl(stmt)
            return [f"__result = {block_name}(__rt, Scope(parent={scope_name}))"]

        if isinstance(stmt, VarDeclaration):
            value_expr = self._compile_expression(stmt.init, scope_name) if stmt.init is not None else "None"
            return [
                f"__result = {value_expr}",
                f"{scope_name}.declare({stmt.name!r}, __result, is_const={stmt.kind == 'const'})",
            ]

        if isinstance(stmt, FunctionDeclaration):
            impl_name = self._compile_function_impl(stmt.body)
            return [
                f"__result = JSFunction(params={stmt.params!r}, body=None, closure={scope_name}, is_arrow=False, impl={impl_name}, name={stmt.name!r})",
                f"{scope_name}.declare({stmt.name!r}, __result, is_const=False)",
            ]

        if isinstance(stmt, ReturnStatement):
            value_expr = self._compile_expression(stmt.argument, scope_name) if stmt.argument is not None else "None"
            return [f"raise JSReturn({value_expr})"]

        if isinstance(stmt, ThrowStatement):
            return [f"raise JSThrow({self._compile_expression(stmt.argument, scope_name)})"]

        if isinstance(stmt, IfStatement):
            lines = [f"if __rt._truthy({self._compile_expression(stmt.test, scope_name)}):"]
            consequent_lines = self._compile_statement(stmt.consequent, scope_name) or ["pass"]
            lines.extend(self._indent(consequent_lines))
            lines.append("else:")
            if stmt.alternate is not None:
                alternate_lines = self._compile_statement(stmt.alternate, scope_name) or ["pass"]
            else:
                alternate_lines = ["__result = None"]
            lines.extend(self._indent(alternate_lines))
            return lines

        if isinstance(stmt, WhileStatement):
            lines = [
                "__result = None",
                f"while __rt._truthy({self._compile_expression(stmt.test, scope_name)}):",
            ]
            body_lines = self._compile_statement(stmt.body, scope_name) or ["pass"]
            lines.extend(self._indent(body_lines))
            return lines

        if isinstance(stmt, ForStatement):
            loop_scope = self._next_name("loop_scope")
            lines = [f"{loop_scope} = Scope(parent={scope_name})"]
            if stmt.init is not None:
                if isinstance(stmt.init, VarDeclaration):
                    lines.extend(self._compile_statement(stmt.init, loop_scope))
                else:
                    discard_name = self._next_name("discard")
                    lines.append(f"{discard_name} = {self._compile_expression(stmt.init, loop_scope)}")
            lines.append("__result = None")
            lines.append("while True:")
            inner_lines: list[str] = []
            if stmt.test is not None:
                inner_lines.append(f"if not __rt._truthy({self._compile_expression(stmt.test, loop_scope)}):")
                inner_lines.append("    break")
            inner_lines.extend(self._compile_statement(stmt.body, loop_scope) or ["pass"])
            if stmt.update is not None:
                discard_name = self._next_name("discard")
                inner_lines.append(f"{discard_name} = {self._compile_expression(stmt.update, loop_scope)}")
            lines.extend(self._indent(inner_lines))
            return lines

        if isinstance(stmt, TryCatchStatement):
            try_block = self._compile_block_impl(stmt.try_block)
            catch_block = self._compile_block_impl(stmt.catch_block)
            exc_name = self._next_name("exc")
            catch_scope = self._next_name("catch_scope")
            return [
                "try:",
                f"    __result = {try_block}(__rt, Scope(parent={scope_name}))",
                f"except JSThrow as {exc_name}:",
                f"    {catch_scope} = Scope(parent={scope_name})",
                f"    {catch_scope}.declare({stmt.catch_name!r}, {exc_name}.value)",
                f"    __result = {catch_block}(__rt, Scope(parent={catch_scope}))",
            ]

        if isinstance(stmt, ExpressionStatement):
            return [f"__result = {self._compile_expression(stmt.expression, scope_name)}"]

        raise JSError(f"Unsupported statement type: {type(stmt).__name__}")

    def _compile_expression(self, expr: object | None, scope_name: str) -> str:
        if expr is None:
            return "None"

        if isinstance(expr, Literal):
            return repr(expr.value)

        if isinstance(expr, Identifier):
            return f"{scope_name}.get({expr.name!r})"

        if isinstance(expr, ArrayLiteral):
            inner = ", ".join(self._compile_expression(item, scope_name) for item in expr.elements)
            return f"[{inner}]"

        if isinstance(expr, ObjectLiteral):
            parts = [
                f"{prop.key!r}: {self._compile_expression(prop.value, scope_name)}"
                for prop in expr.properties
            ]
            return "{" + ", ".join(parts) + "}"

        if isinstance(expr, FunctionExpression):
            impl_name = self._compile_function_impl(expr.body)
            return (
                f"JSFunction(params={expr.params!r}, body=None, closure={scope_name}, "
                f"is_arrow={expr.is_arrow!r}, impl={impl_name})"
            )

        if isinstance(expr, SequenceExpression):
            thunks = ", ".join(
                f"(lambda: {self._compile_expression(item, scope_name)})"
                for item in expr.expressions
            )
            return f"__rt._sequence({thunks})"

        if isinstance(expr, UnaryExpression):
            return f"__rt._unary({expr.op!r}, {self._compile_expression(expr.argument, scope_name)})"

        if isinstance(expr, UpdateExpression):
            delta = 1 if expr.op == "++" else -1
            if isinstance(expr.argument, Identifier):
                return (
                    f"__rt._update_name({scope_name}, {expr.argument.name!r}, "
                    f"{delta}, prefix={expr.prefix!r})"
                )
            if isinstance(expr.argument, MemberExpression):
                return (
                    f"__rt._update_member({self._compile_expression(expr.argument.obj, scope_name)}, "
                    f"{self._compile_expression(expr.argument.prop, scope_name)}, "
                    f"{delta}, prefix={expr.prefix!r})"
                )
            raise JSError("Invalid update target")

        if isinstance(expr, BinaryExpression):
            if expr.op == "||":
                return (
                    f"__rt._logical_or(lambda: {self._compile_expression(expr.left, scope_name)}, "
                    f"lambda: {self._compile_expression(expr.right, scope_name)})"
                )
            if expr.op == "&&":
                return (
                    f"__rt._logical_and(lambda: {self._compile_expression(expr.left, scope_name)}, "
                    f"lambda: {self._compile_expression(expr.right, scope_name)})"
                )
            if expr.op == "??":
                return (
                    f"__rt._nullish(lambda: {self._compile_expression(expr.left, scope_name)}, "
                    f"lambda: {self._compile_expression(expr.right, scope_name)})"
                )
            return (
                f"__rt._binary({expr.op!r}, {self._compile_expression(expr.left, scope_name)}, "
                f"{self._compile_expression(expr.right, scope_name)})"
            )

        if isinstance(expr, ConditionalExpression):
            return (
                f"({self._compile_expression(expr.consequent, scope_name)} "
                f"if __rt._truthy({self._compile_expression(expr.test, scope_name)}) "
                f"else {self._compile_expression(expr.alternate, scope_name)})"
            )

        if isinstance(expr, MemberExpression):
            return (
                f"__rt._get_member({self._compile_expression(expr.obj, scope_name)}, "
                f"{self._compile_expression(expr.prop, scope_name)}, optional={expr.optional!r})"
            )

        if isinstance(expr, AssignmentExpression):
            value_expr = self._compile_expression(expr.value, scope_name)
            if isinstance(expr.target, Identifier):
                return f"__rt._assign_name({scope_name}, {expr.target.name!r}, {value_expr})"
            if isinstance(expr.target, MemberExpression):
                return (
                    f"__rt._assign_member({self._compile_expression(expr.target.obj, scope_name)}, "
                    f"{self._compile_expression(expr.target.prop, scope_name)}, "
                    f"{value_expr}, optional={expr.target.optional!r})"
                )
            raise JSError("Invalid assignment target")

        if isinstance(expr, CallExpression):
            args_expr = ", ".join(self._compile_expression(arg, scope_name) for arg in expr.args)
            return (
                f"__rt._call({self._compile_expression(expr.callee, scope_name)}, "
                f"[{args_expr}], optional={expr.optional!r})"
            )

        raise JSError(f"Unsupported expression type: {type(expr).__name__}")


class JSRuntime:
    def __init__(self, globals_dict: dict[str, Any] | None = None):
        self.global_scope = Scope(parent=None)
        self._compile_cache: dict[str, CompiledProgram] = {}
        self._execution_frames: list[_ExecutionFrame] = []
        self._current_source_name: str | None = None
        self._current_source_text: str | None = None
        if globals_dict:
            for name, value in globals_dict.items():
                self.global_scope.declare(name, value, is_const=True)

    def compile(self, source: str) -> CompiledProgram:
        cached = self._compile_cache.get(source)
        if cached is not None:
            return cached
        compiled = self.compile_program(parse_js(source))
        self._compile_cache[source] = compiled
        return compiled

    def compile_program(self, program: Program) -> CompiledProgram:
        return _JITCompiler().compile(program)

    def transpile(self, source: str) -> str:
        return self.compile(source).python_source

    def execute(self, source: str, source_name: str | None = None) -> Any:
        if source_name is not None:
            return self._execute_with_diagnostics(parse_js(source, source_name=source_name), source, source_name)
        compiled = self.compile(source)
        return compiled.entrypoint(self, self.global_scope)

    def eval_program(self, program: Program) -> Any:
        compiled = self.compile_program(program)
        return compiled.entrypoint(self, self.global_scope)

    def _execute_with_diagnostics(self, program: Program, source: str, source_name: str) -> Any:
        previous_source_name = self._current_source_name
        previous_source_text = self._current_source_text
        self._current_source_name = source_name
        self._current_source_text = source
        self._push_frame("<global>", source_name, source)
        try:
            result = None
            for stmt in program.body:
                result = self._eval_statement(stmt, self.global_scope)
            return result
        except JSThrow as exc:
            js_error = JSError(_js_value_to_error_text(exc.value))
            self._annotate_error(js_error)
            raise js_error from None
        except JSError as exc:
            self._annotate_error(exc)
            raise
        finally:
            self._pop_frame()
            self._current_source_name = previous_source_name
            self._current_source_text = previous_source_text

    def _push_frame(self, function_name: str, source_name: str, source_text: str):
        self._execution_frames.append(
            _ExecutionFrame(function_name=function_name, source_name=source_name, source_text=source_text)
        )

    def _pop_frame(self):
        if self._execution_frames:
            self._execution_frames.pop()

    def _annotate_error(self, exc: JSError):
        if not self._execution_frames:
            return

        current_frame = self._execution_frames[-1]
        current_node = current_frame.node_stack[-1] if current_frame.node_stack else None
        if exc.source_name is None:
            exc.source_name = current_frame.source_name
        if exc.source_text is None:
            exc.source_text = current_frame.source_text
        if exc.pos is None and current_node is not None:
            exc.pos = getattr(current_node, "pos", None)
        if exc.stack:
            return

        stack: list[JSStackFrame] = []
        for frame in reversed(self._execution_frames):
            node = frame.node_stack[-1] if frame.node_stack else None
            pos = getattr(node, "pos", None) if node is not None else None
            line, column = _line_col_from_pos(frame.source_text, pos)
            stack.append(
                JSStackFrame(
                    function_name=frame.function_name,
                    source_name=frame.source_name,
                    line=line,
                    column=column,
                )
            )
        exc.stack = stack

    def _with_node(self, node: object, fn: Callable[[], Any]) -> Any:
        if self._execution_frames:
            self._execution_frames[-1].node_stack.append(node)
        try:
            return fn()
        except JSError as exc:
            self._annotate_error(exc)
            raise
        except JSThrow:
            raise
        finally:
            if self._execution_frames and self._execution_frames[-1].node_stack:
                self._execution_frames[-1].node_stack.pop()

    def _truthy(self, value: Any) -> bool:
        return _truthy(value)

    def _sequence(self, *thunks: Callable[[], Any]) -> Any:
        result = None
        for thunk in thunks:
            result = thunk()
        return result

    def _logical_or(self, left: Callable[[], Any], right: Callable[[], Any]) -> Any:
        left_value = left()
        return left_value if _truthy(left_value) else right()

    def _logical_and(self, left: Callable[[], Any], right: Callable[[], Any]) -> Any:
        left_value = left()
        return right() if _truthy(left_value) else left_value

    def _nullish(self, left: Callable[[], Any], right: Callable[[], Any]) -> Any:
        left_value = left()
        return left_value if left_value is not None else right()

    def _unary(self, op: str, arg: Any) -> Any:
        return _apply_unary(op, arg)

    def _binary(self, op: str, left: Any, right: Any) -> Any:
        return _apply_binary(op, left, right)

    def _get_member(self, obj: Any, prop: Any, *, optional: bool = False) -> Any:
        if optional and obj is None:
            return None
        return _get_property(obj, prop)

    def _assign_name(self, scope: Scope, name: str, value: Any) -> Any:
        scope.assign(name, value)
        return value

    def _assign_member(self, obj: Any, prop: Any, value: Any, *, optional: bool = False) -> Any:
        if optional and obj is None:
            raise JSError("TypeError: Cannot set property on null with optional chain")
        _set_property(obj, prop, value)
        return value

    def _update_name(self, scope: Scope, name: str, delta: int, *, prefix: bool) -> Any:
        current = scope.get(name)
        next_value = _to_number(current) + delta
        scope.assign(name, next_value)
        return next_value if prefix else current

    def _update_member(self, obj: Any, prop: Any, delta: int, *, prefix: bool) -> Any:
        current = _get_property(obj, prop)
        next_value = _to_number(current) + delta
        _set_property(obj, prop, next_value)
        return next_value if prefix else current

    def _call(self, callee: Any, args: list[Any], *, optional: bool = False) -> Any:
        if optional and callee is None:
            return None
        if isinstance(callee, NativeFunction):
            return callee(*args)
        if isinstance(callee, JSFunction):
            return callee.call(self, args)
        if callable(callee):
            return callee(*args)
        raise JSError("TypeError: value is not a function")

    def _eval_block(self, block: BlockStatement, parent_scope: Scope) -> Any:
        block_scope = Scope(parent=parent_scope)
        result = None
        for stmt in block.body:
            result = self._eval_statement(stmt, block_scope)
        return result

    def _eval_statement(self, stmt: Any, scope: Scope) -> Any:
        def evaluate() -> Any:
            if isinstance(stmt, BlockStatement):
                return self._eval_block(stmt, scope)

            if isinstance(stmt, VarDeclaration):
                value = self._eval_expression(stmt.init, scope) if stmt.init is not None else None
                scope.declare(stmt.name, value, is_const=(stmt.kind == "const"))
                return value

            if isinstance(stmt, FunctionDeclaration):
                func = JSFunction(
                    params=stmt.params,
                    body=stmt.body,
                    closure=scope,
                    name=stmt.name,
                    source_name=self._current_source_name,
                    source_text=self._current_source_text,
                )
                scope.declare(stmt.name, func, is_const=False)
                return func

            if isinstance(stmt, ReturnStatement):
                value = self._eval_expression(stmt.argument, scope) if stmt.argument is not None else None
                raise JSReturn(value)

            if isinstance(stmt, ThrowStatement):
                value = self._eval_expression(stmt.argument, scope)
                raise JSThrow(value)

            if isinstance(stmt, IfStatement):
                if _truthy(self._eval_expression(stmt.test, scope)):
                    return self._eval_statement(stmt.consequent, scope)
                if stmt.alternate is not None:
                    return self._eval_statement(stmt.alternate, scope)
                return None

            if isinstance(stmt, WhileStatement):
                result = None
                while _truthy(self._eval_expression(stmt.test, scope)):
                    result = self._eval_statement(stmt.body, scope)
                return result

            if isinstance(stmt, ForStatement):
                loop_scope = Scope(parent=scope)
                result = None
                if stmt.init is not None:
                    if isinstance(stmt.init, VarDeclaration):
                        self._eval_statement(stmt.init, loop_scope)
                    else:
                        self._eval_expression(stmt.init, loop_scope)
                while True:
                    if stmt.test is not None and not _truthy(self._eval_expression(stmt.test, loop_scope)):
                        break
                    result = self._eval_statement(stmt.body, loop_scope)
                    if stmt.update is not None:
                        self._eval_expression(stmt.update, loop_scope)
                return result

            if isinstance(stmt, TryCatchStatement):
                try:
                    return self._eval_block(stmt.try_block, scope)
                except JSThrow as exc:
                    catch_scope = Scope(parent=scope)
                    catch_scope.declare(stmt.catch_name, exc.value)
                    return self._eval_block(stmt.catch_block, catch_scope)

            if isinstance(stmt, ExpressionStatement):
                return self._eval_expression(stmt.expression, scope)

            raise JSError(f"Unsupported statement type: {type(stmt).__name__}")

        return self._with_node(stmt, evaluate)

    def _eval_expression(self, expr: Any, scope: Scope) -> Any:
        if expr is None:
            return None

        def evaluate() -> Any:
            if isinstance(expr, Literal):
                return expr.value

            if isinstance(expr, Identifier):
                return scope.get(expr.name)

            if isinstance(expr, ArrayLiteral):
                return [self._eval_expression(item, scope) for item in expr.elements]

            if isinstance(expr, ObjectLiteral):
                obj: dict[str, Any] = {}
                for prop in expr.properties:
                    obj[prop.key] = self._eval_expression(prop.value, scope)
                return obj

            if isinstance(expr, FunctionExpression):
                return JSFunction(
                    params=expr.params,
                    body=expr.body,
                    closure=scope,
                    is_arrow=expr.is_arrow,
                    name=expr.name or "<anonymous>",
                    source_name=self._current_source_name,
                    source_text=self._current_source_text,
                )

            if isinstance(expr, SequenceExpression):
                result = None
                for sequence_expr in expr.expressions:
                    result = self._eval_expression(sequence_expr, scope)
                return result

            if isinstance(expr, UnaryExpression):
                arg = self._eval_expression(expr.argument, scope)
                return _apply_unary(expr.op, arg)

            if isinstance(expr, UpdateExpression):
                delta = 1 if expr.op == "++" else -1
                if isinstance(expr.argument, Identifier):
                    return self._update_name(scope, expr.argument.name, delta, prefix=expr.prefix)
                if isinstance(expr.argument, MemberExpression):
                    obj = self._eval_expression(expr.argument.obj, scope)
                    prop_value = self._eval_expression(expr.argument.prop, scope)
                    return self._update_member(obj, prop_value, delta, prefix=expr.prefix)
                raise JSError("Invalid update target")

            if isinstance(expr, BinaryExpression):
                if expr.op == "||":
                    left = self._eval_expression(expr.left, scope)
                    return left if _truthy(left) else self._eval_expression(expr.right, scope)

                if expr.op == "&&":
                    left = self._eval_expression(expr.left, scope)
                    return self._eval_expression(expr.right, scope) if _truthy(left) else left

                if expr.op == "??":
                    left = self._eval_expression(expr.left, scope)
                    return left if left is not None else self._eval_expression(expr.right, scope)

                left = self._eval_expression(expr.left, scope)
                right = self._eval_expression(expr.right, scope)
                return _apply_binary(expr.op, left, right)

            if isinstance(expr, ConditionalExpression):
                return (
                    self._eval_expression(expr.consequent, scope)
                    if _truthy(self._eval_expression(expr.test, scope))
                    else self._eval_expression(expr.alternate, scope)
                )

            if isinstance(expr, MemberExpression):
                obj = self._eval_expression(expr.obj, scope)
                if expr.optional and obj is None:
                    return None
                prop_value = self._eval_expression(expr.prop, scope)
                return _get_property(obj, prop_value)

            if isinstance(expr, AssignmentExpression):
                value = self._eval_expression(expr.value, scope)
                if isinstance(expr.target, Identifier):
                    scope.assign(expr.target.name, value)
                    return value
                if isinstance(expr.target, MemberExpression):
                    obj = self._eval_expression(expr.target.obj, scope)
                    if expr.target.optional and obj is None:
                        raise JSError("TypeError: Cannot set property on null with optional chain")
                    prop_value = self._eval_expression(expr.target.prop, scope)
                    _set_property(obj, prop_value, value)
                    return value
                raise JSError("Invalid assignment target")

            if isinstance(expr, CallExpression):
                callee = self._eval_expression(expr.callee, scope)
                if expr.optional and callee is None:
                    return None
                args = [self._eval_expression(arg, scope) for arg in expr.args]
                return self._call(callee, args)

            raise JSError(f"Unsupported expression type: {type(expr).__name__}")

        return self._with_node(expr, evaluate)
