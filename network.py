import logging
import urllib.request

from flags import resolve_bool_flag
from ua_gen import build_user_agent

log = logging.getLogger("Charlie")


class Charlie:
    def __init__(self, proxy_mode: str = "system"):
        self._proxy_mode = None
        self._opener = None
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

    def fetch_text(self, url: str):
        log.info("fetching text url: %s", url)
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
            log.debug("normalized url to %s", url)

        ua = build_user_agent("0.3") if resolve_bool_flag("charlie_use_generated_ua", default_value=False) else "tinybrowser/0.3 (hand-rolled engine)"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": ua},
        )
        with self._opener.open(req) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            data = resp.read().decode(charset, errors="ignore")
            log.info("fetched %d chars from %s", len(data), resp.geturl())
            return data, resp.geturl()

    def fetch_bytes(self, url: str) -> bytes:
        log.info("fetching binary url: %s", url)
        ua = build_user_agent("0.3") if resolve_bool_flag("charlie_use_generated_ua", default_value=False) else "tinybrowser/0.3 (hand-rolled engine)"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": ua},
        )
        with self._opener.open(req) as resp:
            data = resp.read()
            log.info("fetched %d bytes", len(data))
            return data

    #
    # NEW FUNCTION: Fetch metadata without downloading the whole file
    #
    def fetch_metadata(self, url: str):
        log.info("fetching metadata for url: %s", url)

        if not url.startswith(("http://", "https://")):
            url = "http://" + url
            log.debug("normalized url to %s", url)

        ua = build_user_agent("0.3") if resolve_bool_flag("charlie_use_generated_ua", default_value=False) else "tinybrowser/0.3 (hand-rolled engine)"
        req = urllib.request.Request(
            url,
            method="HEAD",  # HEAD request = headers only
            headers={"User-Agent": ua},
        )

        try:
            with self._opener.open(req) as resp:
                headers = resp.headers

                info = {
                    "url": resp.geturl(),
                    "status": getattr(resp, "status", None),
                    "content_type": headers.get("Content-Type"),
                    "content_length": headers.get("Content-Length"),
                    "headers": dict(headers),
                }

                log.info("metadata fetched: %s", info)
                return info

        except urllib.error.HTTPError as e:
            # fallback: some servers reject HEAD; retry GET with no body read
            log.warning("HEAD failed (%s), retrying with GET", e)

            ua = build_user_agent("0.3") if resolve_bool_flag("charlie_use_generated_ua", default_value=False) else "tinybrowser/0.3 (hand-rolled engine)"
            req = urllib.request.Request(
                url,
                method="GET",
                headers={"User-Agent": ua},
            )

            with self._opener.open(req) as resp:
                headers = resp.headers
                info = {
                    "url": resp.geturl(),
                    "status": getattr(resp, "status", None),
                    "content_type": headers.get("Content-Type"),
                    "content_length": headers.get("Content-Length"),
                    "headers": dict(headers),
                }
                log.info("metadata (GET fallback) fetched: %s", info)
                return info