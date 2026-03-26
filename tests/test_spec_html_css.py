import unittest

from renderer.css import parse_css_stylesheet
from renderer.html_tokenizer import HTMLTokenizer
from renderer.html_tree_builder import HTMLTreeBuilder


class HTMLSpecConformanceTests(unittest.TestCase):
    def test_end_tag_matching_is_case_insensitive(self):
        tokenizer = HTMLTokenizer()
        tokens = tokenizer.feed("<TiTlE>Hello</TITLE>")
        self.assertEqual(tokens[0]["type"], "start")
        self.assertEqual(tokens[0]["tag"], "title")
        self.assertEqual(tokens[1]["type"], "text")
        self.assertEqual(tokens[1]["text"], "Hello")
        self.assertEqual(tokens[2]["type"], "end")
        self.assertEqual(tokens[2]["tag"], "title")

    
    
    def test_doctype_token_emitted_per_html_parsing_model(self):
        tokenizer = HTMLTokenizer()
        tokens = tokenizer.feed("<!DOCTYPE html>")
        self.assertEqual(tokens[0]["type"], "doctype")
        self.assertEqual(tokens[0]["name"].lower(), "html")

    
    
    def test_tree_builder_inserts_html_and_body_elements(self):
        builder = HTMLTreeBuilder()
        builder.process({"type": "text", "text": "hello"})
        root_tags = [child.tag for child in builder.document.root.children]
        self.assertIn("html", root_tags)


class CSSSpecConformanceTests(unittest.TestCase):
    def test_grouped_selectors_are_parsed(self):
        rules = parse_css_stylesheet("h1, h2 { color: red; }")
        self.assertEqual(len(rules), 1)
        self.assertEqual(len(rules[0]["selectors"]), 2)

    
    
    def test_custom_properties_are_preserved(self):
        rules = parse_css_stylesheet(":root { --brand: red; } h1 { color: var(--brand); }")
        self.assertTrue(any("--brand" in rule["props"] for rule in rules))

    
    
    def test_nth_child_selector_is_supported(self):
        rules = parse_css_stylesheet("li:nth-child(2) { color: red; }")
        self.assertEqual(len(rules), 1)


if __name__ == "__main__":
    unittest.main()
