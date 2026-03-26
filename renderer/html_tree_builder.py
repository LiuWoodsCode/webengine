import logging

from .constants import BLOCK_TAGS, SELF_CLOSING
from .dom import Document, DOMNode, create_text_node

log = logging.getLogger("Vivienne.HTML.TreeBuilder")


class HTMLTreeBuilder:
    def __init__(self):
        self.document = Document()
        self._stack: list[DOMNode] = [self.document.root]
        self._auto_close_same = {"p", "li", "dt", "dd", "option"}

    def _current(self) -> DOMNode:
        return self._stack[-1]

    def process(self, token: dict):
        ttype = token.get("type")
        if ttype == "text":
            text = token.get("text", "")
            if text:
                self._current().append_child(create_text_node(text))
            return

        if ttype == "self":
            tag = token.get("tag")
            attrs = token.get("attrs", {})
            node = DOMNode(tag=tag, attrs=attrs)
            self._current().append_child(node)
            return

        if ttype == "start":
            tag = token.get("tag")
            attrs = token.get("attrs", {})
            current = self._current()

            if current.tag in self._auto_close_same and current.tag == tag:
                self._stack.pop()
                current = self._current()

            if current.tag == "p" and tag in BLOCK_TAGS and tag != "p":
                self._stack.pop()

            node = DOMNode(tag=tag, attrs=attrs)
            self._current().append_child(node)
            if tag not in SELF_CLOSING:
                self._stack.append(node)
            return

        if ttype == "end":
            tag = token.get("tag")
            for i in range(len(self._stack) - 1, 0, -1):
                if self._stack[i].tag == tag:
                    self._stack = self._stack[:i]
                    return
            log.debug("end tag not found in stack: %s", tag)
