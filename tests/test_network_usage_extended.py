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

    def items(self):
        return self._values.items()

    def __iter__(self):
        return iter(self._values)


class DummyResponse:
    def __init__(self, data=b"", url="http://example.com/", headers=None, status=200):
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
        self.requests = []

    def open(self, req):
        self.requests.append(req)
        return self.response


class HeadThenGetOpener:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def open(self, req):
        self.requests.append(req)
        if req.get_method() == "HEAD":
            raise urllib.error.HTTPError(req.full_url, 405, "Method Not Allowed", None, None)
        return self.response


class NetworkUsageExtendedTests(unittest.TestCase):
    def test_invalid_proxy_mode_falls_back_to_system(self):
        engine = Charlie(proxy_mode="garbage")
        self.assertEqual(engine._proxy_mode, "system")

    def test_set_proxy_mode_no_rebuild_when_same_mode(self):
        engine = Charlie(proxy_mode="system")
        opener = engine._opener
        engine.set_proxy_mode("system")
        self.assertIs(engine._opener, opener)

    def test_fetch_text_uses_response_charset(self):
        headers = DummyHeaders(charset="latin-1")
        resp = DummyResponse(data="olá".encode("latin-1"), headers=headers)
        opener = DummyOpener(resp)
        with mock.patch.object(Charlie, "_build_opener", return_value=opener):
            engine = Charlie(proxy_mode="none")
            text, _ = engine.fetch_text("http://example.com/")
        self.assertEqual(text, "olá")

    def test_fetch_bytes_returns_binary(self):
        resp = DummyResponse(data=b"\x00\x01\x02")
        opener = DummyOpener(resp)
        with mock.patch.object(Charlie, "_build_opener", return_value=opener):
            engine = Charlie(proxy_mode="none")
            data = engine.fetch_bytes("http://example.com/a.bin")
        self.assertEqual(data, b"\x00\x01\x02")

    def test_fetch_metadata_head_then_get_fallback(self):
        headers = DummyHeaders(values={"Content-Type": "text/plain", "Content-Length": "3"})
        resp = DummyResponse(data=b"abc", headers=headers)
        opener = HeadThenGetOpener(resp)
        with mock.patch.object(Charlie, "_build_opener", return_value=opener):
            engine = Charlie(proxy_mode="none")
            info = engine.fetch_metadata("example.com")
        self.assertEqual(info["content_type"], "text/plain")
        self.assertEqual(info["content_length"], "3")
        self.assertEqual(opener.requests[0].get_method(), "HEAD")
        self.assertEqual(opener.requests[1].get_method(), "GET")


if __name__ == "__main__":
    unittest.main()
