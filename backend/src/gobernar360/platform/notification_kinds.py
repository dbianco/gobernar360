"""The kinds of notification email, the platform's own and those dashboards declare, and the
kinds of notice to residents, which only dashboards have."""

from gobernar360.dashboards import registry

STATUS_LIGHT_MISSING = "status_light_missing"


def all_kinds() -> list[str]:
    """Every kind of notification, the platform's first, as users see them in their account."""
    kinds = [STATUS_LIGHT_MISSING]
    for module in registry.all_modules():
        kinds.extend(kind for kind in module.alert_kinds if kind not in kinds)
    return kinds


def notice_kinds() -> list[str]:
    """Every kind of notice to residents."""
    kinds: list[str] = []
    for module in registry.all_modules():
        kinds.extend(kind for kind in module.notice_kinds if kind not in kinds)
    return kinds
