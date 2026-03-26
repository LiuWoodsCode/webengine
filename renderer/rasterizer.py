import logging

from .css import style_to_qss

log = logging.getLogger("Vivienne.Rasterizer")


import html  # built‑in HTML entity decoder

def rasterize(display_list, sink):
    for cmd in display_list:
        if cmd.kind == "text":
            payload = cmd.payload

            # Decode HTML escaped characters like &lt; &amp; &#169; etc.
            text = html.unescape(payload["text"])

            sink.add_text(
                text,
                base_style=payload.get("style"),
                qss_extra=payload.get("qss_extra", ""),
            )
            continue

        if cmd.kind == "link":
            payload = cmd.payload
            style = payload.get("style") or {}
            qss = style_to_qss(style)
            sink.add_link(payload["href"], payload["text"], qss=qss, css=style)
            continue

        if cmd.kind == "image":
            payload = cmd.payload
            style = payload.get("style") or {}
            qss = style_to_qss(style)
            sink.add_image(
                payload.get("src", ""),
                payload.get("alt", ""),
                qss,
                width=payload.get("width"),
                height=payload.get("height"),
                css=style,
            )
            continue

        if cmd.kind == "input_text":
            payload = cmd.payload
            style = payload.get("style") or {}
            qss = style_to_qss(style)
            sink.add_input_text(
                value=payload.get("value", ""),
                name=payload.get("name", ""),
                qss=qss,
                size=payload.get("size"),
                maxlength=payload.get("maxlength"),
                css=style,
            )
            continue

        if cmd.kind == "input_button":
            payload = cmd.payload
            style = payload.get("style") or {}
            qss = style_to_qss(style)
            sink.add_input_button(
                text=payload.get("text", "Button"),
                name=payload.get("name", ""),
                qss=qss,
                input_type=payload.get("input_type", "button"),
                css=style,
            )
            continue

        if cmd.kind == "input_image_button":
            payload = cmd.payload
            style = payload.get("style") or {}
            qss = style_to_qss(style)
            sink.add_input_image_button(
                src=payload.get("src", ""),
                alt=payload.get("alt", ""),
                name=payload.get("name", ""),
                value=payload.get("value", ""),
                qss=qss,
                width=payload.get("width"),
                height=payload.get("height"),
                css=style,
            )
            continue

        if cmd.kind == "input_hidden":
            payload = cmd.payload
            sink.add_input_hidden(
                name=payload.get("name", ""),
                value=payload.get("value", ""),
            )
            continue

        if cmd.kind == "block_start":
            payload = cmd.payload
            style = payload.get("style") or {}
            qss = style_to_qss(style)
            sink.begin_block(
                payload.get("tag"),
                attrs=payload.get("attrs") or {},
                inline=bool(payload.get("inline", False)),
                qss=qss,
                css=style,
            )
            continue

        if cmd.kind == "block_end":
            sink.end_block(tag=(cmd.payload or {}).get("tag"))
            continue

        if cmd.kind == "br":
            sink.add_br()
            continue

        if cmd.kind == "hr":
            sink.add_hr()
            continue
