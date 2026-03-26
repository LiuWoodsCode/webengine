import unittest

from renderer.utils import html_unescape, normalize_ws, parse_px_int, px


class UtilsTests(unittest.TestCase):
    def test_html_unescape(self):
        self.assertEqual(html_unescape("&lt;div&gt;&amp;"), "<div>&")

    def test_normalize_ws(self):
        self.assertEqual(normalize_ws(" a \n  b\t"), "a b")

    def test_px(self):
        self.assertEqual(px("12"), "12px")
        self.assertEqual(px("5px"), "5px")

    def test_parse_px_int(self):
        self.assertEqual(parse_px_int("10px"), 10)
        self.assertEqual(parse_px_int("8"), 8)
        self.assertIsNone(parse_px_int("1.5px"))


if __name__ == "__main__":
    unittest.main()
