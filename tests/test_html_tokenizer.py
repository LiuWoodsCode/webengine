import unittest

from renderer.html_tokenizer import HTMLTokenizer


class HTMLTokenizerTests(unittest.TestCase):
    def test_basic_tokens_and_attrs(self):
        tokenizer = HTMLTokenizer()
        tokens = tokenizer.feed("<div class='a' data-x=1>Hi</div>")
        self.assertEqual(tokens[0]["type"], "start")
        self.assertEqual(tokens[0]["tag"], "div")
        self.assertEqual(tokens[0]["attrs"]["class"], "a")
        self.assertEqual(tokens[0]["attrs"]["data-x"], "1")
        self.assertEqual(tokens[1]["type"], "text")
        self.assertEqual(tokens[1]["text"], "Hi")
        self.assertEqual(tokens[2]["type"], "end")
        self.assertEqual(tokens[2]["tag"], "div")

    def test_raw_tag_script(self):
        tokenizer = HTMLTokenizer()
        tokens = tokenizer.feed("<script>if (a < b) {}</script>")
        self.assertEqual(tokens[0]["type"], "start")
        self.assertEqual(tokens[0]["tag"], "script")
        self.assertEqual(tokens[1]["type"], "text")
        self.assertIn("a < b", tokens[1]["text"])
        self.assertEqual(tokens[2]["type"], "end")
        self.assertEqual(tokens[2]["tag"], "script")

    def test_comments_ignored(self):
        tokenizer = HTMLTokenizer()
        tokens = tokenizer.feed("<!--comment--><p>ok</p>")
        self.assertEqual([t["type"] for t in tokens], ["start", "text", "end"])

    def test_self_closing(self):
        tokenizer = HTMLTokenizer()
        tokens = tokenizer.feed("<img src='x'/>")
        self.assertEqual(tokens[0]["type"], "self")
        self.assertEqual(tokens[0]["tag"], "img")
        self.assertEqual(tokens[0]["attrs"]["src"], "x")


if __name__ == "__main__":
    unittest.main()
