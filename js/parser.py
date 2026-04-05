from __future__ import annotations

from dataclasses import dataclass
import html


class JSParseError(Exception):
	pass


@dataclass
class Token:
	kind: str
	value: str
	pos: int


KEYWORDS = {
	"var",
	"let",
	"const",
	"true",
	"false",
	"null",
	"function",
	"return",
	"if",
	"else",
	"for",
	"while",
	"try",
	"catch",
	"throw",
}

TWO_CHAR_OPS = {
	"==",
	"!=",
	"<=",
	">=",
	"&&",
	"||",
	"=>",
	"??",
	"?.",
}

THREE_CHAR_OPS = {
	"===",
	"!==",
}

ONE_CHAR_OPS = {
	"=",
	"+",
	"-",
	"*",
	"/",
	"<",
	">",
	"!",
	".",
	"?",
	":",
	"&",
	"|",
	"^",
}

PUNCT = {
	"(",
	")",
	"{",
	"}",
	"[",
	"]",
	";",
	",",
}


def preprocess_js(source: str) -> str:
	return html.unescape(source)


def _is_ident_start(ch: str) -> bool:
	return ch.isalpha() or ch in {"_", "$"}


def _is_ident_continue(ch: str) -> bool:
	return ch.isalnum() or ch in {"_", "$"}


def tokenize_js(source: str) -> list[Token]:
	source = preprocess_js(source)
	tokens: list[Token] = []
	i = 0
	n = len(source)

	while i < n:
		ch = source[i]

		if ch.isspace():
			i += 1
			continue

		if ch == "/" and i + 1 < n and source[i + 1] == "/":
			i += 2
			while i < n and source[i] != "\n":
				i += 1
			continue

		if ch == "/" and i + 1 < n and source[i + 1] == "*":
			end = source.find("*/", i + 2)
			if end == -1:
				raise JSParseError("Unterminated block comment")
			i = end + 2
			continue

		if ch in {'"', "'"}:
			quote = ch
			start = i
			i += 1
			out = []
			while i < n:
				c = source[i]
				if c == "\\":
					i += 1
					if i >= n:
						break
					esc = source[i]
					escapes = {
						"n": "\n",
						"t": "\t",
						"r": "\r",
						"\\": "\\",
						'"': '"',
						"'": "'",
					}
					out.append(escapes.get(esc, esc))
					i += 1
					continue
				if c == quote:
					i += 1
					break
				out.append(c)
				i += 1
			else:
				raise JSParseError("Unterminated string")
			tokens.append(Token("string", "".join(out), start))
			continue

		if ch == "`":
			start = i
			i += 1
			out = []
			while i < n:
				c = source[i]
				if c == "\\":
					i += 1
					if i >= n:
						break
					out.append(source[i])
					i += 1
					continue
				if c == "`":
					i += 1
					break
				out.append(c)
				i += 1
			else:
				raise JSParseError("Unterminated template literal")
			tokens.append(Token("template", "".join(out), start))
			continue

		if ch.isdigit():
			start = i
			i += 1
			while i < n and source[i].isdigit():
				i += 1
			if i < n and source[i] == ".":
				i += 1
				while i < n and source[i].isdigit():
					i += 1
			tokens.append(Token("number", source[start:i], start))
			continue

		if _is_ident_start(ch):
			start = i
			i += 1
			while i < n and _is_ident_continue(source[i]):
				i += 1
			value = source[start:i]
			kind = "keyword" if value in KEYWORDS else "identifier"
			tokens.append(Token(kind, value, start))
			continue

		if i + 2 < n and source[i : i + 3] in THREE_CHAR_OPS:
			tokens.append(Token("op", source[i : i + 3], i))
			i += 3
			continue

		if i + 1 < n and source[i : i + 2] in TWO_CHAR_OPS:
			tokens.append(Token("op", source[i : i + 2], i))
			i += 2
			continue

		if ch in ONE_CHAR_OPS:
			tokens.append(Token("op", ch, i))
			i += 1
			continue

		if ch in PUNCT:
			tokens.append(Token("punct", ch, i))
			i += 1
			continue

		raise JSParseError(f"Unexpected character {ch!r} at position {i}")

	tokens.append(Token("eof", "", n))
	return tokens


@dataclass
class Program:
	body: list[object]


@dataclass
class BlockStatement:
	body: list[object]


@dataclass
class VarDeclaration:
	kind: str
	name: str
	init: object | None


@dataclass
class FunctionDeclaration:
	name: str
	params: list[str]
	body: BlockStatement


@dataclass
class ReturnStatement:
	argument: object | None


@dataclass
class IfStatement:
	test: object
	consequent: object
	alternate: object | None


@dataclass
class WhileStatement:
	test: object
	body: object


@dataclass
class ForStatement:
	init: object | None
	test: object | None
	update: object | None
	body: object


@dataclass
class TryCatchStatement:
	try_block: BlockStatement
	catch_name: str
	catch_block: BlockStatement


@dataclass
class ThrowStatement:
	argument: object


@dataclass
class ExpressionStatement:
	expression: object


@dataclass
class Literal:
	value: object


@dataclass
class Identifier:
	name: str


@dataclass
class ArrayLiteral:
	elements: list[object]


@dataclass
class ObjectProperty:
	key: str
	value: object


@dataclass
class ObjectLiteral:
	properties: list[ObjectProperty]


@dataclass
class UnaryExpression:
	op: str
	argument: object


@dataclass
class BinaryExpression:
	left: object
	op: str
	right: object


@dataclass
class ConditionalExpression:
	test: object
	consequent: object
	alternate: object


@dataclass
class SequenceExpression:
	expressions: list[object]


@dataclass
class AssignmentExpression:
	target: object
	value: object


@dataclass
class MemberExpression:
	obj: object
	prop: object
	computed: bool = False
	optional: bool = False


@dataclass
class CallExpression:
	callee: object
	args: list[object]
	optional: bool = False


@dataclass
class FunctionExpression:
	params: list[str]
	body: object
	is_arrow: bool = False


class JSParser:
	def __init__(self, source: str):
		self.tokens = tokenize_js(source)
		self.i = 0

	def _peek(self, offset: int = 0) -> Token:
		idx = self.i + offset
		if idx >= len(self.tokens):
			return self.tokens[-1]
		return self.tokens[idx]

	def _advance(self) -> Token:
		tok = self.tokens[self.i]
		self.i += 1
		return tok

	def _match(self, kind: str, value: str | None = None) -> bool:
		tok = self._peek()
		if tok.kind != kind:
			return False
		if value is not None and tok.value != value:
			return False
		self._advance()
		return True

	def _expect(self, kind: str, value: str | None = None) -> Token:
		tok = self._peek()
		if tok.kind != kind or (value is not None and tok.value != value):
			expected = f"{kind}:{value}" if value is not None else kind
			got = f"{tok.kind}:{tok.value}"
			raise JSParseError(f"Expected {expected}, got {got} at {tok.pos}")
		return self._advance()

	def parse(self) -> Program:
		body: list[object] = []
		while self._peek().kind != "eof":
			if self._match("punct", ";"):
				continue
			body.append(self._statement())
			self._match("punct", ";")
		return Program(body=body)

	def _statement(self) -> object:
		tok = self._peek()
		if tok.kind == "punct" and tok.value == "{":
			return self._block()
		if tok.kind == "keyword":
			if tok.value in {"var", "let", "const"}:
				decl = self._var_decl()
				self._match("punct", ";")
				return decl
			if tok.value == "function":
				return self._function_declaration()
			if tok.value == "return":
				self._advance()
				if self._peek().kind == "punct" and self._peek().value == ";":
					return ReturnStatement(argument=None)
				return ReturnStatement(argument=self._expression())
			if tok.value == "if":
				return self._if_statement()
			if tok.value == "while":
				return self._while_statement()
			if tok.value == "for":
				return self._for_statement()
			if tok.value == "try":
				return self._try_catch_statement()
			if tok.value == "throw":
				self._advance()
				return ThrowStatement(argument=self._expression())
		return ExpressionStatement(expression=self._expression())

	def _block(self) -> BlockStatement:
		self._expect("punct", "{")
		body: list[object] = []
		while not self._match("punct", "}"):
			if self._peek().kind == "eof":
				raise JSParseError("Unterminated block")
			if self._match("punct", ";"):
				continue
			body.append(self._statement())
			self._match("punct", ";")
		return BlockStatement(body=body)

	def _var_decl(self) -> VarDeclaration:
		kind = self._advance().value
		name = self._expect("identifier").value
		init = None
		if self._match("op", "="):
			init = self._expression()
		if kind == "const" and init is None:
			raise JSParseError("Missing initializer in const declaration")
		return VarDeclaration(kind=kind, name=name, init=init)

	def _function_declaration(self) -> FunctionDeclaration:
		self._expect("keyword", "function")
		name = self._expect("identifier").value
		params = self._parse_params()
		body = self._block()
		return FunctionDeclaration(name=name, params=params, body=body)

	def _parse_params(self) -> list[str]:
		self._expect("punct", "(")
		params: list[str] = []
		if not self._match("punct", ")"):
			while True:
				if self._peek().kind == "punct" and self._peek().value == ",":
					self._advance()
					continue
				if self._peek().kind == "punct" and self._peek().value == ")":
					self._advance()
					break
				params.append(self._expect("identifier").value)
				if self._match("punct", ")"):
					break
				self._expect("punct", ",")
		return params

	def _if_statement(self) -> IfStatement:
		self._expect("keyword", "if")
		self._expect("punct", "(")
		test = self._expression()
		self._expect("punct", ")")
		consequent = self._statement()
		alternate = None
		if self._match("keyword", "else"):
			alternate = self._statement()
		return IfStatement(test=test, consequent=consequent, alternate=alternate)

	def _while_statement(self) -> WhileStatement:
		self._expect("keyword", "while")
		self._expect("punct", "(")
		test = self._expression()
		self._expect("punct", ")")
		body = self._statement()
		return WhileStatement(test=test, body=body)

	def _for_statement(self) -> ForStatement:
		self._expect("keyword", "for")
		self._expect("punct", "(")

		init: object | None = None
		if not self._match("punct", ";"):
			if self._peek().kind == "keyword" and self._peek().value in {"var", "let", "const"}:
				init = self._var_decl()
			else:
				init = self._expression()
			self._expect("punct", ";")

		test: object | None = None
		if not self._match("punct", ";"):
			test = self._expression()
			self._expect("punct", ";")

		update: object | None = None
		if not self._match("punct", ")"):
			update = self._expression()
			self._expect("punct", ")")

		body = self._statement()
		return ForStatement(init=init, test=test, update=update, body=body)

	def _try_catch_statement(self) -> TryCatchStatement:
		self._expect("keyword", "try")
		try_block = self._block()
		self._expect("keyword", "catch")
		self._expect("punct", "(")
		catch_name = self._expect("identifier").value
		self._expect("punct", ")")
		catch_block = self._block()
		return TryCatchStatement(try_block=try_block, catch_name=catch_name, catch_block=catch_block)

	def _expression(self) -> object:
		expr = self._assignment()
		if not (self._peek().kind == "punct" and self._peek().value == ","):
			return expr
		exprs = [expr]
		while self._match("punct", ","):
			exprs.append(self._assignment())
		return SequenceExpression(expressions=exprs)

	def _is_arrow_function_start(self) -> bool:
		if self._peek().kind == "identifier" and self._peek(1).kind == "op" and self._peek(1).value == "=>":
			return True
		if self._peek().kind == "punct" and self._peek().value == "(":
			depth = 0
			idx = self.i
			while idx < len(self.tokens):
				tok = self.tokens[idx]
				if tok.kind == "punct" and tok.value == "(":
					depth += 1
				elif tok.kind == "punct" and tok.value == ")":
					depth -= 1
					if depth == 0:
						next_tok = self.tokens[idx + 1] if idx + 1 < len(self.tokens) else self.tokens[-1]
						return next_tok.kind == "op" and next_tok.value == "=>"
				idx += 1
		return False

	def _arrow_function_expression(self) -> FunctionExpression:
		params: list[str]
		if self._peek().kind == "identifier":
			params = [self._advance().value]
		else:
			params = self._parse_params()
		self._expect("op", "=>")
		if self._peek().kind == "punct" and self._peek().value == "{":
			body: object = self._block()
		else:
			body = self._assignment()
		return FunctionExpression(params=params, body=body, is_arrow=True)

	def _assignment(self) -> object:
		if self._is_arrow_function_start():
			return self._arrow_function_expression()
		left = self._conditional()
		if self._match("op", "="):
			if not isinstance(left, (Identifier, MemberExpression)):
				raise JSParseError("Invalid assignment target")
			return AssignmentExpression(target=left, value=self._assignment())
		return left

	def _conditional(self) -> object:
		expr = self._nullish()
		if self._match("op", "?"):
			consequent = self._assignment()
			self._expect("op", ":")
			alternate = self._assignment()
			return ConditionalExpression(test=expr, consequent=consequent, alternate=alternate)
		return expr

	def _nullish(self) -> object:
		expr = self._logical_or()
		while self._match("op", "??"):
			expr = BinaryExpression(left=expr, op="??", right=self._logical_or())
		return expr

	def _logical_or(self) -> object:
		expr = self._logical_and()
		while self._match("op", "||"):
			expr = BinaryExpression(left=expr, op="||", right=self._logical_and())
		return expr

	def _logical_and(self) -> object:
		expr = self._bitwise_or()
		while self._match("op", "&&"):
			expr = BinaryExpression(left=expr, op="&&", right=self._bitwise_or())
		return expr

	def _bitwise_or(self) -> object:
		expr = self._bitwise_xor()
		while self._match("op", "|"):
			expr = BinaryExpression(left=expr, op="|", right=self._bitwise_xor())
		return expr

	def _bitwise_xor(self) -> object:
		expr = self._bitwise_and()
		while self._match("op", "^"):
			expr = BinaryExpression(left=expr, op="^", right=self._bitwise_and())
		return expr

	def _bitwise_and(self) -> object:
		expr = self._equality()
		while self._match("op", "&"):
			expr = BinaryExpression(left=expr, op="&", right=self._equality())
		return expr

	def _equality(self) -> object:
		expr = self._comparison()
		while True:
			if self._match("op", "==="):
				expr = BinaryExpression(left=expr, op="===", right=self._comparison())
			elif self._match("op", "!=="):
				expr = BinaryExpression(left=expr, op="!==", right=self._comparison())
			elif self._match("op", "=="):
				expr = BinaryExpression(left=expr, op="==", right=self._comparison())
			elif self._match("op", "!="):
				expr = BinaryExpression(left=expr, op="!=", right=self._comparison())
			else:
				break
		return expr

	def _comparison(self) -> object:
		expr = self._term()
		while True:
			if self._match("op", "<"):
				expr = BinaryExpression(left=expr, op="<", right=self._term())
			elif self._match("op", "<="):
				expr = BinaryExpression(left=expr, op="<=", right=self._term())
			elif self._match("op", ">"):
				expr = BinaryExpression(left=expr, op=">", right=self._term())
			elif self._match("op", ">="):
				expr = BinaryExpression(left=expr, op=">=", right=self._term())
			else:
				break
		return expr

	def _term(self) -> object:
		expr = self._factor()
		while True:
			if self._match("op", "+"):
				expr = BinaryExpression(left=expr, op="+", right=self._factor())
			elif self._match("op", "-"):
				expr = BinaryExpression(left=expr, op="-", right=self._factor())
			else:
				break
		return expr

	def _factor(self) -> object:
		expr = self._unary()
		while True:
			if self._match("op", "*"):
				expr = BinaryExpression(left=expr, op="*", right=self._unary())
			elif self._match("op", "/"):
				expr = BinaryExpression(left=expr, op="/", right=self._unary())
			else:
				break
		return expr

	def _unary(self) -> object:
		if self._match("op", "!"):
			return UnaryExpression(op="!", argument=self._unary())
		if self._match("op", "-"):
			return UnaryExpression(op="-", argument=self._unary())
		if self._match("op", "+"):
			return UnaryExpression(op="+", argument=self._unary())
		return self._call_member()

	def _call_member(self) -> object:
		expr = self._primary()
		while True:
			if self._match("op", "."):
				prop = self._expect("identifier").value
				expr = MemberExpression(obj=expr, prop=Literal(value=prop), computed=False)
				continue

			if self._match("op", "?."):
				if self._match("punct", "("):
					args = self._parse_call_args(open_consumed=True)
					expr = CallExpression(callee=expr, args=args, optional=True)
					continue
				if self._match("punct", "["):
					prop_expr = self._expression()
					self._expect("punct", "]")
					expr = MemberExpression(obj=expr, prop=prop_expr, computed=True, optional=True)
					continue
				prop = self._expect("identifier").value
				expr = MemberExpression(obj=expr, prop=Literal(value=prop), computed=False, optional=True)
				continue

			if self._match("punct", "["):
				prop_expr = self._expression()
				self._expect("punct", "]")
				expr = MemberExpression(obj=expr, prop=prop_expr, computed=True)
				continue

			if self._match("punct", "("):
				args = self._parse_call_args(open_consumed=True)
				expr = CallExpression(callee=expr, args=args)
				continue

			break
		return expr

	def _parse_call_args(self, open_consumed: bool = False) -> list[object]:
		if not open_consumed:
			self._expect("punct", "(")
		args: list[object] = []
		if not self._match("punct", ")"):
			while True:
				if self._peek().kind == "punct" and self._peek().value == ")":
					self._advance()
					break
				args.append(self._assignment())
				if self._match("punct", ")"):
					break
				self._expect("punct", ",")
				if self._peek().kind == "punct" and self._peek().value == ")":
					self._advance()
					break
		return args

	def _primary(self) -> object:
		tok = self._peek()
		if tok.kind == "number":
			self._advance()
			if "." in tok.value:
				return Literal(value=float(tok.value))
			return Literal(value=int(tok.value))
		if tok.kind == "string":
			self._advance()
			return Literal(value=tok.value)
		if tok.kind == "template":
			self._advance()
			return Literal(value=tok.value)
		if tok.kind == "identifier":
			self._advance()
			return Identifier(name=tok.value)
		if tok.kind == "keyword":
			if tok.value == "true":
				self._advance()
				return Literal(value=True)
			if tok.value == "false":
				self._advance()
				return Literal(value=False)
			if tok.value == "null":
				self._advance()
				return Literal(value=None)
			if tok.value == "function":
				self._advance()
				if self._peek().kind == "identifier":
					self._advance()
				params = self._parse_params()
				body = self._block()
				return FunctionExpression(params=params, body=body, is_arrow=False)
		if self._match("punct", "("):
			expr = self._expression()
			self._expect("punct", ")")
			return expr
		if self._match("punct", "["):
			elements: list[object] = []
			if not self._match("punct", "]"):
				while True:
					if self._peek().kind == "punct" and self._peek().value == ",":
						elements.append(Literal(value=None))
						self._advance()
						if self._match("punct", "]"):
							break
						continue
					if self._peek().kind == "punct" and self._peek().value == "]":
						self._advance()
						break
					elements.append(self._assignment())
					if self._match("punct", "]"):
						break
					self._expect("punct", ",")
					if self._peek().kind == "punct" and self._peek().value == "]":
						self._advance()
						break
			return ArrayLiteral(elements=elements)
		if self._match("punct", "{"):
			props: list[ObjectProperty] = []
			if not self._match("punct", "}"):
				while True:
					if self._peek().kind == "punct" and self._peek().value == "}":
						self._advance()
						break
					key_tok = self._peek()
					if key_tok.kind not in {"identifier", "string"}:
						raise JSParseError(f"Invalid object key {key_tok.kind}:{key_tok.value} at {key_tok.pos}")
					self._advance()
					key = key_tok.value
					self._expect("op", ":")
					value = self._assignment()
					props.append(ObjectProperty(key=key, value=value))
					if self._match("punct", "}"):
						break
					self._expect("punct", ",")
					if self._peek().kind == "punct" and self._peek().value == "}":
						self._advance()
						break
			return ObjectLiteral(properties=props)

		raise JSParseError(f"Unexpected token {tok.kind}:{tok.value} at {tok.pos}")


def parse_js(source: str) -> Program:
	return JSParser(source).parse()
