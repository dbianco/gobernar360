"""When a procedure can be done entirely from home. Always worked out, never typed."""

from sqlalchemy import and_, exists

from gobernar360.dashboards.procedures.models import Procedure, ProcedureRequirement

ONLINE_CHANNELS = ("online", "both")

ONLINE = Procedure.channel.in_(ONLINE_CHANNELS)

# What is asked for on paper has to be brought; what is optional may be left out.
_ASKS_FOR_PAPER = exists().where(
    ProcedureRequirement.procedure_id == Procedure.id,
    ProcedureRequirement.mandatory,
    ProcedureRequirement.format == "paper",
)

# `both` counts: the figure answers what a person could do, not what they do.
FULLY_DIGITAL = and_(Procedure.is_active, ONLINE, Procedure.url != "", ~_ASKS_FOR_PAPER)
