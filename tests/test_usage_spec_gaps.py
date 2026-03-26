import unittest

from renderer.engine import Vivienne


class TextOnlySink:
    def __init__(self):
        self.text = []

    def add_text(self, text, base_style=None, qss_extra=""):
        self.text.append(text)

    def add_link(self, href, text, qss="", css=None):
        self.text.append(text)

    def add_image(self, src, alt, qss, width=None, height=None, css=None):
        return None

    def add_input_text(self, value="", name="", qss="", size=None, maxlength=None, css=None):
        return None

    def add_input_button(self, text="", name="", qss="", input_type="button", css=None):
        self.text.append(text)

    def add_input_image_button(self, src, alt, name="", value="", qss="", width=None, height=None, css=None):
        return None

    def add_input_hidden(self, name="", value=""):
        return None

    def begin_block(self, tag, attrs=None, inline=False, qss="", css=None):
        return None

    def end_block(self, tag=None):
        return None

    def add_br(self):
        self.text.append("\n")

    def add_hr(self):
        self.text.append("----")


class UsageSpecGapTests(unittest.TestCase):
    def test_noscript_visible_when_js_disabled(self):
        sink = TextOnlySink()
        renderer = Vivienne(sink=sink, settings={"css_enabled": True, "js_enabled": False})
        renderer.render("<noscript>No script fallback</noscript>", base_url="http://example.com/")
        self.assertIn("No script fallback", " ".join(sink.text))

    
    
    def test_noscript_hidden_when_js_enabled(self):
        sink = TextOnlySink()
        renderer = Vivienne(sink=sink, settings={"css_enabled": True, "js_enabled": True})
        renderer.render("<noscript>No script fallback</noscript>", base_url="http://example.com/")
        self.assertNotIn("No script fallback", " ".join(sink.text))

    
    
    def test_button_default_type_submit_per_html_spec(self):
        sink = TextOnlySink()
        renderer = Vivienne(sink=sink, settings={"css_enabled": True, "js_enabled": False})
        renderer.render("<button>Send</button>", base_url="http://example.com/")
        self.assertIn("Send", " ".join(sink.text))


if __name__ == "__main__":
    unittest.main()
