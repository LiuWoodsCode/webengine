import unittest

from js.builtins import DocumentBridge, LocationBridge, default_globals
from js.runtime import JSError, JSObject, JSRuntime


class JSRuntimeTests(unittest.TestCase):
    def test_execute_and_assignment(self):
        runtime = JSRuntime()
        result = runtime.execute("var x = 1 + 2; x;")
        self.assertEqual(result, 3.0)

    def test_const_assignment_raises(self):
        runtime = JSRuntime()
        with self.assertRaises(JSError):
            runtime.execute("const y = 1; y = 2;")

    def test_member_assignment(self):
        obj = JSObject({"a": 1})
        runtime = JSRuntime({"obj": obj})
        result = runtime.execute("obj.a = 5; obj.a;")
        self.assertEqual(result, 5)

    def test_console_log_and_bridges(self):
        logs = []
        runtime = JSRuntime(default_globals(console_logger=logs.append))
        runtime.execute("console.log(1, true, null);")
        self.assertEqual(logs, ["1 true null"])

        title_state = {"value": ""}
        doc = DocumentBridge(
            get_title=lambda: title_state["value"],
            set_title=lambda v: title_state.__setitem__("value", v),
        )
        doc.title = "Hello"
        self.assertEqual(title_state["value"], "Hello")

        nav = []
        loc_state = {"href": ""}
        loc = LocationBridge(
            get_href=lambda: loc_state["href"],
            set_href=lambda v: loc_state.__setitem__("href", v),
            navigate=nav.append,
        )
        loc.href = "http://example.com"
        self.assertEqual(loc_state["href"], "http://example.com")
        self.assertEqual(nav, ["http://example.com"])


if __name__ == "__main__":
    unittest.main()
