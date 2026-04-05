from __future__ import annotations

from dataclasses import dataclass
import html


class JSParseError(Exception):
	def __init__(
		self,
		message: str,
		*,
		pos: int | None = None,
		source_name: str | None = None,
		source_text: str | None = None,
	):
		super().__init__(message)
		self.message = message
		self.pos = pos
		self.source_name = source_name
		self.source_text = source_text

	def __str__(self) -> str:
		return self.message

	def format_for_console(self) -> str:
		lines = [f"Uncaught SyntaxError: {self.message}"]
		if self.source_name is not None:
			line, column = _line_col_from_pos(self.source_text, self.pos)
			location = f"{self.source_name}:{line}"
			if column is not None:
				location = f"{location}:{column}"
			lines.append(f"    <parse> {location}")
		excerpt = _format_source_excerpt(self.source_text, self.pos)
		if excerpt:
			lines.extend(["", excerpt])
		return "\n".join(lines)


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


def tokenize_js(source: str, *, source_name: str | None = None) -> list[Token]:
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
				raise JSParseError(
					"Unterminated block comment",
					pos=i,
					source_name=source_name,
					source_text=source,
				)
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
				raise JSParseError("Unterminated string", pos=start, source_name=source_name, source_text=source)
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
				raise JSParseError(
					"Unterminated template literal",
					pos=start,
					source_name=source_name,
					source_text=source,
				)
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

		raise JSParseError(
			f"Unexpected character {ch!r}",
			pos=i,
			source_name=source_name,
			source_text=source,
		)

	tokens.append(Token("eof", "", n))
	return tokens


@dataclass
class Program:
	body: list[object]
	pos: int = 0


@dataclass
class BlockStatement:
	body: list[object]
	pos: int = 0


@dataclass
class VarDeclaration:
	kind: str
	name: str
	init: object | None
	pos: int = 0


@dataclass
class FunctionDeclaration:
	name: str
	params: list[str]
	body: BlockStatement
	pos: int = 0


@dataclass
class ReturnStatement:
	argument: object | None
	pos: int = 0


@dataclass
class IfStatement:
	test: object
	consequent: object
	alternate: object | None
	pos: int = 0


@dataclass
class WhileStatement:
	test: object
	body: object
	pos: int = 0


@dataclass
class ForStatement:
	init: object | None
	test: object | None
	update: object | None
	body: object
	pos: int = 0


@dataclass
class TryCatchStatement:
	try_block: BlockStatement
	catch_name: str
	catch_block: BlockStatement
	pos: int = 0


@dataclass
class ThrowStatement:
	argument: object
	pos: int = 0


@dataclass
class ExpressionStatement:
	expression: object
	pos: int = 0


@dataclass
class Literal:
	value: object
	pos: int = 0


@dataclass
class Identifier:
	name: str
	pos: int = 0


@dataclass
class ArrayLiteral:
	elements: list[object]
	pos: int = 0


@dataclass
class ObjectProperty:
	key: str
	value: object
	pos: int = 0


@dataclass
class ObjectLiteral:
	properties: list[ObjectProperty]
	pos: int = 0


@dataclass
class UnaryExpression:
	op: str
	argument: object
	pos: int = 0


@dataclass
class BinaryExpression:
	left: object
	op: str
	right: object
	pos: int = 0


@dataclass
class ConditionalExpression:
	test: object
	consequent: object
	alternate: object
	pos: int = 0


@dataclass
class SequenceExpression:
	expressions: list[object]
	pos: int = 0


@dataclass
class AssignmentExpression:
	target: object
	value: object
	pos: int = 0


@dataclass
class MemberExpression:
	obj: object
	prop: object
	computed: bool = False
	optional: bool = False
	pos: int = 0


@dataclass
class CallExpression:
	callee: object
	args: list[object]
	optional: bool = False
	pos: int = 0


@dataclass
class FunctionExpression:
	params: list[str]
	body: object
	is_arrow: bool = False
	name: str | None = None
	pos: int = 0


class JSParser:
	def __init__(self, source: str, source_name: str | None = None):
		self.source = preprocess_js(source)
		self.source_name = source_name
		self.tokens = tokenize_js(source, source_name=source_name)
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
			raise JSParseError(
				f"Expected {expected}, got {got}",
				pos=tok.pos,
				source_name=self.source_name,
				source_text=self.source,
			)
		return self._advance()

	def parse(self) -> Program:
		body: list[object] = []
		while self._peek().kind != "eof":
			if self._match("punct", ";"):
				continue
			body.append(self._statement())
			self._match("punct", ";")
		return Program(body=body, pos=0)

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
				start = self._advance()
				if self._peek().kind == "punct" and self._peek().value == ";":
					return ReturnStatement(argument=None, pos=start.pos)
				return ReturnStatement(argument=self._expression(), pos=start.pos)
			if tok.value == "if":
				return self._if_statement()
			if tok.value == "while":
				return self._while_statement()
			if tok.value == "for":
				return self._for_statement()
			if tok.value == "try":
				return self._try_catch_statement()
			if tok.value == "throw":
				start = self._advance()
				return ThrowStatement(argument=self._expression(), pos=start.pos)
		return ExpressionStatement(expression=self._expression(), pos=tok.pos)

	def _block(self) -> BlockStatement:
		start = self._expect("punct", "{")
		body: list[object] = []
		while not self._match("punct", "}"):
			if self._peek().kind == "eof":
				raise JSParseError(
					"Unterminated block",
					pos=self._peek().pos,
					source_name=self.source_name,
					source_text=self.source,
				)
			if self._match("punct", ";"):
				continue
			body.append(self._statement())
			self._match("punct", ";")
		return BlockStatement(body=body, pos=start.pos)

	def _var_decl(self) -> VarDeclaration:
		start = self._advance()
		kind = start.value
		name = self._expect("identifier").value
		init = None
		if self._match("op", "="):
			init = self._expression()
		if kind == "const" and init is None:
			raise JSParseError("Missing initializer in const declaration")
		return VarDeclaration(kind=kind, name=name, init=init, pos=start.pos)

	def _function_declaration(self) -> FunctionDeclaration:
		start = self._expect("keyword", "function")
		name = self._expect("identifier").value
		params = self._parse_params()
		body = self._block()
		return FunctionDeclaration(name=name, params=params, body=body, pos=start.pos)

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
		start = self._expect("keyword", "if")
		self._expect("punct", "(")
		test = self._expression()
		self._expect("punct", ")")
		consequent = self._statement()
		alternate = None
		if self._match("keyword", "else"):
			alternate = self._statement()
		return IfStatement(test=test, consequent=consequent, alternate=alternate, pos=start.pos)

	def _while_statement(self) -> WhileStatement:
		start = self._expect("keyword", "while")
		self._expect("punct", "(")
		test = self._expression()
		self._expect("punct", ")")
		body = self._statement()
		return WhileStatement(test=test, body=body, pos=start.pos)

	def _for_statement(self) -> ForStatement:
		start = self._expect("keyword", "for")
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
		return ForStatement(init=init, test=test, update=update, body=body, pos=start.pos)

	def _try_catch_statement(self) -> TryCatchStatement:
		start = self._expect("keyword", "try")
		try_block = self._block()
		self._expect("keyword", "catch")
		self._expect("punct", "(")
		catch_name = self._expect("identifier").value
		self._expect("punct", ")")
		catch_block = self._block()
		return TryCatchStatement(
			try_block=try_block,
			catch_name=catch_name,
			catch_block=catch_block,
			pos=start.pos,
		)

	def _expression(self) -> object:
		expr = self._assignment()
		if not (self._peek().kind == "punct" and self._peek().value == ","):
			return expr
		exprs = [expr]
		while self._match("punct", ","):
			exprs.append(self._assignment())
		return SequenceExpression(expressions=exprs, pos=getattr(expr, "pos", 0))

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
		start = self._peek()
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
		return FunctionExpression(params=params, body=body, is_arrow=True, pos=start.pos)

	def _assignment(self) -> object:
		if self._is_arrow_function_start():
			return self._arrow_function_expression()
		left = self._conditional()
		if self._match("op", "="):
			if not isinstance(left, (Identifier, MemberExpression)):
				raise JSParseError(
					"Invalid assignment target",
					pos=getattr(left, "pos", self._peek().pos),
					source_name=self.source_name,
					source_text=self.source,
				)
			return AssignmentExpression(target=left, value=self._assignment(), pos=getattr(left, "pos", 0))
		return left

	def _conditional(self) -> object:
		expr = self._nullish()
		if self._match("op", "?"):
			consequent = self._assignment()
			self._expect("op", ":")
			alternate = self._assignment()
			return ConditionalExpression(
				test=expr,
				consequent=consequent,
				alternate=alternate,
				pos=getattr(expr, "pos", 0),
			)
		return expr

	def _nullish(self) -> object:
		expr = self._logical_or()
		while self._match("op", "??"):
			expr = BinaryExpression(left=expr, op="??", right=self._logical_or(), pos=getattr(expr, "pos", 0))
		return expr

	def _logical_or(self) -> object:
		expr = self._logical_and()
		while self._match("op", "||"):
			expr = BinaryExpression(left=expr, op="||", right=self._logical_and(), pos=getattr(expr, "pos", 0))
		return expr

	def _logical_and(self) -> object:
		expr = self._bitwise_or()
		while self._match("op", "&&"):
			expr = BinaryExpression(left=expr, op="&&", right=self._bitwise_or(), pos=getattr(expr, "pos", 0))
		return expr

	def _bitwise_or(self) -> object:
		expr = self._bitwise_xor()
		while self._match("op", "|"):
			expr = BinaryExpression(left=expr, op="|", right=self._bitwise_xor(), pos=getattr(expr, "pos", 0))
		return expr

	def _bitwise_xor(self) -> object:
		expr = self._bitwise_and()
		while self._match("op", "^"):
			expr = BinaryExpression(left=expr, op="^", right=self._bitwise_and(), pos=getattr(expr, "pos", 0))
		return expr

	def _bitwise_and(self) -> object:
		expr = self._equality()
		while self._match("op", "&"):
			expr = BinaryExpression(left=expr, op="&", right=self._equality(), pos=getattr(expr, "pos", 0))
		return expr

	def _equality(self) -> object:
		expr = self._comparison()
		while True:
			if self._match("op", "==="):
				expr = BinaryExpression(left=expr, op="===", right=self._comparison(), pos=getattr(expr, "pos", 0))
			elif self._match("op", "!=="):
				expr = BinaryExpression(left=expr, op="!==", right=self._comparison(), pos=getattr(expr, "pos", 0))
			elif self._match("op", "=="):
				expr = BinaryExpression(left=expr, op="==", right=self._comparison(), pos=getattr(expr, "pos", 0))
			elif self._match("op", "!="):
				expr = BinaryExpression(left=expr, op="!=", right=self._comparison(), pos=getattr(expr, "pos", 0))
			else:
				break
		return expr

	def _comparison(self) -> object:
		expr = self._term()
		while True:
			if self._match("op", "<"):
				expr = BinaryExpression(left=expr, op="<", right=self._term(), pos=getattr(expr, "pos", 0))
			elif self._match("op", "<="):
				expr = BinaryExpression(left=expr, op="<=", right=self._term(), pos=getattr(expr, "pos", 0))
			elif self._match("op", ">"):
				expr = BinaryExpression(left=expr, op=">", right=self._term(), pos=getattr(expr, "pos", 0))
			elif self._match("op", ">="):
				expr = BinaryExpression(left=expr, op=">=", right=self._term(), pos=getattr(expr, "pos", 0))
			else:
				break
		return expr

	def _term(self) -> object:
		expr = self._factor()
		while True:
			if self._match("op", "+"):
				expr = BinaryExpression(left=expr, op="+", right=self._factor(), pos=getattr(expr, "pos", 0))
			elif self._match("op", "-"):
				expr = BinaryExpression(left=expr, op="-", right=self._factor(), pos=getattr(expr, "pos", 0))
			else:
				break
		return expr

	def _factor(self) -> object:
		expr = self._unary()
		while True:
			if self._match("op", "*"):
				expr = BinaryExpression(left=expr, op="*", right=self._unary(), pos=getattr(expr, "pos", 0))
			elif self._match("op", "/"):
				expr = BinaryExpression(left=expr, op="/", right=self._unary(), pos=getattr(expr, "pos", 0))
			else:
				break
		return expr

	def _unary(self) -> object:
		if self._match("op", "!"):
			return UnaryExpression(op="!", argument=self._unary(), pos=self._peek(-1).pos)
		if self._match("op", "-"):
			return UnaryExpression(op="-", argument=self._unary(), pos=self._peek(-1).pos)
		if self._match("op", "+"):
			return UnaryExpression(op="+", argument=self._unary(), pos=self._peek(-1).pos)
		return self._call_member()

	def _call_member(self) -> object:
		expr = self._primary()
		while True:
			if self._match("op", "."):
				prop = self._expect("identifier").value
				expr = MemberExpression(
					obj=expr,
					prop=Literal(value=prop, pos=getattr(expr, "pos", 0)),
					computed=False,
					pos=getattr(expr, "pos", 0),
				)
				continue

			if self._match("op", "?."):
				if self._match("punct", "("):
					args = self._parse_call_args(open_consumed=True)
					expr = CallExpression(callee=expr, args=args, optional=True, pos=getattr(expr, "pos", 0))
					continue
				if self._match("punct", "["):
					prop_expr = self._expression()
					self._expect("punct", "]")
					expr = MemberExpression(
						obj=expr,
						prop=prop_expr,
						computed=True,
						optional=True,
						pos=getattr(expr, "pos", 0),
					)
					continue
				prop = self._expect("identifier").value
				expr = MemberExpression(
					obj=expr,
					prop=Literal(value=prop, pos=getattr(expr, "pos", 0)),
					computed=False,
					optional=True,
					pos=getattr(expr, "pos", 0),
				)
				continue

			if self._match("punct", "["):
				prop_expr = self._expression()
				self._expect("punct", "]")
				expr = MemberExpression(obj=expr, prop=prop_expr, computed=True, pos=getattr(expr, "pos", 0))
				continue

			if self._match("punct", "("):
				args = self._parse_call_args(open_consumed=True)
				expr = CallExpression(callee=expr, args=args, pos=getattr(expr, "pos", 0))
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
				return Literal(value=float(tok.value), pos=tok.pos)
			return Literal(value=int(tok.value), pos=tok.pos)
		if tok.kind == "string":
			self._advance()
			return Literal(value=tok.value, pos=tok.pos)
		if tok.kind == "template":
			self._advance()
			return Literal(value=tok.value, pos=tok.pos)
		if tok.kind == "identifier":
			self._advance()
			return Identifier(name=tok.value, pos=tok.pos)
		if tok.kind == "keyword":
			if tok.value == "true":
				self._advance()
				return Literal(value=True, pos=tok.pos)
			if tok.value == "false":
				self._advance()
				return Literal(value=False, pos=tok.pos)
			if tok.value == "null":
				self._advance()
				return Literal(value=None, pos=tok.pos)
			if tok.value == "function":
				self._advance()
				name = None
				if self._peek().kind == "identifier":
					name = self._advance().value
				params = self._parse_params()
				body = self._block()
				return FunctionExpression(params=params, body=body, is_arrow=False, name=name, pos=tok.pos)
		if self._match("punct", "("):
			expr = self._expression()
			self._expect("punct", ")")
			return expr
		if self._match("punct", "["):
			start = tok.pos
			elements: list[object] = []
			if not self._match("punct", "]"):
				while True:
					if self._peek().kind == "punct" and self._peek().value == ",":
						elements.append(Literal(value=None, pos=self._peek().pos))
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
			return ArrayLiteral(elements=elements, pos=start)
		if self._match("punct", "{"):
			start = tok.pos
			props: list[ObjectProperty] = []
			if not self._match("punct", "}"):
				while True:
					if self._peek().kind == "punct" and self._peek().value == "}":
						self._advance()
						break
					key_tok = self._peek()
					if key_tok.kind not in {"identifier", "string"}:
						raise JSParseError(
							f"Invalid object key {key_tok.kind}:{key_tok.value}",
							pos=key_tok.pos,
							source_name=self.source_name,
							source_text=self.source,
						)
					self._advance()
					key = key_tok.value
					self._expect("op", ":")
					value = self._assignment()
					props.append(ObjectProperty(key=key, value=value, pos=key_tok.pos))
					if self._match("punct", "}"):
						break
					self._expect("punct", ",")
					if self._peek().kind == "punct" and self._peek().value == "}":
						self._advance()
						break
			return ObjectLiteral(properties=props, pos=start)

		raise JSParseError(
			f"Unexpected token {tok.kind}:{tok.value}",
			pos=tok.pos,
			source_name=self.source_name,
			source_text=self.source,
		)


def parse_js(source: str, source_name: str | None = None) -> Program:
	return JSParser(source, source_name=source_name).parse()
