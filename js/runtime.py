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
	SequenceExpression,
	ReturnStatement,
	ThrowStatement,
	TryCatchStatement,
	UnaryExpression,
	VarDeclaration,
	WhileStatement,
	parse_js,
)


class JSError(Exception):
	pass


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

	def call(self, runtime: "JSRuntime", args: list[Any]) -> Any:
		call_scope = Scope(parent=self.closure)
		for i, param in enumerate(self.params):
			call_scope.declare(param, args[i] if i < len(args) else None)
		try:
			if isinstance(self.body, BlockStatement):
				return runtime._eval_block(self.body, call_scope)
			return runtime._eval_expression(self.body, call_scope)
		except JSReturn as ret:
			return ret.value


def _truthy(value: Any) -> bool:
	return bool(value)


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


class JSRuntime:
	def __init__(self, globals_dict: dict[str, Any] | None = None):
		self.global_scope = Scope(parent=None)
		if globals_dict:
			for name, value in globals_dict.items():
				self.global_scope.declare(name, value, is_const=True)

	def execute(self, source: str) -> Any:
		program = parse_js(source)
		return self.eval_program(program)

	def eval_program(self, program: Program) -> Any:
		result = None
		for stmt in program.body:
			result = self._eval_statement(stmt, self.global_scope)
		return result

	def _eval_block(self, block: BlockStatement, parent_scope: Scope) -> Any:
		block_scope = Scope(parent=parent_scope)
		result = None
		for stmt in block.body:
			result = self._eval_statement(stmt, block_scope)
		return result

	def _eval_statement(self, stmt: Any, scope: Scope) -> Any:
		if isinstance(stmt, BlockStatement):
			return self._eval_block(stmt, scope)

		if isinstance(stmt, VarDeclaration):
			value = self._eval_expression(stmt.init, scope) if stmt.init is not None else None
			scope.declare(stmt.name, value, is_const=(stmt.kind == "const"))
			return value

		if isinstance(stmt, FunctionDeclaration):
			func = JSFunction(params=stmt.params, body=stmt.body, closure=scope)
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

	def _eval_expression(self, expr: Any, scope: Scope) -> Any:
		if expr is None:
			return None

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
			return JSFunction(params=expr.params, body=expr.body, closure=scope, is_arrow=expr.is_arrow)

		if isinstance(expr, SequenceExpression):
			result = None
			for sequence_expr in expr.expressions:
				result = self._eval_expression(sequence_expr, scope)
			return result

		if isinstance(expr, UnaryExpression):
			arg = self._eval_expression(expr.argument, scope)
			if expr.op == "!":
				return not _truthy(arg)
			if expr.op == "-":
				return -_to_number(arg)
			if expr.op == "+":
				return _to_number(arg)
			raise JSError(f"Unsupported unary operator: {expr.op}")

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

			if expr.op == "+":
				if _is_stringy(left) or _is_stringy(right):
					return f"{left}{right}"
				return _to_number(left) + _to_number(right)
			if expr.op == "-":
				return _to_number(left) - _to_number(right)
			if expr.op == "*":
				return _to_number(left) * _to_number(right)
			if expr.op == "/":
				return _to_number(left) / _to_number(right)
			if expr.op == "&":
				return int(_to_number(left)) & int(_to_number(right))
			if expr.op == "^":
				return int(_to_number(left)) ^ int(_to_number(right))
			if expr.op == "|":
				return int(_to_number(left)) | int(_to_number(right))
			if expr.op == "==":
				return _js_loose_eq(left, right)
			if expr.op == "!=":
				return not _js_loose_eq(left, right)
			if expr.op == "===":
				return _js_strict_eq(left, right)
			if expr.op == "!==":
				return not _js_strict_eq(left, right)
			if expr.op == "<":
				return _to_number(left) < _to_number(right)
			if expr.op == "<=":
				return _to_number(left) <= _to_number(right)
			if expr.op == ">":
				return _to_number(left) > _to_number(right)
			if expr.op == ">=":
				return _to_number(left) >= _to_number(right)

			raise JSError(f"Unsupported binary operator: {expr.op}")

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
			prop_value = self._eval_expression(expr.prop, scope) if expr.computed else self._eval_expression(expr.prop, scope)
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
			if isinstance(callee, NativeFunction):
				return callee(*args)
			if isinstance(callee, JSFunction):
				return callee.call(self, args)
			if callable(callee):
				return callee(*args)
			raise JSError("TypeError: value is not a function")

		raise JSError(f"Unsupported expression type: {type(expr).__name__}")
