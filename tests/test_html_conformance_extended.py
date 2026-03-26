import unittest

from renderer.html_tokenizer import HTMLTokenizer
from renderer.html_tree_builder import HTMLTreeBuilder


class HTMLTokenizerCoverageTests(unittest.TestCase):
    def test_start_end_and_text_tokens(self):
        tokens = HTMLTokenizer().feed("<div>Hello</div>")
        self.assertEqual([t["type"] for t in tokens], ["start", "text", "end"])

    def test_attributes_unquoted_and_quoted(self):
        tokens = HTMLTokenizer().feed('<img alt="A" width=10>')
        self.assertEqual(tokens[0]["attrs"]["alt"], "A")
        self.assertEqual(tokens[0]["attrs"]["width"], "10")

    def test_comment_ignored(self):
        tokens = HTMLTokenizer().feed("<!--x--><p>y</p>")
        self.assertEqual([t["type"] for t in tokens], ["start", "text", "end"])

    def test_rawtext_script(self):
        tokens = HTMLTokenizer().feed("<script>a < b</script>")
        self.assertEqual(tokens[1]["type"], "text")
        self.assertIn("a < b", tokens[1]["text"])

    def test_tag_and_attribute_names_lowercased(self):
        tokens = HTMLTokenizer().feed("<DiV DATA-X='1'></DiV>")
        self.assertEqual(tokens[0]["tag"], "div")
        self.assertIn("data-x", tokens[0]["attrs"])

    def test_streaming_feed_across_chunks(self):
        tokenizer = HTMLTokenizer()
        t1 = tokenizer.feed("<div>hel")
        t2 = tokenizer.feed("lo</div>")
        tokens = t1 + t2
        self.assertEqual(tokens[0]["type"], "start")
        self.assertEqual(tokens[0]["tag"], "div")
        self.assertIn("hello", "".join(t.get("text", "") for t in tokens if t["type"] == "text"))
        self.assertEqual(tokens[-1]["type"], "end")

    def test_close_flushes_leftover_text(self):
        tokenizer = HTMLTokenizer()
        tokenizer.feed("plain")
        leftover = tokenizer.close()
        self.assertEqual(leftover, [{"type": "text", "text": "plain"}])

    
    
    def test_doctype_tokenization(self):
        tokens = HTMLTokenizer().feed("<!DOCTYPE html>")
        self.assertEqual(tokens[0]["type"], "doctype")

    
    
    def test_character_references_decoded_in_tokenizer(self):
        tokens = HTMLTokenizer().feed("<p>&nbsp;</p>")
        self.assertEqual(tokens[1]["text"], "\u00a0")

    
    
    def test_bogus_comment_handling(self):
        tokens = HTMLTokenizer().feed("<!----->")
        self.assertEqual(tokens, [])

    
    
    def test_rcdata_title_character_reference_processing(self):
        tokens = HTMLTokenizer().feed("<title>a &amp; b</title>")
        self.assertEqual(tokens[1]["text"], "a & b")

    
    
    def test_attribute_without_value_is_empty_string_boolean_attr(self):
        tokens = HTMLTokenizer().feed("<input disabled>")
        self.assertEqual(tokens[0]["attrs"]["disabled"], "")


class HTMLTreeBuilderCoverageTests(unittest.TestCase):
    def test_build_simple_tree(self):
        b = HTMLTreeBuilder()
        for token in HTMLTokenizer().feed("<div><span>x</span></div>"):
            b.process(token)
        div = b.document.root.children[0]
        self.assertEqual(div.tag, "div")
        self.assertEqual(div.children[0].tag, "span")

    def test_auto_close_p_before_div(self):
        b = HTMLTreeBuilder()
        for token in HTMLTokenizer().feed("<p>a<div>b</div>"):
            b.process(token)
        tags = [n.tag for n in b.document.root.children]
        self.assertEqual(tags[0], "p")
        self.assertEqual(tags[1], "div")

    def test_auto_close_repeated_li(self):
        b = HTMLTreeBuilder()
        for token in HTMLTokenizer().feed("<li>a<li>b"):
            b.process(token)
        tags = [n.tag for n in b.document.root.children]
        self.assertEqual(tags, ["li", "li"])

    def test_self_closing_element_inserted(self):
        b = HTMLTreeBuilder()
        for token in HTMLTokenizer().feed("<div><img src='x'></div>"):
            b.process(token)
        div = b.document.root.children[0]
        self.assertEqual(div.tag, "div")
        self.assertEqual(div.children[0].tag, "img")

    def test_unmatched_end_tag_is_ignored(self):
        b = HTMLTreeBuilder()
        for token in HTMLTokenizer().feed("<div>x</span></div>"):
            b.process(token)
        self.assertEqual(b.document.root.children[0].tag, "div")

    def test_nested_list_structure(self):
        b = HTMLTreeBuilder()
        html = "<ul><li>one</li><li>two</li></ul>"
        for token in HTMLTokenizer().feed(html):
            b.process(token)
        ul = b.document.root.children[0]
        self.assertEqual(ul.tag, "ul")
        self.assertEqual([child.tag for child in ul.children], ["li", "li"])

    
    
    def test_implied_html_head_body_elements(self):
        b = HTMLTreeBuilder()
        tokenizer = HTMLTokenizer()
        for token in tokenizer.feed("hello"):
            b.process(token)
        for token in tokenizer.close():
            b.process(token)
        tags = [n.tag for n in b.document.root.children]
        self.assertIn("html", tags)
        html = b.document.root.children[0]
        self.assertEqual([child.tag for child in html.children], ["head", "body"])
        self.assertEqual(html.children[1].children[0].text, "hello")

    
    
    def test_adoption_agency_algorithm_for_misnested_formatting(self):
        b = HTMLTreeBuilder()
        for token in HTMLTokenizer().feed("<b><i>x</b>y</i>"):
            b.process(token)
        self.assertEqual([child.tag for child in b.document.root.children], ["b", "i"])
        self.assertEqual(b.document.root.children[0].children[0].tag, "i")
        self.assertEqual(b.document.root.children[0].children[0].children[0].text, "x")
        self.assertEqual(b.document.root.children[1].children[0].text, "y")

    
    
    def test_table_foster_parenting(self):
        b = HTMLTreeBuilder()
        for token in HTMLTokenizer().feed("<table>text<tr><td>x</td></tr></table>"):
            b.process(token)
        self.assertEqual(b.document.root.children[0].tag, "#text")
        self.assertEqual(b.document.root.children[0].text, "text")
        self.assertEqual(b.document.root.children[1].tag, "table")
        self.assertEqual(b.document.root.children[1].children[0].tag, "tr")

    
    
    def test_template_content_model(self):
        b = HTMLTreeBuilder()
        for token in HTMLTokenizer().feed("<template><div>x</div></template>"):
            b.process(token)
        template = b.document.root.children[0]
        self.assertEqual(template.tag, "template")
        self.assertEqual(template.children[0].tag, "div")
        self.assertEqual(template.children[0].children[0].text, "x")

    
    
    def test_noscript_tree_rules_depend_on_scripting_flag(self):
        disabled = HTMLTreeBuilder(scripting_enabled=False)
        enabled = HTMLTreeBuilder(scripting_enabled=True)
        tokens = HTMLTokenizer().feed("<noscript><p>x</p></noscript>")
        for token in tokens:
            disabled.process(token)
            enabled.process(token)

        self.assertEqual(disabled.document.root.children[0].children[0].tag, "p")
        self.assertEqual(disabled.document.root.children[0].children[0].children[0].text, "x")
        self.assertEqual(enabled.document.root.children[0].tag, "noscript")
        self.assertEqual(enabled.document.root.children[0].children, [])


if __name__ == "__main__":
    unittest.main()
