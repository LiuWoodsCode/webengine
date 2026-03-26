import logging
from html.parser import HTMLParser

log = logging.getLogger("Vivienne.HTML.Tokenizer")


class _TokenSink(HTMLParser):
    def __init__(self, out):
        super().__init__(convert_charrefs=True)
        self._out = out
        self._pending_text = []

    def _flush_text(self):
        if not self._pending_text:
            return
        self._out.append({
            "type": "text",
            "text": "".join(self._pending_text),
        })
        self._pending_text = []

    def _attrs_dict(self, attrs):
        normalized = {}
        for name, value in attrs:
            normalized[name] = "" if value is None else value
        return normalized

    # ---------- TAGS ----------

    def handle_starttag(self, tag, attrs):
        self._flush_text()
        self._out.append({
            "type": "start",
            "tag": tag,
            "attrs": self._attrs_dict(attrs),
        })

    def handle_startendtag(self, tag, attrs):
        self._flush_text()
        self._out.append({
            "type": "self",
            "tag": tag,
            "attrs": self._attrs_dict(attrs),
        })

    def handle_endtag(self, tag):
        self._flush_text()
        self._out.append({
            "type": "end",
            "tag": tag,
        })

    # ---------- TEXT ----------

    def handle_data(self, data):
        if data:
            self._pending_text.append(data)

    def handle_entityref(self, name):
        self._pending_text.append(f"&{name};")

    def handle_charref(self, name):
        self._pending_text.append(f"&#{name};")

    # ---------- IGNORED ----------

    def handle_comment(self, _):
        pass

    def handle_decl(self, decl):
        self._flush_text()
        raw = (decl or "").strip()
        if not raw:
            return
        parts = raw.split(None, 1)
        if parts[0].lower() != "doctype":
            return
        name = parts[1].strip() if len(parts) > 1 else ""
        self._out.append({
            "type": "doctype",
            "name": name,
        })

    def handle_pi(self, _):
        pass

    def flush(self):
        self._flush_text()


class HTMLTokenizer:
    def __init__(self):
        self._tokens = []
        self._parser = _TokenSink(self._tokens)

    def feed(self, data: str):
        if not data:
            return []

        start = len(self._tokens)
        self._parser.feed(data)
        return self._tokens[start:]

    def close(self):
        start = len(self._tokens)
        self._parser.close()
        self._parser.flush()
        return self._tokens[start:]
