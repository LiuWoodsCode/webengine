import unittest

from js.builtins import DocumentBridge, LocationBridge, default_globals
from js.runtime import JSError, JSObject, JSRuntime


class JSRuntimeTests(unittest.TestCase):
    def test_execute_and_assignment(self):
        runtime = JSRuntime()
        result = runtime.execute("var x = 1 + 2; x;")
        self.assertEqual(result, 3.0)

    def test_transpile_emits_python_runtime_calls(self):
        runtime = JSRuntime()
        python_source = runtime.transpile("var x = 1 + 2; x;")
        self.assertIn("def __js_program", python_source)
        self.assertIn("__scope.declare('x', __result, is_const=False)", python_source)
        self.assertIn("__rt._binary('+', 1, 2)", python_source)

    def test_compile_cache_reuses_compiled_program(self):
        runtime = JSRuntime()
        compiled_one = runtime.compile("var x = 1; x;")
        compiled_two = runtime.compile("var x = 1; x;")
        self.assertIs(compiled_one, compiled_two)

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

    def test_compiled_functions_capture_scope_like_closures(self):
        runtime = JSRuntime()
        result = runtime.execute("var x = 5; var f = (y) => x + y; x = 7; f(3);")
        self.assertEqual(result, 10.0)

    def test_arrow_function_can_be_passed_as_call_argument(self):
        runtime = JSRuntime()
        runtime.global_scope.declare("invoke", lambda fn, value: fn.call(runtime, [value]), is_const=True)
        result = runtime.execute("invoke((value) => value + 1, 2);")
        self.assertEqual(result, 3.0)

    def test_arrow_function_in_object_literal_value(self):
        runtime = JSRuntime()
        result = runtime.execute("var handlers = {click: () => 7}; handlers.click();")
        self.assertEqual(result, 7)


if __name__ == "__main__":
    unittest.main()
