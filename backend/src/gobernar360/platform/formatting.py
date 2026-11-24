"""Numbers, dates and months written the Argentine way, for documents made on the server.

The web app formats with the browser's Intl API; these mirror it: 1.234,5 and 03/11/2026.
"""

from datetime import date

MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
EMPTY = "—"


def month_name(month: int) -> str:
    """ "Octubre" for 10, to start a line with."""
    return MONTHS[month - 1].capitalize()


def month_and_year(year: int, month: int) -> str:
    """ "octubre de 2026": lower case, as months are written inside a sentence."""
    return f"{MONTHS[month - 1]} de {year}"


def format_number(value: float | int | None, decimals: int = 2) -> str:
    """1234.5 -> "1.234,5": thousands with dots, decimals with a comma, no trailing zeros."""
    if value is None:
        return EMPTY
    text = f"{abs(value):,.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"-{text}" if value < 0 and text.strip("0.,") else text


def format_indicator(value: float | int | None, unit: str | None) -> str:
    """An indicator's value in its unit: "12", "42 %" (percent), "25,6 %" (0..1 ratio)."""
    if value is None:
        return EMPTY
    if unit == "percent":
        return f"{format_number(value, 1)} %"
    if unit == "ratio":
        return f"{format_number(value * 100, 1)} %"
    return format_number(value)


def format_change(value: float | int | None, unit: str | None) -> str:
    """A change with its sign; percentages and ratios change in percentage points."""
    if value is None:
        return EMPTY
    magnitude = abs(value) * 100 if unit == "ratio" else abs(value)
    amount = format_number(magnitude, 1 if unit in ("percent", "ratio") else 2)
    if unit in ("percent", "ratio"):
        amount = f"{amount} p.p."
    if amount.startswith("0") and amount.strip("0,. p") == "":
        return amount
    return f"{'+' if value > 0 else '-'}{amount}"


def format_date(value: date | str | None) -> str:
    """ "03/11/2026"; accepts a date or an ISO string."""
    if value is None:
        return EMPTY
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    return value.strftime("%d/%m/%Y")
