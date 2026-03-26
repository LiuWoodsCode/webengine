# ui_builder.py

from PySide6.QtWidgets import (
    QWidget, QLabel, QFrame, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QPixmap, QIcon

from renderer import style_to_css, style_to_qss
from renderer.utils import parse_px_int
import urllib.parse
import logging

log = logging.getLogger("Crimew.UIBuilder")


class PageElementBuilder:
    """
    Shared HTML-like page construction layer.

    REQUIRES host class to already have:

        self.page_layout : QVBoxLayout
        self.scroll      : QScrollArea
        self.engine      : Charlie
        self.settings    : dict
        self.open_link() : callable
        self.current_url : str
    """

    # -------------------------
    # Core layout state
    # -------------------------

    def _reset_layout_stack(self):
        self._form_stack = []
        self._layout_stack = [{
            "layout": self.page_layout,
            "css": {},
            "line_widget": None,
            "line_layout": None,
            "float_context": None,
            "tag": "#root",
            "attrs": {},
        }]

    def add_hr(self):
        self._add_hr()

    def add_br(self):
        self._add_br()

    def add_text(self, text: str, base_style: dict | None=None, qss_extra: str=''):
        self._add_text(text, base_style=base_style, qss_extra=qss_extra)

    def begin_block(self, tag: str | None, attrs: dict | None=None, inline: bool=False, qss: str='', css: dict | None=None):
        self._begin_block(tag, attrs=attrs, inline=inline, qss=qss, css=css)

    def end_block(self, tag: str | None=None, payload: dict | None=None):
        resolved_tag = tag
        if payload and (not resolved_tag):
            resolved_tag = payload.get('tag')
        self._end_block(tag=resolved_tag)

    def add_link(self, href: str, text: str, qss: str='', css: dict | None=None):
        self._add_link(href, text, qss=qss, css=css)

    def add_image(self, src: str, alt: str, qss: str, width: int | None=None, height: int | None=None, css: dict | None=None):
        self._add_image(src, alt, qss, width=width, height=height, css=css)

    def add_input_text(self, value: str='', name: str='', qss: str='', size: str | None=None, maxlength: str | None=None, css: dict | None=None):
        self._add_input_text(value=value, name=name, qss=qss, size=size, maxlength=maxlength, css=css)

    def add_input_button(self, text: str='Button', name: str='', qss: str='', input_type: str='button', css: dict | None=None):
        self._add_input_button(text=text, name=name, qss=qss, input_type=input_type, css=css)

    def add_input_image_button(self, src: str='', alt: str='', name: str='', value: str='', qss: str='', width: int | None=None, height: int | None=None, css: dict | None=None):
        self._add_input_image_button(src=src, alt=alt, name=name, value=value, qss=qss, width=width, height=height, css=css)

    def add_input_hidden(self, name: str='', value: str=''):
        self._add_input_hidden(name=name, value=value)

    def _reset_layout_stack(self):
        self._form_stack = []
        self._layout_stack = [{'layout': self.page_layout, 'css': {}, 'line_widget': None, 'line_layout': None, 'float_context': None, 'tag': '#root', 'attrs': {}}]

    def _add_hr(self):
        log.debug('adding <hr>')
        self._end_inline_line()
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self._add_widget(line, inline=False, css={})

    def _add_br(self):
        log.debug('adding <br>')
        self._end_inline_line()
        spacer = QLabel('')
        spacer.setFixedHeight(6)
        self._add_widget(spacer, inline=False, css={})

    def _current_block(self) -> dict:
        if not getattr(self, '_layout_stack', None):
            self._reset_layout_stack()
        return self._layout_stack[-1]

    def _current_layout(self):
        return self._current_block()['layout']

    def _current_content_layout(self):
        block = self._current_block()
        float_context = block.get('float_context')
        if float_context is not None:
            return float_context['center_layout']
        return block['layout']

    def _clear_float_context(self):
        block = self._current_block()
        block['float_context'] = None

    def _ensure_float_context(self):
        block = self._current_block()
        existing = block.get('float_context')
        if existing is not None:
            return existing
        row_widget = QWidget()
        row_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        row_layout.setAlignment(Qt.AlignTop)
        left_widget = QWidget()
        left_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.setAlignment(Qt.AlignTop)
        center_widget = QWidget()
        center_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.setAlignment(Qt.AlignTop)
        right_widget = QWidget()
        right_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.setAlignment(Qt.AlignTop)
        row_layout.addWidget(left_widget, 0)
        row_layout.addWidget(center_widget, 1)
        row_layout.addWidget(right_widget, 0)
        block['layout'].addWidget(row_widget)
        context = {'row_widget': row_widget, 'left_layout': left_layout, 'center_layout': center_layout, 'right_layout': right_layout}
        block['float_context'] = context
        return context

    def _end_inline_line(self):
        block = self._current_block()
        if block.get('line_widget') is not None:
            block['line_widget'] = None
            block['line_layout'] = None

    def _ensure_inline_line(self) -> QHBoxLayout:
        block = self._current_block()
        line_layout = block.get('line_layout')
        if line_layout is not None:
            return line_layout
        line_widget = QWidget()
        line_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        line_layout = QHBoxLayout(line_widget)
        line_layout.setContentsMargins(0, 0, 0, 0)
        line_layout.setSpacing(0)
        text_align = str((block.get('css') or {}).get('text-align', '')).strip().lower()
        if text_align == 'right':
            line_layout.setAlignment(Qt.AlignRight)
        elif text_align == 'center':
            line_layout.setAlignment(Qt.AlignHCenter)
        else:
            line_layout.setAlignment(Qt.AlignLeft)
        self._current_content_layout().addWidget(line_widget)
        block['line_widget'] = line_widget
        block['line_layout'] = line_layout
        return line_layout

    def _add_widget(self, widget: QWidget, inline: bool, css: dict | None=None):
        style = dict(css or {})
        float_value = str(style.get('float', '')).strip().lower()
        clear_value = str(style.get('clear', '')).strip().lower()
        clear_requested = clear_value in {'left', 'right', 'both', 'all', 'inline-start', 'inline-end'}
        if clear_requested:
            self._end_inline_line()
            self._clear_float_context()
        if float_value in {'left', 'right', 'inline-start', 'inline-end'}:
            self._end_inline_line()
            float_context = self._ensure_float_context()
            if float_value in {'right', 'inline-end'}:
                float_context['right_layout'].addWidget(widget)
            else:
                float_context['left_layout'].addWidget(widget)
            return
        if inline:
            self._ensure_inline_line().addWidget(widget, 0, Qt.AlignLeft | Qt.AlignTop)
        else:
            self._end_inline_line()
            block = self._current_block()
            float_context = block.get('float_context')
            if float_context is not None:
                float_context['center_layout'].addWidget(widget)
            else:
                block['layout'].addWidget(widget)

    def _is_inline_display(self, css: dict | None, default_inline: bool=True) -> bool:
        if not css:
            return default_inline
        display = str(css.get('display', '')).strip().lower()
        if not display:
            return default_inline
        if display in ('block', 'flex', 'grid', 'table', 'list-item'):
            return False
        return True

    def _begin_block(self, tag: str | None, attrs: dict | None=None, inline: bool=False, qss: str='', css: dict | None=None):
        if not inline:
            self._end_inline_line()
        container = QFrame()
        container.setFrameShape(QFrame.NoFrame)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        css = dict(css or {})
        display = str(css.get('display', '')).strip().lower()
        flex_dir = str(css.get('flex-direction', 'row')).strip().lower()
        if display in ('flex', 'inline-flex') and flex_dir in ('column', 'column-reverse'):
            layout = QVBoxLayout(container)
        elif display in ('flex', 'inline-flex'):
            layout = QHBoxLayout(container)
        else:
            layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(0)
        if display in ('flex', 'inline-flex'):
            justify = str(css.get('justify-content', '')).strip().lower()
            if justify in ('flex-end', 'end', 'right'):
                layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            elif justify in ('center',):
                layout.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            elif justify in ('space-between', 'space-around', 'space-evenly'):
                layout.setSpacing(12)
            else:
                layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        css_width = parse_px_int(css.get('width'))
        css_height = parse_px_int(css.get('height'))
        if css_width:
            container.setFixedWidth(max(1, css_width))
        if css_height:
            container.setFixedHeight(max(1, css_height))
        if qss:
            container.setStyleSheet(qss)
        if css:
            container.setProperty('css', css)
            css_text = style_to_css(css)
            if css_text:
                container.setProperty('cssText', css_text)
        if tag:
            container.setProperty('tag', tag)
        attrs = dict(attrs or {})
        self._add_widget(container, inline=inline, css=css)
        self._layout_stack.append({'layout': layout, 'css': dict(css), 'line_widget': None, 'line_layout': None, 'float_context': None, 'tag': tag, 'attrs': attrs})
        if (tag or '').lower() == 'form':
            self._form_stack.append({'action': attrs.get('action', ''), 'method': str(attrs.get('method', 'get')).strip().lower() or 'get', 'entries': []})

    def _end_block(self, tag: str | None=None):
        if getattr(self, '_layout_stack', None) and len(self._layout_stack) > 1:
            self._end_inline_line()
            popped = self._layout_stack.pop()
            popped_tag = (tag or popped.get('tag') or '').lower()
            if popped_tag == 'form' and self._form_stack:
                self._form_stack.pop()

    def _current_form(self):
        if not getattr(self, '_form_stack', None):
            return None
        if not self._form_stack:
            return None
        return self._form_stack[-1]

    def _submit_form(self, form_ctx: dict, submit_name: str='', submit_value: str='', submit_extra: list[tuple[str, str]] | None=None):
        if not form_ctx:
            return
        base = self.current_url or self.address.text().strip()
        action = (form_ctx.get('action') or '').strip()
        target = urllib.parse.urljoin(base, action) if action else base
        if not target:
            return
        params: list[tuple[str, str]] = []
        for entry in form_ctx.get('entries', []):
            etype = entry.get('type')
            name = entry.get('name', '')
            if not name:
                continue
            if etype == 'hidden':
                params.append((name, entry.get('value', '')))
                continue
            if etype == 'text':
                widget = entry.get('widget')
                value = widget.text() if widget is not None else ''
                params.append((name, value))
        if submit_name:
            params.append((submit_name, submit_value))
        if submit_extra:
            params.extend(submit_extra)
        method = str(form_ctx.get('method') or 'get').lower()
        if method != 'get':
            log.warning("form method '%s' not supported; falling back to GET", method)
        parsed = urllib.parse.urlparse(target)
        existing = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query = urllib.parse.urlencode(existing + params, doseq=True)
        final_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))
        self.open_link(final_url)

    def _add_text(self, text: str, base_style: dict | None=None, qss_extra: str=''):
        if not text:
            return
        log.debug('adding text: %r', text)
        lbl = QLabel(text)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        style = dict(base_style or {})
        white_space = str(style.get('white-space', '')).strip().lower()
        lbl.setWordWrap(white_space in {'pre-wrap', 'break-spaces'})
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        qss = style_to_qss(style)
        css_text = style_to_css(style)
        if qss_extra:
            qss = (qss + ' ' + qss_extra).strip()
        if 'text-align' in style:
            align = style['text-align'].strip().lower()
            if align == 'center':
                lbl.setAlignment(Qt.AlignCenter)
            elif align == 'right':
                lbl.setAlignment(Qt.AlignRight)
            else:
                lbl.setAlignment(Qt.AlignLeft)
        if qss:
            lbl.setStyleSheet(qss)
        if style:
            lbl.setProperty('css', style)
        if css_text:
            lbl.setProperty('cssText', css_text)
        self._add_widget(lbl, inline=True, css=style)

    def _add_link(self, href: str, text: str, qss: str='', css: dict | None=None):
        log.debug('adding link: %s -> %s', text, href)
        lbl = QLabel(f'<a href="{href}">{text}</a>')
        lbl.setTextFormat(Qt.RichText)
        lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
        lbl.setOpenExternalLinks(False)
        lbl.setToolTip(str(href))
        lbl.linkActivated.connect(lambda u=href: self.open_link(u))
        lbl.setWordWrap(False)
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        if qss:
            lbl.setStyleSheet(qss)
        if css:
            lbl.setProperty('css', css)
            css_text = style_to_css(css)
            if css_text:
                lbl.setProperty('cssText', css_text)
        self._add_widget(lbl, inline=self._is_inline_display(css, default_inline=True), css=css)

    def _add_image(self, src: str, alt: str, qss: str, width: int | None=None, height: int | None=None, css: dict | None=None):
        if not self.settings['images_enabled']:
            log.warning('images disabled, skipping image')
            return
        if not src:
            if alt:
                self._add_text(f'[image: {alt}]')
            return
        img_url = src
        log.info('loading image: %s', img_url)
        try:
            self._set_status(f'Downloading image: {img_url}')
            raw = self.engine.fetch_bytes(img_url)
            pix = QPixmap()
            if not pix.loadFromData(QByteArray(raw)):
                raise ValueError('image decode failed')
            if width and height:
                pix = pix.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            elif width:
                pix = pix.scaledToWidth(width, Qt.SmoothTransformation)
            elif height:
                pix = pix.scaledToHeight(height, Qt.SmoothTransformation)
            else:
                target_w = max(300, self.scroll.viewport().width() - 40)
                if pix.width() > target_w:
                    pix = pix.scaledToWidth(target_w, Qt.SmoothTransformation)
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignLeft)
            lbl.setPixmap(pix)
            if alt:
                lbl.setToolTip(alt)
            if qss:
                lbl.setStyleSheet(qss)
            if css:
                lbl.setProperty('css', css)
                css_text = style_to_css(css)
                if css_text:
                    lbl.setProperty('cssText', css_text)
            inline_image = self._is_inline_display(css, default_inline=True)
            self._add_widget(lbl, inline=inline_image, css=css)
            self._set_status(f'Downloaded image: {img_url}')
        except Exception:
            log.error('image failed: %s', img_url, exc_info=True)
            fallback = f"{alt.strip()}" if alt.strip() else src
            self._add_text(f'[image failed: {fallback}]')
            self._set_status(f'Image failed: {img_url}', 5000)

    def _add_input_text(self, value: str='', name: str='', qss: str='', size: str | None=None, maxlength: str | None=None, css: dict | None=None):
        inp = QLineEdit()
        inp.setText(value or '')
        try:
            if maxlength and str(maxlength).strip().isdigit():
                inp.setMaxLength(int(str(maxlength).strip()))
        except Exception:
            pass
        css_width = parse_px_int((css or {}).get('width'))
        css_height = parse_px_int((css or {}).get('height'))
        width_chars = None
        if size and str(size).strip().isdigit():
            width_chars = int(str(size).strip())
        if css_width:
            inp.setFixedWidth(max(40, css_width))
        elif width_chars:
            inp.setFixedWidth(max(80, width_chars * 8 + 20))
        else:
            inp.setFixedWidth(220)
        if css_height:
            inp.setFixedHeight(max(18, css_height))
        if qss:
            inp.setStyleSheet(qss)
        if css:
            inp.setProperty('css', css)
            css_text = style_to_css(css)
            if css_text:
                inp.setProperty('cssText', css_text)
        if name:
            inp.setObjectName(name)
        form_ctx = self._current_form()
        if form_ctx:
            form_ctx['entries'].append({'type': 'text', 'name': name, 'widget': inp})
            inp.returnPressed.connect(lambda c=form_ctx: self._submit_form(c))
        self._add_widget(inp, inline=self._is_inline_display(css, default_inline=True), css=css)

    def _add_input_button(self, text: str='Button', name: str='', qss: str='', input_type: str='button', css: dict | None=None):
        log.debug('adding input button w text: %r', text)
        btn = QPushButton(text or 'Button')
        css_width = parse_px_int((css or {}).get('width'))
        css_height = parse_px_int((css or {}).get('height'))
        if css_width:
            btn.setFixedWidth(max(30, css_width))
        if css_height:
            btn.setFixedHeight(max(18, css_height))
        if qss:
            btn.setStyleSheet(qss)
        if css:
            btn.setProperty('css', css)
            css_text = style_to_css(css)
            if css_text:
                btn.setProperty('cssText', css_text)
        if name:
            btn.setObjectName(name)
        btn.setToolTip(f'{input_type} control')
        form_ctx = self._current_form()
        if form_ctx and input_type == 'submit':
            btn.clicked.connect(lambda _checked=False, c=form_ctx, n=name, t=text or '': self._submit_form(c, submit_name=n, submit_value=t))
        self._add_widget(btn, inline=self._is_inline_display(css, default_inline=True), css=css)

    def _add_input_hidden(self, name: str='', value: str=''):
        form_ctx = self._current_form()
        if not form_ctx:
            return
        form_ctx['entries'].append({'type': 'hidden', 'name': name, 'value': value})

    def _add_input_image_button(self, src: str='', alt: str='', name: str='', value: str='', qss: str='', width: int | None=None, height: int | None=None, css: dict | None=None):
        btn = QPushButton()
        btn.setFlat(True)
        btn.setCursor(Qt.PointingHandCursor)
        pix = QPixmap()
        loaded = False
        if src and self.settings.get('images_enabled', True):
            try:
                raw = self.engine.fetch_bytes(src)
                loaded = pix.loadFromData(QByteArray(raw))
            except Exception:
                loaded = False
        if loaded:
            if width and height:
                pix = pix.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            elif width:
                pix = pix.scaledToWidth(width, Qt.SmoothTransformation)
            elif height:
                pix = pix.scaledToHeight(height, Qt.SmoothTransformation)
            btn.setIcon(QIcon(pix))
            btn.setIconSize(pix.size())
            btn.setFixedSize(pix.size())
        else:
            btn.setText(alt or value or 'Image')
        css_width = parse_px_int((css or {}).get('width'))
        css_height = parse_px_int((css or {}).get('height'))
        if css_width and css_height:
            btn.setFixedSize(max(1, css_width), max(1, css_height))
        elif css_width:
            btn.setFixedWidth(max(1, css_width))
        elif css_height:
            btn.setFixedHeight(max(1, css_height))
        if qss:
            btn.setStyleSheet(qss)
        if css:
            btn.setProperty('css', css)
            css_text = style_to_css(css)
            if css_text:
                btn.setProperty('cssText', css_text)
        if name:
            btn.setObjectName(name)
        if alt:
            btn.setToolTip(alt)
        form_ctx = self._current_form()
        if form_ctx:
            btn.clicked.connect(lambda _checked=False, c=form_ctx, n=name, v=value: self._submit_form(c, submit_name=n, submit_value=v, submit_extra=[(f'{n}.x', '0'), (f'{n}.y', '0')] if n else None))
        self._add_widget(btn, inline=self._is_inline_display(css, default_inline=True), css=css)

