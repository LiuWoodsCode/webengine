from __future__ import annotations

import logging
import re

from dataclasses import dataclass, field

from .constants import BLOCK_TAGS, INHERITED_PROPERTIES, SKIP_TAGS
from .dom import DOMNode, create_text_node
from .utils import px

log = logging.getLogger("Vivienne.CSS")

SUPPORTED_PROPERTIES = {
    "background",
    "margin",
    "margin-top",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "margin-block-start",
    "margin-block-end",
    "margin-inline-start",
    "margin-inline-end",
    "padding",
    "padding-top",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "border",
    "border-top",
    "border-bottom",
    "border-left",
    "border-right",
    "border-radius",
    "border-collapse",
    "border-width",
    "border-style",
    "border-color",
    "width",
    "max-width",
    "height",
    "color",
    "font-size",
    "font-weight",
    "font-style",
    "font-family",
    "line-height",
    "text-align",
    "text-decoration",
    "white-space",
    "vertical-align",
    "display",
    "float",
    "clear",
    "position",
    "overflow-x",
    "justify-content",
    "flex-direction",
    "grid-template-columns",
    "list-style",
    "list-style-type",
    "image-rendering",
    "content",
    "counter-reset",
    "counter-increment",
    "cursor",
    "outline",
    "outline-offset",
    "background-color",
    "all",
}

KEYWORD_PROPERTIES = {
    "display": {
        "block",
        "inline",
        "inline-block",
        "inline-flex",
        "inline-table",
        "table",
        "table-row",
        "table-cell",
        "table-row-group",
        "table-header-group",
        "table-footer-group",
        "table-caption",
        "flex",
        "grid",
        "contents",
        "none",
    },
    "position": {"static", "relative", "absolute", "fixed", "sticky"},
    "float": {"none", "left", "right", "inline-start", "inline-end"},
    "clear": {"none", "left", "right", "both", "inline-start", "inline-end"},
    "text-align": {"left", "right", "center", "justify"},
    "text-decoration": {
        "none",
        "underline",
        "line-through",
        "overline",
    },
    "white-space": {
        "normal",
        "nowrap",
        "pre",
        "pre-wrap",
        "pre-line",
        "break-spaces",
    },
    "font-style": {"normal", "italic", "oblique"},
    "font-weight": {"normal", "bold", "bolder", "lighter"},
    "vertical-align": {"baseline", "middle", "top", "bottom"},
    "overflow-x": {"visible", "hidden", "scroll", "auto", "clip"},
    "justify-content": {
        "flex-start",
        "flex-end",
        "center",
        "space-between",
        "space-around",
        "space-evenly",
    },
    "flex-direction": {"row", "row-reverse", "column", "column-reverse"},
    "list-style-type": {
        "disc",
        "decimal",
        "none",
        "lower-alpha",
        "upper-alpha",
        "lower-roman",
        "upper-roman",
    },
    "image-rendering": {
        "auto",
        "pixelated",
        "crisp-edges",
        "optimize-contrast",
        "optimizespeed",
    },
}

PSEUDO_CLASSES = {"focus", "first-child", "last-child", "hover", "root"}
PSEUDO_ELEMENTS = {"before", "after", "selection"}

VENDOR_KEYWORDS = {
    "-moz-crisp-edges",
    "-o-crisp-edges",
    "-webkit-optimize-contrast",
    "optimizespeed",
    "optimize-contrast",
}

ALL_PROPERTIES = set(SUPPORTED_PROPERTIES)


@dataclass
class AttributeSelector:
    name: str
    value: str | None = None


@dataclass
class CompoundSelector:
    tag: str | None = None
    universal: bool = False
    id: str | None = None
    classes: list[str] = field(default_factory=list)
    attrs: list[AttributeSelector] = field(default_factory=list)
    pseudo_classes: list[str] = field(default_factory=list)
    pseudo_functions: list["FunctionalPseudoClass"] = field(default_factory=list)
    pseudo_element: str | None = None


@dataclass
class FunctionalPseudoClass:
    name: str
    argument: str
    selector: Selector | None = None


@dataclass
class SelectorPart:
    combinator: str | None
    compound: CompoundSelector


@dataclass
class Selector:
    parts: list[SelectorPart]
    specificity: tuple[int, int, int]
    pseudo_element: str | None = None


def _expand_box_shorthand(value: str) -> dict:
    parts = [p for p in value.split() if p]
    if not parts:
        return {}
    if len(parts) == 1:
        top = right = bottom = left = parts[0]
    elif len(parts) == 2:
        top, right = parts
        bottom, left = top, right
    elif len(parts) == 3:
        top, right, bottom = parts
        left = right
    else:
        top, right, bottom, left = parts[:4]
    return {
        "top": top,
        "right": right,
        "bottom": bottom,
        "left": left,
    }


def _normalize_style_props(props: dict) -> dict:
    if not props:
        return {}

    out = dict(props)

    def unpack(value):
        if isinstance(value, tuple):
            if len(value) == 3:
                return value[0], value[1], value[2]
            return value[0], value[1], None
        return value, False, None

    if "background" in out and "background-color" not in out:
        out["background-color"] = out["background"]

    if "margin" in out:
        margin_value, margin_important, margin_ast = unpack(out["margin"])
        expanded = _expand_box_shorthand(margin_value)
        for side, value in expanded.items():
            out[f"margin-{side}"] = (value, margin_important, margin_ast)

    if "margin-block-start" in out and "margin-top" not in out:
        value, important, ast = unpack(out["margin-block-start"])
        out["margin-top"] = (value, important, ast)
    if "margin-block-end" in out and "margin-bottom" not in out:
        value, important, ast = unpack(out["margin-block-end"])
        out["margin-bottom"] = (value, important, ast)
    if "margin-inline-start" in out and "margin-left" not in out:
        value, important, ast = unpack(out["margin-inline-start"])
        out["margin-left"] = (value, important, ast)
    if "margin-inline-end" in out and "margin-right" not in out:
        value, important, ast = unpack(out["margin-inline-end"])
        out["margin-right"] = (value, important, ast)

    if "padding" in out:
        padding_value, padding_important, padding_ast = unpack(out["padding"])
        expanded = _expand_box_shorthand(padding_value)
        for side, value in expanded.items():
            out[f"padding-{side}"] = (value, padding_important, padding_ast)

    if "border-width" in out:
        border_width_value, border_width_important, border_width_ast = unpack(
            out["border-width"]
        )
        expanded = _expand_box_shorthand(border_width_value)
        for side, value in expanded.items():
            out[f"border-{side}-width"] = (
                value,
                border_width_important,
                border_width_ast,
            )

    def _extract_border_width(raw_value: str | None) -> str | None:
        if not raw_value:
            return None
        for part in [p for p in raw_value.split() if p]:
            p = part.strip().lower()
            if p in {"thin", "medium", "thick"}:
                return p
            if re.fullmatch(r"[-+]?\d+(?:\.\d+)?(?:px|em|rem|%)?", p):
                return part
        return None

    if "border" in out:
        border_value, border_important, border_ast = unpack(out["border"])
        width = _extract_border_width(border_value)
        if width:
            for side in ("top", "right", "bottom", "left"):
                key = f"border-{side}-width"
                if key not in out:
                    out[key] = (width, border_important, border_ast)

    for side in ("top", "right", "bottom", "left"):
        side_key = f"border-{side}"
        width_key = f"border-{side}-width"
        if side_key in out and width_key not in out:
            side_value, side_important, side_ast = unpack(out[side_key])
            width = _extract_border_width(side_value)
            if width:
                out[width_key] = (width, side_important, side_ast)

    return out


def _strip_comments(css_text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css_text or "", flags=re.S)


def _is_ident_char(ch: str) -> bool:
    return ch.isalnum() or ch in ("-", "_", "*")


def _parse_string(s: str, start: int) -> tuple[str | None, int]:
    quote = s[start]
    i = start + 1
    out = []
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            out.append(s[i + 1])
            i += 2
            continue
        if ch == quote:
            return "".join(out), i + 1
        out.append(ch)
        i += 1
    return None, i


def _parse_value_ast(value: str):
    if value is None:
        return None

    tokens = []
    i = 0
    depth = 0
    while i < len(value):
        ch = value[i]
        if ch.isspace():
            i += 1
            continue
        if ch in ("'", '"'):
            s, j = _parse_string(value, i)
            if s is None:
                return None
            tokens.append({"type": "string", "value": s})
            i = j
            continue
        if ch == "#":
            j = i + 1
            while j < len(value) and value[j].isalnum():
                j += 1
            tokens.append({"type": "hash", "value": value[i:j]})
            i = j
            continue
        if ch.isdigit() or (
            ch == "." and i + 1 < len(value) and value[i + 1].isdigit()
        ) or (
            ch in ("+", "-")
            and i + 1 < len(value)
            and (value[i + 1].isdigit() or value[i + 1] == ".")
        ):
            j = i + 1
            while j < len(value) and (value[j].isdigit() or value[j] == "."):
                j += 1
            number = value[i:j]
            unit = ""
            k = j
            while k < len(value) and value[k].isalpha():
                unit += value[k]
                k += 1
            if k < len(value) and value[k] == "%":
                tokens.append({"type": "percentage", "value": number + "%"})
                i = k + 1
                continue
            if unit:
                tokens.append({"type": "dimension", "value": number + unit, "unit": unit})
                i = k
                continue
            tokens.append({"type": "number", "value": number})
            i = j
            continue
        if ch.isalpha() or ch in ("-", "_"):
            j = i + 1
            while j < len(value) and _is_ident_char(value[j]):
                j += 1
            ident = value[i:j]
            if j < len(value) and value[j] == "(":
                depth += 1
                tokens.append({"type": "function", "name": ident, "start": j})
                i = j + 1
                continue
            tokens.append({"type": "ident", "value": ident})
            i = j
            continue
        if ch == "(":
            depth += 1
            tokens.append({"type": "paren", "value": "("})
            i += 1
            continue
        if ch == ")":
            depth -= 1
            if depth < 0:
                return None
            tokens.append({"type": "paren", "value": ")"})
            i += 1
            continue
        if ch == ",":
            tokens.append({"type": "comma", "value": ","})
            i += 1
            continue
        tokens.append({"type": "delim", "value": ch})
        i += 1
    if depth != 0:
        return None
    return tokens


def _value_is_valid(prop: str, raw: str, ast) -> bool:
    if raw is None:
        return False
    raw_stripped = raw.strip()
    if not raw_stripped:
        return False

    lower = raw_stripped.lower()
    if lower in ("inherit", "initial", "unset"):
        return True
    if lower in VENDOR_KEYWORDS or lower.startswith("-"):
        return True

    if prop in KEYWORD_PROPERTIES:
        if lower in KEYWORD_PROPERTIES[prop]:
            return True
        if re.fullmatch(r"\d+", lower) and prop == "font-weight":
            return True
        if any(tok["type"] in {"dimension", "percentage", "number", "function"} for tok in (ast or [])):
            return True
        return False

    return ast is not None


def _parse_declarations_from_text(text: str) -> dict:
    props = {}
    if not text:
        return props

    text = _strip_comments(text)
    i = 0
    buf = ""
    depth = 0
    decls = []
    in_string = False
    string_char = ""

    while i < len(text):
        ch = text[i]
        if in_string:
            buf += ch
            if ch == string_char:
                in_string = False
            elif ch == "\\" and i + 1 < len(text):
                buf += text[i + 1]
                i += 1
            i += 1
            continue
        if ch in ("'", '"'):
            in_string = True
            string_char = ch
            buf += ch
            i += 1
            continue
        if ch == "(":
            depth += 1
            buf += ch
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            buf += ch
            i += 1
            continue
        if ch == ";" and depth == 0:
            decls.append(buf)
            buf = ""
            i += 1
            continue
        buf += ch
        i += 1

    if buf.strip():
        decls.append(buf)

    for decl in decls:
        if ":" not in decl:
            continue
        name, value = decl.split(":", 1)
        prop = name.strip().lower()
        if not prop:
            continue
        is_custom_property = prop.startswith("--")
        if prop not in SUPPORTED_PROPERTIES and not is_custom_property:
            continue
        raw = value.strip()
        important = False
        if raw.lower().endswith("!important"):
            raw = raw[: -len("!important")].strip()
            important = True
        ast = _parse_value_ast(raw)
        if is_custom_property:
            props[prop] = (raw, important, ast)
            continue
        if not _value_is_valid(prop, raw, ast):
            continue
        props[prop] = (raw, important, ast)

    return _normalize_style_props(props)


def parse_inline_style(style: str) -> dict:
    return _parse_declarations_from_text(style or "")


def _tokenize_selector(selector: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    i = 0
    while i < len(selector):
        ch = selector[i]
        if ch.isspace():
            while i < len(selector) and selector[i].isspace():
                i += 1
            tokens.append(("WS", " "))
            continue
        if selector.startswith("::", i):
            tokens.append(("DOUBLE_COLON", "::"))
            i += 2
            continue
        if ch in (":", ".", "#", ",", ">", "*", "[", "]", "=", "(", ")", "+"):
            tokens.append((ch, ch))
            i += 1
            continue
        if ch in ("'", '"'):
            s, j = _parse_string(selector, i)
            if s is None:
                tokens.append(("ERROR", ""))
                return tokens
            tokens.append(("STRING", s))
            i = j
            continue
        if _is_ident_char(ch):
            j = i + 1
            while j < len(selector) and _is_ident_char(selector[j]):
                j += 1
            tokens.append(("IDENT", selector[i:j]))
            i = j
            continue
        tokens.append(("ERROR", ch))
        return tokens
    return tokens


def _selector_token_text(token: tuple[str, str]) -> str:
    token_type, token_value = token
    if token_type == "STRING":
        return f'"{token_value}"'
    return token_value


def _parse_function_argument(tokens: list[tuple[str, str]], i: int) -> tuple[str, int] | None:
    if i >= len(tokens) or tokens[i][0] != "(":
        return None

    depth = 1
    i += 1
    arg_tokens: list[tuple[str, str]] = []
    while i < len(tokens) and depth:
        token = tokens[i]
        if token[0] == "(":
            depth += 1
        elif token[0] == ")":
            depth -= 1
            if depth == 0:
                return "".join(_selector_token_text(t) for t in arg_tokens).strip(), i + 1
        if depth:
            arg_tokens.append(token)
        i += 1
    return None


def _parse_simple_selector(selector: str) -> Selector | None:
    parsed = _parse_selector(selector)
    if parsed is None or len(parsed.parts) != 1:
        return None
    if parsed.parts[0].combinator not in (None,):
        return None
    return parsed


def _is_supported_nth_argument(argument: str) -> bool:
    arg = (argument or "").strip().lower().replace(" ", "")
    if not arg:
        return False
    if arg in {"odd", "even"}:
        return True
    if re.fullmatch(r"[-+]?\d+", arg):
        return True
    return re.fullmatch(r"[-+]?(?:\d+)?n(?:[-+]?\d+)?", arg) is not None


def _parse_selector(selector: str) -> Selector | None:
    tokens = _tokenize_selector(selector)
    if not tokens or any(t[0] == "ERROR" for t in tokens):
        return None

    parts: list[SelectorPart] = []
    i = 0
    current_combinator = None
    while i < len(tokens):
        token_type, token_value = tokens[i]
        if token_type == "WS":
            if current_combinator is None:
                current_combinator = " "
            i += 1
            continue
        if token_value == ">":
            current_combinator = ">"
            i += 1
            continue

        compound = CompoundSelector()
        if token_value == "*":
            compound.universal = True
            i += 1
        elif token_type == "IDENT":
            compound.tag = token_value
            i += 1

        while i < len(tokens):
            t_type, t_val = tokens[i]
            if t_type in ("WS",) or t_val in (",", ">"):
                break
            if t_val == ".":
                i += 1
                if i >= len(tokens) or tokens[i][0] != "IDENT":
                    return None
                compound.classes.append(tokens[i][1])
                i += 1
                continue
            if t_val == "#":
                i += 1
                if i >= len(tokens) or tokens[i][0] != "IDENT":
                    return None
                compound.id = tokens[i][1]
                i += 1
                continue
            if t_val == "[":
                i += 1
                if i >= len(tokens) or tokens[i][0] != "IDENT":
                    return None
                attr_name = tokens[i][1]
                attr_val = None
                i += 1
                if i < len(tokens) and tokens[i][0] == "=":
                    i += 1
                    if i >= len(tokens) or tokens[i][0] not in ("IDENT", "STRING"):
                        return None
                    attr_val = tokens[i][1]
                    i += 1
                if i >= len(tokens) or tokens[i][0] != "]":
                    return None
                compound.attrs.append(AttributeSelector(name=attr_name, value=attr_val))
                i += 1
                continue
            if t_type == "DOUBLE_COLON" or t_val == ":":
                is_element = t_type == "DOUBLE_COLON"
                i += 1
                if i >= len(tokens) or tokens[i][0] != "IDENT":
                    return None
                name = tokens[i][1].lower()
                i += 1
                argument = None
                if i < len(tokens) and tokens[i][0] == "(":
                    parsed_argument = _parse_function_argument(tokens, i)
                    if parsed_argument is None:
                        return None
                    argument, i = parsed_argument
                if is_element or name in PSEUDO_ELEMENTS:
                    if argument is not None:
                        return None
                    compound.pseudo_element = name
                else:
                    if argument is None:
                        if name not in PSEUDO_CLASSES:
                            return None
                        compound.pseudo_classes.append(name)
                    elif name == "nth-child":
                        if not _is_supported_nth_argument(argument):
                            return None
                        compound.pseudo_functions.append(
                            FunctionalPseudoClass(name=name, argument=argument)
                        )
                    elif name == "not":
                        inner = _parse_simple_selector(argument)
                        if inner is None:
                            return None
                        compound.pseudo_functions.append(
                            FunctionalPseudoClass(name=name, argument=argument, selector=inner)
                        )
                    else:
                        return None
                continue
            if t_type == "IDENT" and compound.tag is None and not compound.universal:
                compound.tag = t_val
                i += 1
                continue
            return None

        if not parts and current_combinator == " ":
            current_combinator = None
        parts.append(SelectorPart(combinator=current_combinator, compound=compound))
        current_combinator = None

    if not parts:
        return None

    specificity = selector_specificity(parts)
    pseudo_element = parts[-1].compound.pseudo_element
    return Selector(parts=parts, specificity=specificity, pseudo_element=pseudo_element)


def _parse_selector_list(sel_blob: str) -> list[Selector] | None:
    raw_selectors = []
    buf = ""
    bracket_depth = 0
    paren_depth = 0
    in_string = False
    string_char = ""
    for ch in sel_blob:
        if in_string:
            buf += ch
            if ch == string_char:
                in_string = False
            continue
        if ch in ("'", '"'):
            in_string = True
            string_char = ch
            buf += ch
            continue
        if ch == "[":
            bracket_depth += 1
        elif ch == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth = max(0, paren_depth - 1)
        if ch == "," and bracket_depth == 0 and paren_depth == 0:
            if buf.strip():
                raw_selectors.append(buf.strip())
            buf = ""
            continue
        buf += ch
    if buf.strip():
        raw_selectors.append(buf.strip())

    selectors: list[Selector] = []
    for raw in raw_selectors:
        parsed = _parse_selector(raw)
        if parsed is None:
            return None
        selectors.append(parsed)
    return selectors


def _at_rule_includes_inner_rules(at_name: str, prelude: str) -> bool:
    prelude_lower = (prelude or "").strip().lower()
    if at_name == "media":
        if not prelude_lower or prelude_lower == "all":
            return True
        if "(" in prelude_lower:
            return False
        return "screen" in prelude_lower and "print" not in prelude_lower
    if at_name in {"supports", "layer"}:
        return True
    return False


def parse_css_stylesheet(css_text: str):
    rules = []
    if not css_text:
        return rules

    css_text = _strip_comments(css_text)
    i = 0
    order = 0

    while i < len(css_text):
        if css_text[i].isspace():
            i += 1
            continue
        if css_text[i] == "@":
            at_name_start = i + 1
            at_name_end = at_name_start
            while at_name_end < len(css_text) and (
                css_text[at_name_end].isalnum() or css_text[at_name_end] in ("-", "_")
            ):
                at_name_end += 1
            at_name = css_text[at_name_start:at_name_end].lower()

            semi = css_text.find(";", i)
            brace = css_text.find("{", i)
            if brace != -1 and (semi == -1 or brace < semi):
                prelude = css_text[at_name_end:brace]
            elif semi != -1:
                prelude = css_text[at_name_end:semi]
            else:
                prelude = css_text[at_name_end:]
            if brace != -1 and (semi == -1 or brace < semi):
                depth = 1
                j = brace + 1
                while j < len(css_text) and depth:
                    if css_text[j] == "{":
                        depth += 1
                    elif css_text[j] == "}":
                        depth -= 1
                    j += 1

                if _at_rule_includes_inner_rules(at_name, prelude) and j <= len(css_text):
                    inner_css = css_text[brace + 1 : j - 1]
                    inner_rules = parse_css_stylesheet(inner_css)
                    for inner_rule in inner_rules:
                        inner_rule["order"] = order
                        rules.append(inner_rule)
                        order += 1

                i = j
            elif semi != -1:
                i = semi + 1
            else:
                break
            continue

        sel_start = i
        depth = 0
        in_string = False
        string_char = ""
        while i < len(css_text):
            ch = css_text[i]
            if in_string:
                if ch == string_char:
                    in_string = False
                elif ch == "\\" and i + 1 < len(css_text):
                    i += 1
                i += 1
                continue
            if ch in ("'", '"'):
                in_string = True
                string_char = ch
                i += 1
                continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth = max(0, depth - 1)
            if ch == "{" and depth == 0:
                break
            i += 1

        if i >= len(css_text) or css_text[i] != "{":
            break

        sel_blob = css_text[sel_start:i].strip()
        i += 1
        block_start = i
        depth = 1
        in_string = False
        string_char = ""
        while i < len(css_text) and depth:
            ch = css_text[i]
            if in_string:
                if ch == string_char:
                    in_string = False
                elif ch == "\\" and i + 1 < len(css_text):
                    i += 1
                i += 1
                continue
            if ch in ("'", '"'):
                in_string = True
                string_char = ch
                i += 1
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            i += 1

        props_blob = css_text[block_start : i - 1].strip()
        selectors = _parse_selector_list(sel_blob)
        if selectors is None:
            continue
        props = parse_inline_style(props_blob)
        if selectors and props:
            rules.append(
                {
                    "selectors": selectors,
                    "props": props,
                    "order": order,
                    "origin": "author",
                }
            )
            order += 1

    return rules


def selector_specificity(parts: list[SelectorPart] | str) -> tuple[int, int, int]:
    if isinstance(parts, str):
        parsed = _parse_selector(parts)
        if not parsed:
            return (0, 0, 0)
        return parsed.specificity

    a = b = c = 0
    for part in parts:
        comp = part.compound
        if comp.id:
            a += 1
        b += len(comp.classes)
        b += len(comp.attrs)
        b += len(comp.pseudo_classes)
        for pseudo in comp.pseudo_functions:
            if pseudo.name == "not" and pseudo.selector is not None:
                inner = pseudo.selector.specificity
                a += inner[0]
                b += inner[1]
                c += inner[2]
            else:
                b += 1
        if comp.tag:
            c += 1
        if comp.pseudo_element:
            c += 1
    return (a, b, c)


def _node_element_siblings(node: DOMNode) -> list[DOMNode]:
    parent = node.parent
    if not parent:
        return []
    return [child for child in parent.children if not child.is_text()]


def _parse_nth_expression(argument: str) -> tuple[int, int] | None:
    arg = (argument or "").strip().lower().replace(" ", "")
    if arg == "odd":
        return (2, 1)
    if arg == "even":
        return (2, 0)
    if re.fullmatch(r"[-+]?\d+", arg):
        return (0, int(arg))

    match = re.fullmatch(r"([+-]?(?:\d+)?)n([+-]?\d+)?", arg)
    if not match:
        return None

    a_raw, b_raw = match.groups()
    if a_raw in ("", "+", None):
        a = 1
    elif a_raw == "-":
        a = -1
    else:
        a = int(a_raw)
    b = int(b_raw or 0)
    return (a, b)


def _matches_nth_child(argument: str, node: DOMNode) -> bool:
    siblings = _node_element_siblings(node)
    if not siblings or node not in siblings:
        return False

    index = siblings.index(node) + 1
    parsed = _parse_nth_expression(argument)
    if parsed is None:
        return False

    a, b = parsed
    if a == 0:
        return index == b

    delta = index - b
    if a > 0:
        return delta >= 0 and delta % a == 0
    return delta <= 0 and delta % a == 0


def _matches_compound(compound: CompoundSelector, node: DOMNode) -> bool:
    if node.is_text():
        return False

    if compound.tag and compound.tag.lower() != node.tag.lower():
        return False
    if not compound.tag and compound.universal is False and compound.id is None:
        if compound.classes or compound.attrs or compound.pseudo_classes:
            pass

    node_id = (node.attrs.get("id") or "").strip()
    if compound.id and compound.id != node_id:
        return False

    class_attr = node.attrs.get("class") or ""
    node_classes = [c for c in class_attr.split() if c]
    for cls in compound.classes:
        if cls not in node_classes:
            return False

    for attr in compound.attrs:
        if attr.name not in node.attrs:
            return False
        if attr.value is not None:
            if str(node.attrs.get(attr.name)) != attr.value:
                return False

    for pseudo in compound.pseudo_classes:
        if pseudo == "focus":
            if not (
                node.attrs.get("data-focus")
                or "autofocus" in node.attrs
                or node.attrs.get("tabindex") is not None
            ):
                return False
        elif pseudo == "first-child":
            siblings = _node_element_siblings(node)
            if not siblings or siblings[0] is not node:
                return False
        elif pseudo == "last-child":
            siblings = _node_element_siblings(node)
            if not siblings or siblings[-1] is not node:
                return False
        elif pseudo == "hover":
            if not (node.attrs.get("data-hover") or "hover" in node.attrs):
                return False
        elif pseudo == "root":
            if not node.parent or node.parent.tag != "#document":
                return False
        else:
            return False

    for pseudo in compound.pseudo_functions:
        if pseudo.name == "nth-child":
            if not _matches_nth_child(pseudo.argument, node):
                return False
        elif pseudo.name == "not":
            if pseudo.selector and selector_matches_node(pseudo.selector, node):
                return False
        else:
            return False
    return True


def selector_matches(selector: Selector | str, tag: str | None, attrs: dict | None) -> bool:
    if isinstance(selector, str):
        parsed = _parse_selector(selector)
        if not parsed:
            return False
        selector = parsed

    if not selector.parts:
        return False

    if tag is None or attrs is None:
        return False

    node = DOMNode(tag=tag, attrs=attrs)
    return selector_matches_node(selector, node)


def selector_matches_node(selector: Selector, node: DOMNode) -> bool:
    parts = selector.parts

    def match_from(idx: int, current: DOMNode) -> bool:
        if not _matches_compound(parts[idx].compound, current):
            return False
        if idx == 0:
            return True
        combinator = parts[idx].combinator or " "
        if combinator == ">":
            parent = current.parent
            if not parent:
                return False
            return match_from(idx - 1, parent)
        if combinator == " ":
            parent = current.parent
            while parent:
                if match_from(idx - 1, parent):
                    return True
                parent = parent.parent
            return False
        return False

    return match_from(len(parts) - 1, node)


def default_tag_style(tag: str) -> dict:
    tag = tag.lower()
    if tag == "center":
        return {"text-align": "center"}
    if tag == "table":
        return {"display": "table"}
    if tag == "caption":
        return {"display": "table-caption"}
    if tag == "thead":
        return {"display": "table-header-group"}
    if tag == "tbody":
        return {"display": "table-row-group"}
    if tag == "tfoot":
        return {"display": "table-footer-group"}
    if tag == "tr":
        return {"display": "table-row"}
    if tag in ("td", "th"):
        return {"display": "table-cell"}
    if tag == "h1":
        return {"font-size": "26px", "font-weight": "800"}
    if tag == "h2":
        return {"font-size": "20px", "font-weight": "700"}
    if tag == "h3":
        return {"font-size": "16px", "font-weight": "700"}
    if tag == "h4":
        return {"font-size": "14px", "font-weight": "700"}
    if tag == "h5":
        return {"font-size": "12px", "font-weight": "700"}
    if tag == "h6":
        return {"font-size": "11px", "font-weight": "700"}
    if tag in ("b", "strong"):
        return {"font-weight": "700"}
    if tag in ("i", "em"):
        return {"font-style": "italic"}
    if tag in ("tt", "kbd", "samp"):
        return {"font-family": "monospace"}
    if tag in ("var", "cite", "dfn"):
        return {"font-style": "italic"}
    if tag == "address":
        return {"font-style": "italic"}
    if tag == "u":
        return {"text-decoration": "underline"}
    if tag == "small":
        return {"font-size": "12px"}
    if tag == "code":
        return {
            "font-family": "monospace",
            "background-color": "rgba(0,0,0,0.06)",
            "padding": "2px",
        }
    if tag == "blockquote":
        return {"margin-left": "18px", "color": "#555"}
    return {}


def _apply_prop(style: dict, weights: dict, prop: str, value: str, score: tuple):
    if prop not in weights or score > weights[prop]:
        weights[prop] = score
        style[prop] = value


def _split_top_level_comma(text: str) -> tuple[str, str | None]:
    depth = 0
    in_string = False
    string_char = ""
    for i, ch in enumerate(text):
        if in_string:
            if ch == string_char:
                in_string = False
            elif ch == "\\" and i + 1 < len(text):
                continue
            continue
        if ch in ("'", '"'):
            in_string = True
            string_char = ch
            continue
        if ch == "(":
            depth += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            continue
        if ch == "," and depth == 0:
            return text[:i], text[i + 1 :]
    return text, None


def _find_matching_paren(text: str, open_index: int) -> int:
    depth = 1
    i = open_index + 1
    in_string = False
    string_char = ""
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == string_char:
                in_string = False
            elif ch == "\\" and i + 1 < len(text):
                i += 1
            i += 1
            continue
        if ch in ("'", '"'):
            in_string = True
            string_char = ch
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _resolve_value_with_custom_properties(
    value: str,
    custom_props: dict[str, str],
    seen: set[str] | None = None,
) -> str | None:
    if not isinstance(value, str) or "var(" not in value:
        return value

    seen = set(seen or ())
    result: list[str] = []
    i = 0
    while i < len(value):
        if not value.startswith("var(", i):
            result.append(value[i])
            i += 1
            continue

        close = _find_matching_paren(value, i + 3)
        if close == -1:
            return None

        inner = value[i + 4 : close]
        name_part, fallback_part = _split_top_level_comma(inner)
        var_name = name_part.strip()
        replacement = None

        if var_name and var_name not in seen and var_name in custom_props:
            replacement = _resolve_value_with_custom_properties(
                custom_props[var_name],
                custom_props,
                seen | {var_name},
            )

        if replacement is None and fallback_part is not None:
            replacement = _resolve_value_with_custom_properties(
                fallback_part.strip(),
                custom_props,
                seen,
            )

        if replacement is None:
            return None

        result.append(replacement)
        i = close + 1

    return "".join(result)


def _inherit_custom_properties(style: dict, parent_style: dict | None):
    if not parent_style:
        return
    for prop, value in parent_style.items():
        if prop.startswith("--") and prop not in style:
            style[prop] = value


def _resolve_var_functions(style: dict):
    custom_props = {
        prop: value for prop, value in style.items()
        if prop.startswith("--") and isinstance(value, str)
    }
    for prop, value in list(style.items()):
        if prop.startswith("--") or not isinstance(value, str) or "var(" not in value:
            continue
        resolved = _resolve_value_with_custom_properties(value, custom_props)
        if resolved is None:
            style.pop(prop, None)
        else:
            style[prop] = resolved


def _resolve_special_values(style: dict, parent_style: dict | None):
    if "all" in style:
        all_value = str(style["all"]).strip().lower()
        if all_value in ("inherit", "initial", "unset"):
            for prop in ALL_PROPERTIES:
                if prop == "all":
                    continue
                if all_value == "inherit":
                    if parent_style and prop in parent_style:
                        style[prop] = parent_style[prop]
                    else:
                        style.pop(prop, None)
                elif all_value == "initial":
                    style.pop(prop, None)
                elif all_value == "unset":
                    if prop in INHERITED_PROPERTIES and parent_style and prop in parent_style:
                        style[prop] = parent_style[prop]
                    else:
                        style.pop(prop, None)
        style.pop("all", None)

    for prop, value in list(style.items()):
        if not isinstance(value, str):
            continue
        lower = value.strip().lower()
        if lower == "inherit":
            if parent_style and prop in parent_style:
                style[prop] = parent_style[prop]
            else:
                style.pop(prop, None)
        elif lower == "initial":
            style.pop(prop, None)
        elif lower == "unset":
            if prop in INHERITED_PROPERTIES and parent_style and prop in parent_style:
                style[prop] = parent_style[prop]
            else:
                style.pop(prop, None)


def _parse_counter_list(raw: str) -> list[tuple[str, int]]:
    if not raw:
        return []
    tokens = re.findall(r"[a-zA-Z_][\w-]*|[-+]?\d+", raw)
    out: list[tuple[str, int]] = []
    i = 0
    while i < len(tokens):
        name = tokens[i]
        value = 0
        if i + 1 < len(tokens) and re.fullmatch(r"[-+]?\d+", tokens[i + 1]):
            value = int(tokens[i + 1])
            i += 1
        out.append((name, value))
        i += 1
    return out


def _parse_counter_increment(raw: str) -> list[tuple[str, int]]:
    if not raw:
        return []
    tokens = re.findall(r"[a-zA-Z_][\w-]*|[-+]?\d+", raw)
    out: list[tuple[str, int]] = []
    i = 0
    while i < len(tokens):
        name = tokens[i]
        value = 1
        if i + 1 < len(tokens) and re.fullmatch(r"[-+]?\d+", tokens[i + 1]):
            value = int(tokens[i + 1])
            i += 1
        out.append((name, value))
        i += 1
    return out


def _parse_content_items(raw: str) -> list[dict]:
    if not raw:
        return []
    raw_stripped = raw.strip()
    if raw_stripped.lower() in ("none", "normal"):
        return []

    items: list[dict] = []
    i = 0
    while i < len(raw_stripped):
        ch = raw_stripped[i]
        if ch.isspace():
            i += 1
            continue
        if ch in ("'", '"'):
            s, j = _parse_string(raw_stripped, i)
            if s is None:
                break
            items.append({"type": "string", "value": s})
            i = j
            continue
        if raw_stripped.startswith("counter(", i):
            j = i + len("counter(")
            name_buf = ""
            while j < len(raw_stripped) and raw_stripped[j] != ")":
                name_buf += raw_stripped[j]
                j += 1
            if j < len(raw_stripped) and raw_stripped[j] == ")":
                name = name_buf.strip()
                items.append({"type": "counter", "name": name})
                i = j + 1
                continue
        if _is_ident_char(ch):
            j = i + 1
            while j < len(raw_stripped) and _is_ident_char(raw_stripped[j]):
                j += 1
            items.append({"type": "string", "value": raw_stripped[i:j]})
            i = j
            continue
        i += 1
    return items


def compute_styles(root, css_rules: list, css_enabled: bool):
    def compute_node_style(node, parent_style: dict | None):
        if node.is_text():
            node.computed_style = dict(parent_style or {})
            return

        style = default_tag_style(node.tag)
        weights: dict[str, tuple] = {}
        pseudo_buckets: dict[str, dict] = {
            "before": {"style": {}, "weights": {}},
            "after": {"style": {}, "weights": {}},
            "selection": {"style": {}, "weights": {}},
        }

        for prop, value in style.items():
            _apply_prop(style, weights, prop, value, (0, 0, 0, 0, 0, -1))

        align_attr = str(node.attrs.get("align", "")).strip().lower()
        if align_attr in {"left", "right", "center", "justify"}:
            style["text-align"] = align_attr

        bgcolor_attr = str(node.attrs.get("bgcolor", "")).strip()
        if bgcolor_attr:
            style["background-color"] = bgcolor_attr

        if "nowrap" in node.attrs:
            style["white-space"] = "nowrap"

        width_attr = str(node.attrs.get("width", "")).strip().lower()
        if width_attr:
            if width_attr.isdigit():
                style["width"] = f"{width_attr}px"
            else:
                style["width"] = width_attr

        height_attr = str(node.attrs.get("height", "")).strip().lower()
        if height_attr:
            if height_attr.isdigit():
                style["height"] = f"{height_attr}px"
            else:
                style["height"] = height_attr

        if css_enabled:
            for rule in css_rules:
                for sel in rule["selectors"]:
                    if not selector_matches_node(sel, node):
                        continue
                    specificity = sel.specificity
                    target_pseudo = sel.pseudo_element
                    for prop, (value, important, _ast) in rule["props"].items():
                        score = (
                            1 if important else 0,
                            1,
                            specificity[0],
                            specificity[1],
                            specificity[2],
                            rule["order"],
                        )
                        if target_pseudo and target_pseudo in pseudo_buckets:
                            _apply_prop(
                                pseudo_buckets[target_pseudo]["style"],
                                pseudo_buckets[target_pseudo]["weights"],
                                prop,
                                value,
                                score,
                            )
                        elif not target_pseudo:
                            _apply_prop(style, weights, prop, value, score)

            inline_props = parse_inline_style(node.attrs.get("style", ""))
            for prop, (value, important, _ast) in inline_props.items():
                score = (1 if important else 0, 2, 1, 0, 0, 1_000_000)
                _apply_prop(style, weights, prop, value, score)

        if node.tag == "#document":
            style["display"] = "block"
        elif node.tag in SKIP_TAGS:
            style["display"] = "none"
        elif "display" not in style:
            if node.tag in BLOCK_TAGS:
                style["display"] = "block"
            else:
                style["display"] = "inline"

        _inherit_custom_properties(style, parent_style)
        _resolve_var_functions(style)
        _resolve_special_values(style, parent_style)

        if parent_style:
            for prop in INHERITED_PROPERTIES:
                if prop not in style and prop in parent_style:
                    style[prop] = parent_style[prop]

        node.computed_style = style

        node.pseudo_styles = {}
        for pseudo_name, bucket in pseudo_buckets.items():
            if bucket["style"]:
                pseudo_style = dict(style)
                pseudo_style.update(bucket["style"])
                _resolve_var_functions(pseudo_style)
                _resolve_special_values(pseudo_style, style)
                node.pseudo_styles[pseudo_name] = pseudo_style

        for child in node.children:
            compute_node_style(child, style)

    compute_node_style(root, None)

    def apply_counters(node, counters: dict[str, list[int]]):
        if node.is_text():
            return

        local_counters = {k: v[:] for k, v in counters.items()}

        reset_raw = node.computed_style.get("counter-reset")
        if isinstance(reset_raw, str):
            for name, value in _parse_counter_list(reset_raw):
                stack = local_counters.setdefault(name, [])
                stack.append(value)

        increment_raw = node.computed_style.get("counter-increment")
        if isinstance(increment_raw, str):
            for name, value in _parse_counter_increment(increment_raw):
                stack = local_counters.setdefault(name, [])
                if not stack:
                    stack.append(0)
                stack[-1] += value

        node.counter_values = {k: (v[-1] if v else 0) for k, v in local_counters.items()}

        for child in node.children:
            apply_counters(child, local_counters)

    apply_counters(root, {})

    def insert_pseudo_elements(node):
        if node.is_text():
            return

        node.children = [
            c for c in node.children if not getattr(c, "pseudo_element", None)
        ]

        if hasattr(node, "pseudo_styles"):
            for pseudo_name, pseudo_style in node.pseudo_styles.items():
                if pseudo_name == "selection":
                    continue
                if pseudo_style.get("display", "").strip().lower() == "none":
                    continue
                content_raw = pseudo_style.get("content", "")
                items = _parse_content_items(str(content_raw))
                if not items:
                    continue

                pseudo_node = DOMNode(tag=f"::{pseudo_name}")
                pseudo_node.pseudo_element = pseudo_name
                pseudo_node.computed_style = dict(pseudo_style)

                text_parts = []
                for item in items:
                    if item["type"] == "string":
                        text_parts.append(item["value"])
                    elif item["type"] == "counter":
                        value = node.counter_values.get(item["name"], 0)
                        text_parts.append(str(value))
                content_text = "".join(text_parts)
                if content_text:
                    text_node = create_text_node(content_text)
                    text_node.computed_style = dict(pseudo_style)
                    pseudo_node.append_child(text_node)

                if pseudo_name == "before":
                    node.children.insert(0, pseudo_node)
                else:
                    node.children.append(pseudo_node)

        for child in node.children:
            insert_pseudo_elements(child)

    insert_pseudo_elements(root)


def style_to_qss(style: dict) -> str:
    qss = []

    def _font_px_or_none(v) -> int | None:
        if v is None:
            return None
        s = str(v).strip().lower()
        if s.endswith("px"):
            s = s[:-2].strip()
        if re.fullmatch(r"[-+]?\d+", s):
            return int(s)
        return None

    if "color" in style:
        qss.append(f"color: {style['color']};")
    if "background-color" in style:
        qss.append(f"background-color: {style['background-color']};")

    if "font-size" in style:
        font_px = _font_px_or_none(style.get("font-size"))
        if font_px is None or font_px > 0:
            qss.append(f"font-size: {px(style['font-size'])};")
    if "font-weight" in style:
        qss.append(f"font-weight: {style['font-weight']};")
    if "font-style" in style:
        qss.append(f"font-style: {style['font-style']};")
    if "font-family" in style:
        qss.append(f"font-family: {style['font-family']};")

    if style.get("text-decoration", "").strip().lower() == "underline":
        qss.append("text-decoration: underline;")
    if style.get("text-decoration", "").strip().lower() == "line-through":
        qss.append("text-decoration: line-through;")

    if "margin-left" in style:
        qss.append(f"margin-left: {px(style['margin-left'])};")
    if "margin-right" in style:
        qss.append(f"margin-right: {px(style['margin-right'])};")
    if "margin-top" in style:
        qss.append(f"margin-top: {px(style['margin-top'])};")
    if "margin-bottom" in style:
        qss.append(f"margin-bottom: {px(style['margin-bottom'])};")
    if "padding" in style:
        qss.append(f"padding: {px(style['padding'])};")
    if "padding-left" in style:
        qss.append(f"padding-left: {px(style['padding-left'])};")
    if "padding-right" in style:
        qss.append(f"padding-right: {px(style['padding-right'])};")
    if "padding-top" in style:
        qss.append(f"padding-top: {px(style['padding-top'])};")
    if "padding-bottom" in style:
        qss.append(f"padding-bottom: {px(style['padding-bottom'])};")
    if "border-radius" in style:
        qss.append(f"border-radius: {px(style['border-radius'])};")
    if "border" in style:
        qss.append(f"border: {style['border']};")
    if "border-width" in style:
        qss.append(f"border-width: {px(style['border-width'])};")
    if "border-left-width" in style:
        qss.append(f"border-left-width: {px(style['border-left-width'])};")
    if "border-right-width" in style:
        qss.append(f"border-right-width: {px(style['border-right-width'])};")
    if "border-top-width" in style:
        qss.append(f"border-top-width: {px(style['border-top-width'])};")
    if "border-bottom-width" in style:
        qss.append(f"border-bottom-width: {px(style['border-bottom-width'])};")
    if "border-style" in style:
        qss.append(f"border-style: {style['border-style']};")
    if "border-color" in style:
        qss.append(f"border-color: {style['border-color']};")

    return " ".join(qss)


def style_to_css(style: dict) -> str:
    if not style:
        return ""

    length_props = {
        "font-size",
        "line-height",
        "margin-left",
        "margin-right",
        "margin-top",
        "margin-bottom",
        "padding",
        "padding-left",
        "padding-right",
        "padding-top",
        "padding-bottom",
        "border-radius",
        "border-width",
        "border-left-width",
        "border-right-width",
        "border-top-width",
        "border-bottom-width",
        "width",
        "max-width",
        "height",
    }

    parts = []
    for key, value in style.items():
        if value is None:
            continue
        val = str(value)
        if key in length_props:
            val = px(val)
        parts.append(f"{key}: {val};")

    return " ".join(parts)
