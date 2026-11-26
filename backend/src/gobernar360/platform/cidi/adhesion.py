"""The request to adhere to CiDi, for a municipality to print, sign and file with the Province.

It is the Province's own form (Documento III of docs/cidi/source), with what the platform
knows filled in. Nothing is sent to anybody from here.
"""

import html
import re
from importlib import resources

from gobernar360.core.config import get_settings

TO_FILL_IN = "(completar)"
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_STYLE = (
    "body{font-family:Arial,Helvetica,sans-serif;line-height:1.5;margin:2cm auto;max-width:17cm}"
    "h1{font-size:1.3rem}h2{font-size:1.05rem;margin-top:1.5rem}ul{list-style:none;padding:0}"
    "li{margin:.4rem 0}"
)


def request_text(municipality: str, publication_url: str) -> str:
    """The form in Markdown."""
    source = resources.files("gobernar360.platform.cidi") / "adhesion_request.md"
    return (
        source.read_text(encoding="utf-8")
        .replace("{{municipality}}", municipality)
        .replace("{{publication_url}}", publication_url)
    )


def _line(text: str) -> str:
    text = html.escape(text).replace("[x]", "☒").replace("[ ]", "☐")
    return _BOLD.sub(r"<strong>\1</strong>", text)


def _block(block: str) -> str:
    if block.startswith("## "):
        return f"<h2>{_line(block[3:])}</h2>"
    if block.startswith("# "):
        return f"<h1>{_line(block[2:])}</h1>"
    if block.startswith("- "):
        items = (f"<li>{_line(line[2:])}</li>" for line in block.splitlines())
        return f"<ul>{''.join(items)}</ul>"
    return f"<p>{_line(block)}</p>"


def request_page(municipality: str) -> str:
    """The form as a page to print."""
    text = request_text(municipality, get_settings().app_url)
    body = "".join(_block(block) for block in text.strip().split("\n\n"))
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        f"<title>gobernar360 – {html.escape(municipality)}</title><style>{_STYLE}</style></head>"
        f"<body>{body}</body></html>"
    )
