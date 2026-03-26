from __future__ import annotations

import logging
import re

from dataclasses import dataclass, field

from .constants import BLOCK_TAGS

log = logging.getLogger("Vivienne.Layout")


@dataclass
class LayoutNode:
    dom_node: object
    children: list["LayoutNode"] = field(default_factory=list)
    display: str = "inline"
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    anonymous: bool = False

    def append_child(self, node: "LayoutNode"):
        self.children.append(node)


def build_layout_tree(dom_root) -> LayoutNode:
    def node_display(dom_node) -> str:
        if dom_node.is_text():
            return "inline"
        return (dom_node.computed_style.get("display") or "inline").strip().lower()

    def build(dom_node) -> LayoutNode | None:
        display = node_display(dom_node)
        if display == "none":
            return None

        node = LayoutNode(dom_node=dom_node, display=display)

        if dom_node.is_text():
            return node

        children = []
        for child in dom_node.children:
            child_layout = build(child)
            if child_layout:
                children.append(child_layout)

        if display == "block":
            inline_buffer = []
            for child_layout in children:
                if child_layout.display == "inline":
                    inline_buffer.append(child_layout)
                    continue

                if inline_buffer:
                    anon = LayoutNode(dom_node=dom_node, display="block", anonymous=True)
                    for inline_child in inline_buffer:
                        anon.append_child(inline_child)
                    node.append_child(anon)
                    inline_buffer = []

                node.append_child(child_layout)

            if inline_buffer:
                anon = LayoutNode(dom_node=dom_node, display="block", anonymous=True)
                for inline_child in inline_buffer:
                    anon.append_child(inline_child)
                node.append_child(anon)
        else:
            for child_layout in children:
                node.append_child(child_layout)

        return node

    return build(dom_root)


class LayoutEngine:
    def __init__(self, viewport_width: int = 800):
        self.viewport_width = viewport_width

    def layout(self, root: LayoutNode):
        self._layout_block(root, 0, 0, self.viewport_width)

    def _parse_length(self, value, basis: int = 0, allow_auto: bool = True) -> int | None:
        if value is None:
            return None
        raw = str(value).strip().lower()
        if not raw:
            return None
        if allow_auto and raw == "auto":
            return None
        if raw in {"thin", "medium", "thick"}:
            return {"thin": 1, "medium": 3, "thick": 5}[raw]
        if raw.endswith("px"):
            raw = raw[:-2].strip()
        if raw.endswith("%"):
            number = raw[:-1].strip()
            try:
                return max(0, int(float(basis) * float(number) / 100.0))
            except Exception:
                return None
        if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", raw):
            try:
                return max(0, int(float(raw)))
            except Exception:
                return None
        return None

    def _style(self, node: LayoutNode) -> dict:
        return node.dom_node.computed_style or {}

    def _line_height(self, style: dict, font_size: int) -> int:
        raw = style.get("line-height")
        if raw is None:
            return max(1, int(font_size * 1.2))

        val = str(raw).strip().lower()
        if val in ("normal", ""):
            return max(1, int(font_size * 1.2))
        if val.endswith("%"):
            try:
                pct = float(val[:-1].strip())
                return max(1, int(font_size * pct / 100.0))
            except Exception:
                return max(1, int(font_size * 1.2))
        if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", val):
            try:
                return max(1, int(font_size * float(val)))
            except Exception:
                return max(1, int(font_size * 1.2))

        px_value = self._parse_length(raw)
        if px_value is None:
            return max(1, int(font_size * 1.2))
        return max(1, px_value)

    def _layout_block(self, node: LayoutNode, x: int, y: int, width: int) -> int:
        style = self._style(node)
        margin_left = self._parse_length(style.get("margin-left"), width) or 0
        margin_right = self._parse_length(style.get("margin-right"), width) or 0
        margin_top = self._parse_length(style.get("margin-top"), width) or 0
        margin_bottom = self._parse_length(style.get("margin-bottom"), width) or 0

        padding_left = self._parse_length(style.get("padding-left"), width) or 0
        padding_right = self._parse_length(style.get("padding-right"), width) or 0
        padding_top = self._parse_length(style.get("padding-top"), width) or 0
        padding_bottom = self._parse_length(style.get("padding-bottom"), width) or 0

        border_left = (
            self._parse_length(style.get("border-left-width"), width)
            or self._parse_length(style.get("border-width"), width)
            or 0
        )
        border_right = (
            self._parse_length(style.get("border-right-width"), width)
            or self._parse_length(style.get("border-width"), width)
            or 0
        )
        border_top = (
            self._parse_length(style.get("border-top-width"), width)
            or self._parse_length(style.get("border-width"), width)
            or 0
        )
        border_bottom = (
            self._parse_length(style.get("border-bottom-width"), width)
            or self._parse_length(style.get("border-width"), width)
            or 0
        )

        specified_width = self._parse_length(style.get("width"), width)
        non_content_h = (
            margin_left
            + margin_right
            + border_left
            + border_right
            + padding_left
            + padding_right
        )
        auto_content_width = max(0, width - non_content_h)
        content_width = auto_content_width if specified_width is None else max(0, specified_width)

        node.x = x + margin_left
        node.y = y + margin_top
        node.width = content_width + padding_left + padding_right + border_left + border_right

        content_x = node.x + border_left + padding_left
        content_y = node.y + border_top + padding_top
        cursor_y = content_y

        if node.display != "block":
            height = self._layout_inline(node, content_x, content_y, content_width)
            node.height = height
            return node.y + height + margin_bottom

        if node.anonymous and all(child.display == "inline" for child in node.children):
            cursor_y = self._layout_inline(node, content_x, content_y, content_width)
            content_height = max(0, cursor_y - content_y)
            specified_height = self._parse_length(style.get("height"), content_width)
            if specified_height is not None:
                content_height = max(content_height, specified_height)
            node.height = content_height + padding_top + padding_bottom + border_top + border_bottom
            return node.y + node.height + margin_bottom

        for child in node.children:
            if child.display == "block":
                cursor_y = self._layout_block(child, content_x, cursor_y, content_width)
            else:
                cursor_y = self._layout_inline(child, content_x, cursor_y, content_width)

        content_height = max(0, cursor_y - content_y)
        specified_height = self._parse_length(style.get("height"), content_width)
        if specified_height is not None:
            content_height = max(content_height, specified_height)

        node.height = content_height + padding_top + padding_bottom + border_top + border_bottom
        return node.y + node.height + margin_bottom

    def _layout_inline(self, node: LayoutNode, x: int, y: int, width: int) -> int:
        style = self._style(node)
        margin_left = self._parse_length(style.get("margin-left"), width) or 0
        margin_right = self._parse_length(style.get("margin-right"), width) or 0
        margin_top = self._parse_length(style.get("margin-top"), width) or 0
        margin_bottom = self._parse_length(style.get("margin-bottom"), width) or 0

        padding_left = self._parse_length(style.get("padding-left"), width) or 0
        padding_right = self._parse_length(style.get("padding-right"), width) or 0
        padding_top = self._parse_length(style.get("padding-top"), width) or 0
        padding_bottom = self._parse_length(style.get("padding-bottom"), width) or 0

        border_left = (
            self._parse_length(style.get("border-left-width"), width)
            or self._parse_length(style.get("border-width"), width)
            or 0
        )
        border_right = (
            self._parse_length(style.get("border-right-width"), width)
            or self._parse_length(style.get("border-width"), width)
            or 0
        )
        border_top = (
            self._parse_length(style.get("border-top-width"), width)
            or self._parse_length(style.get("border-width"), width)
            or 0
        )
        border_bottom = (
            self._parse_length(style.get("border-bottom-width"), width)
            or self._parse_length(style.get("border-width"), width)
            or 0
        )

        inline_x = x + margin_left
        inline_y = y + margin_top
        inner_x = inline_x + border_left + padding_left
        available_width = max(
            0,
            width
            - margin_left
            - margin_right
            - border_left
            - border_right
            - padding_left
            - padding_right,
        )

        node.x = inline_x
        node.y = inline_y
        node.width = available_width + padding_left + padding_right + border_left + border_right

        font_size = self._parse_length(style.get("font-size")) or 14
        line_height = self._line_height(style, font_size)
        cursor_x = x
        cursor_y = inner_y = inline_y + border_top + padding_top

        def measure_text(text: str, font_size: int) -> tuple[int, int]:
            w = int(len(text) * font_size * 0.6)
            h = int(font_size * 1.2)
            return max(0, w), max(0, h)

        if node.dom_node.is_text():
            text = node.dom_node.text or ""
            node_style = node.dom_node.computed_style or {}
            font_size = self._parse_length(node_style.get("font-size")) or font_size
            line_height = self._line_height(node_style, font_size)
            w, h = measure_text(text, font_size)
            if cursor_x + w > inner_x + available_width:
                cursor_x = inner_x
                cursor_y += line_height
            node.height = max(h, line_height)
            node.width = w
            node.x = cursor_x
            node.y = cursor_y
            return cursor_y + node.height + margin_bottom

        cursor_x = inner_x

        for child in node.children:
            if child.display == "block":
                cursor_y = self._layout_block(child, inner_x, cursor_y, available_width)
                cursor_x = inner_x
            else:
                cursor_y = self._layout_inline(child, cursor_x, cursor_y, available_width)

        content_height = max(line_height, cursor_y - inner_y)
        node.height = content_height + padding_top + padding_bottom + border_top + border_bottom
        return node.y + node.height + margin_bottom
