import logging

from js import DocumentBridge, JSError, JSParseError, JSRuntime, LocationBridge, default_globals

from .css import compute_styles, parse_css_stylesheet
from .display_list import build_display_list
from .html_tokenizer import HTMLTokenizer
from .html_tree_builder import HTMLTreeBuilder
from .layout import LayoutEngine, build_layout_tree
from .resource_discovery import ResourceDiscovery
from .utils import html_unescape, normalize_ws

log = logging.getLogger("Vivienne.Engine")
js_log = logging.getLogger("Medrano")


class RenderMetadata:
    def __init__(self):
        self.title = ""
        self.inline_css = ""
        self.inline_scripts: list[str] = []
        self.stylesheets: list[str] = []


class Vivienne:
    def __init__(self, sink, settings: dict, resource_loader=None, js_console_sink=None):
        self.sink = sink
        self.settings = settings
        self.resource_loader = resource_loader
        self.js_console_sink = js_console_sink

    def _emit_js_console(self, message: str):
        text = str(message)
        js_log.info("js: %s", text)
        if self.js_console_sink:
            try:
                self.js_console_sink(text)
            except Exception:
                log.warning("js console sink failed", exc_info=True)

    def render(self, html: str, base_url: str | None = None) -> str | None:
        log.info("rendering html")
        document, meta, resources = self._parse_stream(html, base_url)

        self._run_scripts(meta, resources, base_url)

        css_texts = []
        if meta.inline_css:
            css_texts.append(meta.inline_css)

        if self.resource_loader and resources:
            for res in resources:
                if res.kind == "stylesheet":
                    try:
                        text, final_url = self.resource_loader(res.url)
                        css_texts.append(text)
                        log.info("loaded stylesheet: %s", final_url)
                    except Exception:
                        log.warning("stylesheet load failed: %s", res.url, exc_info=True)

        css_rules = []
        if self.settings.get("css_enabled", True):
            for css_text in css_texts:
                css_rules.extend(parse_css_stylesheet(css_text))

        compute_styles(document.root, css_rules, self.settings.get("css_enabled", True))

        layout_root = build_layout_tree(document.root)
        LayoutEngine().layout(layout_root)

        display_list = build_display_list(layout_root, base_url=base_url)

        from .rasterizer import rasterize

        rasterize(display_list, self.sink)

        title_text = normalize_ws(html_unescape(meta.title))
        return title_text if title_text else None

    def _run_scripts(self, meta: RenderMetadata, resources, base_url: str | None):
        if not self.settings.get("js_enabled", True):
            return

        title_state = {"value": normalize_ws(html_unescape(meta.title))}
        location_state = {"href": base_url or ""}

        document_bridge = DocumentBridge(
            get_title=lambda: title_state["value"],
            set_title=lambda new_title: title_state.__setitem__("value", normalize_ws(str(new_title))),
        )
        location_bridge = LocationBridge(
            get_href=lambda: location_state["href"],
            set_href=lambda href: location_state.__setitem__("href", str(href)),
            navigate=None,
        )

        runtime = JSRuntime(
            default_globals(
                document=document_bridge,
                location=location_bridge,
                console_logger=self._emit_js_console,
            )
        )

        script_sources: list[tuple[str, str]] = []
        inline_source_name = base_url or "<inline-script>"
        script_sources.extend((script, inline_source_name) for script in meta.inline_scripts)

        if self.resource_loader:
            for res in resources:
                if res.kind != "script":
                    continue
                try:
                    text, final_url = self.resource_loader(res.url)
                    script_sources.append((text, final_url))
                    log.info("loaded script: %s", final_url)
                except Exception:
                    log.warning("script load failed: %s", res.url, exc_info=True)

        for script, source_name in script_sources:
            if not script.strip():
                continue
            try:
                runtime.execute(script, source_name=source_name)
            except (JSParseError, JSError) as exc:
                self._emit_js_console(exc.format_for_console())
                js_log.warning("script execution failed: %s", exc)
            except Exception:
                js_log.warning("script execution failed", exc_info=True)

        meta.title = title_state["value"]

    def _parse_stream(self, html: str, base_url: str | None):
        tokenizer = HTMLTokenizer()
        tree = HTMLTreeBuilder(scripting_enabled=bool(self.settings.get("js_enabled", True)))
        discovery = ResourceDiscovery()
        meta = RenderMetadata()

        in_style = False
        in_title = False
        in_script = False
        in_noscript = False
        noscript_skip = False
        script_buffer: list[str] = []

        chunk_size = 4096
        for i in range(0, len(html), chunk_size):
            chunk = html[i : i + chunk_size]
            tokens = tokenizer.feed(chunk)
            for token in tokens:
                if token.get("type") == "start" and token.get("tag") == "style":
                    in_style = True
                elif token.get("type") == "end" and token.get("tag") == "style":
                    in_style = False
                elif in_style and token.get("type") == "text":
                    meta.inline_css += token.get("text", "")

                if token.get("type") == "start" and token.get("tag") == "script":
                    in_script = True
                    script_buffer = []
                elif token.get("type") == "end" and token.get("tag") == "script":
                    if in_script and script_buffer:
                        meta.inline_scripts.append("".join(script_buffer))
                    in_script = False
                    script_buffer = []
                elif in_script and token.get("type") == "text":
                    script_buffer.append(token.get("text", ""))

                if token.get("type") == "start" and token.get("tag") == "title":
                    in_title = True
                elif token.get("type") == "end" and token.get("tag") == "title":
                    in_title = False
                elif in_title and token.get("type") == "text":
                    meta.title += token.get("text", "")

                # Handle <noscript> according to scripting setting: when scripting
                # is enabled, the contents of <noscript> should not be exposed
                # to the DOM (i.e., skipped). When scripting is disabled, the
                # contents are processed normally.
                if token.get("type") == "start" and token.get("tag") == "noscript":
                    in_noscript = True
                    noscript_skip = bool(self.settings.get("js_enabled", True))
                elif token.get("type") == "end" and token.get("tag") == "noscript":
                    in_noscript = False
                    noscript_skip = False

                # If we're inside a <noscript> and scripting is enabled, skip
                # passing tokens to resource discovery and the tree builder.
                if not (in_noscript and noscript_skip):
                    discovery.on_token(token, base_url)
                    tree.process(token)

        for token in tokenizer.close():
            discovery.on_token(token, base_url)
            tree.process(token)

            if in_script and token.get("type") == "text":
                script_buffer.append(token.get("text", ""))

        if in_script and script_buffer:
            meta.inline_scripts.append("".join(script_buffer))

        meta.stylesheets = [r.url for r in discovery.resources if r.kind == "stylesheet"]
        return tree.document, meta, discovery.resources
