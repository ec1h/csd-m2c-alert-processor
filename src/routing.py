"""Grafana `M2C` alert-type routing rules.

Unmapped or missing alert types are surfaced as a failure by the caller
(see lambda_function.py) rather than silently routed to a fallback team.
"""

from dataclasses import dataclass

from config import Config


@dataclass(frozen=True)
class AlertRoute:
    team_id_attr: str  # Config attribute name holding the resolved team id
    responsible: str
    action: str


# Canonical, case-sensitive Grafana `M2C` label values confirmed with the
# Halo integration owner. Do not add an entry without confirming the target
# team first - an incorrect team assignment misroutes field work.
_ROUTES: dict[str, AlertRoute] = {
    "Low Battery": AlertRoute(
        team_id_attr="halo_team_ec1",
        responsible="EC1 Installers",
        action=(
            "Monitor device for 36 hours. If the alarm persists or "
            "communication is lost, schedule a site visit for battery replacement."
        ),
    ),
    "Tamper": AlertRoute(
        team_id_attr="halo_team_ec1",
        responsible="EC1 Installers",
        action=(
            "Initiate on-site inspection immediately. Check for physical "
            "tampering, cable cuts between pulse reader and transponder, "
            "or device removal."
        ),
    ),
    "No Usage": AlertRoute(
        team_id_attr="halo_team_ec1",
        responsible="EC1 Installers",
        action=(
            "No usage recorded outside normal consumption history. "
            "Schedule on-site inspection to verify meter and pulse reader status."
        ),
    ),
    "Excessive Usage": AlertRoute(
        team_id_attr="halo_team_jw",
        responsible="JW Metering",
        action=(
            "Excessive consumption detected outside normal history. "
            "Review IoT and SAP data before dispatching for on-site inspection."
        ),
    ),
    "No Communication": AlertRoute(
        team_id_attr="halo_team_ec1",
        responsible="EC1 Installers",
        action=(
            "No communication from pulse reader for 72 hours. Schedule "
            "on-site inspection - possible device failure, theft, or network issue."
        ),
    ),
    "Reverse Flow": AlertRoute(
        team_id_attr="halo_team_jw",
        responsible="JW Metering",
        action=(
            "Negative consumption detected. On-site inspection required to "
            "identify meter issue, borehole presence, or illegal connection."
        ),
    ),
    "Device Reboot": AlertRoute(
        team_id_attr="halo_team_internal",
        responsible="EC1 Internal Support",
        action=(
            "Device reboot detected. Internal IoT team to investigate "
            "firmware stability and physical condition of the device."
        ),
    ),
    # "Boot" is intentionally NOT mapped: Grafana sends it but the target
    # team/action has not been confirmed. It falls through to the
    # unmapped_alert_type outcome until an owner confirms the routing.
}


def resolve_route(alert_type: str) -> AlertRoute | None:
    """Return the exact-match route, or None if the type is unmapped."""
    return _ROUTES.get(alert_type)


def team_id_for(route: AlertRoute, config: Config) -> int:
    return getattr(config, route.team_id_attr)


def known_alert_types() -> list[str]:
    return sorted(_ROUTES)
