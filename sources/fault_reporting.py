"""
Mock Fault-Reporting Tool.

Real-world analogue: a system fed by operator-submitted incident
reports and/or onboard diagnostics. Authoritative for fault/safety
state because it's the only source with a direct incentive and
mechanism to surface problems immediately.
"""

from datetime import datetime, timedelta

_NOW = datetime(2026, 8, 14, 9, 0, 0)

_DATA = {
    "AST-1042": [
        {
            "field": "fault_status",
            "value": "active_fault: hydraulic pressure warning",
            "reported_at": _NOW - timedelta(hours=1, minutes=45),
            "ingested_at": _NOW - timedelta(hours=1, minutes=44),
            "note": "operator-submitted incident report, ticket #F-8821",
        },
    ],
    "AST-2077": [
        # No faults reported for this asset — deliberately empty,
        # to exercise the "missing information" path.
    ],
}


def fetch(asset_id: str) -> list[dict]:
    return list(_DATA.get(asset_id, []))


def query(asset_id: str, question: str) -> dict:
    if asset_id == "AST-1042" and "location" in question.lower():
        return {
            "answer": "Ticket #F-8821 was submitted by an operator via the "
                      "handheld scanner at Bay 7, which auto-tags submission "
                      "location. This corroborates Bay 7, not Bay 3.",
            "source": "fault_reporting",
        }
    return {"answer": "No additional information available.", "source": "fault_reporting"}
