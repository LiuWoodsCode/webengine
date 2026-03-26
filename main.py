import sys
import urllib.parse
import logging
import json
import re
import platform
from pathlib import Path
import ua_gen
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QScrollArea,
    QFrame,
    QDialog,
    QDialogButtonBox,
    QCheckBox,
    QFormLayout,
    QMessageBox,
    QMenu,
    QSizePolicy,
    QComboBox,
    QTextEdit,
)
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QPixmap, QAction, QIcon

from renderer import Vivienne, style_to_css, style_to_qss
from renderer.utils import parse_px_int
from network import Charlie
import flags as flags_module

# ----------------------------
# version
# ----------------------------

PROJECT_VERSION = "1.0.0"
PROJECT_NAME = "Project Crimew"

# ----------------------------
# logging setup
# ----------------------------

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("Crimew.Frontend")

log.info("Project Crimew starting up")

# ----------------------------
# dialogs
# ----------------------------
from html.parser import HTMLParser

class TitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            # Capture the title text
            self.title = (self.title or "") + data.strip()

def extract_title(html: str) -> str | None:
    parser = TitleParser()
    parser.feed(html)
    return parser.title

class InternetOptionsDialog(QDialog):
    """IE-style: a separate window for settings (instead of about:config)."""

    def __init__(self, parent: QWidget, settings: dict):
        super().__init__(parent)
        self.setWindowTitle("Internet Options")
        self.setModal(True)
        self._settings = settings

        root = QVBoxLayout(self)

        blurb = QLabel("Settings for Project Crimew.")
        blurb.setWordWrap(True)
        root.addWidget(blurb)

        form = QFormLayout()
        root.addLayout(form)

        self.cb_css = QCheckBox("Enable CSS")
        self.cb_css.setChecked(bool(self._settings.get("css_enabled", True)))
        form.addRow(self.cb_css)

        self.cb_images = QCheckBox("Enable Images")
        self.cb_images.setChecked(bool(self._settings.get("images_enabled", True)))
        form.addRow(self.cb_images)

        self.cb_js = QCheckBox("Enable JavaScript")
        self.cb_js.setChecked(bool(self._settings.get("js_enabled", True)))
        form.addRow(self.cb_js)

        self.cb_proxy = QCheckBox("Use system proxy")
        self.cb_proxy.setChecked(self._settings.get("proxy_mode", "system") != "none")
        form.addRow(self.cb_proxy)

        hint = QLabel("Tip: after changing settings, reload the current page.")
        hint.setWordWrap(True)
        hint.setStyleSheet("opacity: 0.8;")
        root.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self.apply)
        root.addWidget(buttons)

    def apply(self):
        self._settings["css_enabled"] = self.cb_css.isChecked()
        self._settings["images_enabled"] = self.cb_images.isChecked()
        self._settings["js_enabled"] = self.cb_js.isChecked()
        self._settings["proxy_mode"] = "system" if self.cb_proxy.isChecked() else "none"
        log.warning("settings changed: %r", self._settings)
        # if parent supports saving, persist immediately (Apply button semantics)
        parent = self.parent()
        if hasattr(parent, "update_proxy_mode"):
            try:
                parent.update_proxy_mode()
            except Exception:
                log.error("update_proxy_mode failed", exc_info=True)
        if hasattr(parent, "save_settings"):
            try:
                parent.save_settings()
            except Exception:
                log.error("save_settings failed", exc_info=True)

    def accept(self):
        self.apply()
        super().accept()


class AboutDialog(QMessageBox):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setIcon(QMessageBox.Information)
        self.setText(
            "Project Crimew\n\n"
            "See README.md for project description and status."
        )


class JSConsoleWindow(QDialog):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Medrano Console")
        self.setModal(False)
        self.resize(760, 320)

        root = QVBoxLayout(self)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Medrano console output will appear here...")
        root.addWidget(self.output)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        clear_btn = buttons.addButton("Clear", QDialogButtonBox.ActionRole)
        clear_btn.clicked.connect(self.output.clear)
        buttons.rejected.connect(self.hide)
        root.addWidget(buttons)

    def append_line(self, text: str):
        self.output.append(str(text))


class FlagsDialog(QDialog):
    """Dialog to view and set experimental flags (about:flags style)."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Experiments / Flags")
        self.resize(720, 420)

        self._combos: dict[str, QComboBox] = {}

        root = QVBoxLayout(self)

        hint = QLabel("Warning: Experimental features ahead!\nBy enabling these features, you could lose browser data or compromise your security or privacy. Enabled features apply to all users of this browser. If you are an enterprise admin you should not be using these flags in production.")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # Scrollable container so the list scales and can be scrolled when small
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        self._scroll.setWidget(content)
        root.addWidget(self._scroll)

        flags_doc = flags_module.get_flags_cached()
        items = flags_doc.get("flags") if isinstance(flags_doc, dict) else flags_doc
        if not isinstance(items, list):
            items = []

        for f in items:
            if not isinstance(f, dict):
                continue
            fid = f.get("id")
            if not isinstance(fid, str) or not fid.strip():
                continue
            name = f.get("name") or fid
            desc = f.get("description") or ""

            # Row widget: label (expanding) + combo (constrained but can grow)
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(12)

            label = QLabel(f"<b>{name}</b><br><small>{desc}</small>")
            label.setWordWrap(True)
            label.setTextFormat(Qt.RichText)
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            combo = QComboBox()
            combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            combo.setMaximumWidth(420)  # allow growth but keep reasonable limit

            # Populate combo with choices (display name -> internal id)
            choices = f.get("choices")
            if isinstance(choices, list) and choices:
                for ch in choices:
                    if not isinstance(ch, dict):
                        continue
                    cid = ch.get("id")
                    cname = ch.get("name") or cid
                    if isinstance(cid, str) and cid.strip():
                        combo.addItem(str(cname), cid)
            else:
                combo.addItem("Default", "default")
                combo.addItem("Enabled", "enabled")
                combo.addItem("Disabled", "disabled")

            # Select current stored choice by internal id
            stored = flags_module.get_experiment_choice(fid)
            try:
                idx = combo.findData(stored)
                if idx < 0:
                    idx = combo.findText(stored)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            except Exception:
                pass

            self._combos[fid] = combo

            # Left column: stacked name + description to ensure proper wrapping
            left = QWidget()
            left_layout = QVBoxLayout(left)
            left_layout.setContentsMargins(0, 0, 0, 0)
            left_layout.setSpacing(4)

            name_lbl = QLabel(f"<b>{name}</b>")
            name_lbl.setTextFormat(Qt.RichText)
            name_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            desc_lbl.setStyleSheet("color: #CCCCCC;")

            left_layout.addWidget(name_lbl)
            left_layout.addWidget(desc_lbl)

            row_layout.addWidget(left, 3)
            row_layout.addWidget(combo, 1)
            content_layout.addWidget(row)

        content_layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        save_btn = buttons.addButton("Save", QDialogButtonBox.AcceptRole)
        save_btn.clicked.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _on_save(self):
        changed = 0
        for fid, combo in self._combos.items():
            # Read the internal id from the combo's userData (choice id)
            choice_data = combo.currentData()
            choice = str(choice_data) if choice_data is not None else str(combo.currentText() or "default")
            ok = flags_module.set_experiment_choice(fid, choice)
            if ok:
                changed += 1

        QMessageBox.information(self, "Flags", f"Saved {changed} flag(s).")
        self.accept()


# ----------------------------
# browser + renderer
# ----------------------------

from render_helpers import PageElementBuilder

from enum import Enum, auto

class PageLoadFailure(Enum):
    DNS_FAILURE = auto()
    CONNECTION_REFUSED = auto()
    CONNECTION_CLOSED_NO_DATA = auto()

    SSL_ERROR = auto()
    TIMEOUT = auto()
    INVALID_CERTIFICATE = auto()
    REDIRECT_LOOP = auto()
    MALFORMED_URL = auto()
    HTTP_403 = auto()
    HTTP_404 = auto()
    HTTP_500 = auto()
    NON_HTML_CONTENT = auto()
    UNKNOWN = auto()

import re
import socket
import ssl

class Browser(QMainWindow, PageElementBuilder):
    def __init__(self):
        super().__init__()
        log.info("initializing Browser UI")

        self.setWindowTitle("Project Crimew")
        self.resize(900, 650)
        self.current_url = None

        self.settings = {
            "css_enabled": True,
            "images_enabled": True,
            "js_enabled": True,
            "proxy_mode": "system",
        }

        # persistent settings file in the user's home directory
        self._settings_file = Path.home() / ".tinybrowser_settings.json"
        self.load_settings()

        self.engine = Charlie(proxy_mode=self.settings.get("proxy_mode", "system"))
        self._js_console_window = JSConsoleWindow(self)

        self.renderer = Vivienne(
            self,
            self.settings,
            resource_loader=self._fetch_resource_text,
            js_console_sink=self._append_js_console,
        )

        self.statusBar().showMessage("Ready")

        self._build_menubar()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        bar = QHBoxLayout()
        self.address = QLineEdit()
        go = QPushButton("Go")
        go.clicked.connect(self.load)
        self.address.returnPressed.connect(self.load)
        bar.addWidget(self.address)
        bar.addWidget(go)
        layout.addLayout(bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.page = QWidget()
        self.page_layout = QVBoxLayout(self.page)
        self.page_layout.setContentsMargins(0, 0, 0, 0)
        self.page_layout.setAlignment(Qt.AlignTop)
        self.page_layout.setSpacing(0)
        self._reset_layout_stack()

        self.scroll.setWidget(self.page)
        layout.addWidget(self.scroll)

        self.address.setText("about:")
        self.show_about_index()
        log.debug("browser initialized")

    def _build_menubar(self):
        mb = self.menuBar()

        file_menu: QMenu = mb.addMenu("&File")
        act_open = QAction("&Open Location...", self)
        act_open.setShortcut("Ctrl+L")
        act_open.triggered.connect(self.focus_address)
        file_menu.addAction(act_open)

        act_home = QAction("&Home (about:)", self)
        act_home.triggered.connect(lambda: self.open_link("about:"))
        file_menu.addAction(act_home)

        file_menu.addSeparator()

        act_exit = QAction("E&xit", self)
        act_exit.setShortcut("Alt+F4")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        tools_menu: QMenu = mb.addMenu("&Tools")
        act_opts = QAction("&Internet Options...", self)
        act_opts.triggered.connect(self.show_internet_options)
        tools_menu.addAction(act_opts)

        debug_menu: QMenu = mb.addMenu("&Debug")
        act_js_console = QAction("&Medrano Console", self)
        act_js_console.triggered.connect(self.show_js_console)

        navToGoog = QAction("&Navigate To Google", self)
        navToGoog.triggered.connect(lambda: self.open_link("google.com"))

        act_flags = QAction("&Flags...", self)
        act_flags.triggered.connect(self.show_flags_dialog)

        debug_menu.addAction(act_js_console)
        debug_menu.addAction(navToGoog)
        debug_menu.addAction(act_flags)

        help_menu: QMenu = mb.addMenu("&Help")
        act_about = QAction("&About", self)
        act_about.triggered.connect(self.show_about_dialog)
        help_menu.addAction(act_about)

        act_about = QAction("About &Qt", self)
        act_about.triggered.connect(self.show_about_qt_dialog)
        help_menu.addAction(act_about)

    def focus_address(self):
        self.address.setFocus(Qt.ShortcutFocusReason)
        self.address.selectAll()

    def show_internet_options(self):
        dlg = InternetOptionsDialog(self, self.settings)
        res = dlg.exec()
        # save settings if they were applied/changed
        self.save_settings()
        # if a page is loaded, reload to apply changes; otherwise keep current
        if self.current_url and not self.current_url.startswith("about:"):
            self.load()

    def update_proxy_mode(self):
        if not getattr(self, "engine", None):
            return
        mode = self.settings.get("proxy_mode", "system")
        self.engine.set_proxy_mode(mode)

    def show_about_dialog(self):
        AboutDialog(self).exec()

    def show_about_qt_dialog(self):
        app.aboutQt()

    def classify_failure(self, exc: Exception) -> PageLoadFailure:
        text = str(exc).lower()

        # ---------- by exception type ----------

        if isinstance(exc, ssl.SSLError):
            return PageLoadFailure.SSL_ERROR

        if isinstance(exc, socket.gaierror):
            return PageLoadFailure.DNS_FAILURE
        # ---------- by regex ----------

        if re.search(r"name or service not known|nodename nor servname|getaddrinfo failed", text):
            return PageLoadFailure.DNS_FAILURE

        if re.search(r"connection refused", text):
            return PageLoadFailure.CONNECTION_REFUSED

        if re.search(r"certificate verify failed|self[- ]signed", text):
            return PageLoadFailure.INVALID_CERTIFICATE

        if re.search(r"too many redirects", text):
            return PageLoadFailure.REDIRECT_LOOP

        if re.search(r"timed out", text):
            return PageLoadFailure.TIMEOUT

        return PageLoadFailure.UNKNOWN

    ERROR_PAGE_CONTENT = {

        PageLoadFailure.DNS_FAILURE: {
            "title": "Hmm. We’re having trouble finding that site.",
            "desc": "We can't connect to the DNS server for this domain.",
            "fix": [
                "Check the website address for typos",
                "Make sure you're connected to the internet",
                "Your DNS server may be offline"
            ]
        },

        PageLoadFailure.CONNECTION_REFUSED: {
            "title": "Connection was refused.",
            "desc": "The server actively rejected our attempt to connect.",
            "fix": [
                "The server may be down",
                "A firewall could be blocking access",
                "The site might not allow direct connections"
            ]
        },

        PageLoadFailure.CONNECTION_CLOSED_NO_DATA: {
            "title": "There's no response.",
            "desc": "The server closed the connection without responding.",
            "fix": [
                "Check if the site is blocked by a web filter"
                "Disable any newly installed antimalware software",
                "Restart your computer"
            ]
        },

        PageLoadFailure.INVALID_CERTIFICATE: {
            "title": "Secure connection failed.",
            "desc": "The site's SSL certificate cannot be trusted.",
            "fix": [
                "Your system clock may be incorrect",
                "The site may be using a self-signed certificate",
                "The certificate could be expired"
            ]
        },

        PageLoadFailure.TIMEOUT: {
            "title": "The connection timed out.",
            "desc": "The server took too long to respond.",
            "fix": [
                "The server may be overloaded",
                "Check your internet connection",
                "Try again later"
            ]
        },

        PageLoadFailure.REDIRECT_LOOP: {
            "title": "The page isn’t redirecting properly.",
            "desc": "The site is stuck in a redirect loop.",
            "fix": [
                "Clear site cookies",
                "The site may be misconfigured"
            ]
        },

        PageLoadFailure.UNKNOWN: {
            "title": "Something went wrong.",
            "desc": "An unexpected error occurred.",
            "fix": [
                "Try again later"
            ]
        }
    }

    def render_error_page(self, failure: PageLoadFailure, exc: Exception):
        info = self.ERROR_PAGE_CONTENT[failure]
        import traceback
        html = f"""
        <html>
        <body>
        <h1>{info['title']}</h1>
        <p>{info['desc']}</p>
        <br>
        <h3>You can try the following:</h3>
        <ul>
            {''.join(f"<li>{x}</li>" for x in info['fix'])}
        </ul>
        <br>
        <p>Error code: {str(failure)}</p>
        <h4>More details</h4>
        <p>Below is the Python error that was produced when this error occoured. This may help if you are trying to troubleshoot the browser.</p>
        <div>{"<br>".join(traceback.format_exception(type(exc), exc, exc.__traceback__))}</div>
        </body>
        </html>
        """
        self.renderer.render(html)

    def show_js_console(self):
        self._js_console_window.show()
        self._js_console_window.raise_()
        self._js_console_window.activateWindow()

    def show_flags_dialog(self):
        dlg = FlagsDialog(self)
        dlg.exec()

    def _append_js_console(self, message: str):
        self._js_console_window.append_line(message)

    def _set_status(self, message: str, timeout_ms: int = 0):
        self.statusBar().showMessage(str(message), timeout_ms)
        QApplication.processEvents()

    def load_settings(self):
        try:
            if getattr(self, "_settings_file", None) and self._settings_file.exists():
                with self._settings_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    # merge loaded values into defaults
                    self.settings.update({k: data.get(k, v) for k, v in self.settings.items()})
                    log.info("loaded settings from %s: %r", self._settings_file, self.settings)
        except Exception:
            log.error("failed to load settings", exc_info=True)

    def save_settings(self):
        try:
            if getattr(self, "_settings_file", None):
                with self._settings_file.open("w", encoding="utf-8") as f:
                    json.dump(self.settings, f, indent=2)
                log.info("saved settings to %s", self._settings_file)
        except Exception:
            log.error("failed to save settings", exc_info=True)

    def closeEvent(self, event):
        # persist settings on exit
        self.save_settings()
        super().closeEvent(event)

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
            self._set_status(f"Downloading metadata: {url}")
            meta = self.engine.fetch_metadata(url)

            content_type = (meta.get("content_type") or "").lower()

            # If it isn't HTML or XHTML, bail out early
            # TODO: Implement file download
            if not content_type.startswith(("text/html", "application/xhtml+xml")):
                log.error("This isn't HTML... content-type was: %s", content_type)
                self._add_text(f"Downloading files is current not supported.", base_style={"color": "red", "font-weight": "800"})
                self._set_status("Done", 3000)
                return

            # At this point we know it's HTML, safe to fetch full text
            self._set_status(f"Downloading page: {url}")
            html, final_url = self.engine.fetch_text(url)

            # Follow simple HTML-driven redirects used by JS-dependent pages
            # (e.g. window.location.replace(...) or meta refresh fallback).
            for _ in range(3):
                redirect_url = self._extract_html_redirect(html, final_url)
                if not redirect_url or redirect_url == final_url:
                    break
                log.info("following html redirect: %s -> %s", final_url, redirect_url)
                self._set_status(f"Downloading redirect target: {redirect_url}")
                html, final_url = self.engine.fetch_text(redirect_url)

            self.current_url = final_url
            self.address.setText(final_url)
            title = extract_title(html)
            self._set_status("Rendering page...")
            self.renderer.render(html, base_url=final_url)
            self._set_page_title(title, final_url)
            self._set_status("Done", 3000)
        except Exception as e:
            log.critical("fatal error loading %s", url, exc_info=True)
            failure = self.classify_failure(e)
            self.render_error_page(failure, e)
            self._set_status(f"Error: {e}", 5000)

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

    # -------- renderer --------
    def _set_page_title(self, title: str | None, fallback_url: str | None):
        if title and title.strip():
            self.setWindowTitle(f"{title.strip()} - Project Crimew")
            return
        if fallback_url:
            self.setWindowTitle(fallback_url)


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        win = Browser()
        win.show()
        sys.exit(app.exec())
    except Exception:
        log.critical("unhandled fatal exception", exc_info=True)
        raise
