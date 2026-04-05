import unittest

from js import default_globals
from js.parser import JSParseError, parse_js, tokenize_js
from js.runtime import JSError, JSRuntime


class ECMATokenizerCoverageTests(unittest.TestCase):
    def test_tokenize_numbers_strings_and_ops(self):
        tokens = tokenize_js("1 + 2; 'x'; true;")
        kinds = [t.kind for t in tokens]
        self.assertIn("number", kinds)
        self.assertIn("string", kinds)
        self.assertIn("op", kinds)

    def test_tokenize_comments_are_ignored(self):
        tokens = tokenize_js("1;//x\n2;/*y*/3;")
        numbers = [t.value for t in tokens if t.kind == "number"]
        self.assertEqual(numbers, ["1", "2", "3"])

    def test_unterminated_block_comment_raises(self):
        with self.assertRaises(JSParseError):
            tokenize_js("/*")

    def test_html_entities_preprocessed(self):
        tokens = tokenize_js("1 &lt; 2;")
        ops = [t.value for t in tokens if t.kind == "op"]
        self.assertIn("<", ops)

    def test_tokenize_keywords_identifiers_and_punctuation(self):
        tokens = tokenize_js("let alpha = true; const beta = null; { } ( )")
        keyword_values = [t.value for t in tokens if t.kind == "keyword"]
        ident_values = [t.value for t in tokens if t.kind == "identifier"]
        punct_values = [t.value for t in tokens if t.kind == "punct"]
        self.assertIn("let", keyword_values)
        self.assertIn("const", keyword_values)
        self.assertIn("alpha", ident_values)
        self.assertIn("beta", ident_values)
        self.assertIn("{", punct_values)
        self.assertIn("}", punct_values)

    def test_two_char_operators_tokenized(self):
        tokens = tokenize_js("a==b; a!=b; a<=b; a>=b; a&&b; a||b;")
        ops = [t.value for t in tokens if t.kind == "op"]
        for op in ("==", "!=", "<=", ">=", "&&", "||"):
            self.assertIn(op, ops)

    def test_unterminated_string_raises(self):
        with self.assertRaises(JSParseError):
            tokenize_js("'abc")

    def test_tokenize_bitwise_xor(self):
        tokens = tokenize_js("a ^ b;")
        ops = [t.value for t in tokens if t.kind == "op"]
        self.assertIn("^", ops)


class ECMAParserCoverageTests(unittest.TestCase):
    def test_parse_var_and_expression(self):
        program = parse_js("var x = 1; x + 2;")
        self.assertEqual(len(program.body), 2)

    def test_parse_member_and_call(self):
        program = parse_js("console.log(1);")
        self.assertGreaterEqual(len(program.body), 1)

    def test_parse_nested_parenthesized_expression(self):
        program = parse_js("(1 + (2 * 3));")
        self.assertEqual(len(program.body), 1)

    def test_parse_assignment_chain(self):
        program = parse_js("var a = 0; var b = 0; a = b = 3;")
        self.assertEqual(len(program.body), 3)

    def test_parse_unary_expression(self):
        program = parse_js("var x = -1; !x;")
        self.assertEqual(len(program.body), 2)

    
    
    def test_parse_function_declaration(self):
        parse_js("function add(a,b){ return a+b; }")

    
    
    def test_parse_ternary_operator(self):
        parse_js("var x = true ? 1 : 2;")

    
    
    def test_parse_array_literal(self):
        parse_js("var x = [1,2,3];")

    
    
    def test_parse_object_literal(self):
        parse_js("var x = {a:1};")

    
    
    def test_parse_if_statement(self):
        parse_js("if (true) { 1; }")

    
    
    def test_parse_for_statement(self):
        parse_js("for (var i=0; i<3; i=i+1) { i; }")

    
    
    def test_parse_arrow_function(self):
        parse_js("var f = (a) => a + 1;")

    def test_parse_arrow_function_in_call_arguments(self):
        parse_js("console.log(() => 1, (a) => a + 1);")

    def test_parse_arrow_function_in_array_literal(self):
        parse_js("var handlers = [() => 1, (value) => value + 1];")

    def test_parse_arrow_function_in_object_literal(self):
        parse_js("var handlers = {click: () => 1, keyup: (value) => value + 1};")

    
    
    def test_parse_template_literal(self):
        parse_js("var s = `hello`;")

    def test_parse_function_expression_iife(self):
        parse_js("(function(a){ return a + 1; })(2);")

    def test_parse_sequence_expression(self):
        parse_js("(1, 2, 3);")

    def test_parse_array_elision_and_trailing_comma(self):
        parse_js("var a = [1,,3,];")

    def test_parse_call_trailing_comma(self):
        parse_js("console.log(1, 2,);")


class ECMARuntimeCoverageTests(unittest.TestCase):
    def test_arithmetic_precedence(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("1 + 2 * 3;"), 7.0)

    def test_logical_short_circuit(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("0 || 5;"), 5.0)
        self.assertEqual(rt.execute("1 && 5;"), 5.0)

    def test_var_let_const_assignment_rules(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("let x = 1; x = 2; x;"), 2.0)
        with self.assertRaises(JSError):
            rt.execute("const y = 1; y = 2;")

    def test_member_assignment_and_read(self):
        rt = JSRuntime({"obj": {"a": 1}})
        self.assertEqual(rt.execute("obj.a = 7; obj.a;"), 7.0)

    def test_string_concatenation(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("'Hello, ' + 'world';"), "Hello, world")

    def test_unary_plus_minus_not(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("-5;"), -5.0)
        self.assertEqual(rt.execute("+5;"), 5.0)
        self.assertEqual(rt.execute("!0;"), True)

    def test_comparison_operators(self):
        rt = JSRuntime()
        self.assertTrue(rt.execute("3 > 2;"))
        self.assertTrue(rt.execute("3 >= 3;"))
        self.assertTrue(rt.execute("2 < 3;"))
        self.assertTrue(rt.execute("2 <= 2;"))

    def test_reference_error_for_unknown_identifier(self):
        rt = JSRuntime()
        with self.assertRaises(JSError):
            rt.execute("unknown_var;")

    def test_builtin_math_in_real_usage_expression(self):
        rt = JSRuntime(default_globals())
        self.assertEqual(rt.execute("Math.max(1, 9) - Math.min(4, 7);"), 5.0)

    def test_builtin_console_log_available(self):
        logs = []
        rt = JSRuntime(default_globals(console_logger=logs.append))
        result = rt.execute("console.log('a', 2, true, null);")
        self.assertIsNone(result)
        self.assertEqual(logs, ["a 2 true null"])

    
    
    def test_abstract_equality_type_coercion(self):
        rt = JSRuntime()
        self.assertIs(rt.execute('"" == 0;'), True)

    
    
    def test_strict_equality(self):
        rt = JSRuntime()
        self.assertIs(rt.execute("1 === 1;"), True)

    
    
    def test_const_without_initializer_is_syntax_error(self):
        rt = JSRuntime()
        with self.assertRaises(JSParseError):
            rt.execute("const x;")

    
    
    def test_function_call_user_defined(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("function add(a,b){return a+b;} add(1,2);"), 3)

    
    
    def test_nullish_coalescing(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("null ?? 3;"), 3)

    
    
    def test_optional_chaining(self):
        rt = JSRuntime({"obj": None})
        self.assertIsNone(rt.execute("obj?.a;"))

    
    
    def test_loose_not_equal_coercion(self):
        rt = JSRuntime()
        self.assertIs(rt.execute("0 != false;"), False)

    
    
    def test_array_index_access(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("var a=[10,20]; a[1];"), 20)

    
    
    def test_json_object_literal_property_access(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("var obj={x:1}; obj.x;"), 1)

    
    
    def test_if_statement_runtime(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("var x=0; if (true) { x=1; } x;"), 1)

    
    
    def test_while_loop_runtime(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("var i=0; while(i<3){ i=i+1; } i;"), 3)

    
    
    def test_try_catch_runtime(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("try { throw 1; } catch(e) { e; }"), 1)

    def test_function_expression_iife_runtime(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("(function(a){ return a + 1; })(2);"), 3)

    def test_bitwise_and_runtime(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("6 & 3;"), 2)

    def test_bitwise_xor_runtime(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("6 ^ 3;"), 5)

    def test_sequence_expression_runtime(self):
        rt = JSRuntime()
        self.assertEqual(rt.execute("(1, 2, 3);"), 3)


if __name__ == "__main__":
    unittest.main()
