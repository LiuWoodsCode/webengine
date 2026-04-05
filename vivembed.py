import platform

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QScrollArea,
    QFrame,
    QCheckBox,
    QFormLayout,
    QMessageBox,
    QMenu,
    QSizePolicy,
    QComboBox,
    QTextEdit,
)
from PySide6.QtCore import Qt, Signal, QByteArray
from PySide6.QtGui import QPixmap, QAction, QIcon

import logging
import urllib.parse
import re

from renderer import Vivienne, style_to_css, style_to_qss
from renderer.utils import parse_px_int
from network import Charlie
import flags as flags_module
log = logging.getLogger("Crimew.View")


from render_helpers import PageElementBuilder

class CrimewView(QWidget, PageElementBuilder):
    """
    Embeddable browser widget.
    Comparable to QWebEngineView / CEF browser instance.
    """

    # Signals exposed to host applications
    pageTitleChanged = Signal(str)
    urlChanged = Signal(str)
    loadStarted = Signal(str)
    loadFinished = Signal(str, bool)

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)

        self.settings = {
            "css_enabled": True,
            "images_enabled": True,
            "js_enabled": True,
            "proxy_mode": "system",
        }
        if settings:
            self.settings.update(settings)

        self.current_url = None

        # Network + renderer
        self.engine = Charlie(proxy_mode=self.settings["proxy_mode"])
        self.renderer = Vivienne(
            self,
            self.settings,
            resource_loader=self._fetch_resource_text,
        )

        # Scrollable render surface
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll)

        self.page = QWidget()
        self.page_layout = QVBoxLayout(self.page)
        self.page_layout.setAlignment(Qt.AlignTop)
        self.page_layout.setContentsMargins(0, 0, 0, 0)

        # we need to create this for navigation to work
        # even if it's not visable
        self.address = QLineEdit()
        go = QPushButton('Go')
        go.clicked.connect(self.load)
        self.address.returnPressed.connect(self.load)

        self.scroll.setWidget(self.page)

        self._reset_layout_stack()

    # -------------------------
    # Public API
    # -------------------------

    def load_url(self, url: str):
        """Navigate to URL (like QWebEngineView.load)."""
        url = url.strip()
        if not url:
            return

        self.loadStarted.emit(url)
        self.current_url = url
        self.urlChanged.emit(url)

        try:
            html, meta = self.engine.fetch_text_with_metadata(url)
            ct = (meta.get("content_type") or "").lower()

            if not ct.startswith(("text/html", "application/xhtml+xml")):
                raise RuntimeError(f"Unsupported content type: {ct}")

            final_url = meta.get("url") or url
            self._render_html(html, final_url)
            self.loadFinished.emit(final_url, True)

        except Exception as e:
            self.clear()
            self._add_text(f"Load error: {e}", base_style={"color": "red"})
            log.exception("load_url failed")
            self.loadFinished.emit(url, False)

    def load_html(self, html: str, base_url: str = ""):
        """Direct HTML injection (like setHtml)."""
        self.loadStarted.emit(base_url or "about:blank")
        self._render_html(html, base_url)
        self.loadFinished.emit(base_url or "about:blank", True)

    def reload(self):
        if self.current_url:
            self.load_url(self.current_url)

    def stop(self):
        # placeholder – future streaming/network cancel support
        pass

    def set_settings(self, settings: dict):
        self.settings.update(settings)
        self.engine.set_proxy_mode(self.settings.get("proxy_mode", "system"))

    def clear(self):
        while self.page_layout.count():
            item = self.page_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._reset_layout_stack()

    # -------------------------
    # Internal helpers
    # -------------------------
    def clear_page(self):
        log.debug("clearing page")
        while self.page_layout.count():
            item = self.page_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._reset_layout_stack()

    # -------- about: pages --------

    def show_about_index(self):
        log.info("showing about:index")
        self.clear_page()
        self.current_url = "about:"
        self.address.setText("about:")
        self.setWindowTitle("about: - Project Crimew")

        self._add_text("Project Crimew", base_style={"font-size": "26px", "font-weight": "800"})
        self._add_text("pages:", base_style={"font-weight": "700"})

        self._add_link("about:blank", "about:blank")
        self._add_link("about:version", "about:version")

        self._add_hr()
        self._add_text("tools → internet options opens settings in a window (ie-style).")

    def show_about_blank(self):
        log.info("showing about:blank")
        self.clear_page()
        self.current_url = "about:blank"
        self.address.setText("about:blank")
        self.setWindowTitle("about:blank - Project Crimew")
        
    def show_about_version(self):
        """Display system and browser version information."""
        log.info("showing about:version")
        self.clear_page()
        self.current_url = "about:version"
        self.address.setText("about:version")
        self.setWindowTitle("about:version - Project Crimew")

        self._add_text(PROJECT_NAME, base_style={"font-size": "26px", "font-weight": "800"})
        self._add_hr()

        # Python and system info
        python_version = platform.python_version()
        system_os = platform.system()
        system_release = platform.release()
        architecture = platform.architecture()[0]
        processor = platform.processor()

        # Project version info
        version_text = f"{PROJECT_VERSION} (Development build)"
        self._add_text(f"Version: {version_text}", base_style={"font-weight": "700"})
        self._add_br()

        # Python and system info
        python_version = platform.python_version()
        system_os = platform.system()
        system_release = platform.release()
        architecture = platform.architecture()[0]
        processor = platform.processor()

        self._add_text(f"Python: {python_version}", base_style={"font-family": "monospace"})
        self._add_br()
        self._add_text(f"Operating System: {system_os} {system_release} ({architecture})", base_style={"font-family": "monospace"})
        self._add_br()
        self._add_text(f"Processor: {processor}", base_style={"font-family": "monospace"})
        self._add_br()

        # Implementation details
        self._add_hr()
        self._add_text("Implementation", base_style={"font-weight": "700"})
        self._add_br()
        self._add_text(f"Renderer: Vivienne", base_style={"font-family": "monospace"})
        self._add_br()
        self._add_text(f"HTML+CSS Engine: Vivienne", base_style={"font-family": "monospace"})
        self._add_br()
        self._add_text(f"JavaScript Engine: Medrano", base_style={"font-family": "monospace"})
        self._add_br()

        # User agent
        self._add_hr()
        self._add_text("User Agent", base_style={"font-weight": "700"})
        self._add_br()
        user_agent = ua_gen.build_user_agent(PROJECT_VERSION)
        self._add_text(user_agent, base_style={"font-family": "monospace", "font-size": "11px", "white-space": "pre-wrap"})
        self._add_br()
        self._add_hr()
        self._add_link("about:", "back to about:")

    # -------- loading --------


    def is_html(text: str) -> bool:
        """
        Detects whether the given text is likely to be HTML.
        Returns True if HTML is detected, otherwise False.
        """

        # Trim whitespace
        stripped = text.strip()

        # Empty string is not HTML
        if not stripped:
            return False

        # Common HTML tags pattern
        html_tag_pattern = re.compile(
            r'<\/?\s*(html|head|body|div|span|p|a|script|style|h[1-6]|table|tr|td|ul|ol|li|br|meta|link)[^>]*>',
            re.IGNORECASE
        )

        # If it contains any HTML-like tags
        if html_tag_pattern.search(stripped):
            return True

        # Heuristic: starts with <!DOCTYPE html> or <html>
        if stripped.lower().startswith("<!doctype html") or stripped.lower().startswith("<html"):
            return True

        # Heuristic: looks like HTML overall (generic <tag> ... </tag>)
        generic_tag_pattern = re.compile(r'<[^>]+>', re.IGNORECASE)
        if generic_tag_pattern.search(stripped):
            return True

        return False
    
    
    def _render_html(self, html: str, base_url: str):
        self.clear()
        self.current_url = base_url
        self.urlChanged.emit(base_url)

        title = self._extract_title(html)
        if title:
            self.pageTitleChanged.emit(title)

        self.renderer.render(html, base_url=base_url)

    def _fetch_resource_text(self, url: str):
        return self.engine.fetch_text(url)

    def load(self):
        url = self.address.text().strip()
        log.info("loading url: %s", url)

        if not url:
            log.warning("empty url")
            self._set_status("No URL entered")
            return

        self._set_status(f"Loading: {url}")

        if url.startswith("about:"):
            if url == "about:":
                self.show_about_index()
                self._set_status("Done", 3000)
                return
            if url == "about:blank":
                self.show_about_blank()
                self._set_status("Done", 3000)
                return
            if url == "about:version":
                self.show_about_version()
                self._set_status("Done", 3000)
                return

            self.clear_page()
            self.current_url = url
            log.error("unknown about page: %s", url)
            self._add_text(f"unknown page: {url}", base_style={"color": "red", "font-weight": "800"})
            self._add_link("about:", "back to about:")
            self._set_status("Done", 3000)
            return

        self.clear_page()

        try:
            self._set_status(f"Downloading page: {url}")
            html, meta = self.engine.fetch_text_with_metadata(url)

            content_type = (meta.get("content_type") or "").lower()

            # If it isn't HTML or XHTML, bail out early
            # TODO: Implement file download
            if not content_type.startswith(("text/html", "application/xhtml+xml")):
                log.error("This isn't HTML... content-type was: %s", content_type)
                self._add_text(f"Downloading files is current not supported.", base_style={"color": "red", "font-weight": "800"})
                self._set_status("Done", 3000)
                return

            final_url = meta.get("url") or url

            # Follow simple HTML-driven redirects used by JS-dependent pages
            # (e.g. window.location.replace(...) or meta refresh fallback).
            for _ in range(3):
                redirect_url = self._extract_html_redirect(html, final_url)
                if not redirect_url or redirect_url == final_url:
                    break
                log.info("following html redirect: %s -> %s", final_url, redirect_url)
                self._set_status(f"Downloading redirect target: {redirect_url}")
                html, redirect_meta = self.engine.fetch_text_with_metadata(redirect_url)
                final_url = redirect_meta.get("url") or redirect_url

            self.current_url = final_url
            self.address.setText(final_url)
            self._set_status("Rendering page...")
            self.renderer.render(html, base_url=final_url)
            self._set_status("Done", 3000)
        except Exception as e:
            log.critical("fatal error loading %s", url, exc_info=True)
            self._add_text(f"error: {e}", base_style={"color": "red", "font-weight": "800"})
            self._set_status(f"Error: {e}", 5000)

    def _set_status(self, pos1, pos2="test"):
        pass
    
    def extract_title(pos1):
        pass

    def _extract_html_redirect(self, html: str, base_url: str) -> str | None:
        if not html:
            return None

        # Meta refresh: <meta http-equiv='refresh' content='0;URL=...'>
        for m in re.finditer(r"<meta\b[^>]*>", html, flags=re.I):
            tag = m.group(0)
            http_equiv = re.search(
                r"http-equiv\s*=\s*(['\"]?)refresh\1",
                tag,
                flags=re.I,
            )
            if not http_equiv:
                continue
            content = re.search(
                r"content\s*=\s*(['\"])(.*?)\1",
                tag,
                flags=re.I | re.S,
            )
            if not content:
                continue
            content_value = content.group(2)
            u = re.search(r"url\s*=\s*([^;]+)", content_value, flags=re.I)
            if not u:
                continue
            target = u.group(1).strip().strip("'\"")
            if target:
                return urllib.parse.urljoin(base_url, target)

        return None

    def open_link(self, url: str):
        log.info("opening link: %s", url)
        self.address.setText(url)
        self.load()

    def _fetch_resource_text(self, url: str):
        self._set_status(f"Downloading resource: {url}")
        text, final_url = self.engine.fetch_text(url)
        self._set_status(f"Downloaded resource: {final_url}")
        return text, final_url

    def _extract_title(self, html: str) -> str | None:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        return m.group(1).strip() if m else None

    # --- layout stack copied verbatim ---
    # Reduce nothing here; renderer relies on it.

    def _reset_layout_stack(self):
        self._form_stack = []
        self._layout_stack = [
            {
                "layout": self.page_layout,
                "css": {},
                "line_widget": None,
                "line_layout": None,
                "float_context": None,
                "tag": "#root",
                "attrs": {},
            }
        ]