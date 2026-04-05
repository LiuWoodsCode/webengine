import unittest

from renderer.engine import Vivienne


class RecordingSink:
    def __init__(self):
        self.calls = []

    def add_text(self, text, base_style=None, qss_extra=""):
        self.calls.append(("text", text, base_style or {}, qss_extra))

    def add_link(self, href, text, qss="", css=None):
        self.calls.append(("link", href, text, css or {}))

    def add_image(self, src, alt, qss, width=None, height=None, css=None):
        self.calls.append(("image", src, alt, width, height, css or {}))

    def add_input_text(self, value="", name="", qss="", size=None, maxlength=None, css=None):
        self.calls.append(("input_text", name, value, size, maxlength, css or {}))

    def add_input_button(self, text="", name="", qss="", input_type="button", css=None):
        self.calls.append(("input_button", name, text, input_type, css or {}))

    def add_input_image_button(self, src, alt, name="", value="", qss="", width=None, height=None, css=None):
        self.calls.append(("input_image_button", src, alt, name, value, width, height, css or {}))

    def add_input_hidden(self, name="", value=""):
        self.calls.append(("input_hidden", name, value))

    def begin_block(self, tag, attrs=None, inline=False, qss="", css=None):
        self.calls.append(("block_start", tag, bool(inline), css or {}))

    def end_block(self, tag=None):
        self.calls.append(("block_end", tag))

    def add_br(self):
        self.calls.append(("br",))

    def add_hr(self):
        self.calls.append(("hr",))


class EngineIntegrationUsageTests(unittest.TestCase):
    def test_render_returns_document_title(self):
        sink = RecordingSink()
        renderer = Vivienne(sink=sink, settings={"css_enabled": True, "js_enabled": False})
        title = renderer.render("<title>My Page</title><p>Hello</p>", base_url="http://example.com/")
        self.assertEqual(title, "My Page")

    def test_inline_script_updates_title_when_js_enabled(self):
        sink = RecordingSink()
        renderer = Vivienne(sink=sink, settings={"css_enabled": True, "js_enabled": True})
        title = renderer.render(
            "<title>Before</title><script>document.title='After';</script>",
            base_url="http://example.com/",
        )
        self.assertEqual(title, "After")

    def test_external_script_loaded_and_executed(self):
        sink = RecordingSink()
        loaded = []

        def loader(url):
            loaded.append(url)
            if url.endswith("app.js"):
                return "document.title='Loaded';", url
            return "", url

        renderer = Vivienne(
            sink=sink,
            settings={"css_enabled": True, "js_enabled": True},
            resource_loader=loader,
        )
        title = renderer.render("<script src='app.js'></script>", base_url="http://example.com/")
        self.assertEqual(title, "Loaded")
        self.assertIn("http://example.com/app.js", loaded)

    def test_external_script_error_reaches_js_console_with_source_context(self):
        sink = RecordingSink()
        console_lines = []

        def loader(url):
            if url.endswith("app.js"):
                return (
                    "function throwErrorNoHandle() {\n"
                    "  notDefinedFunction();\n"
                    "}\n"
                    "throwErrorNoHandle();\n",
                    "http://example.com/assets/app.js",
                )
            return "", url

        renderer = Vivienne(
            sink=sink,
            settings={"css_enabled": True, "js_enabled": True},
            resource_loader=loader,
            js_console_sink=console_lines.append,
        )

        renderer.render("<script src='app.js'></script>", base_url="http://example.com/")

        self.assertEqual(len(console_lines), 1)
        self.assertIn("Uncaught ReferenceError: notDefinedFunction is not defined", console_lines[0])
        self.assertIn("throwErrorNoHandle http://example.com/assets/app.js:2", console_lines[0])
        self.assertIn("Source context:", console_lines[0])

    def test_external_script_syntax_error_reaches_js_console_with_source_context(self):
        sink = RecordingSink()
        console_lines = []

        def loader(url):
            if url.endswith("app.js"):
                return (
                    "function broken() {\n"
                    "  console.log((value) => 1 + ;\n"
                    "}\n",
                    "http://example.com/assets/app.js",
                )
            return "", url

        renderer = Vivienne(
            sink=sink,
            settings={"css_enabled": True, "js_enabled": True},
            resource_loader=loader,
            js_console_sink=console_lines.append,
        )

        renderer.render("<script src='app.js'></script>", base_url="http://example.com/")

        self.assertEqual(len(console_lines), 1)
        self.assertIn("Uncaught SyntaxError: Unexpected token punct:;", console_lines[0])
        self.assertIn("<parse> http://example.com/assets/app.js:2", console_lines[0])
        self.assertIn("Source context:", console_lines[0])

    def test_external_stylesheet_loaded_when_css_enabled(self):
        sink = RecordingSink()

        def loader(url):
            if url.endswith("style.css"):
                return "p { color: green; }", url
            return "", url

        renderer = Vivienne(
            sink=sink,
            settings={"css_enabled": True, "js_enabled": False},
            resource_loader=loader,
        )
        renderer.render("<link rel='stylesheet' href='style.css'><p>x</p>", base_url="http://example.com/")

        text_calls = [c for c in sink.calls if c[0] == "text"]
        self.assertTrue(any(call[2].get("color") == "green" for call in text_calls))

    def test_external_stylesheet_ignored_when_css_disabled(self):
        sink = RecordingSink()

        def loader(url):
            return "p { color: green; }", url

        renderer = Vivienne(
            sink=sink,
            settings={"css_enabled": False, "js_enabled": False},
            resource_loader=loader,
        )
        renderer.render("<link rel='stylesheet' href='style.css'><p>x</p>", base_url="http://example.com/")

        text_calls = [c for c in sink.calls if c[0] == "text"]
        self.assertTrue(text_calls)
        self.assertFalse(any(call[2].get("color") == "green" for call in text_calls))

    def test_float_and_clear_styles_reach_block_commands(self):
        sink = RecordingSink()
        renderer = Vivienne(sink=sink, settings={"css_enabled": True, "js_enabled": False})

        html = "<div id='left' style='float:left;width:40px'>A</div><div id='after' style='clear:left'>B</div>"

        renderer.render(html, base_url="http://example.com/")

        div_starts = [c for c in sink.calls if c[0] == "block_start" and c[1] == "div"]
        self.assertGreaterEqual(len(div_starts), 2)
        self.assertEqual(div_starts[0][3].get("float"), "left")
        self.assertEqual(div_starts[1][3].get("clear"), "left")


if __name__ == "__main__":
    unittest.main()
