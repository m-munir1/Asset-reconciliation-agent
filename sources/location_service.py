"""
Mock Location Service.

Real-world analogue: RTLS / GPS beacon system that pings asset
location periodically. Fast-updating, but occasionally reports a
stale cached position when a beacon drops signal.
"""

from datetime import datetime, timedelta

_NOW = datetime(2026, 8, 14, 9, 0, 0)

# Raw "API responses" keyed by asset id. Each source is deliberately
# built as a plain function returning records, so it's trivial to
# swap for a real HTTP client later.
_DATA = {
    "AST-1042": [
        {
            "field": "location",
            "value": "Bay 3",
            "reported_at": _NOW - timedelta(hours=6),
            "ingested_at": _NOW - timedelta(hours=6, minutes=-1),
            "note": "beacon ping, signal strength normal",
        },
    ],
    "AST-2077": [
        {
            "field": "location",
            "value": "Loading Dock B",
            "reported_at": _NOW - timedelta(minutes=15),
            "ingested_at": _NOW - timedelta(minutes=14),
            "note": "beacon ping, signal strength normal",
        },
    ],
}


def fetch(asset_id: str) -> list[dict]:
    """Return all field reports this source currently holds for the asset."""
    return list(_DATA.get(asset_id, []))


def query(asset_id: str, question: str) -> dict:
    """
    Simulates a targeted follow-up query against the source's live API,
    e.g. asking it to re-ping the beacon rather than serving cached data.
    This is one of the tools the agent can call to resolve ambiguity.
    """
    if asset_id == "AST-1042" and "last signal" in question.lower():
        return {
            "answer": "Last confirmed beacon signal was 6 hours ago. "
                      "No signal received since — beacon may be out of "
                      "range, powered off, or the asset may have moved "
                      "to an area without RTLS coverage.",
            "source": "location_service",
        }
    return {"answer": "No additional information available.", "source": "location_service"}
