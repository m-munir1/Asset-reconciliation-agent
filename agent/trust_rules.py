"""
Trust configuration.

This is the part of the system a reviewer should be able to read in
thirty seconds and understand *why* the agent trusts what it trusts.
It is deliberately kept as plain data + short functions, not buried
inside a prompt, so the rules are inspectable and testable on their
own — independent of whatever LLM is or isn't available.

"""

from datetime import timedelta


FIELD_AUTHORITY: dict[str, str] = {
    "fault_status": "fault_reporting",
    "condition": "maintenance_log",
    "last_service_date": "maintenance_log",
    "asset_type": "inventory_db",
    "owner": "inventory_db",
}

FIELD_AUTHORITY_REASON: dict[str, str] = {
    "fault_status": (
        "fault_reporting is authoritative for fault state: it is the only "
        "source fed by direct operator incident reports, so it has both the "
        "mechanism and the incentive to surface faults immediately."
    ),
    "condition": (
        "maintenance_log is authoritative for physical condition: entries "
        "come from a technician's direct visual inspection, not an inferred "
        "or automated signal."
    ),
    "last_service_date": (
        "maintenance_log is the system technicians log service events into "
        "directly; no other source tracks this field."
    ),
    "asset_type": (
        "inventory_db is the system of record for asset classification, "
        "set once at onboarding and not expected to change."
    ),
    "owner": (
        "inventory_db is the system of record for asset ownership."
    ),
}

# Fields that need bespoke resolution logic rather than a flat authority,
# because more than one source can plausibly know the current truth and
# the right answer depends on freshness and corroboration, not policy
# alone. "location" is the canonical hard case for this assessment.
CONTESTED_FIELDS = {"location"}

# Every field the agent expects an asset record to have an opinion on.
# Used to detect *missing* information, not just conflicting information.
EXPECTED_FIELDS = [
    "location",
    "fault_status",
    "condition",
    "last_service_date",
    "asset_type",
    "owner",
]

# How stale a location-service beacon report can be before we no longer
# trust it over a more recent, physically-confirmed report from another
# source. Chosen because RTLS beacons are expected to refresh roughly
# every few minutes when working normally; anything older than this
# suggests a dropped signal rather than a truly unchanged position.
LOCATION_STALENESS_THRESHOLD = timedelta(hours=1)
