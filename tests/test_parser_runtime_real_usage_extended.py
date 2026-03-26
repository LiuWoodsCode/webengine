import unittest

from js import default_globals, parse_js
from js.runtime import JSRuntime


class ParserRuntimeRealUsageExtendedTests(unittest.TestCase):
    def test_parse_and_execute_multi_statement_ui_flow(self):
        code = (
            "var total = 0;"
            "total = total + 10;"
            "total = total - 3;"
            "total;"
        )
        parse_js(code)
        result = JSRuntime().execute(code)
        self.assertEqual(result, 7.0)

    def test_stateful_assignments_like_form_updates(self):
        rt = JSRuntime()
        code = (
            "var formValue = 'a';"
            "formValue = formValue + 'b';"
            "formValue;"
        )
        self.assertEqual(rt.execute(code), "ab")

    def test_window_console_and_math_available_from_default_globals(self):
        logs = []
        rt = JSRuntime(default_globals(console_logger=logs.append))
        result = rt.execute("window.console.log(Math.round(1.6));")
        self.assertIsNone(result)
        self.assertEqual(logs, ["2"])

    def test_location_href_setter_integration(self):
        nav_log = []
        globals_dict = default_globals(
            location=type(
                "Loc",
                (),
                {
                    "href": "",
                    "replace": lambda self, v: nav_log.append(v),
                },
            )(),
            console_logger=lambda _msg: None,
        )
        rt = JSRuntime(globals_dict)
        rt.execute("location.href = 'http://example.com';")
        self.assertEqual(globals_dict["location"].href, "http://example.com")


if __name__ == "__main__":
    unittest.main()
