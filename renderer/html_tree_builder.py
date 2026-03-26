import logging

from .constants import BLOCK_TAGS, INLINE_TAGS, SELF_CLOSING
from .dom import Document, DOMNode, create_text_node

log = logging.getLogger("Vivienne.HTML.TreeBuilder")

TABLE_CONTEXT_TAGS = {"table", "tbody", "thead", "tfoot", "tr"}


class HTMLTreeBuilder:
    def __init__(self, scripting_enabled: bool = False):
        self.document = Document()
        self.scripting_enabled = scripting_enabled
        self._stack: list[DOMNode] = [self.document.root]
        self._auto_close_same = {"p", "li", "dt", "dd", "option"}
        self._noscript_skip_depth = 0
        self._html_node: DOMNode | None = None
        self._head_node: DOMNode | None = None
        self._body_node: DOMNode | None = None

    def _current(self) -> DOMNode:
        return self._stack[-1]

    def _find_open_element(self, tag: str) -> tuple[int, DOMNode] | None:
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                return i, self._stack[i]
        return None

    def _ensure_html_body(self) -> DOMNode:
        if self._html_node and self._body_node:
            return self._body_node

        for child in self.document.root.children:
            if child.tag == "html":
                self._html_node = child
                break

        if self._html_node is None:
            self._html_node = DOMNode(tag="html")
            self.document.root.append_child(self._html_node)

        for child in self._html_node.children:
            if child.tag == "head" and self._head_node is None:
                self._head_node = child
            elif child.tag == "body" and self._body_node is None:
                self._body_node = child

        if self._head_node is None:
            self._head_node = DOMNode(tag="head")
            self._html_node.append_child(self._head_node)

        if self._body_node is None:
            self._body_node = DOMNode(tag="body")
            self._html_node.append_child(self._body_node)

        return self._body_node

    def _append_to_current(self, node: DOMNode):
        current = self._current()
        if current.tag == "#document" and self._body_node is not None:
            self._body_node.append_child(node)
            return
        current.append_child(node)

    def _foster_parent_text(self, text: str) -> bool:
        if not text.strip():
            return False

        table_entry = self._find_open_element("table")
        if table_entry is None:
            return False

        _table_index, table_node = table_entry
        if self._current().tag not in TABLE_CONTEXT_TAGS:
            return False

        foster_parent = table_node.parent or self.document.root
        insert_at = foster_parent.children.index(table_node)
        foster_parent.insert_child(insert_at, create_text_node(text))
        return True

    def _reopen_inline_formatting(self, match_index: int):
        closed_node = self._stack[match_index]
        reopened_source = self._stack[match_index + 1 :]
        parent = closed_node.parent or self.document.root

        self._stack = self._stack[:match_index]

        current_parent = parent
        reopened_nodes: list[DOMNode] = []
        for old in reopened_source:
            if old.tag not in INLINE_TAGS or old.tag in SELF_CLOSING:
                continue
            clone = DOMNode(tag=old.tag, attrs=dict(old.attrs))
            current_parent.append_child(clone)
            reopened_nodes.append(clone)
            current_parent = clone

        self._stack.extend(reopened_nodes)

    def _handle_noscript_skip(self, token: dict) -> bool:
        if not self._noscript_skip_depth:
            return False

        ttype = token.get("type")
        tag = token.get("tag")
        if ttype == "start" and tag == "noscript":
            self._noscript_skip_depth += 1
            return True
        if ttype == "end" and tag == "noscript":
            self._noscript_skip_depth = max(0, self._noscript_skip_depth - 1)
            if self._noscript_skip_depth == 0 and self._current().tag == "noscript":
                self._stack.pop()
            return True
        return True

    def process(self, token: dict):
        ttype = token.get("type")
        if ttype == "doctype":
            return

        if self._handle_noscript_skip(token):
            return

        if ttype == "text":
            text = token.get("text", "")
            if not text:
                return
            if self._current().tag == "#document":
                self._ensure_html_body()
                self._body_node.append_child(create_text_node(text))
                return
            if self._foster_parent_text(text):
                return
            self._current().append_child(create_text_node(text))
            return

        if ttype == "self":
            tag = token.get("tag")
            attrs = token.get("attrs", {})
            node = DOMNode(tag=tag, attrs=attrs)
            self._append_to_current(node)
            return

        if ttype == "start":
            tag = token.get("tag")
            attrs = token.get("attrs", {})

            if tag == "noscript" and self.scripting_enabled:
                node = DOMNode(tag=tag, attrs=attrs)
                self._append_to_current(node)
                self._stack.append(node)
                self._noscript_skip_depth = 1
                return

            current = self._current()

            if current.tag in self._auto_close_same and current.tag == tag:
                self._stack.pop()
                current = self._current()

            if current.tag == "p" and tag in BLOCK_TAGS and tag != "p":
                self._stack.pop()

            node = DOMNode(tag=tag, attrs=attrs)
            self._append_to_current(node)
            if tag not in SELF_CLOSING:
                self._stack.append(node)
            return

        if ttype == "end":
            tag = token.get("tag")
            match = self._find_open_element(tag)
            if match is None:
                log.debug("end tag not found in stack: %s", tag)
                return

            index, node = match
            if index == len(self._stack) - 1:
                self._stack = self._stack[:index]
                return

            if node.tag in INLINE_TAGS and node.tag not in SELF_CLOSING:
                self._reopen_inline_formatting(index)
                return

            self._stack = self._stack[:index]
