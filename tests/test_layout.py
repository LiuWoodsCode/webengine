import unittest

from renderer.dom import DOMNode
from renderer.layout import LayoutEngine, build_layout_tree


class LayoutTests(unittest.TestCase):
    def test_build_layout_tree_wraps_inline_runs(self):
        root = DOMNode(tag="div")
        root.computed_style = {"display": "block"}

        span1 = DOMNode(tag="span")
        span1.computed_style = {"display": "inline"}
        span2 = DOMNode(tag="span")
        span2.computed_style = {"display": "inline"}
        block = DOMNode(tag="div")
        block.computed_style = {"display": "block"}

        root.append_child(span1)
        root.append_child(span2)
        root.append_child(block)

        layout_root = build_layout_tree(root)
        self.assertEqual(len(layout_root.children), 2)
        self.assertTrue(layout_root.children[0].anonymous)
        self.assertEqual(len(layout_root.children[0].children), 2)
        self.assertEqual(layout_root.children[1].display, "block")

    def test_layout_engine_positions(self):
        root = DOMNode(tag="div")
        root.computed_style = {"display": "block"}
        child = DOMNode(tag="div")
        child.computed_style = {"display": "block"}
        root.append_child(child)

        layout_root = build_layout_tree(root)
        engine = LayoutEngine(viewport_width=200)
        engine.layout(layout_root)
        self.assertEqual(layout_root.width, 200)
        self.assertGreaterEqual(layout_root.height, 0)


if __name__ == "__main__":
    unittest.main()
