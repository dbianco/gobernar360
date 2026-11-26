"""Email templates on their own: what an administrator may save, and how a saved text
becomes the email that is sent."""

import pytest

from gobernar360.core.errors import ApiError
from gobernar360.platform import email_templates as templates
from gobernar360.platform.email_templates import Html, Spec, Template
from gobernar360.platform.notification_kinds import all_kinds, notice_kinds

INVITATION = templates.get_spec(templates.INVITATION)
NOTIFICATION = Spec("status_light_missing", ("municipality", "items"), ("items",), True)


def _refused(spec: Spec, subject: str, html: str) -> ApiError:
    with pytest.raises(ApiError) as raised:
        templates.validate(spec, subject, html)
    return raised.value


def _error(error: ApiError) -> tuple:
    return (error.status_code, error.code, error.message, error.details)


# What kinds of email there are


def test_the_account_emails_come_first_then_one_per_kind_of_notification_and_notice(client):
    specs = templates.specs()

    assert [spec.key for spec in specs] == [
        "invitation",
        "membership_added",
        "password_reset",
        *all_kinds(),
        *(f"notice.{kind}" for kind in notice_kinds()),
    ]
    notifications = 3 + len(all_kinds())
    for spec in specs[notifications:]:
        assert spec.variables == ("name", "municipality", "code", "type", "message")
        assert (spec.required, spec.notification) == (("name", "municipality", "code"), False)
    assert specs[0] == Spec(
        "invitation", ("name", "inviter", "municipality", "link", "expires"), ("link",)
    )
    assert specs[1] == Spec("membership_added", ("name", "inviter", "municipality", "link"), ())
    assert specs[2] == Spec("password_reset", ("name", "link", "expires"), ("link",))
    for spec in specs[3:notifications]:
        assert spec.variables == ("municipality", "month", "items", "account_link")
        assert (spec.required, spec.notification) == (("items",), True)


def test_an_unknown_kind_of_email_is_not_found():
    with pytest.raises(ApiError) as raised:
        templates.get_spec("newsletter")

    assert _error(raised.value) == (404, "not_found", "Unknown kind of email.", None)


def test_placeholders_are_read_with_or_without_spaces():
    assert templates.placeholders("Hola {{name}}, {{ link }} {{link}} {name} {{}}") == {
        "name",
        "link",
    }


# What may be saved


def test_a_valid_text_is_stored_with_the_subject_on_one_line():
    html = '<p>Entrá: <a href="{{link}}">acá</a></p>'
    subject, stored = templates.validate(INVITATION, "  Bienvenida a\n {{municipality}}  ", html)

    assert subject == "Bienvenida a {{municipality}}"
    assert stored == html


@pytest.mark.parametrize("subject", ["", "   \n "])
def test_the_subject_cannot_be_empty(subject):
    error = _refused(INVITATION, subject, "<p>{{link}}</p>")
    assert _error(error) == (
        422,
        "validation_error",
        "The subject must have 1 to 300 characters.",
        None,
    )


def test_the_subject_has_at_most_300_characters_once_spaces_are_collapsed():
    assert templates.validate(INVITATION, "x" * 300, "<p>{{link}}</p>")[0] == "x" * 300
    assert templates.validate(INVITATION, "x  " * 150, "<p>{{link}}</p>")[0] == "x " * 149 + "x"

    error = _refused(INVITATION, "x" * 301, "<p>{{link}}</p>")
    assert error.message == "The subject must have 1 to 300 characters."


def test_the_text_has_at_most_fifty_thousand_characters():
    html = "<p>{{link}}</p>"
    longest = html + "a" * (templates.MAX_HTML_LENGTH - len(html))
    assert templates.validate(INVITATION, "Hola", longest)[1].startswith(html)

    error = _refused(INVITATION, "Hola", longest + "a")
    assert _error(error) == (422, "validation_error", "The text is too long.", None)


def test_unknown_variables_are_named_with_the_field_they_are_in():
    error = _refused(INVITATION, "Hola {{nombre}}", "<p>{{link}}</p>")
    assert _error(error) == (
        422,
        "template_unknown_variable",
        "The text uses unknown variables.",
        [{"field": "subject", "message": "nombre"}],
    )

    error = _refused(INVITATION, "Hola", "<p>{{link}} {{zeta}} {{alfa}}</p>")
    assert error.details == [{"field": "html", "message": "alfa, zeta"}]


def test_a_variable_removed_by_sanitising_is_not_checked():
    # The script goes away with its content, so the unknown variable does too.
    subject, html = templates.validate(
        INVITATION, "Hola", "<p>{{link}}</p><script>{{secret}}</script>"
    )
    assert html == "<p>{{link}}</p>"


def test_the_list_of_events_cannot_go_in_the_subject():
    error = _refused(NOTIFICATION, "Avisos {{items}}", "<p>{{items}}</p>")
    assert _error(error) == (
        422,
        "template_unknown_variable",
        "The list cannot go in the subject.",
        [{"field": "subject", "message": "items"}],
    )


def test_the_required_variables_must_stay_in_the_text():
    error = _refused(INVITATION, "Hola {{link}}", "<p>Hola {{name}}</p>")
    assert _error(error) == (
        422,
        "template_missing_variable",
        "The text lacks required variables.",
        [{"field": "html", "message": "link"}],
    )


def test_a_required_variable_only_in_a_stripped_attribute_is_missing():
    error = _refused(INVITATION, "Hola", '<p onclick="{{link}}">Hola</p>')
    assert error.code == "template_missing_variable"


# Sanitising


def test_sanitising_keeps_the_formatting_the_editor_makes():
    html = (
        "<h1>T</h1><h2>T</h2><h3>T</h3><p>a<br>b <strong>c</strong> <b>d</b> <em>e</em> <i>f</i>"
        " <u>g</u> <s>h</s> <code>i</code></p><ul><li>j</li></ul><ol><li>k</li></ol>"
        "<blockquote>l</blockquote><hr>"
    )
    assert templates.sanitize(html) == html


def test_sanitising_keeps_links_with_their_address_and_title_only():
    assert (
        templates.sanitize(
            '<a href="https://muni.gob.ar" title="Sitio" target="_blank" style="color:red">x</a>'
        )
        == '<a href="https://muni.gob.ar" title="Sitio">x</a>'
    )
    assert templates.sanitize('<a href="mailto:ana@muni.gob.ar">x</a>') == (
        '<a href="mailto:ana@muni.gob.ar">x</a>'
    )
    assert templates.sanitize('<a href="http://muni.gob.ar">x</a>') == (
        '<a href="http://muni.gob.ar">x</a>'
    )


def test_sanitising_drops_dangerous_addresses_and_other_tags():
    assert templates.sanitize('<a href="javascript:alert(1)">x</a>') == "<a>x</a>"
    assert templates.sanitize('<a href="ftp://files.test/a">x</a>') == "<a>x</a>"
    assert templates.sanitize('<img src="x" onerror="alert(1)"><div>y</div>') == "y"
    assert templates.sanitize('<p style="color:red" class="c">z</p>') == "<p>z</p>"
    assert templates.sanitize("<span>a</span><table><tr><td>b</td></tr></table>") == "ab"


# Turning a template into an email


def test_filling_escapes_the_values_in_html_but_not_code_built_html():
    template = "{{name}} {{list}} {{missing}}|"
    params = {"name": '<Ana & "Bea">', "list": Html("<ul><li>x</li></ul>")}

    assert templates.fill(template, params, escape=True) == (
        "&lt;Ana &amp; &quot;Bea&quot;&gt; <ul><li>x</li></ul> |"
    )
    assert templates.fill(template, params, escape=False) == ('<Ana & "Bea"> <ul><li>x</li></ul> |')
    assert templates.fill("{{ n }}", {"n": 7}, escape=True) == "7"


def test_the_document_wraps_the_body_for_mail_clients():
    assert templates.document("<p>Hola</p>") == (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"></head>'
        '<body style="margin:0;padding:24px;background:#f4f5f7">'
        '<div style="max-width:600px;margin:0 auto;padding:24px;background:#ffffff;'
        "border-radius:8px;font-family:Arial,Helvetica,sans-serif;font-size:15px;"
        'line-height:1.5;color:#1f2328"><p>Hola</p></div></body></html>'
    )


def test_the_text_version_keeps_paragraphs_lists_and_links():
    html = (
        "<h2>Avisos</h2><p>Hola   Ana,<br>hay novedades:</p>"
        "<ul><li>Uno</li><li>Dos</li></ul><hr>"
        '<p><a href="https://muni.test/x">Entrar</a> o <a href="https://muni.test/y">'
        'https://muni.test/y</a> o <a href="https://muni.test/z"></a> o <a>nada</a></p>'
        "<blockquote>Cita</blockquote><div>Fin &amp; chau</div>"
    )

    assert templates.to_text(html) == (
        "Avisos\n\n"
        "Hola Ana,\nhay novedades:\n\n"
        "• Uno\n• Dos\n\n"
        "----\n\n"
        "Entrar (https://muni.test/x) o https://muni.test/y o https://muni.test/z o nada\n\n"
        "Cita\n\n"
        "Fin & chau\n"
    )


def test_the_text_version_of_an_ordered_list_and_headings():
    assert templates.to_text("<h1>A</h1><h3>B</h3><ol><li>c</li></ol>") == "A\n\nB\n\n• c\n"


def test_an_unclosed_link_leaves_its_text_alone():
    assert templates.to_text('<p><a href="https://x.test">sin cerrar</p>') == "sin cerrar\n"


def test_rendering_fills_subject_html_and_text():
    template = Template(
        "invitation",
        "Hola {{name}} & cía",
        '<p>Hola {{name}}: <a href="{{link}}">entrá</a></p>',
        True,
    )

    rendered = templates.render(template, {"name": "Ana <A>", "link": "https://x.test/?a=1&b=2"})

    assert rendered.subject == "Hola Ana <A> & cía"
    assert '<p>Hola Ana &lt;A&gt;: <a href="https://x.test/?a=1&amp;b=2">entrá</a></p>' in (
        rendered.html
    )
    assert rendered.text == "Hola Ana <A>: entrá (https://x.test/?a=1&b=2)\n"


def test_the_list_of_events_is_built_from_the_item_text_of_the_kind():
    html = templates.items_list(
        "milestone_overdue",
        [
            {"project": "Plaza <Norte>", "milestone": "Licitación", "due": "01/03/2026"},
            {"project": "Cloacas", "milestone": "Obra", "due": "02/03/2026"},
        ],
    )

    assert isinstance(html, Html)
    assert html.startswith("<ul><li>")
    assert html.endswith("</li></ul>")
    assert html.count("<li>") == 2
    assert "Plaza &lt;Norte&gt;" in html
    assert "Cloacas" in html


def test_the_default_texts_come_from_the_locale_file():
    invitation = templates.default("invitation")

    assert invitation.key == "invitation"
    assert invitation.customized is False
    assert "{{link}}" in invitation.html
    assert invitation.subject
    for spec in templates.specs():
        default = templates.default(spec.key)
        # Every default passes the checks an administrator's text must pass.
        assert templates.validate(spec, default.subject, default.html)[1] == default.html


def test_the_list_of_events_is_one_list_item_per_event():
    html = templates.items_list(
        "status_light_missing",
        [
            {"link": "https://x.test/a", "dashboard": "Proyectos"},
            {"link": "https://x.test/b", "dashboard": "Social & Salud"},
        ],
    )

    assert html == (
        '<ul><li><a href="https://x.test/a">Proyectos</a></li>'
        '<li><a href="https://x.test/b">Social &amp; Salud</a></li></ul>'
    )


def test_a_link_whose_text_is_its_address_is_written_once_even_with_formatting_inside():
    html = (
        '<p><a href="https://x.test/y">https://x.test/<b>y</b></a>'
        ' y <a href="https://x.test/z"><b>zeta</b> z</a></p>'
    )

    assert templates.to_text(html) == "https://x.test/y y zeta z (https://x.test/z)\n"


def test_each_line_of_the_text_version_is_trimmed():
    assert templates.to_text("<p>Hola <br> Ana </p><p> Chau</p>") == "Hola\nAna\n\nChau\n"
