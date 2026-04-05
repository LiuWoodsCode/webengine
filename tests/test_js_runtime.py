import unittest

from js.builtins import DocumentBridge, LocationBridge, default_globals
from js import JSParseError
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

    def test_runtime_error_includes_stack_and_source_context(self):
        runtime = JSRuntime()
        source = (
            "function throwErrorNoHandle() {\n"
            "  notDefinedFunction();\n"
            "}\n"
            "throwErrorNoHandle();\n"
        )

        with self.assertRaises(JSError) as ctx:
            runtime.execute(source, source_name="http://localhost:8000/inspection/javascript.html")

        formatted = ctx.exception.format_for_console()
        self.assertIn("Uncaught ReferenceError: notDefinedFunction is not defined", formatted)
        self.assertIn(
            "throwErrorNoHandle http://localhost:8000/inspection/javascript.html:2",
            formatted,
        )
        self.assertIn("<global> http://localhost:8000/inspection/javascript.html:4", formatted)
        self.assertIn("Source context:", formatted)
        self.assertIn("> 2 |   notDefinedFunction();", formatted)
        self.assertIn("^", formatted)

    def test_syntax_error_includes_source_context(self):
        runtime = JSRuntime()
        source = (
            "function broken() {\n"
            "  console.log((value) => 1 + ;\n"
            "}\n"
        )

        with self.assertRaises(JSParseError) as ctx:
            runtime.execute(source, source_name="http://localhost:8000/inspection/javascript.html")

        formatted = ctx.exception.format_for_console()
        self.assertIn("Uncaught SyntaxError: Unexpected token punct:;", formatted)
        self.assertIn("<parse> http://localhost:8000/inspection/javascript.html:2", formatted)
        self.assertIn("> 2 |   console.log((value) => 1 + ;", formatted)
        self.assertIn("^", formatted)


if __name__ == "__main__":
    unittest.main()
