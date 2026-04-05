import logging
import urllib.error
import urllib.request

from flags import resolve_bool_flag
from ua_gen import build_user_agent

log = logging.getLogger("Charlie")

DEFAULT_TIMEOUT_SECONDS = 15.0


class Charlie:
    def __init__(self, proxy_mode: str = "system", timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
        self._proxy_mode = None
        self._opener = None
        self._timeout_seconds = float(timeout_seconds)
        self.set_proxy_mode(proxy_mode)

    def set_proxy_mode(self, proxy_mode: str):
        mode = (proxy_mode or "").strip().lower()
        if mode not in ("system", "none"):
            mode = "system"
        if mode == self._proxy_mode and self._opener is not None:
            return
        self._proxy_mode = mode
        self._opener = self._build_opener()
        log.info("proxy mode set to %s", self._proxy_mode)

    def _build_opener(self):
        if self._proxy_mode == "none":
            handler = urllib.request.ProxyHandler({})
        else:
            handler = urllib.request.ProxyHandler()
        return urllib.request.build_opener(handler)

    def _normalize_url(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
            log.debug("normalized url to %s", url)
        return url

    def _user_agent(self) -> str:
        if resolve_bool_flag("charlie_use_generated_ua", default_value=False):
            return build_user_agent("0.3")
        return "tinybrowser/0.3 (hand-rolled engine)"

    def _request(self, url: str, method: str = "GET") -> urllib.request.Request:
        return urllib.request.Request(
            self._normalize_url(url),
            method=method,
            headers={"User-Agent": self._user_agent()},
        )

    def _open(self, req: urllib.request.Request):
        return self._opener.open(req, timeout=self._timeout_seconds)

    def _headers_to_dict(self, headers) -> dict[str, str]:
        if headers is None:
            return {}
        items = getattr(headers, "items", None)
        if callable(items):
            return {str(k): str(v) for k, v in items()}
        return {
            str(k): str(v)
            for k, v in headers
        }

    def _metadata_from_response(self, resp) -> dict:
        headers = resp.headers
        info = {
            "url": resp.geturl(),
            "status": getattr(resp, "status", None),
            "content_type": headers.get("Content-Type"),
            "content_length": headers.get("Content-Length"),
            "headers": self._headers_to_dict(headers),
        }
        return info

    def fetch_text(self, url: str):
        data, info = self.fetch_text_with_metadata(url)
        return data, info.get("url") or self._normalize_url(url)

    def fetch_text_with_metadata(self, url: str):
        log.info("fetching text url: %s", url)
        req = self._request(url, method="GET")
        with self._open(req) as resp:
            info = self._metadata_from_response(resp)
            charset = resp.headers.get_content_charset() or "utf-8"
            data = resp.read().decode(charset, errors="ignore")
            log.info("fetched %d chars from %s", len(data), info.get("url"))
            return data, info

    def fetch_bytes(self, url: str) -> bytes:
        log.info("fetching binary url: %s", url)
        req = self._request(url, method="GET")
        with self._open(req) as resp:
            data = resp.read()
            log.info("fetched %d bytes", len(data))
            return data

    def fetch_metadata(self, url: str):
        log.info("fetching metadata for url: %s", url)
        req = self._request(url, method="HEAD")

        try:
            with self._open(req) as resp:
                info = self._metadata_from_response(resp)
                log.info("metadata fetched: %s", info)
                return info

        except urllib.error.HTTPError as e:
            log.warning("HEAD failed (%s), retrying with GET", e)
            req = self._request(url, method="GET")
            with self._open(req) as resp:
                info = self._metadata_from_response(resp)
                log.info("metadata (GET fallback) fetched: %s", info)
                return info
