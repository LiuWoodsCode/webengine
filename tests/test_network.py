import unittest
from unittest import mock
import urllib.error

from network import Charlie


class DummyHeaders:
    def __init__(self, charset="utf-8", values=None):
        self._charset = charset
        self._values = values or {}

    def get_content_charset(self):
        return self._charset

    def get(self, key):
        return self._values.get(key)

    def __iter__(self):
        return iter(self._values.items())


class DummyResponse:
    def __init__(self, data=b"hello", url="http://example.com/", headers=None, status=200):
        self._data = data
        self._url = url
        self.headers = headers or DummyHeaders()
        self.status = status

    def read(self):
        return self._data

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyOpener:
    def __init__(self, response):
        self.response = response
        self.last_request = None

    def open(self, req, timeout=None):
        self.last_request = req
        method = req.get_method()
        if method == "HEAD":
            raise urllib.error.HTTPError(req.full_url, 405, "Method Not Allowed", None, None)
        return self.response


class NetworkTests(unittest.TestCase):
    def test_fetch_text_normalizes_url(self):
        response = DummyResponse(data=b"hi", url="http://example.com/")
        opener = DummyOpener(response)
        with mock.patch.object(Charlie, "_build_opener", return_value=opener):
            engine = Charlie(proxy_mode="none")
            text, url = engine.fetch_text("example.com")

        self.assertEqual(text, "hi")
        self.assertEqual(url, "http://example.com/")

    def test_fetch_metadata_head_fallback(self):
        headers = DummyHeaders(values={"Content-Type": "text/html", "Content-Length": "10"})
        response = DummyResponse(data=b"", url="http://example.com/", headers=headers, status=200)
        opener = DummyOpener(response)
        with mock.patch.object(Charlie, "_build_opener", return_value=opener):
            engine = Charlie(proxy_mode="system")
            info = engine.fetch_metadata("example.com")

        self.assertEqual(info["content_type"], "text/html")
        self.assertEqual(info["content_length"], "10")
        self.assertEqual(info["url"], "http://example.com/")


if __name__ == "__main__":
    unittest.main()
