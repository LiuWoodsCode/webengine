import unittest

from renderer.display_list import build_display_list
from renderer.dom import DOMNode, create_text_node
from renderer.layout import build_layout_tree


class DisplayListUsageExtendedTests(unittest.TestCase):
    def test_ordered_list_generates_numbered_items(self):
        root = DOMNode("ol")
        root.computed_style = {"display": "block"}

        li1 = DOMNode("li")
        li1.computed_style = {"display": "block"}
        li1.append_child(create_text_node("One"))

        li2 = DOMNode("li")
        li2.computed_style = {"display": "block"}
        li2.append_child(create_text_node("Two"))

        root.append_child(li1)
        root.append_child(li2)

        cmds = build_display_list(build_layout_tree(root), base_url="http://example.com/")
        texts = [c.payload["text"] for c in cmds if c.kind == "text"]
        self.assertIn("1. One", texts)
        self.assertIn("2. Two", texts)

    def test_unordered_list_generates_bullets(self):
        root = DOMNode("ul")
        root.computed_style = {"display": "block"}
        li = DOMNode("li")
        li.computed_style = {"display": "block"}
        li.append_child(create_text_node("Item"))
        root.append_child(li)

        cmds = build_display_list(build_layout_tree(root), base_url="http://example.com/")
        texts = [c.payload["text"] for c in cmds if c.kind == "text"]
        self.assertIn("• Item", texts)

    def test_pre_preserves_newlines(self):
        root = DOMNode("pre")
        root.computed_style = {"display": "block"}
        root.append_child(create_text_node("a\n  b"))

        cmds = build_display_list(build_layout_tree(root), base_url=None)
        text_cmd = next(c for c in cmds if c.kind == "text")
        self.assertEqual(text_cmd.payload["text"], "a\n  b")
        self.assertIn("monospace", text_cmd.payload["qss_extra"])

    def test_br_and_hr_emit_separate_commands(self):
        root = DOMNode("div")
        root.computed_style = {"display": "block"}
        br = DOMNode("br")
        br.computed_style = {"display": "inline"}
        hr = DOMNode("hr")
        hr.computed_style = {"display": "block"}

        root.append_child(create_text_node("A"))
        root.append_child(br)
        root.append_child(hr)
        root.append_child(create_text_node("B"))

        cmds = build_display_list(build_layout_tree(root), base_url=None)
        kinds = [c.kind for c in cmds]
        self.assertIn("br", kinds)
        self.assertIn("hr", kinds)

    def test_input_variants_emit_correct_command_types(self):
        root = DOMNode("div")
        root.computed_style = {"display": "block"}

        t = DOMNode("input", attrs={"type": "text", "name": "q", "value": "x"})
        t.computed_style = {"display": "inline"}
        b = DOMNode("input", attrs={"type": "submit", "name": "go", "value": "Go"})
        b.computed_style = {"display": "inline"}
        h = DOMNode("input", attrs={"type": "hidden", "name": "token", "value": "1"})
        h.computed_style = {"display": "inline"}

        root.append_child(t)
        root.append_child(b)
        root.append_child(h)

        cmds = build_display_list(build_layout_tree(root), base_url=None)
        kinds = [c.kind for c in cmds]
        self.assertIn("input_text", kinds)
        self.assertIn("input_button", kinds)
        self.assertIn("input_hidden", kinds)


if __name__ == "__main__":
    unittest.main()
