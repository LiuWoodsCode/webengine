import re


def html_unescape(s: str) -> str:
    return (
        s.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
    )


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def px(v: str) -> str:
    v = v.strip().lower()
    if v.endswith("px"):
        return v
    if re.fullmatch(r"\d+", v):
        return v + "px"
    return v


def parse_px_int(v: str | None) -> int | None:
    if not v:
        return None
    v = v.strip().lower()
    if v.endswith("px"):
        v = v[:-2]
    if re.fullmatch(r"\d+", v):
        return int(v)
    return None
