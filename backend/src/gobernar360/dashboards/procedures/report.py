"""What the procedures dashboard adds to a month's report: sign-in with CiDi."""

from datetime import date

from gobernar360.dashboards.procedures.summary import by_cidi_level
from gobernar360.dashboards.registry import ReportColumn, ReportTable
from gobernar360.platform.access import RequestContext

LEVEL_NAMES = {
    1: "Nivel 1 – Confirmado",
    2: "Nivel 2 – Verificado",
    3: "Nivel 3 – Autenticado",
    None: "Sin CiDi",
}


def report_tables(ctx: RequestContext, first: date, last: date) -> list[ReportTable]:
    """Procedures per CiDi level, counts only.

    The inventory keeps no past, so it is as it stands when the report is made; the title
    says so. Without procedures there is no table.
    """
    levels = by_cidi_level(ctx)
    if not any(row.count for row in levels):
        return []
    return [
        ReportTable(
            key="procedures.cidi_levels",
            title="Trámites por nivel de CiDi, al cerrar el informe",
            columns=(ReportColumn("Nivel de CiDi"), ReportColumn("Trámites vigentes", "number")),
            rows=[(LEVEL_NAMES[row.level], row.count) for row in levels],
        )
    ]
