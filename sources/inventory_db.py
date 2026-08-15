"""
Mock Inventory Database.

Real-world analogue: the system of record for asset ownership,
classification, and assigned "home" location. Updated infrequently
and often lags reality — it's authoritative for what an asset *is*,
not necessarily for where it currently *is*.
"""

from datetime import datetime, timedelta

_NOW = datetime(2026, 8, 14, 9, 0, 0)

_DATA = {
    "AST-1042": [
        {
            "field": "asset_type",
            "value": "Electric Forklift, Class II",
            "reported_at": _NOW - timedelta(days=400),
            "ingested_at": _NOW - timedelta(days=400),
            "note": "asset onboarding record",
        },
        {
            "field": "location",
            "value": "Bay 3",
            "reported_at": _NOW - timedelta(days=20),
            "ingested_at": _NOW - timedelta(days=20),
            "note": "assigned home location, last updated at quarterly audit",
        },
        {
            "field": "owner",
            "value": "Warehouse Ops Team",
            "reported_at": _NOW - timedelta(days=400),
            "ingested_at": _NOW - timedelta(days=400),
            "note": "asset onboarding record",
        },
    ],
    "AST-2077": [
        {
            "field": "asset_type",
            "value": "Pallet Jack, Manual",
            "reported_at": _NOW - timedelta(days=200),
            "ingested_at": _NOW - timedelta(days=200),
            "note": "asset onboarding record",
        },
    ],
}


def fetch(asset_id: str) -> list[dict]:
    return list(_DATA.get(asset_id, []))


def query(asset_id: str, question: str) -> dict:
    if asset_id == "AST-1042" and "update frequency" in question.lower():
        return {
            "answer": "This system's location field is only refreshed during "
                      "quarterly physical audits and is not intended to reflect "
                      "real-time position.",
            "source": "inventory_db",
        }
    return {"answer": "No additional information available.", "source": "inventory_db"}
