import unittest

from js.parser import JSParseError
from js.runtime import JSRuntime
from renderer.resource_discovery import ResourceDiscovery


class URLRFCConformanceTests(unittest.TestCase):
    def test_relative_url_resolution_matches_rfc3986_behavior(self):
        discovery = ResourceDiscovery()
        discovery.on_token(
            {"type": "self", "tag": "img", "attrs": {"src": "../img/logo.png"}},
            "http://example.com/a/b/c/",
        )
        self.assertEqual(discovery.resources[0].url, "http://example.com/a/b/img/logo.png")


class ECMAScriptConformanceGapTests(unittest.TestCase):
    def test_basic_arithmetic_works(self):
        runtime = JSRuntime()
        self.assertEqual(runtime.execute("1 + 2 * 3;"), 7.0)

    
    
    
    def test_abstract_equality_empty_string_equals_zero(self):
        runtime = JSRuntime()
        self.assertIs(runtime.execute('"" == 0;'), True)

    
    
    def test_strict_equality_operator_supported(self):
        runtime = JSRuntime()
        self.assertIs(runtime.execute("1 === 1;"), True)

    
    
    def test_const_requires_initializer(self):
        runtime = JSRuntime()
        with self.assertRaises(JSParseError):
            runtime.execute("const x;")


if __name__ == "__main__":
    unittest.main()
