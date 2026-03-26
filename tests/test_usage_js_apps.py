import unittest

from js import default_globals
from js.runtime import JSRuntime


class JSRealWorldUsageTests(unittest.TestCase):
    def test_calculator_like_state_updates_without_syntax_error(self):
        runtime = JSRuntime()
        script = (
            "var display = '0';"
            "display = '12';"
            "var lhs = 12;"
            "var rhs = 8;"
            "var op = '-';"
            "var result = lhs - rhs;"
            "display = '' + result;"
            "display;"
        )
        self.assertEqual(runtime.execute(script), "4.0")

    def test_math_object_usage_for_common_ui_calculation(self):
        runtime = JSRuntime({"Math": default_globals()["Math"]})
        result = runtime.execute("Math.max(2, 5) + Math.abs(-3);")
        self.assertEqual(result, 8.0)

    
    
    
    def test_real_world_function_declaration_calculator_helper(self):
        runtime = JSRuntime()
        self.assertEqual(runtime.execute("function add(a,b){ return a+b; } add(1,2);"), 3)

    
    
    def test_real_world_ternary_expression_for_button_state(self):
        runtime = JSRuntime()
        self.assertEqual(runtime.execute("var enabled = 1 > 0 ? true : false; enabled;"), True)


if __name__ == "__main__":
    unittest.main()
