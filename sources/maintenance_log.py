"""
Mock Maintenance Log.

Real-world analogue: a system technicians log into by hand when they
service or move an asset. Slower and less frequent than the location
service, but authoritative when a human has actually laid eyes on
the asset, because it reflects direct physical confirmation.
"""

from datetime import datetime, timedelta

_NOW = datetime(2026, 8, 14, 9, 0, 0)

_DATA = {
    "AST-1042": [
        {
            "field": "location",
            "value": "Bay 7",
            "reported_at": _NOW - timedelta(hours=2),
            "ingested_at": _NOW - timedelta(hours=2, minutes=-3),
            "note": "technician logged asset moved to Bay 7 for inspection",
        },
        {
            "field": "last_service_date",
            "value": "2026-08-14",
            "reported_at": _NOW - timedelta(hours=2),
            "ingested_at": _NOW - timedelta(hours=2, minutes=-3),
            "note": "routine inspection completed",
        },
        {
            "field": "condition",
            "value": "minor hydraulic leak noted, flagged for parts order",
            "reported_at": _NOW - timedelta(hours=2),
            "ingested_at": _NOW - timedelta(hours=2, minutes=-3),
            "note": "technician visual inspection",
        },
    ],
    "AST-2077": [
        {
            "field": "last_service_date",
            "value": "2026-07-30",
            "reported_at": _NOW - timedelta(days=15),
            "ingested_at": _NOW - timedelta(days=15),
            "note": "scheduled maintenance",
        },
    ],
}


def fetch(asset_id: str) -> list[dict]:
    return list(_DATA.get(asset_id, []))


def query(asset_id: str, question: str) -> dict:
    if asset_id == "AST-1042" and "confirm" in question.lower():
        return {
            "answer": "Technician entry includes a timestamped photo reference "
                      "(IMG_20260814_0700_bay7.jpg) and technician ID T-114. "
                      "This was a direct physical inspection, not a remote signal.",
            "source": "maintenance_log",
        }
    return {"answer": "No additional information available.", "source": "maintenance_log"}
