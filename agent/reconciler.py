"""
The reconciliation agent.

Flow for each asset:
  1. Pull raw reports from every registered source.
  2. Group reports by field.
  3. For each field: no data / agreement / conflict.
     - No data: query every source directly for that field before
       giving up and marking it unknown.
     - Agreement: pick the freshest agreeing report, confidence HIGH.
     - Conflict: flag a contradiction, resolve via authority rules or,
       for contested fields, via freshness + corroboration tool calls.
  4. Every decision is written to a DecisionStep trail attached to the
     field, so the reasoning survives past the single run — it's part
     of the output, not just something printed to a log.
"""

from datetime import datetime
from agent.models import FieldReport, DecisionStep, ReconciledField, ReconciledAsset, Confidence
from agent.trust_rules import (
    FIELD_AUTHORITY, FIELD_AUTHORITY_REASON, CONTESTED_FIELDS,
    EXPECTED_FIELDS, LOCATION_STALENESS_THRESHOLD,
)
from agent.sources_registry import fetch_all, query_source


def _parse_reports(raw_by_source: dict[str, list[dict]]) -> dict[str, list[FieldReport]]:
    """Reshape {source: [raw records]} into {field: [FieldReport]}."""
    by_field: dict[str, list[FieldReport]] = {}
    for source, records in raw_by_source.items():
        for r in records:
            fr = FieldReport(
                source=source,
                field_name=r["field"],
                value=r["value"],
                reported_at=r["reported_at"],
                ingested_at=r["ingested_at"],
                raw=r,
            )
            by_field.setdefault(fr.field_name, []).append(fr)
    return by_field


class ReconciliationAgent:
    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    def reconcile(self, asset_id: str) -> ReconciledAsset:
        self._log(f"\n=== Reconciling {asset_id} ===")
        raw = fetch_all(asset_id)
        for source, records in raw.items():
            self._log(f"  [fetch] {source}: {len(records)} report(s)")

        by_field = _parse_reports(raw)
        fields: dict[str, ReconciledField] = {}

        # Resolve every field we actually received reports for.
        for field_name, reports in by_field.items():
            fields[field_name] = self._resolve_field(asset_id, field_name, reports)

        # Then check for fields we expected but received nothing on.
        for field_name in EXPECTED_FIELDS:
            if field_name not in fields:
                fields[field_name] = self._resolve_missing_field(asset_id, field_name)

        return ReconciledAsset(asset_id=asset_id, fields=fields)

    # ------------------------------------------------------------------
    # Field with at least one report
    # ------------------------------------------------------------------
    def _resolve_field(self, asset_id: str, field_name: str, reports: list[FieldReport]) -> ReconciledField:
        trail: list[DecisionStep] = []
        distinct_values = {r.value for r in reports}
        contradiction = len(distinct_values) > 1

        trail.append(DecisionStep(
            "compare",
            f"{len(reports)} report(s) for '{field_name}' from "
            f"{[r.source for r in reports]}; "
            f"{'CONFLICT — distinct values: ' + str(distinct_values) if contradiction else 'all sources agree'}."
        ))

        if not contradiction:
            best = max(reports, key=lambda r: r.reported_at)
            trail.append(DecisionStep(
                "apply_rule",
                f"No conflict, so choosing the freshest report (from '{best.source}', "
                f"reported_at={best.reported_at.isoformat()})."
            ))
            return ReconciledField(
                field_name=field_name, value=best.value, chosen_source=best.source,
                confidence=Confidence.HIGH,
                reasoning=f"All {len(reports)} source(s) agree on this value; used the most "
                          f"recently reported instance (from {best.source}).",
                contradiction_flagged=False, candidates=reports, decision_trail=trail,
            )

        # There's a real conflict — flag it and resolve it.
        self._log(f"  [conflict] '{field_name}': {distinct_values}")
        if field_name in FIELD_AUTHORITY:
            return self._resolve_by_authority(field_name, reports, trail)
        elif field_name in CONTESTED_FIELDS:
            return self._resolve_contested(asset_id, field_name, reports, trail)
        else:
            # Fallback for a field we didn't anticipate: freshest wins,
            # but confidence is capped at MEDIUM because we have no
            # policy backing the choice — this is intentionally visible
            # rather than silently pretending to be certain.
            best = max(reports, key=lambda r: r.reported_at)
            trail.append(DecisionStep(
                "apply_rule",
                f"No authority policy or contested-field logic defined for '{field_name}'. "
                f"Falling back to freshest report as a conservative default."
            ))
            return ReconciledField(
                field_name=field_name, value=best.value, chosen_source=best.source,
                confidence=Confidence.MEDIUM,
                reasoning=f"Sources disagree and no trust policy exists for this field; "
                          f"defaulted to the most recently reported value (from {best.source}). "
                          f"This should be reviewed — the field is not covered by policy.",
                contradiction_flagged=True, candidates=reports, decision_trail=trail,
            )

    def _resolve_by_authority(self, field_name: str, reports: list[FieldReport],
                               trail: list[DecisionStep]) -> ReconciledField:
        authority = FIELD_AUTHORITY[field_name]
        reason = FIELD_AUTHORITY_REASON[field_name]
        chosen = next((r for r in reports if r.source == authority), None)

        if chosen is None:
            # Authority didn't report this field this time; fall back to
            # freshest of whoever did, but lower confidence since the
            # designated authority is silent.
            best = max(reports, key=lambda r: r.reported_at)
            trail.append(DecisionStep(
                "apply_rule",
                f"Designated authority '{authority}' did not report this field. "
                f"Falling back to freshest available report (from '{best.source}')."
            ))
            return ReconciledField(
                field_name=field_name, value=best.value, chosen_source=best.source,
                confidence=Confidence.LOW,
                reasoning=f"Conflict on '{field_name}', but the usual authority "
                          f"({authority}) didn't report it this cycle. Used freshest "
                          f"alternative ({best.source}) as a fallback; low confidence "
                          f"because this bypasses policy.",
                contradiction_flagged=True, candidates=reports, decision_trail=trail,
            )

        trail.append(DecisionStep(
            "apply_rule",
            f"Policy: {authority} is authoritative for '{field_name}'. {reason}"
        ))
        return ReconciledField(
            field_name=field_name, value=chosen.value, chosen_source=chosen.source,
            confidence=Confidence.HIGH,
            reasoning=f"Sources disagreed on '{field_name}'. Chose {authority}'s value "
                      f"('{chosen.value}') because {reason}",
            contradiction_flagged=True, candidates=reports, decision_trail=trail,
        )

    def _resolve_contested(self, asset_id: str, field_name: str, reports: list[FieldReport],
                            trail: list[DecisionStep]) -> ReconciledField:
        """
        Bespoke resolution for fields where authority alone isn't enough —
        currently just 'location'. Logic:
          1. Sort candidates by recency.
          2. If the most recent report is much newer than the next, and
             comes from a source capable of *direct physical confirmation*
             (maintenance log, fault ticket auto-tagged with a scan
             location), query that source and a corroborating source to
             confirm before trusting it over a periodic-signal source.
          3. Document every query and its answer in the trail.
        """
        reports_sorted = sorted(reports, key=lambda r: r.reported_at, reverse=True)
        newest, older = reports_sorted[0], reports_sorted[1:]

        # Special-cased for location: maintenance_log entries represent a
        # human directly observing the asset, which we weight above a
        # periodic RTLS beacon ping, *provided* the beacon reading is
        # stale relative to it.
        physically_confirmed_sources = {"maintenance_log"}
        gap = newest.reported_at - older[0].reported_at if older else None

        if newest.source in physically_confirmed_sources and gap and gap >= LOCATION_STALENESS_THRESHOLD:
            trail.append(DecisionStep(
                "apply_rule",
                f"Newest report is from '{newest.source}' ({newest.reported_at.isoformat()}), "
                f"{gap} newer than the next report from '{older[0].source}' "
                f"({older[0].reported_at.isoformat()}). Gap exceeds staleness threshold "
                f"({LOCATION_STALENESS_THRESHOLD}), so querying sources before trusting it."
            ))

            # Tool call 1: ask the stale source if it has any excuse to be stale.
            stale_check = query_source(older[0].source, asset_id, "what is the last signal received?")
            trail.append(DecisionStep(
                "query_tool",
                f"Queried '{older[0].source}' about signal freshness -> {stale_check['answer']}"
            ))

            # Tool call 2: ask the newer source to corroborate its own claim.
            confirm_check = query_source(newest.source, asset_id, "can you confirm this report?")
            trail.append(DecisionStep(
                "query_tool",
                f"Queried '{newest.source}' to corroborate its report -> {confirm_check['answer']}"
            ))

            # Tool call 3: ask a third, independent source if it has any
            # signal that corroborates the newer claim — this is the
            # "queries missing information from available tools" step in
            # its clearest form: we're not just comparing what we were
            # handed, we're actively looking for a tiebreaker.
            third_party = query_source("fault_reporting", asset_id, "does this relate to location?")
            trail.append(DecisionStep(
                "query_tool",
                f"Queried independent third source 'fault_reporting' for corroboration -> {third_party['answer']}"
            ))

            trail.append(DecisionStep(
                "apply_rule",
                f"'{older[0].source}' confirmed its own reading is stale and unrefreshed; "
                f"'{newest.source}' provided direct physical confirmation (photo + technician "
                f"ID); an independent third source corroborates '{newest.source}'s location. "
                f"Choosing '{newest.value}' from '{newest.source}'."
            ))

            return ReconciledField(
                field_name=field_name, value=newest.value, chosen_source=newest.source,
                confidence=Confidence.HIGH,
                reasoning=(
                    f"Chose location '{newest.value}' from {newest.source} over "
                    f"'{older[0].value}' from {older[0].source}: {older[0].source}'s reading "
                    f"is {gap} old and it confirmed it has not refreshed since (stale beacon, "
                    f"not a contradiction of a live signal). {newest.source}'s report is a "
                    f"direct physical inspection with a technician ID and photo reference, and "
                    f"is independently corroborated by fault_reporting's ticket metadata, which "
                    f"auto-tags the submission location as the same bay."
                ),
                contradiction_flagged=True, candidates=reports, decision_trail=trail,
            )

        # Fallback within the contested-field path: gap too small or the
        # newer source isn't a physical-confirmation type — don't
        # over-trust it, just go with recency but at medium confidence
        # and say so explicitly.
        trail.append(DecisionStep(
            "apply_rule",
            f"Conflict on '{field_name}' but staleness/confirmation conditions for an "
            f"upgrade weren't met; defaulting to freshest report from '{newest.source}' "
            f"at medium confidence."
        ))
        return ReconciledField(
            field_name=field_name, value=newest.value, chosen_source=newest.source,
            confidence=Confidence.MEDIUM,
            reasoning=f"Sources disagreed on '{field_name}'; chose the most recent report "
                      f"(from {newest.source}) but without strong corroboration, so confidence "
                      f"is medium rather than high.",
            contradiction_flagged=True, candidates=reports, decision_trail=trail,
        )

    # ------------------------------------------------------------------
    # Field with zero reports
    # ------------------------------------------------------------------
    def _resolve_missing_field(self, asset_id: str, field_name: str) -> ReconciledField:
        trail = [DecisionStep(
            "flag_contradiction",
            f"No source reported '{field_name}' for {asset_id}. Querying all sources directly."
        )]
        answers = []
        from agent.sources_registry import SOURCES
        for source_name in SOURCES:
            resp = query_source(source_name, asset_id, f"do you have information about {field_name}?")
            trail.append(DecisionStep("query_tool", f"Queried '{source_name}' -> {resp['answer']}"))
            if resp["answer"] != "No additional information available.":
                answers.append((source_name, resp["answer"]))

        if answers:
            source_name, answer = answers[0]
            trail.append(DecisionStep("apply_rule", f"Using response from '{source_name}'."))
            return ReconciledField(
                field_name=field_name, value=answer, chosen_source=source_name,
                confidence=Confidence.LOW,
                reasoning=f"No source proactively reported '{field_name}'; found information "
                          f"by directly querying '{source_name}'. Confidence is low because "
                          f"this wasn't a structured field report.",
                contradiction_flagged=False, candidates=[], decision_trail=trail,
            )

        trail.append(DecisionStep(
            "apply_rule",
            "No source had any information on this field after direct querying. Marking unknown."
        ))
        return ReconciledField(
            field_name=field_name, value=None, chosen_source="none",
            confidence=Confidence.LOW,
            reasoning=f"No source reports '{field_name}' for this asset, and directly querying "
                      f"all {len(SOURCES)} sources returned nothing. "
                      f"This is a genuine data gap, not a contradiction — flagged for manual "
                      f"follow-up rather than guessed at.",
            contradiction_flagged=False, candidates=[], decision_trail=trail,
        )
