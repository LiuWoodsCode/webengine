import logging
from dataclasses import dataclass
from urllib.parse import urljoin

log = logging.getLogger("Vivienne.ResourceDiscovery")


@dataclass
class ResourceRequest:
    kind: str
    url: str
    tag: str


class ResourceDiscovery:
    def __init__(self):
        self.resources: list[ResourceRequest] = []

    def on_token(self, token: dict, base_url: str | None):
        if token.get("type") not in {"start", "self"}:
            return

        tag = token.get("tag")
        attrs = token.get("attrs", {})

        def add(kind: str, url: str | None):
            if not url:
                return
            full = urljoin(base_url or "", url)
            self.resources.append(ResourceRequest(kind=kind, url=full, tag=tag))

        if tag == "link":
            rel = (attrs.get("rel") or "").lower()
            href = attrs.get("href")
            if "stylesheet" in rel:
                add("stylesheet", href)
            return

        if tag == "script":
            add("script", attrs.get("src"))
            return

        if tag in {"img", "video", "audio", "source", "picture"}:
            add(tag, attrs.get("src"))
