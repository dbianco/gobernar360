"""A closed monthly report as a PDF, rendered on the server.

Deterministic: the document is built only from the frozen report, with the PDF's base
fonts (no font files from the machine) and the closing time as its date, so the same
report always gives the same bytes. Lights are drawn with their own mark and named, so a
black-and-white print still tells them apart.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fpdf import FPDF, FontFace

from gobernar360.platform.formatting import (
    EMPTY,
    format_change,
    format_date,
    format_indicator,
    format_number,
    month_and_year,
)
from gobernar360.platform.masking import is_masked

STATE_NAMES = {"green": "En orden", "yellow": "Con atención", "red": "Crítico", None: "Sin estado"}
# Fill and mark colors of each light; the mark, not the color, is what identifies it.
LIGHT_FILL = {"green": (46, 125, 50), "yellow": (250, 204, 21), "red": (198, 40, 40)}
LIGHT_MARK = {"green": (255, 255, 255), "yellow": (33, 37, 41), "red": (255, 255, 255)}

MARGIN = 15
WIDTH = 210 - 2 * MARGIN
INK = (33, 37, 41)
MUTED = (110, 110, 110)
RULE = (190, 190, 190)
HEADER_FILL = (235, 235, 235)
# Indicator table: name, value, previous month, change, target, state, twelve months.
COLUMNS = (
    ("Indicador", 48),
    ("Valor", 22),
    ("Mes anterior", 22),
    ("Variación", 20),
    ("Meta", 20),
    ("Estado", 25),
    ("12 meses", 23),
)


def _text(value: str) -> str:
    """Text the base fonts can write: Windows-1252, with anything else replaced."""
    value = value.replace("\u2212", "-").replace("\u2192", "->")
    return value.encode("cp1252", errors="replace").decode("cp1252")


@dataclass(frozen=True)
class ReportDocument:
    content: dict[str, Any]
    comments: dict[str, str]
    version: int
    closed_at: datetime
    # Set for the public rendition: counts below it are masked and only aggregate
    # indicators are shown.
    public_threshold: int | None = None


class _Pdf(FPDF):
    def __init__(self, footer: str) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.core_fonts_encoding = "windows-1252"
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.set_auto_page_break(True, margin=18)
        self.footer_text = footer

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("helvetica", size=8)
        self.set_text_color(*MUTED)
        self.cell(WIDTH * 0.75, 5, _text(self.footer_text))
        self.cell(WIDTH * 0.25, 5, f"Página {self.page_no()} de {{nb}}", align="R")


def _light(pdf: FPDF, cx: float, cy: float, radius: float, color: str | None) -> None:
    """A light: a filled circle with its mark, or a dashed empty circle when unset."""
    if color is None:
        pdf.set_draw_color(*MUTED)
        pdf.set_line_width(0.3)
        pdf.set_dash_pattern(dash=0.7, gap=0.6)
        pdf.circle(cx, cy, radius, style="D")
        pdf.set_dash_pattern()
        return
    pdf.set_fill_color(*LIGHT_FILL[color])
    pdf.set_draw_color(*INK)
    pdf.set_line_width(0.2)
    pdf.circle(cx, cy, radius, style="DF")
    pdf.set_draw_color(*LIGHT_MARK[color])
    pdf.set_fill_color(*LIGHT_MARK[color])
    pdf.set_line_width(radius * 0.24)
    r = radius
    if color == "green":
        pdf.polyline([(cx - r * 0.48, cy + r * 0.02), (cx - r * 0.12, cy + r * 0.38),
                      (cx + r * 0.5, cy - r * 0.38)])  # fmt: skip
    elif color == "yellow":
        pdf.line(cx, cy - r * 0.52, cx, cy + r * 0.12)
        pdf.circle(cx, cy + r * 0.42, r * 0.12, style="F")
    else:
        pdf.line(cx - r * 0.4, cy - r * 0.4, cx + r * 0.4, cy + r * 0.4)
        pdf.line(cx - r * 0.4, cy + r * 0.4, cx + r * 0.4, cy - r * 0.4)
    pdf.set_line_width(0.2)


def _runs(values: list[float | None]) -> list[list[tuple[int, float]]]:
    result, current = [], []
    for index, value in enumerate(values):
        if value is None:
            if current:
                result.append(current)
            current = []
        else:
            current.append((index, value))
    if current:
        result.append(current)
    return result


def _sparkline(pdf: FPDF, x: float, y: float, w: float, h: float, series: list[dict]) -> None:
    """Twelve months as a line, with the target as a dashed grey line; gaps stay gaps."""
    values = [point["value"] for point in series]
    targets = [point["target"] for point in series]
    known = [value for value in values + targets if value is not None]
    if not any(value is not None for value in values):
        return
    low, high = min(known), max(known)
    span = (high - low) or 1
    step = w / max(len(series) - 1, 1)

    def at(index: int, value: float) -> tuple[float, float]:
        top = y + h / 2 if high == low else y + (high - value) / span * h
        return x + index * step, top

    pdf.set_draw_color(*MUTED)
    pdf.set_line_width(0.25)
    pdf.set_dash_pattern(dash=0.8, gap=0.6)
    for run in _runs(targets):
        if len(run) > 1:
            pdf.polyline([at(index, value) for index, value in run])
    pdf.set_dash_pattern()
    pdf.set_draw_color(*INK)
    pdf.set_fill_color(*INK)
    pdf.set_line_width(0.35)
    for run in _runs(values):
        if len(run) > 1:
            pdf.polyline([at(index, value) for index, value in run])
    last = len(values) - 1
    if values[last] is not None:
        px, py = at(last, values[last])
        pdf.circle(px, py, 0.6, style="F")
    pdf.set_line_width(0.2)


class _Renderer:
    def __init__(self, document: ReportDocument) -> None:
        self.document = document
        content = document.content
        self.period = month_and_year(content["year"], content["month"])
        self.threshold = document.public_threshold
        name = content["municipality"]["name"]
        self.pdf = _Pdf(
            f"{name} · Informe de gestión de {self.period} · versión {document.version}"
        )
        self.pdf.set_creation_date(document.closed_at)
        self.pdf.set_producer("gobernar360")
        self.pdf.set_title(_text(f"Informe de gestión de {self.period} - {name}"))
        self.pdf.set_author(_text(name))

    # Values, masked in the public rendition.

    def _hidden(self, indicator: dict, value: Any) -> bool:
        return self.threshold is not None and is_masked(value, indicator["unit"], self.threshold)

    def _value(self, indicator: dict, value: Any) -> str:
        if self._hidden(indicator, value):
            return f"menos de {format_number(self.threshold)}"
        return format_indicator(value, indicator["unit"])

    def _indicators(self, dashboard: dict) -> list[dict]:
        rows = dashboard["indicators"]
        if self.threshold is None:
            return rows
        # Only what could be published: aggregate indicators, small counts masked.
        shown = []
        for row in rows:
            if not row["aggregate"]:
                continue
            hidden = self._hidden(row, row["value"])
            shown.append(
                row
                | {
                    "change": None
                    if hidden or self._hidden(row, row["previous_value"])
                    else row["change"],
                    "on_track": None if hidden else row["on_track"],
                    "series": [
                        point | {"value": None} if self._hidden(row, point["value"]) else point
                        for point in row["series"]
                    ],
                }
            )
        return shown

    # Blocks.

    def _font(self, size: float, style: str = "", color: tuple[int, int, int] = INK) -> None:
        self.pdf.set_font("helvetica", style=style, size=size)
        self.pdf.set_text_color(*color)

    def _room(self, height: float) -> None:
        """Start a new page unless `height` fits on this one."""
        if self.pdf.will_page_break(height):
            self.pdf.add_page()

    def _title(self) -> None:
        content, pdf = self.document.content, self.pdf
        municipality = content["municipality"]
        kind = "Municipio" if municipality["kind"] == "municipality" else "Comuna"
        self._font(10, color=MUTED)
        pdf.cell(WIDTH, 5, _text(kind.upper()), new_x="LMARGIN", new_y="NEXT")
        self._font(22, "B")
        pdf.cell(WIDTH, 10, _text(municipality["name"]), new_x="LMARGIN", new_y="NEXT")
        self._font(15)
        pdf.cell(WIDTH, 8, _text(f"Informe de gestión de {self.period}"), new_x="LMARGIN",
                 new_y="NEXT")  # fmt: skip
        self._font(9, color=MUTED)
        closed = format_date(self.document.closed_at.date())
        pdf.cell(WIDTH, 5, _text(f"Versión {self.document.version}, cerrada el {closed}."),
                 new_x="LMARGIN", new_y="NEXT")  # fmt: skip
        if self.threshold is not None:
            pdf.multi_cell(
                WIDTH,
                4.5,
                _text(
                    "Versión pública: las cantidades de 1 a "
                    f"{format_number(self.threshold - 1)} se muestran como «menos de "
                    f"{format_number(self.threshold)}»."
                ),
                new_x="LMARGIN",
                new_y="NEXT",
            )
        pdf.ln(3)
        pdf.set_draw_color(*RULE)
        pdf.line(MARGIN, pdf.get_y(), MARGIN + WIDTH, pdf.get_y())
        pdf.ln(4)

    def _summary(self) -> None:
        pdf = self.pdf
        self._font(13, "B")
        pdf.cell(WIDTH, 8, "Resumen del mes", new_x="LMARGIN", new_y="NEXT")
        widths = (55, 45, 80)
        self._header_row(("Tablero", "Estado del mes", "Metas"), widths)
        for dashboard in self.document.content["dashboards"]:
            rows = self._indicators(dashboard)
            with_target = [row for row in rows if row["on_track"] is not None]
            met = sum(row["on_track"] is True for row in with_target)
            goals = f"{met} de {len(with_target)} en meta" if with_target else "Sin metas"
            self._room(8)
            y = pdf.get_y()
            self._font(10)
            pdf.set_draw_color(*RULE)
            pdf.cell(widths[0], 8, _text(dashboard["name"]), border="B")
            pdf.cell(widths[1], 8, "", border="B")
            pdf.cell(widths[2], 8, _text(goals), border="B", new_x="LMARGIN", new_y="NEXT")
            _light(pdf, MARGIN + widths[0] + 4, y + 4, 2.4, dashboard["light"])
            self._font(10)
            pdf.set_xy(MARGIN + widths[0] + 8, y)
            pdf.cell(widths[1] - 8, 8, _text(STATE_NAMES[dashboard["light"]]))
            pdf.set_xy(MARGIN, y + 8)
        pdf.ln(4)

    def _header_row(self, titles: tuple[str, ...], widths: tuple[float, ...]) -> None:
        pdf = self.pdf
        self._room(16)
        self._font(8, "B")
        pdf.set_fill_color(*HEADER_FILL)
        pdf.set_draw_color(*RULE)
        for title, width in zip(titles, widths, strict=True):
            pdf.cell(width, 7, _text(title), border=1, fill=True, align="C")
        pdf.ln(7)

    def _indicator_table(self, dashboard: dict) -> None:
        pdf = self.pdf
        rows = self._indicators(dashboard)
        if not rows:
            self._font(9, color=MUTED)
            pdf.cell(WIDTH, 6, "Sin indicadores.", new_x="LMARGIN", new_y="NEXT")
            return
        titles = tuple(title for title, _ in COLUMNS)
        widths = tuple(width for _, width in COLUMNS)
        self._header_row(titles, widths)
        for row in rows:
            self._font(9)
            lines = pdf.multi_cell(widths[0] - 2, 4.2, _text(row["name"]), dry_run=True,
                                   output="LINES")  # fmt: skip
            height = max(10.0, len(lines) * 4.2 + 2)
            if pdf.will_page_break(height):
                pdf.add_page()
                self._header_row(titles, widths)
                self._font(9)
            x, y = MARGIN, pdf.get_y()
            state = EMPTY
            if row["on_track"] is not None:
                state = "En meta" if row["on_track"] else "Fuera de meta"
            elif row["target"] is None:
                state = "Sin meta"
            cells = (
                self._value(row, row["value"]),
                self._value(row, row["previous_value"]),
                format_change(row["change"], row["unit"]),
                format_indicator(row["target"], row["unit"]),
                state,
            )
            pdf.set_draw_color(*RULE)
            for width in widths:
                pdf.rect(x, y, width, height)
                x += width
            pdf.set_xy(MARGIN + 1, y + (height - len(lines) * 4.2) / 2)
            pdf.multi_cell(widths[0] - 2, 4.2, _text(row["name"]), align="L")
            x = MARGIN + widths[0]
            for position, (text, width) in enumerate(zip(cells, widths[1:6], strict=True)):
                pdf.set_xy(x, y)
                # The month's value stands out.
                self._font(9, "B" if position == 0 else "")
                pdf.cell(width, height, _text(text), align="C")
                x += width
            _sparkline(pdf, x + 2, y + 2, widths[6] - 4, height - 4, row["series"])
            pdf.set_xy(MARGIN, y + height)
        pdf.ln(2)

    def _comment(self, text: str) -> None:
        pdf = self.pdf
        self._font(9, "B")
        self._room(14)
        pdf.cell(WIDTH, 6, "Comentario de la gestión", new_x="LMARGIN", new_y="NEXT")
        self._font(10)
        pdf.multi_cell(WIDTH, 5, _text(text), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    def _table(self, table: dict) -> None:
        pdf = self.pdf
        self._room(22)
        self._font(10, "B")
        pdf.cell(WIDTH, 7, _text(table["title"]), new_x="LMARGIN", new_y="NEXT")
        if not table["rows"]:
            self._font(9, color=MUTED)
            pdf.cell(WIDTH, 6, "Ninguno en el mes.", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            return
        kinds = [column["kind"] for column in table["columns"]]
        # Text columns share what dates and numbers leave.
        fixed = {"date": 28, "number": 30}
        free = WIDTH - sum(fixed.get(kind, 0) for kind in kinds)
        text_columns = max(1, kinds.count("text"))
        widths = [fixed.get(kind, free / text_columns) for kind in kinds]

        def cell(value: Any, kind: str) -> str:
            if kind == "date":
                return format_date(value)
            if kind == "number":
                return format_number(value)
            return _text(str(value) if value is not None else EMPTY)

        self._font(9)
        pdf.set_draw_color(*RULE)
        pdf.set_fill_color(255, 255, 255)
        with pdf.table(
            col_widths=widths,
            text_align=["LEFT" if kind == "text" else "CENTER" for kind in kinds],
            line_height=4.6,
            headings_style=FontFace(emphasis="BOLD", fill_color=HEADER_FILL),
            borders_layout="HORIZONTAL_LINES",
            cell_fill_mode="NONE",
            first_row_as_headings=True,
        ) as rendered:
            heading = rendered.row()
            for column in table["columns"]:
                heading.cell(_text(column["title"]))
            for values in table["rows"]:
                line = rendered.row()
                for value, kind in zip(values, kinds, strict=True):
                    line.cell(cell(value, kind))
        pdf.ln(3)

    def _dashboard(self, dashboard: dict) -> None:
        pdf = self.pdf
        self._room(45)
        y = pdf.get_y()
        _light(pdf, MARGIN + 3.5, y + 4, 3.2, dashboard["light"])
        pdf.set_xy(MARGIN + 9, y)
        self._font(14, "B")
        pdf.cell(90, 8, _text(dashboard["name"]))
        self._font(10, color=MUTED)
        pdf.cell(WIDTH - 99, 8, _text(f"Estado del mes: {STATE_NAMES[dashboard['light']]}"),
                 align="R", new_x="LMARGIN", new_y="NEXT")  # fmt: skip
        pdf.ln(2)
        comment = self.document.comments.get(dashboard["key"])
        if comment:
            self._comment(comment)
        self._indicator_table(dashboard)
        for table in dashboard["tables"]:
            self._table(table)
        pdf.ln(4)

    def render(self) -> bytes:
        self.pdf.add_page()
        self._title()
        self._summary()
        for dashboard in self.document.content["dashboards"]:
            self._dashboard(dashboard)
        return bytes(self.pdf.output())


def render_report(document: ReportDocument) -> bytes:
    return _Renderer(document).render()
