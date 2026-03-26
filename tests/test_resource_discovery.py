import unittest

from renderer.resource_discovery import ResourceDiscovery


class ResourceDiscoveryTests(unittest.TestCase):
    def test_discovers_resources(self):
        discovery = ResourceDiscovery()
        base = "http://example.com/dir/"

        discovery.on_token(
            {"type": "start", "tag": "link", "attrs": {"rel": "stylesheet", "href": "style.css"}},
            base,
        )
        discovery.on_token(
            {"type": "start", "tag": "script", "attrs": {"src": "app.js"}},
            base,
        )
        discovery.on_token(
            {"type": "self", "tag": "img", "attrs": {"src": "img.png"}},
            base,
        )

        urls = [res.url for res in discovery.resources]
        self.assertIn("http://example.com/dir/style.css", urls)
        self.assertIn("http://example.com/dir/app.js", urls)
        self.assertIn("http://example.com/dir/img.png", urls)


if __name__ == "__main__":
    unittest.main()
