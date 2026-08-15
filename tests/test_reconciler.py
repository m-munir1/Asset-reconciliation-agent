"""
Unit tests for the reconciliation logic. These don't touch the live
mock sources' fixed demo data — they build FieldReport lists directly,
so the trust-rule logic can be tested against cases the demo scenario
doesn't happen to cover (agreement, authority fallback, unpolicied
fields, etc).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from agent.models import FieldReport, Confidence
from agent.reconciler import ReconciliationAgent


def _report(source, field, value, hours_ago):
    t = datetime(2026, 8, 14, 9, 0, 0) - timedelta(hours=hours_ago)
    return FieldReport(source=source, field_name=field, value=value,
                        reported_at=t, ingested_at=t)


def test_agreement_no_contradiction():
    agent = ReconciliationAgent(verbose=False)
    reports = [
        _report("maintenance_log", "condition", "fine", 2),
        _report("maintenance_log", "condition", "fine", 5),
    ]
    result = agent._resolve_field("X", "condition", reports)
    assert result.contradiction_flagged is False
    assert result.confidence == Confidence.HIGH
    assert result.value == "fine"


def test_authority_field_conflict_resolves_to_authority():
    agent = ReconciliationAgent(verbose=False)
    reports = [
        _report("fault_reporting", "fault_status", "active_fault", 1),
        _report("maintenance_log", "fault_status", "no fault logged", 3),
    ]
    result = agent._resolve_field("X", "fault_status", reports)
    assert result.contradiction_flagged is True
    assert result.chosen_source == "fault_reporting"
    assert result.confidence == Confidence.HIGH
    assert "authoritative" in result.reasoning or "fault_reporting" in result.reasoning


def test_authority_absent_falls_back_with_low_confidence():
    agent = ReconciliationAgent(verbose=False)
    # fault_reporting (the designated authority) says nothing here;
    # only two non-authoritative sources disagree.
    reports = [
        _report("maintenance_log", "fault_status", "no fault logged", 1),
        _report("location_service", "fault_status", "unknown", 3),
    ]
    result = agent._resolve_field("X", "fault_status", reports)
    assert result.contradiction_flagged is True
    assert result.confidence == Confidence.LOW
    assert result.chosen_source == "maintenance_log"  # freshest of the two


def test_contested_field_stale_beacon_loses_to_fresh_physical_confirmation():
    agent = ReconciliationAgent(verbose=False)
    reports = [
        _report("location_service", "location", "Bay 3", 6),   # 6h old, stale
        _report("maintenance_log", "location", "Bay 7", 2),    # 2h old, physical confirm
    ]
    result = agent._resolve_field("AST-1042", "location", reports)
    assert result.value == "Bay 7"
    assert result.chosen_source == "maintenance_log"
    assert result.confidence == Confidence.HIGH
    assert result.contradiction_flagged is True
    # tool calls should be in the trail
    actions = [s.action for s in result.decision_trail]
    assert actions.count("query_tool") >= 2


def test_contested_field_small_gap_stays_medium_confidence():
    agent = ReconciliationAgent(verbose=False)
    # Gap under the staleness threshold -> should NOT trigger the
    # high-confidence override path.
    reports = [
        _report("location_service", "location", "Bay 3", 1.0),
        _report("maintenance_log", "location", "Bay 7", 0.75),
    ]
    result = agent._resolve_field("AST-1042", "location", reports)
    assert result.confidence == Confidence.MEDIUM
    assert result.chosen_source == "maintenance_log"  # still freshest


def test_unpolicied_field_conflict_is_flagged_medium_confidence():
    agent = ReconciliationAgent(verbose=False)
    reports = [
        _report("inventory_db", "serial_number", "SN-1", 5),
        _report("maintenance_log", "serial_number", "SN-2", 1),
    ]
    result = agent._resolve_field("X", "serial_number", reports)
    assert result.contradiction_flagged is True
    assert result.confidence == Confidence.MEDIUM
    assert result.value == "SN-2"  # freshest, as a conservative default


def test_missing_field_with_no_source_data_marks_unknown():
    agent = ReconciliationAgent(verbose=False)
    result = agent._resolve_missing_field("AST-2077", "owner")
    assert result.value is None
    assert result.confidence == Confidence.LOW
    assert result.contradiction_flagged is False


def test_full_reconcile_produces_all_expected_fields():
    agent = ReconciliationAgent(verbose=False)
    result = agent.reconcile("AST-1042")
    from agent.trust_rules import EXPECTED_FIELDS
    for f in EXPECTED_FIELDS:
        assert f in result.fields
    # the known conflict scenario should resolve to Bay 7
    assert result.fields["location"].value == "Bay 7"
    assert result.fields["fault_status"].contradiction_flagged is False


def test_reconciled_asset_query_interface():
    agent = ReconciliationAgent(verbose=False)
    result = agent.reconcile("AST-1042")
    field = result.query("location")
    assert field is not None
    assert field.field_name == "location"
    assert result.query("nonexistent_field") is None


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
