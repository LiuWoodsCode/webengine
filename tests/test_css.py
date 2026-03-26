import unittest

from renderer.css import (
    compute_styles,
    parse_css_stylesheet,
    parse_inline_style,
    style_to_css,
    style_to_qss,
)
from renderer.dom import DOMNode, create_text_node


class CSSTests(unittest.TestCase):
    def test_parse_inline_style_expands_margin(self):
        props = parse_inline_style("color: red; margin: 1px 2px;")
        self.assertEqual(props["color"][0], "red")
        self.assertEqual(props["margin-top"][0], "1px")
        self.assertEqual(props["margin-right"][0], "2px")
        self.assertEqual(props["margin-bottom"][0], "1px")
        self.assertEqual(props["margin-left"][0], "2px")

    def test_compute_styles_applies_rules(self):
        root = DOMNode(tag="div")
        para = DOMNode(tag="p")
        para.append_child(create_text_node("hello"))
        root.append_child(para)

        rules = parse_css_stylesheet("p { color: red; }")
        compute_styles(root, rules, True)

        self.assertEqual(para.computed_style.get("color"), "red")
        self.assertEqual(para.children[0].computed_style.get("color"), "red")

    def test_style_to_qss_and_css(self):
        style = {"color": "red", "font-size": "12", "width": "10"}
        qss = style_to_qss(style)
        css = style_to_css(style)
        self.assertIn("color: red;", qss)
        self.assertIn("font-size: 12px;", qss)
        self.assertIn("width: 10px;", css)

    def test_parse_inline_style_supports_float_and_clear(self):
        props = parse_inline_style("float: left; clear: both;")
        self.assertEqual(props["float"][0], "left")
        self.assertEqual(props["clear"][0], "both")


if __name__ == "__main__":
    unittest.main()
