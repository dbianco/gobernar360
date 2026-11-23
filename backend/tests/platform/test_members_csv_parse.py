"""Reading a members file, without the database: what each cell may say, and how every
problem is reported."""

import pytest

from gobernar360.core.errors import ApiError
from gobernar360.platform import members_csv
from gobernar360.platform.members_csv import MemberRow, parse

ENABLED = ["projects", "social"]
INSTALLED = {"projects", "social", "economic"}


def _rows(content: str, enabled=ENABLED) -> list[MemberRow]:
    return parse(content, enabled, INSTALLED)


def _problems(content: str, enabled=ENABLED) -> ApiError:
    with pytest.raises(ApiError) as raised:
        parse(content, enabled, INSTALLED)
    assert (raised.value.status_code, raised.value.code) == (422, "invalid_csv")
    return raised.value


def _error(line: int, code: str, column: str = "", value: str = "") -> dict:
    return {"line": line, "code": code, "column": column, "value": value}


def test_a_row_gives_the_person_and_the_access_of_each_dashboard_column():
    rows = _rows("email,nombre,administrador,Proyectos\nana@x.test,Ana Pérez,no,Carga\n")

    assert rows == [MemberRow(2, "ana@x.test", "Ana Pérez", False, {"projects": "editor"})]


def test_a_file_without_administrator_column_leaves_that_alone():
    assert _rows("email,nombre\nana@x.test,Ana\n")[0].is_admin is None


@pytest.mark.parametrize(
    ("answer", "is_admin"),
    [("sí", True), ("SI", True), ("x", True), ("1", True), ("no", False), ("", False)],
)
def test_the_administrator_cell_says_yes_or_no(answer, is_admin):
    assert _rows(f"email,nombre,admin\nana@x.test,Ana,{answer}\n")[0].is_admin is is_admin


@pytest.mark.parametrize(
    ("cell", "level"),
    [
        ("Lectura", "viewer"),
        ("viewer", "viewer"),
        ("carga", "editor"),
        ("EDITOR", "editor"),
        ("Administración", "admin"),
        ("administracion", "admin"),
        ("admin", "admin"),
        ("", None),
        ("sin acceso", None),
        ("Ninguno", None),
        ("none", None),
        ("no", None),
    ],
)
def test_each_way_of_writing_a_level(cell, level):
    assert _rows(f"email,nombre,proyectos\nana@x.test,Ana,{cell}\n")[0].grants == {
        "projects": level
    }


def test_a_dashboard_column_may_be_named_by_its_key():
    assert _rows("email,nombre,projects\nana@x.test,Ana,viewer\n")[0].grants == {
        "projects": "viewer"
    }


def test_semicolons_and_tabs_separate_cells_too():
    assert _rows("email;nombre\nana@x.test;Ana\n")[0].full_name == "Ana"
    assert _rows("email\tnombre\nana@x.test\tAna\n")[0].full_name == "Ana"


def test_a_comma_inside_a_name_does_not_change_the_separator_of_a_semicolon_file():
    rows = _rows('email;nombre\nana@x.test;"Pérez, Ana"\nbea@x.test;Bea\n')
    assert [row.full_name for row in rows] == ["Pérez, Ana", "Bea"]


def test_a_header_that_looks_like_nothing_is_read_as_commas():
    # One column only: nothing to sniff a separator from.
    error = _problems("email\nana@x.test\n")
    assert error.details == [_error(1, "missing_column", "nombre")]


def test_a_byte_order_mark_is_ignored():
    assert _rows("\ufeffemail,nombre\nana@x.test,Ana\n")[0].email == "ana@x.test"


def test_spaces_in_names_are_collapsed_and_emails_trimmed():
    row = _rows("email,nombre\n  Ana@X.test , Ana   María  Pérez \n")[0]
    assert (row.email, row.full_name) == ("ana@x.test", "Ana María Pérez")


def test_empty_lines_and_empty_trailing_columns_are_skipped():
    rows = _rows("email,nombre,,\n\nana@x.test,Ana,,\n , \nbea@x.test,Bea\n")

    assert [(row.line, row.email) for row in rows] == [(3, "ana@x.test"), (5, "bea@x.test")]


def test_an_empty_column_between_others_is_skipped_too():
    row = _rows("email,,nombre,proyectos\nana@x.test,,Ana,carga\n")[0]
    assert (row.full_name, row.grants) == ("Ana", {"projects": "editor"})


def test_the_last_row_for_an_email_wins_and_keeps_its_place_at_the_end():
    rows = _rows(
        "email,nombre,proyectos\nana@x.test,Ana,viewer\nbea@x.test,Bea,\nANA@x.test,Ana P,editor\n"
    )

    assert [(row.line, row.email, row.full_name) for row in rows] == [
        (3, "bea@x.test", "Bea"),
        (4, "ana@x.test", "Ana P"),
    ]
    assert rows[1].grants == {"projects": "editor"}
    assert rows[0].grants == {"projects": None}


def test_a_short_row_has_empty_cells():
    row = _rows("email,nombre,proyectos,social\nana@x.test,Ana\n")[0]
    assert row.grants == {"projects": None, "social": None}


def test_an_empty_file_is_refused():
    error = _problems("")
    assert error.message == "The file is empty."
    assert error.details == [_error(1, "no_rows")]


def test_a_file_with_only_the_header_is_refused():
    error = _problems("email,nombre\n\n")
    assert error.message == "The file has no rows."
    assert error.details == [_error(1, "no_rows")]


def test_wrong_columns_are_all_reported_on_the_first_line():
    error = _problems("Correo,Nombre,Económico,Teléfono,mail\nana@x.test,Ana,,,\n")

    assert error.message == "The file has errors."
    assert error.details == [
        _error(1, "dashboard_not_enabled", "Económico"),
        _error(1, "unknown_column", "Teléfono"),
        _error(1, "duplicate_column", "mail"),
    ]


def test_a_disabled_dashboard_is_recognised_by_its_key_too():
    error = _problems("email,nombre,economic\nana@x.test,Ana,\n")
    assert error.details == [_error(1, "dashboard_not_enabled", "economic")]


def test_a_duplicated_dashboard_column_is_reported_and_the_rest_is_read():
    error = _problems("email,proyectos,projects,nombre\nana@x.test,,,Ana\n")
    assert error.details == [_error(1, "duplicate_column", "projects")]


def test_both_missing_columns_are_reported():
    error = _problems("administrador,proyectos\nsí,carga\n")
    assert error.details == [
        _error(1, "missing_column", "email"),
        _error(1, "missing_column", "nombre"),
    ]


def test_every_problem_of_the_rows_is_reported_with_its_line_column_and_value():
    long_name = "x" * 201
    error = _problems(
        "email,nombre,admin,proyectos\n"
        "no-es-email,Ana,talvez,Jefa\n"
        f"bea@x.test,{long_name},no,carga,sobra\n"
        "carla@x.test,  ,sí,\n"
    )

    assert error.details == [
        _error(2, "invalid_email", "email", "no-es-email"),
        _error(2, "invalid_admin", "admin", "talvez"),
        _error(2, "invalid_level", "proyectos", "Jefa"),
        _error(3, "extra_cells"),
        _error(3, "name_too_long", "nombre"),
        _error(4, "missing_name", "nombre"),
    ]


def test_a_name_of_exactly_two_hundred_characters_is_accepted():
    assert len(_rows(f"email,nombre\nana@x.test,{'x' * 200}\n")[0].full_name) == 200


def test_empty_extra_cells_are_not_a_problem():
    assert _rows("email,nombre\nana@x.test,Ana,, \n")[0].full_name == "Ana"


def test_at_most_fifty_problems_are_reported():
    content = "email,nombre\n" + "".join(f"mal{index},Ana\n" for index in range(60))

    error = _problems(content)

    assert len(error.details) == members_csv.MAX_ERRORS == 50
    assert error.details[-1] == _error(51, "invalid_email", "email", "mal49")


def test_a_file_with_more_rows_than_allowed_is_refused_at_the_first_one_too_many(monkeypatch):
    monkeypatch.setattr(members_csv, "MAX_ROWS", 2)

    assert len(_rows("email,nombre\na@x.test,A\n\nb@x.test,B\n")) == 2
    error = _problems("email,nombre\na@x.test,A\nb@x.test,B\nc@x.test,C\nd@x.test,D\n")
    assert error.details == [_error(4, "too_many_rows", value="2")]


def test_the_example_file_lists_the_enabled_dashboards():
    header, rows = members_csv.template(["projects", "social"])

    assert header == ["email", "nombre", "administrador", "Proyectos", "Social"]
    assert rows == [
        ["ana.perez@ejemplo.gob.ar", "Ana Pérez", "no", "Carga", "Lectura"],
        ["juan.gomez@ejemplo.gob.ar", "Juan Gómez", "sí", "", ""],
    ]


def test_folding_ignores_case_accents_and_surrounding_spaces():
    assert members_csv.fold("  Administración ÑANDÚ ") == "administracion nandu"
