import unittest

from renderer.html_tree_builder import HTMLTreeBuilder


class HTMLTreeBuilderTests(unittest.TestCase):
    def test_auto_close_p_with_block(self):
        builder = HTMLTreeBuilder()
        builder.process({"type": "start", "tag": "p", "attrs": {}})
        builder.process({"type": "start", "tag": "div", "attrs": {}})
        builder.process({"type": "end", "tag": "div"})
        root = builder.document.root
        self.assertEqual([child.tag for child in root.children], ["p", "div"])

    def test_auto_close_same_tag(self):
        builder = HTMLTreeBuilder()
        builder.process({"type": "start", "tag": "li", "attrs": {}})
        builder.process({"type": "text", "text": "a"})
        builder.process({"type": "start", "tag": "li", "attrs": {}})
        builder.process({"type": "text", "text": "b"})
        root = builder.document.root
        self.assertEqual([child.tag for child in root.children], ["li", "li"])
        self.assertEqual(root.children[0].children[0].text, "a")
        self.assertEqual(root.children[1].children[0].text, "b")


if __name__ == "__main__":
    unittest.main()
