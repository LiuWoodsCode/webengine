import unittest

import js
import renderer
from renderer.constants import BLOCK_TAGS, INHERITED_PROPERTIES, INLINE_TAGS, SELF_CLOSING, SKIP_TAGS
from renderer.dom import DOMNode, Document, create_text_node


class DOMTests(unittest.TestCase):
    def test_create_text_node(self):
        node = create_text_node("hello")
        self.assertEqual(node.tag, "#text")
        self.assertEqual(node.text, "hello")
        self.assertTrue(node.is_text())

    def test_append_child_sets_parent(self):
        root = DOMNode("div")
        child = DOMNode("span")
        root.append_child(child)
        self.assertIs(child.parent, root)
        self.assertEqual(root.children[0].tag, "span")

    def test_document_default_root(self):
        doc = Document()
        self.assertEqual(doc.root.tag, "#document")


class ConstantsTests(unittest.TestCase):
    def test_expected_tag_sets_contain_core_items(self):
        self.assertIn("div", BLOCK_TAGS)
        self.assertIn("span", INLINE_TAGS)
        self.assertIn("img", SELF_CLOSING)
        self.assertIn("script", SKIP_TAGS)

    def test_inherited_properties_core(self):
        self.assertIn("color", INHERITED_PROPERTIES)
        self.assertIn("font-size", INHERITED_PROPERTIES)


class ExportSurfaceTests(unittest.TestCase):
    def test_renderer_exports(self):
        self.assertTrue(hasattr(renderer, "Vivienne"))
        self.assertTrue(hasattr(renderer, "style_to_css"))
        self.assertTrue(hasattr(renderer, "style_to_qss"))

    def test_js_exports(self):
        self.assertTrue(hasattr(js, "JSRuntime"))
        self.assertTrue(hasattr(js, "parse_js"))
        self.assertTrue(hasattr(js, "default_globals"))


if __name__ == "__main__":
    unittest.main()
