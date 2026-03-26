from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from .constants import BLOCK_TAGS
from .utils import html_unescape, normalize_ws, parse_px_int

log = logging.getLogger("Vivienne.DisplayList")


@dataclass
class DisplayCommand:
    kind: str
    payload: dict


class DisplayListBuilder:
    def __init__(self, base_url: str | None):
        self.base_url = base_url
        self.commands: list[DisplayCommand] = []
        self._text_buf = ""
        self._in_pre = False
        self._link_href = None
        self._link_text = ""
        self._link_style = {}
        self._list_stack: list[dict] = []
        self._in_li = False
        self._li_text = ""
        self._li_style = {}
        self._style_stack: list[dict] = []

    def _collapse_ws_preserve_edges(self, text: str) -> str:
        if not text:
            return ""
        collapsed = re.sub(r"\s+", " ", text)
        if not collapsed.strip():
            return ""
        return collapsed

    def _current_style(self) -> dict:
        return self._style_stack[-1] if self._style_stack else {}

    def block_start(self, tag: str, attrs: dict, style: dict, inline: bool = False):
        self.commands.append(
            DisplayCommand(
                kind="block_start",
                payload={"tag": tag, "attrs": attrs, "style": dict(style), "inline": bool(inline)},
            )
        )

    def block_end(self, tag: str):
        self.commands.append(DisplayCommand(kind="block_end", payload={"tag": tag}))

    def _flush_text(self, tag: str | None = None):
        if not self._text_buf:
            return

        text = html_unescape(self._text_buf)
        self._text_buf = ""

        style = dict(self._current_style())

        if self._in_pre:
            text = text.replace("\r\n", "\n")
            if text.strip("\n") == "":
                return
            self.commands.append(
                DisplayCommand(
                    kind="text",
                    payload={
                        "text": text,
                        "style": style,
                        "qss_extra": "font-family: monospace; background: rgba(0,0,0,0.06);",
                    },
                )
            )
            return

        text = self._collapse_ws_preserve_edges(text)
        if not text.strip():
            return

        self.commands.append(
            DisplayCommand(
                kind="text",
                payload={
                    "text": text,
                    "style": style,
                    "qss_extra": "",
                },
            )
        )

    def _flush_li(self):
        if not self._li_text:
            return

        text = html_unescape(self._li_text)
        self._li_text = ""

        if self._in_pre:
            text = text.replace("\r\n", "\n")
        else:
            text = normalize_ws(text)

        if not text:
            return

        bullet = "• " + text
        indent_px = 18 * max(0, len(self._list_stack) - 1)
        if self._list_stack:
            top = self._list_stack[-1]
            if top["type"] == "ol":
                bullet = f"{top['index']}. " + text

        style = dict(self._li_style)
        if "margin-left" not in style:
            style["margin-left"] = f"{indent_px}px"

        self.commands.append(
            DisplayCommand(
                kind="text",
                payload={"text": bullet, "style": style, "qss_extra": ""},
            )
        )

    def _flush_link(self):
        text = normalize_ws(html_unescape(self._link_text))
        href = self._link_href
        style = dict(self._link_style)
        self._link_text = ""
        self._link_href = None
        self._link_style = {}

        if not href or not text:
            return

        full_href = urljoin(self.base_url or "", href)
        self.commands.append(
            DisplayCommand(
                kind="link",
                payload={
                    "href": full_href,
                    "text": text,
                    "style": style,
                },
            )
        )

    def start_element(self, tag: str, attrs: dict, style: dict):
        if tag in BLOCK_TAGS and self._link_href is None and not self._in_li:
            self._flush_text(tag)

        local_style = dict(style or {})
        if tag == "nobr" or "nowrap" in attrs:
            local_style["white-space"] = "nowrap"

        self._style_stack.append(local_style)

        if tag == "pre":
            self._in_pre = True

        if tag == "a":
            if self._link_href is None and not self._in_li:
                self._flush_text(tag)
            self._link_href = attrs.get("href")
            self._link_text = ""
            self._link_style = local_style

        if tag in ("ul", "menu", "dir"):
            self._list_stack.append({"type": "ul", "index": 0})

        if tag == "ol":
            self._list_stack.append({"type": "ol", "index": 0})

        if tag == "li":
            self._in_li = True
            self._li_text = ""
            self._li_style = local_style
            if self._list_stack and self._list_stack[-1]["type"] == "ol":
                self._list_stack[-1]["index"] += 1

    def end_element(self, tag: str):
        if tag == "a" and self._link_href is not None:
            self._flush_link()

        if tag == "li" and self._in_li:
            self._flush_li()
            self._in_li = False
            self._li_style = {}

        if tag in ("ul", "ol", "menu", "dir") and self._list_stack:
            self._list_stack.pop()

        if tag == "pre":
            self._flush_text(tag)
            self._in_pre = False

        if tag in BLOCK_TAGS and self._link_href is None and not self._in_li:
            self._flush_text(tag)

        if self._style_stack:
            self._style_stack.pop()

    def text(self, text: str):
        if not text:
            return
        if self._link_href is not None:
            self._link_text += text
        elif self._in_li:
            self._li_text += text
        else:
            self._text_buf += text

    def self_element(self, tag: str, attrs: dict, style: dict):
        if tag == "br":
            self._flush_text(tag)
            self.commands.append(DisplayCommand(kind="br", payload={}))
            return

        if tag == "hr":
            self._flush_text(tag)
            self.commands.append(DisplayCommand(kind="hr", payload={}))
            return

        if tag == "img":
            self._flush_text(tag)
            src = attrs.get("src", "")
            full_src = urljoin(self.base_url or "", src)
            width = parse_px_int(style.get("width") or attrs.get("width"))
            height = parse_px_int(style.get("height") or attrs.get("height"))
            self.commands.append(
                DisplayCommand(
                    kind="image",
                    payload={
                        "src": full_src,
                        "alt": attrs.get("alt", ""),
                        "style": style,
                        "width": width,
                        "height": height,
                    },
                )
            )
            return

        if tag == "input":
            kind = (attrs.get("type") or "text").strip().lower()
            if kind == "hidden":
                self.commands.append(
                    DisplayCommand(
                        kind="input_hidden",
                        payload={
                            "name": attrs.get("name", ""),
                            "value": attrs.get("value", ""),
                        },
                    )
                )
                return

            if kind == "image":
                self._flush_text(tag)
                src = attrs.get("src", "")
                full_src = urljoin(self.base_url or "", src)
                width = parse_px_int(style.get("width") or attrs.get("width"))
                height = parse_px_int(style.get("height") or attrs.get("height"))
                self.commands.append(
                    DisplayCommand(
                        kind="input_image_button",
                        payload={
                            "src": full_src,
                            "alt": attrs.get("alt", ""),
                            "name": attrs.get("name", ""),
                            "value": attrs.get("value", ""),
                            "style": style,
                            "width": width,
                            "height": height,
                        },
                    )
                )
                return

            if kind in ("submit", "button", "reset"):
                self._flush_text(tag)
                label = attrs.get("value") or ("Submit" if kind == "submit" else "Button")
                self.commands.append(
                    DisplayCommand(
                        kind="input_button",
                        payload={
                            "text": label,
                            "name": attrs.get("name", ""),
                            "input_type": kind,
                            "style": style,
                        },
                    )
                )
                return

            self._flush_text(tag)
            self.commands.append(
                DisplayCommand(
                    kind="input_text",
                    payload={
                        "value": attrs.get("value", ""),
                        "name": attrs.get("name", ""),
                        "size": attrs.get("size"),
                        "maxlength": attrs.get("maxlength"),
                        "style": style,
                    },
                )
            )
            return

    def finish(self):
        if self._link_href is not None:
            self._flush_link()
        if self._in_li and self._li_text.strip():
            self._flush_li()
        if self._text_buf.strip():
            self._flush_text()


def build_display_list(layout_root, base_url: str | None):
    builder = DisplayListBuilder(base_url=base_url)

    def walk(layout_node):
        dom = layout_node.dom_node
        if dom.tag == "#text":
            builder.text(dom.text or "")
            return

        if layout_node.anonymous:
            for child in layout_node.children:
                walk(child)
            return

        tag = dom.tag
        attrs = dom.attrs
        style = dom.computed_style

        display = (layout_node.display or "").strip().lower()
        is_container = (
            not layout_node.anonymous
            and tag not in ("#document",)
            and display in {
                "block",
                "flex",
                "inline-block",
                "inline-flex",
                "table",
                "table-row",
                "table-cell",
                "table-row-group",
                "table-header-group",
                "table-footer-group",
                "table-caption",
            }
        )
        inline_container = display in {"inline-block", "inline-flex", "table-cell", "table-caption"}

        if tag in ("br", "hr", "img", "input"):
            builder.self_element(tag, attrs, style)
            return

        builder.start_element(tag, attrs, style)
        if is_container:
            builder.block_start(tag, attrs, style, inline=inline_container)
        for child in layout_node.children:
            walk(child)
        builder.end_element(tag)
        if is_container:
            builder.block_end(tag)

    walk(layout_root)
    builder.finish()
    return builder.commands
