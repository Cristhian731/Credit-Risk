"""Render docs/USER_MANUAL.md as simple HTML (headings, paragraphs, images, bold and italic)."""
import re
from pathlib import Path

from markupsafe import Markup, escape

MANUAL_PATH = Path(__file__).resolve().parents[2] / "docs" / "USER_MANUAL.md"
_IMAGE = re.compile(r"!\[([^\]]*)\]\(img/user_manual/([\w.-]+)\)")
_LINK = re.compile(r"&lt;(https?://[^\s&]+)&gt;")


def _inline(text):
    text = str(escape(text))
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(.+?)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return _LINK.sub(r'<a href="\1">\1</a>', text)


def render_manual(static_url):
    """Return (title, html) of the manual; ``static_url(name)`` builds the URL of an image."""
    blocks = MANUAL_PATH.read_text(encoding="utf-8").split("\n\n")
    parts, title = [], "User Manual"
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        image = _IMAGE.fullmatch(block)
        if block.startswith("# "):
            title = block[2:].strip()
        elif block.startswith("## "):
            parts.append(f"<h2 class='h4 fw-bold mt-5 mb-3'>{_inline(block[3:])}</h2>")
        elif image:
            src = static_url(f"img/manual/{image.group(2)}")
            parts.append(f'<img class="img-fluid border rounded manual-figure" src="{src}" alt="{escape(image.group(1))}">')
        elif block.startswith("*") and block.endswith("*") and not block.startswith("**"):
            parts.append(f"<p class='small text-muted mb-4'>{_inline(block)}</p>")
        else:
            parts.append(f"<p>{_inline(block)}</p>")
    return title, Markup("\n".join(parts))
