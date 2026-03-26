import logging
from html.parser import HTMLParser

log = logging.getLogger("Vivienne.HTML.Tokenizer")


class _TokenSink(HTMLParser):
    def __init__(self, out):
        super().__init__(convert_charrefs=True)
        self._out = out

    # ---------- TAGS ----------

    def handle_starttag(self, tag, attrs):
        self._out.append({
            "type": "start",
            "tag": tag,
            "attrs": dict(attrs),
        })

    def handle_startendtag(self, tag, attrs):
        self._out.append({
            "type": "self",
            "tag": tag,
            "attrs": dict(attrs),
        })

    def handle_endtag(self, tag):
        self._out.append({
            "type": "end",
            "tag": tag,
        })

    # ---------- TEXT ----------

    def handle_data(self, data):
        if data:
            self._out.append({
                "type": "text",
                "text": data,
            })

    def handle_entityref(self, name):
        self._out.append({
            "type": "text",
            "text": f"&{name};",
        })

    def handle_charref(self, name):
        self._out.append({
            "type": "text",
            "text": f"&#{name};",
        })

    # ---------- IGNORED ----------

    def handle_comment(self, _):
        pass

    def handle_decl(self, _):
        pass

    def handle_pi(self, _):
        pass


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
        return self._tokens[start:]