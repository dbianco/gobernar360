"""Members of a municipality as a CSV file: the example to download and the import.

One row per person: email, name, whether they administer the municipality, and one
column per enabled dashboard with their access level. The file is meant to be edited by
hand in a spreadsheet, so reading it is lenient: comma, semicolon or tab separated;
headers and values in Spanish (as in the example) or as the API's keys; case, accents
and surrounding spaces do not matter.

A dashboard column left out of the file leaves that access as it is; an empty cell in a
present column means no access. The whole file is checked before anything changes, and
every problem is reported with its line.
"""

import csv
import io
import unicodedata
from dataclasses import dataclass, field

from gobernar360.core.errors import ApiError
from gobernar360.platform.schemas import valid_email
from gobernar360.platform.texts import dashboard_name, text

MAX_ROWS = 1000
MAX_ERRORS = 50
LEVELS = ("viewer", "editor", "admin")


def fold(value: str) -> str:
    """Lowercase, without accents or surrounding spaces: how headers and values compare."""
    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


# Runs once, while the module is imported, where mutation testing cannot reach it (hence
# the pragma); tests/platform/test_members_csv_parse.py checks every alias it builds.
def _aliases(*values: str) -> set[str]:  # pragma: no mutate block
    return {fold(value) for value in values}


EMAIL_HEADERS = _aliases("email", "correo", "correo electronico", "e-mail", "mail")
NAME_HEADERS = _aliases("nombre", "nombre y apellido", "full_name", "name")
ADMIN_HEADERS = _aliases("administrador", "administrador del municipio", "is_admin", "admin")
YES = _aliases("si", "sí", "s", "yes", "y", "true", "1", "x")
NO = _aliases("no", "n", "false", "0", "")
NO_ACCESS = _aliases("", "sin acceso", "ninguno", "none", "no")


def _level_aliases() -> dict[str, str]:
    aliases = {fold(level): level for level in LEVELS}
    for level in LEVELS:
        aliases[fold(text(f"membersCsv.levels.{level}"))] = level
    return aliases


@dataclass
class MemberRow:
    line: int
    email: str
    full_name: str
    # None: the file has no administrator column.
    is_admin: bool | None
    # Only the dashboards with a column in the file; None is no access.
    grants: dict[str, str | None] = field(default_factory=dict)


class _Errors:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, line: int, code: str, column: str = "", value: str = "") -> None:
        if len(self.items) < MAX_ERRORS:
            self.items.append({"line": line, "code": code, "column": column, "value": value})

    def raise_if_any(self) -> None:
        if self.items:
            raise ApiError(422, "invalid_csv", "The file has errors.", details=self.items)


def _dialect(content: str) -> type[csv.Dialect] | csv.Dialect:
    first_line = content.split("\n", 1)[0]
    try:
        return csv.Sniffer().sniff(first_line, delimiters=",;\t")
    except csv.Error:
        return csv.excel


def _columns(
    header: list[str], enabled: list[str], installed: set[str], errors: _Errors
) -> dict[int, str]:
    """Which field each column holds: "email", "name", "admin" or a dashboard key."""
    by_name = {fold(key): key for key in enabled}
    by_name.update({fold(dashboard_name(key)): key for key in enabled})
    disabled = {fold(key): key for key in installed - set(enabled)}
    disabled.update({fold(dashboard_name(key)): key for key in installed - set(enabled)})
    columns: dict[int, str] = {}
    for index, raw in enumerate(header):
        name = fold(raw)
        if not name:
            continue  # spreadsheets often leave empty columns at the end
        if name in EMAIL_HEADERS:
            target = "email"
        elif name in NAME_HEADERS:
            target = "name"
        elif name in ADMIN_HEADERS:
            target = "admin"
        elif name in by_name:
            target = by_name[name]
        else:
            errors.add(1, "dashboard_not_enabled" if name in disabled else "unknown_column", raw)
            continue
        if target in columns.values():
            errors.add(1, "duplicate_column", raw)
            continue
        columns[index] = target
    for required in ("email", "name"):
        if required not in columns.values():
            errors.add(1, "missing_column", text(f"membersCsv.columns.{required}"))
    return columns


def parse(content: str, enabled: list[str], installed: set[str]) -> list[MemberRow]:
    """The rows of the file, the last one winning for each email, or every problem found."""
    errors = _Errors()
    reader = csv.reader(io.StringIO(content.lstrip("\ufeff")), _dialect(content))
    header = next(reader, None)
    if header is None:
        raise ApiError(422, "invalid_csv", "The file is empty.", details=[_empty()])
    columns = _columns(header, enabled, installed, errors)
    errors.raise_if_any()
    levels = _level_aliases()
    header_of = {index: header[index] for index in columns}

    rows: dict[str, MemberRow] = {}
    count = 0
    for cells in reader:
        line = reader.line_num
        if not any(cell.strip() for cell in cells):
            continue
        count += 1
        if count > MAX_ROWS:
            errors.add(line, "too_many_rows", value=str(MAX_ROWS))
            break
        if any(cell.strip() for cell in cells[len(header) :]):
            errors.add(line, "extra_cells")
        values = {target: (cells[i] if i < len(cells) else "") for i, target in columns.items()}
        column_of = {target: header_of[i] for i, target in columns.items()}

        email_cell = values["email"].strip()
        try:
            email = valid_email(email_cell)
        except ValueError:
            errors.add(line, "invalid_email", column_of["email"], email_cell)
            email = ""
        full_name = " ".join(values["name"].split())
        if not full_name:
            errors.add(line, "missing_name", column_of["name"])
        elif len(full_name) > 200:
            errors.add(line, "name_too_long", column_of["name"])

        is_admin = None
        if "admin" in values:
            answer = fold(values["admin"])
            if answer in YES:
                is_admin = True
            elif answer in NO:
                is_admin = False
            else:
                errors.add(line, "invalid_admin", column_of["admin"], values["admin"].strip())

        grants: dict[str, str | None] = {}
        for target, value in values.items():
            if target in ("email", "name", "admin"):
                continue
            answer = fold(value)
            if answer in levels:
                grants[target] = levels[answer]
            elif answer in NO_ACCESS:
                grants[target] = None
            else:
                errors.add(line, "invalid_level", column_of[target], value.strip())

        if email:
            # The last row for an email wins.
            rows.pop(email, None)
            rows[email] = MemberRow(line, email, full_name, is_admin, grants)
    errors.raise_if_any()
    if not rows:
        raise ApiError(422, "invalid_csv", "The file has no rows.", details=[_empty()])
    return list(rows.values())


def _empty() -> dict:
    return {"line": 1, "code": "no_rows", "column": "", "value": ""}


def template(enabled: list[str]) -> tuple[list[str], list[list[str]]]:
    """Header and two example rows for the municipality's enabled dashboards."""
    header = [
        text("membersCsv.columns.email"),
        text("membersCsv.columns.name"),
        text("membersCsv.columns.admin"),
        *(dashboard_name(key) for key in enabled),
    ]
    viewer, editor = text("membersCsv.levels.viewer"), text("membersCsv.levels.editor")
    first = [
        text("membersCsv.example.first.email"),
        text("membersCsv.example.first.name"),
        text("membersCsv.no"),
        *(editor if index == 0 else viewer for index, _ in enumerate(enabled)),
    ]
    second = [
        text("membersCsv.example.second.email"),
        text("membersCsv.example.second.name"),
        text("membersCsv.yes"),
        *("" for _ in enabled),
    ]
    return header, [first, second]
