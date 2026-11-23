"""Email texts: the defaults and each municipality's own version of them.

A template is a plain-text subject and an HTML body, both with `{{placeholders}}`. The
defaults live in the backend locale file; a municipality's administrators can replace
any of them in Configuración. What they save is sanitised to a small set of formatting
tags, may only use the placeholders of that kind of email, and must keep the ones the
email cannot work without (an invitation without its link is useless).

Values filled into the HTML are escaped, except `Html` ones, which the code built.
Every email also carries a plain-text version derived from its HTML.
"""

import html as html_lib
import re
import uuid
from dataclasses import dataclass
from html.parser import HTMLParser

import nh3
from sqlalchemy import select
from sqlalchemy.orm import Session

from gobernar360.core.errors import ApiError, not_found
from gobernar360.platform.models import EmailTemplate
from gobernar360.platform.notification_kinds import all_kinds
from gobernar360.platform.outbox import enqueue
from gobernar360.platform.texts import PLACEHOLDER, raw

INVITATION = "invitation"
MEMBERSHIP_ADDED = "membership_added"
PASSWORD_RESET = "password_reset"

ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "a",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "blockquote",
    "hr",
    "code",
}
MAX_HTML_LENGTH = 50_000


@dataclass(frozen=True)
class Spec:
    """What one kind of email may and must contain."""

    key: str
    variables: tuple[str, ...]
    required: tuple[str, ...]
    # True for notification kinds, whose `items` is the list of events.
    notification: bool = False


_ACCOUNT_SPECS = (
    Spec(INVITATION, ("name", "inviter", "municipality", "link", "expires"), ("link",)),
    Spec(MEMBERSHIP_ADDED, ("name", "inviter", "municipality", "link"), ()),
    Spec(PASSWORD_RESET, ("name", "link", "expires"), ("link",)),
)
_NOTIFICATION_VARIABLES = ("municipality", "month", "items", "account_link")


def specs() -> list[Spec]:
    """Every kind of email a municipality can customise."""
    notifications = [
        Spec(kind, _NOTIFICATION_VARIABLES, ("items",), notification=True) for kind in all_kinds()
    ]
    return [*_ACCOUNT_SPECS, *notifications]


def get_spec(key: str) -> Spec:
    spec = next((spec for spec in specs() if spec.key == key), None)
    if spec is None:
        raise not_found("Unknown kind of email.")
    return spec


class Html(str):
    """HTML built by the code, inserted into a template without escaping."""


def placeholders(template: str) -> set[str]:
    return {match.group(1) for match in PLACEHOLDER.finditer(template)}


def sanitize(html: str) -> str:
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes={"a": {"href", "title"}},
        url_schemes={"http", "https", "mailto"},
        link_rel=None,
    )


def _template_error(code: str, message: str, field: str, names: set[str]) -> ApiError:
    return ApiError(
        422, code, message, details=[{"field": field, "message": ", ".join(sorted(names))}]
    )


def validate(spec: Spec, subject: str, html: str) -> tuple[str, str]:
    """The subject and sanitised HTML to store, or an error naming the wrong placeholders."""
    subject = " ".join(subject.split())
    if not subject or len(subject) > 300:
        raise ApiError(422, "validation_error", "The subject must have 1 to 300 characters.")
    if len(html) > MAX_HTML_LENGTH:
        raise ApiError(422, "validation_error", "The text is too long.")
    clean = sanitize(html)
    allowed = set(spec.variables)
    for field, value in (("subject", subject), ("html", clean)):
        unknown = placeholders(value) - allowed
        if unknown:
            raise _template_error(
                "template_unknown_variable", "The text uses unknown variables.", field, unknown
            )
    # `items` is a list: it cannot go in a one-line subject.
    if "items" in placeholders(subject):
        raise _template_error(
            "template_unknown_variable", "The list cannot go in the subject.", "subject", {"items"}
        )
    missing = set(spec.required) - placeholders(clean)
    if missing:
        raise _template_error(
            "template_missing_variable", "The text lacks required variables.", "html", missing
        )
    return subject, clean


@dataclass(frozen=True)
class Template:
    key: str
    subject: str
    html: str
    customized: bool


def default(key: str) -> Template:
    base = f"email.templates.{key}"
    return Template(key, raw(base + ".subject"), raw(base + ".html"), False)


def load(db: Session, municipality_id: uuid.UUID | None, key: str) -> Template:
    """The municipality's version of an email, or the default one."""
    if municipality_id is not None:
        row = db.scalar(
            select(EmailTemplate).where(
                EmailTemplate.municipality_id == municipality_id, EmailTemplate.key == key
            )
        )
        if row is not None:
            return Template(key, row.subject, row.html, True)
    return default(key)


def fill(template: str, params: dict[str, object], escape: bool) -> str:
    """Replace placeholders; a placeholder without a value is left empty."""

    def value(match: re.Match[str]) -> str:
        raw = params.get(match.group(1), "")
        if not escape or isinstance(raw, Html):
            return str(raw)
        return html_lib.escape(str(raw), quote=True)

    return PLACEHOLDER.sub(value, template)


def document(body: str) -> str:
    """A complete HTML email around a body, with styles that mail clients accept."""
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"></head>'
        '<body style="margin:0;padding:24px;background:#f4f5f7">'
        '<div style="max-width:600px;margin:0 auto;padding:24px;background:#ffffff;'
        "border-radius:8px;font-family:Arial,Helvetica,sans-serif;font-size:15px;"
        f'line-height:1.5;color:#1f2328">{body}</div></body></html>'
    )


class _TextConverter(HTMLParser):
    BLOCKS = {"p", "h1", "h2", "h3", "blockquote", "ul", "ol", "div"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[tuple[str | None, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.BLOCKS:
            self.parts.append("\n\n")
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n• ")
        elif tag == "hr":
            self.parts.append("\n\n----\n\n")
        elif tag == "a":
            self.links.append((dict(attrs).get("href"), len(self.parts)))

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BLOCKS:
            self.parts.append("\n\n")
        elif tag == "a" and self.links:
            href, start = self.links.pop()
            label = "".join(self.parts[start:]).strip()
            if href and href != label:
                self.parts.append(f" ({href})" if label else href)

    def handle_data(self, data: str) -> None:
        self.parts.append(re.sub(r"\s+", " ", data))


def to_text(html: str) -> str:
    """The plain-text version of an email's HTML, links written out."""
    converter = _TextConverter()
    converter.feed(html)
    converter.close()
    lines = [line.strip() for line in "".join(converter.parts).split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


@dataclass(frozen=True)
class Rendered:
    subject: str
    html: str
    text: str


def render(template: Template, params: dict[str, object]) -> Rendered:
    body = fill(template.html, params, escape=True)
    return Rendered(
        subject=fill(template.subject, params, escape=False),
        html=document(body),
        text=to_text(body),
    )


def send(
    db: Session, to: str, municipality_id: uuid.UUID | None, key: str, **params: object
) -> None:
    """Queue the email `key` in the municipality's version, in the caller's transaction."""
    rendered = render(load(db, municipality_id, key), params)
    enqueue(db, to, rendered.subject, rendered.text, rendered.html)


def items_list(key: str, items: list[dict[str, str]]) -> Html:
    """The HTML list of events of a notification, each from the kind's item text."""
    lines = "".join(
        f"<li>{fill(raw(f'email.items.{key}'), item, escape=True)}</li>" for item in items
    )
    return Html(f"<ul>{lines}</ul>")
