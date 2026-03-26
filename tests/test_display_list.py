import unittest

from renderer.display_list import build_display_list
from renderer.dom import DOMNode, create_text_node
from renderer.layout import build_layout_tree


class DisplayListTests(unittest.TestCase):
    def test_link_command_includes_full_href(self):
        root = DOMNode(tag="div")
        root.computed_style = {"display": "block"}
        link = DOMNode(tag="a", attrs={"href": "page.html"})
        link.computed_style = {}
        link.append_child(create_text_node("Link"))
        root.append_child(link)

        layout_root = build_layout_tree(root)
        commands = build_display_list(layout_root, base_url="http://example.com/")

        link_cmds = [cmd for cmd in commands if cmd.kind == "link"]
        self.assertEqual(len(link_cmds), 1)
        self.assertEqual(link_cmds[0].payload["href"], "http://example.com/page.html")
        self.assertEqual(link_cmds[0].payload["text"], "Link")


if __name__ == "__main__":
    unittest.main()
