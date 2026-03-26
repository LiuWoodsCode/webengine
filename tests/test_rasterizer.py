import unittest

from renderer.rasterizer import rasterize
from renderer.display_list import DisplayCommand


class DummySink:
    def __init__(self):
        self.calls = []

    def add_text(self, text, base_style=None, qss_extra=""):
        self.calls.append(("text", text, base_style, qss_extra))

    def add_link(self, href, text, qss="", css=None):
        self.calls.append(("link", href, text, qss, css))

    def add_image(self, src, alt, qss, width=None, height=None, css=None):
        self.calls.append(("image", src, alt, qss, width, height, css))

    def add_input_text(self, value="", name="", qss="", size=None, maxlength=None, css=None):
        self.calls.append(("input_text", value, name, qss, size, maxlength, css))

    def add_input_button(self, text="", name="", qss="", input_type="button", css=None):
        self.calls.append(("input_button", text, name, qss, input_type, css))

    def add_input_image_button(self, src, alt, name="", value="", qss="", width=None, height=None, css=None):
        self.calls.append(("input_image_button", src, alt, name, value, qss, width, height, css))

    def add_input_hidden(self, name="", value=""):
        self.calls.append(("input_hidden", name, value))

    def begin_block(self, tag, attrs=None, inline=False, qss="", css=None):
        self.calls.append(("block_start", tag, attrs, inline, qss, css))

    def end_block(self, tag=None):
        self.calls.append(("block_end", tag))

    def add_br(self):
        self.calls.append(("br",))

    def add_hr(self):
        self.calls.append(("hr",))


class RasterizerTests(unittest.TestCase):
    def test_rasterize_dispatches_commands(self):
        sink = DummySink()
        display_list = [
            DisplayCommand(kind="text", payload={"text": "Tom &amp; Jerry", "style": {}, "qss_extra": ""}),
            DisplayCommand(kind="link", payload={"href": "http://x", "text": "X", "style": {"color": "red"}}),
            DisplayCommand(kind="image", payload={"src": "img.png", "alt": "img", "style": {}, "width": 10, "height": 20}),
            DisplayCommand(kind="input_text", payload={"value": "v", "name": "n", "style": {}, "size": 4, "maxlength": 8}),
            DisplayCommand(kind="input_button", payload={"text": "Go", "name": "btn", "style": {}, "input_type": "submit"}),
            DisplayCommand(kind="input_image_button", payload={"src": "btn.png", "alt": "b", "name": "n", "value": "v", "style": {}, "width": 1, "height": 2}),
            DisplayCommand(kind="input_hidden", payload={"name": "h", "value": "1"}),
            DisplayCommand(kind="block_start", payload={"tag": "div", "attrs": {}, "inline": False, "style": {"color": "red"}}),
            DisplayCommand(kind="block_end", payload={"tag": "div"}),
            DisplayCommand(kind="br", payload={}),
            DisplayCommand(kind="hr", payload={}),
        ]

        rasterize(display_list, sink)

        self.assertEqual(sink.calls[0][0], "text")
        self.assertEqual(sink.calls[0][1], "Tom & Jerry")
        kinds = [call[0] for call in sink.calls]
        self.assertIn("link", kinds)
        self.assertIn("image", kinds)
        self.assertIn("input_text", kinds)
        self.assertIn("input_button", kinds)
        self.assertIn("input_image_button", kinds)
        self.assertIn("input_hidden", kinds)
        self.assertIn("block_start", kinds)
        self.assertIn("block_end", kinds)
        self.assertIn("br", kinds)
        self.assertIn("hr", kinds)


if __name__ == "__main__":
    unittest.main()
