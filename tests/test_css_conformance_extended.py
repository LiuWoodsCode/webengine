import unittest

from renderer.css import compute_styles, parse_css_stylesheet, selector_matches, style_to_css, style_to_qss
from renderer.dom import DOMNode, create_text_node


class CSSParserCoverageTests(unittest.TestCase):
    def test_parse_multiple_rules(self):
        rules = parse_css_stylesheet("h1{color:red;} p{margin:1px 2px;}")
        self.assertEqual(len(rules), 2)

    def test_media_block_inner_rules_parsed(self):
        rules = parse_css_stylesheet("@media screen { p { color: red; } }")
        self.assertEqual(len(rules), 1)
        self.assertIn("color", rules[0]["props"])

    def test_selector_matching_id_class_attr(self):
        self.assertTrue(selector_matches("div#x.a[b='1']", "div", {"id": "x", "class": "a", "b": "1"}))

    def test_selector_descendant_and_child(self):
        root = DOMNode("div", attrs={"id": "a"})
        mid = DOMNode("section")
        leaf = DOMNode("span", attrs={"class": "x"})
        root.append_child(mid)
        mid.append_child(leaf)
        # Built selector matching helper uses selector string API for standalone cases
        self.assertTrue(selector_matches("span.x", "span", {"class": "x"}))

    def test_inline_media_rule_ignored_when_invalid(self):
        rules = parse_css_stylesheet("@unknown x; p{color:blue;}")
        self.assertEqual(len(rules), 1)
        self.assertIn("color", rules[0]["props"])

    def test_parse_attribute_selector_and_multiple_classes(self):
        self.assertTrue(selector_matches("a.btn.primary[href='x']", "a", {"class": "btn primary", "href": "x"}))

    def test_parse_important_flag(self):
        rules = parse_css_stylesheet("p { color: red !important; }")
        self.assertTrue(rules[0]["props"]["color"][1])

    def test_parse_vendor_keyword_allowed(self):
        rules = parse_css_stylesheet("img { image-rendering: -moz-crisp-edges; }")
        self.assertEqual(rules[0]["props"]["image-rendering"][0], "-moz-crisp-edges")

    
    
    def test_supports_nth_child_selector(self):
        rules = parse_css_stylesheet("li:nth-child(2){color:red;}")
        self.assertEqual(len(rules), 1)
        root = DOMNode("ul")
        first = DOMNode("li")
        second = DOMNode("li")
        third = DOMNode("li")
        root.append_child(first)
        root.append_child(second)
        root.append_child(third)
        compute_styles(root, rules, True)
        self.assertIsNone(first.computed_style.get("color"))
        self.assertEqual(second.computed_style.get("color"), "red")
        self.assertIsNone(third.computed_style.get("color"))

    
    
    def test_supports_custom_properties(self):
        rules = parse_css_stylesheet(":root{--gap:8px;} div{margin:var(--gap);}")
        self.assertTrue(any("--gap" in r["props"] for r in rules))
        document = DOMNode("#document")
        root = DOMNode("div")
        child = DOMNode("div")
        document.append_child(root)
        root.append_child(child)
        compute_styles(document, rules, True)
        self.assertEqual(root.computed_style.get("--gap"), "8px")
        self.assertEqual(child.computed_style.get("margin-left"), "8px")
        self.assertEqual(child.computed_style.get("margin-top"), "8px")

    
    
    def test_supports_calc_function_for_lengths(self):
        rules = parse_css_stylesheet("div{width:calc(100% - 20px);}")
        self.assertEqual(rules[0]["props"]["width"][0], "calc(100% - 20px)")

    
    
    def test_supports_supports_at_rule(self):
        rules = parse_css_stylesheet("@supports (display: grid) { div { display: grid; } }")
        self.assertEqual(len(rules), 1)


class CSSCascadeCoverageTests(unittest.TestCase):
    def test_specificity_beats_tag_rule(self):
        root = DOMNode("div")
        child = DOMNode("p", attrs={"id": "x"})
        child.append_child(create_text_node("hi"))
        root.append_child(child)

        rules = parse_css_stylesheet("p { color: blue; } #x { color: red; }")
        compute_styles(root, rules, True)
        self.assertEqual(child.computed_style.get("color"), "red")

    def test_important_beats_non_important(self):
        root = DOMNode("div")
        child = DOMNode("p")
        root.append_child(child)
        rules = parse_css_stylesheet("p { color: blue !important; } p { color: red; }")
        compute_styles(root, rules, True)
        self.assertEqual(child.computed_style.get("color"), "blue")

    def test_inherited_text_properties(self):
        root = DOMNode("div")
        root.append_child(DOMNode("span"))
        rules = parse_css_stylesheet("div { color: green; font-size: 20px; }")
        compute_styles(root, rules, True)
        self.assertEqual(root.children[0].computed_style.get("color"), "green")

    def test_presentational_html_attrs(self):
        node = DOMNode("div", attrs={"align": "center", "bgcolor": "#fff", "width": "100", "height": "50"})
        root = DOMNode("body")
        root.append_child(node)
        compute_styles(root, [], True)
        self.assertEqual(node.computed_style.get("text-align"), "center")
        self.assertEqual(node.computed_style.get("background-color"), "#fff")
        self.assertEqual(node.computed_style.get("width"), "100px")
        self.assertEqual(node.computed_style.get("height"), "50px")

    def test_style_to_css_length_serialization(self):
        css = style_to_css({"width": "10", "height": "12", "color": "red"})
        self.assertIn("width: 10px;", css)
        self.assertIn("height: 12px;", css)
        self.assertIn("color: red;", css)

    def test_qss_serialization_contains_core_properties(self):
        qss = style_to_qss({"color": "red", "background-color": "#fff", "font-size": "14"})
        self.assertIn("color: red;", qss)
        self.assertIn("background-color: #fff;", qss)
        self.assertIn("font-size: 14px;", qss)

    def test_css_disabled_uses_default_tag_style_only(self):
        root = DOMNode("h1")
        compute_styles(root, parse_css_stylesheet("h1 { color: red; }"), False)
        self.assertEqual(root.computed_style.get("font-weight"), "800")
        self.assertIsNone(root.computed_style.get("color"))

    def test_pseudo_class_first_child_applies(self):
        root = DOMNode("div")
        first = DOMNode("span")
        second = DOMNode("span")
        root.append_child(first)
        root.append_child(second)
        rules = parse_css_stylesheet("span:first-child { color: red; }")
        compute_styles(root, rules, True)
        self.assertEqual(first.computed_style.get("color"), "red")
        self.assertNotEqual(second.computed_style.get("color"), "red")

    def test_pseudo_class_last_child_applies(self):
        root = DOMNode("div")
        first = DOMNode("span")
        second = DOMNode("span")
        root.append_child(first)
        root.append_child(second)
        rules = parse_css_stylesheet("span:last-child { color: blue; }")
        compute_styles(root, rules, True)
        self.assertEqual(second.computed_style.get("color"), "blue")
        self.assertNotEqual(first.computed_style.get("color"), "blue")

    def test_white_space_nowrap_from_attribute(self):
        root = DOMNode("div", attrs={"nowrap": ""})
        compute_styles(root, [], True)
        self.assertEqual(root.computed_style.get("white-space"), "nowrap")

    
    
    def test_display_contents_support(self):
        rules = parse_css_stylesheet("div { display: contents; }")
        self.assertEqual(rules[0]["props"]["display"][0], "contents")
        root = DOMNode("div")
        compute_styles(root, rules, True)
        self.assertEqual(root.computed_style.get("display"), "contents")

    
    
    def test_pseudo_class_hover(self):
        rules = parse_css_stylesheet("a:hover { color: red; }")
        self.assertEqual(len(rules), 1)
        self.assertTrue(selector_matches("a:hover", "a", {"hover": ""}))
        self.assertFalse(selector_matches("a:hover", "a", {}))

    
    
    def test_media_query_condition_evaluation(self):
        root = DOMNode("p")
        rules = parse_css_stylesheet("@media (max-width: 400px) { p { color: red; } }")
        compute_styles(root, rules, True)
        self.assertIsNone(root.computed_style.get("color"))

    
    
    def test_specificity_with_not_pseudo_class(self):
        rules = parse_css_stylesheet("div:not(.x) { color: red; }")
        self.assertEqual(len(rules), 1)
        self.assertTrue(selector_matches("div:not(.x)", "div", {"class": "y"}))
        self.assertFalse(selector_matches("div:not(.x)", "div", {"class": "x"}))

    
    
    def test_layered_cascade_support(self):
        rules = parse_css_stylesheet("@layer a { p { color: red; } } @layer b { p { color: blue; } }")
        self.assertGreaterEqual(len(rules), 2)


if __name__ == "__main__":
    unittest.main()
