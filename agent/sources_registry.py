"""
Registry of available sources. Each source module exposes:
    fetch(asset_id) -> list[dict]
    query(asset_id, question) -> dict

Kept as a simple name -> module map so the reconciler can call any
source generically (including sources it wasn't specifically written
to know about), and so adding a fifth or sixth source later is a
one-line change.
"""

from sources import location_service, maintenance_log, inventory_db, fault_reporting

SOURCES = {
    "location_service": location_service,
    "maintenance_log": maintenance_log,
    "inventory_db": inventory_db,
    "fault_reporting": fault_reporting,
}


def fetch_all(asset_id: str) -> dict[str, list[dict]]:
    """Pull raw reports from every registered source for one asset."""
    return {name: mod.fetch(asset_id) for name, mod in SOURCES.items()}


def query_source(source_name: str, asset_id: str, question: str) -> dict:
    """
    The agent's tool-call interface: ask a specific source a targeted
    follow-up question to resolve ambiguity. This is what the assessment
    means by 'query missing information from available tools' — the
    agent doesn't just compare cached reports, it can go back to a
    source and ask something more specific.
    """
    mod = SOURCES.get(source_name)
    if mod is None:
        return {"answer": f"Unknown source: {source_name}", "source": source_name}
    return mod.query(asset_id, question)
