from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DOMNode:
    tag: str
    attrs: dict[str, Any] = field(default_factory=dict)
    text: str | None = None
    children: list["DOMNode"] = field(default_factory=list)
    parent: "DOMNode | None" = None
    computed_style: dict[str, Any] = field(default_factory=dict)

    def append_child(self, node: "DOMNode"):
        node.parent = self
        self.children.append(node)

    def insert_child(self, index: int, node: "DOMNode"):
        node.parent = self
        self.children.insert(index, node)

    def is_text(self) -> bool:
        return self.tag == "#text"


@dataclass
class Document:
    root: DOMNode = field(default_factory=lambda: DOMNode(tag="#document"))


def create_text_node(text: str) -> DOMNode:
    return DOMNode(tag="#text", text=text)
