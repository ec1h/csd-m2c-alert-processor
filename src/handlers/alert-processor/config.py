"""Environment-driven configuration for the M2C alert processor.

See README.md for the full environment variable reference.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    halo_base_url: str
    halo_client_id: str
    halo_client_secret: str
    halo_ticket_type_id: int
    halo_team_ec1: int
    halo_team_jw: int
    halo_team_internal: int
    dynamodb_table: str
    webhook_secret: str
    dynamodb_ttl_days: int


def load_config() -> Config:
    """Read and validate configuration from the environment.

    Required variables raise ``KeyError`` immediately, matching the previous
    fail-fast behaviour on Lambda cold start.
    """
    return Config(
        halo_base_url=os.environ["HALO_BASE_URL"].rstrip("/"),
        halo_client_id=os.environ["HALO_CLIENT_ID"],
        halo_client_secret=os.environ["HALO_CLIENT_SECRET"],
        halo_ticket_type_id=int(os.environ.get("HALO_TICKET_TYPE_ID", "64")),
        halo_team_ec1=int(os.environ.get("HALO_TEAM_EC1", "12")),
        halo_team_jw=int(os.environ.get("HALO_TEAM_JW", "13")),
        halo_team_internal=int(os.environ.get("HALO_TEAM_INTERNAL", "14")),
        dynamodb_table=os.environ["DYNAMODB_TABLE"],
        webhook_secret=os.environ.get("WEBHOOK_SECRET", ""),
        dynamodb_ttl_days=int(os.environ.get("DYNAMODB_TTL_DAYS", "90")),
    )
