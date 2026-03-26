import unittest

from renderer.engine import Vivienne


class RecordingSink:
    def __init__(self):
        self.calls = []

    def add_text(self, text, base_style=None, qss_extra=""):
        self.calls.append(("text", text))

    def add_link(self, href, text, qss="", css=None):
        self.calls.append(("link", href, text))

    def add_image(self, src, alt, qss, width=None, height=None, css=None):
        self.calls.append(("image", src, alt, width, height))

    def add_input_text(self, value="", name="", qss="", size=None, maxlength=None, css=None):
        self.calls.append(("input_text", name, value, size, maxlength))

    def add_input_button(self, text="", name="", qss="", input_type="button", css=None):
        self.calls.append(("input_button", name, text, input_type))

    def add_input_image_button(self, src, alt, name="", value="", qss="", width=None, height=None, css=None):
        self.calls.append(("input_image_button", src, alt, name, value, width, height))

    def add_input_hidden(self, name="", value=""):
        self.calls.append(("input_hidden", name, value))

    def begin_block(self, tag, attrs=None, inline=False, qss="", css=None):
        self.calls.append(("block_start", tag, bool(inline)))

    def end_block(self, tag=None):
        self.calls.append(("block_end", tag))

    def add_br(self):
        self.calls.append(("br",))

    def add_hr(self):
        self.calls.append(("hr",))


class RenderingUsageTests(unittest.TestCase):
    def test_form_controls_render_in_source_order(self):
        sink = RecordingSink()
        renderer = Vivienne(sink=sink, settings={"css_enabled": True, "js_enabled": False})

        html = (
            "<form>"
            "<input type='button' name='one' value='One'>"
            "<input type='button' name='two' value='Two'>"
            "</form>"
        )
        renderer.render(html, base_url="http://example.com/")

        button_calls = [c for c in sink.calls if c[0] == "input_button"]
        self.assertEqual([c[1] for c in button_calls], ["one", "two"])

    def test_blocks_create_separate_block_boundaries(self):
        sink = RecordingSink()
        renderer = Vivienne(sink=sink, settings={"css_enabled": True, "js_enabled": False})
        renderer.render("<div>First</div><div>Second</div>", base_url="http://example.com/")

        block_starts = [c for c in sink.calls if c[0] == "block_start" and c[1] == "div"]
        self.assertEqual(len(block_starts), 2)

    def test_external_resource_buttons_keep_attributes(self):
        sink = RecordingSink()
        renderer = Vivienne(sink=sink, settings={"css_enabled": True, "js_enabled": False})

        html = "<input type='image' src='btn.png' alt='Go' name='go' value='1' width='24' height='16'>"
        renderer.render(html, base_url="http://example.com/ui/")

        image_btns = [c for c in sink.calls if c[0] == "input_image_button"]
        self.assertEqual(len(image_btns), 1)
        self.assertEqual(image_btns[0][1], "http://example.com/ui/btn.png")
        self.assertEqual(image_btns[0][5], 24)
        self.assertEqual(image_btns[0][6], 16)


if __name__ == "__main__":
    unittest.main()
