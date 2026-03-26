import unittest

from renderer.resource_discovery import ResourceDiscovery


class ResourceDiscoveryExtendedTests(unittest.TestCase):
    def test_stylesheet_detection_when_rel_contains_multiple_tokens(self):
        d = ResourceDiscovery()
        d.on_token(
            {"type": "start", "tag": "link", "attrs": {"rel": "preload stylesheet", "href": "a.css"}},
            "http://example.com/",
        )
        self.assertEqual(len(d.resources), 1)
        self.assertEqual(d.resources[0].kind, "stylesheet")

    def test_script_without_src_is_ignored(self):
        d = ResourceDiscovery()
        d.on_token({"type": "start", "tag": "script", "attrs": {}}, "http://example.com/")
        self.assertEqual(len(d.resources), 0)

    def test_media_sources_discovered(self):
        d = ResourceDiscovery()
        base = "http://example.com/media/"
        for tag in ("img", "video", "audio", "source", "picture"):
            d.on_token({"type": "self", "tag": tag, "attrs": {"src": "x.bin"}}, base)
        self.assertEqual(len(d.resources), 5)
        self.assertTrue(all(r.url == "http://example.com/media/x.bin" for r in d.resources))

    def test_relative_url_normalization_parent_segments(self):
        d = ResourceDiscovery()
        d.on_token(
            {"type": "self", "tag": "img", "attrs": {"src": "../img/p.png"}},
            "http://example.com/a/b/c/",
        )
        self.assertEqual(d.resources[0].url, "http://example.com/a/b/img/p.png")


if __name__ == "__main__":
    unittest.main()
