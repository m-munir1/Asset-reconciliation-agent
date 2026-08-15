# Asset State Reconciliation Agent

An agent that pulls asset-state reports from four independent, conflicting
data sources and produces a single reconciled record — with a fully
auditable explanation of *why* it trusted what it trusted for every field.

Built for the LEC AI build assessment.

## The problem this solves

Four systems know things about the same physical asset, and they don't
agree:

- **`location_service`** — RTLS/beacon pings. Fast-updating, but goes stale
  silently if a beacon drops signal (it doesn't know it's wrong).
- **`maintenance_log`** — technician entries. Slow, but reflects direct
  physical inspection (photo + technician ID attached).
- **`inventory_db`** — system of record for asset classification and
  ownership. Rarely wrong about *what* an asset is, frequently wrong about
  *where* it currently is (only refreshed at quarterly audits).
- **`fault_reporting`** — operator-submitted incident tickets. The only
  source with both the mechanism and incentive to surface faults fast.

No single source is "the truth." The agent's job is to decide, per field,
which source to believe, detect when they contradict each other, ask
follow-up questions when it isn't sure, and write down its reasoning in a
form someone else can check later.

## How it works

```
sources/            four mock data sources (fetch + query "tools")
agent/
  models.py          FieldReport, ReconciledField, decision-trail data model
  trust_rules.py      the actual trust policy — plain data, not buried in a prompt
  sources_registry.py generic fetch/query interface over all sources
  reconciler.py        the decision engine (this is the core of the assessment)
  llm_narrator.py      optional Gemini call for a human-readable summary
main.py               CLI entry point
tests/test_reconciler.py   unit tests for every decision path
```

**The reconciliation logic itself is deterministic and has zero external
dependencies.** That's a deliberate choice, not a missed opportunity to use
an LLM everywhere: a reconciliation decision needs to be reproducible and
defensible on review, and "the model felt like it" is not an audit trail.
Gemini is used for exactly one thing — turning the structured decision
trail into a readable paragraph for a human reviewer — and the whole
system runs and passes its tests with no API key at all.

### Three ways a field gets resolved

1. **All sources agree** → take the freshest report, confidence `high`,
   no contradiction flagged.
2. **Sources disagree, and one source has policy authority for that field**
   (e.g. `fault_reporting` is authoritative for `fault_status` because
   it's the only source fed by direct operator reports) → take the
   authoritative source's value, explain the policy reason, confidence
   `high`. If the authority didn't report anything this cycle, fall back
   to the freshest alternative at `low` confidence — the gap is disclosed,
   not hidden.
3. **Sources disagree and no fixed authority applies** (currently just
   `location`) → this is the hard case the assessment is really testing.
   The agent:
   - Sorts candidate reports by recency.
   - If the newest report is meaningfully newer than the rest *and* comes
     from a source capable of direct physical confirmation, it doesn't
     just trust recency blindly — it **calls `query()` on the stale
     source** to check if it has an excuse (e.g. "no signal in 6 hours"),
     **calls `query()` on the new source** to ask it to corroborate itself,
     and **calls `query()` on a third, independent source** looking for a
     tiebreaker. Every call and its answer is written to the decision
     trail before a value is chosen.
   - If the gap is small or the new report isn't a physical-confirmation
     type, it still picks the freshest value but caps confidence at
     `medium` and says explicitly that the choice isn't strongly backed.
4. **No source reports a field at all** → the agent doesn't leave a gap
   silently. It actively queries every source asking about that field
   before marking it `unknown` at `low` confidence. This is the "missing
   information" path, exercised by `AST-2077` (no fault, condition, or
   owner data anywhere).

Every one of these paths writes a `DecisionStep` trail — an ordered list
of `compare` / `query_tool` / `apply_rule` / `flag_contradiction` entries —
onto the field, so the reasoning is part of the output, not something
you'd have to re-derive from logs.

### Querying the audit trail after the fact

```bash
python main.py AST-1042 --query location
```

prints just that field's chosen value, source, confidence, every candidate
considered, and the full step-by-step trail that led to the decision —
this is the "queryable and reviewable" requirement in the brief, not just
a nice-to-have.

## Running it

```bash
pip install -r requirements.txt   # only needed for pytest + optional Gemini
python main.py                    # reconciles both demo assets
python main.py AST-1042           # just one asset
python main.py AST-1042 --query location   # audit trail for one field
python -m pytest tests/ -v        # 9 tests covering every decision path
```

No API key is required for any of the above. To see the LLM-written
summary instead of the template one:

```bash
cp .env.example .env      # then fill in GEMINI_API_KEY
export $(cat .env | xargs)
python main.py
```

Get a free Gemini key at https://aistudio.google.com/apikey.

## The demo scenario (`AST-1042`)

- `location_service` last pinged **Bay 3**, 6 hours ago.
- `maintenance_log` says a technician physically moved it to **Bay 7**,
  2 hours ago, with a photo and technician ID attached.
- `inventory_db` still lists **Bay 3** as the "home location" from a
  quarterly audit 20 days ago.
- `fault_reporting` has an open ticket against the asset, submitted via a
  handheld scanner that auto-tags submission location — at **Bay 7**.

Three sources, three different timestamps, two different answers. The
agent doesn't just pick the newest timestamp and move on — it checks
*why* the old one is old (stale beacon, confirmed via `query()`), checks
*why* the new one should be trusted more than a ping (physical inspection,
confirmed via `query()`), and finds independent corroboration from a
fourth, unrelated system before committing to `Bay 7`. All of that is in
the decision trail, not just the final answer.

## What I'd do with more time

- **Real source adapters.** The four sources are stubbed as Python
  functions with fixed demo data on purpose — the assessment says fetching
  data isn't the hard part, and I didn't want to spend the limited time on
  HTTP boilerplate instead of the reconciliation logic. Swapping `fetch()`
  for a real API/DB client is a contained change; the trust engine doesn't
  care where reports came from.
- **Confidence as a function of source track record, not just policy.**
  Right now confidence is set by which *branch* of logic resolved the
  field. A more realistic version would maintain a rolling accuracy score
  per source per field (e.g. "location_service has been wrong 40% of the
  time it disagreed with maintenance_log over the last quarter") and fold
  that into both the decision and the confidence score.
- **True out-of-order and late-arriving updates.** The current model
  assumes all reports for an asset are visible at reconciliation time. A
  streaming version would need to handle a report arriving *after* a
  reconciled record was already produced and published, and decide
  whether to revise history or just flag the anomaly.
- **A second contested field.** `location` is the only field with bespoke
  resolution logic; a real system would eventually need the same treatment
  for things like `operational_status` (is it in use right now?) where
  multiple sources can plausibly know and none is a fixed authority.
  The pattern in `_resolve_contested` generalizes, but I kept it to one
  worked example rather than over-building speculative cases.
- **Gemini function-calling instead of a fixed query sequence.** Right now
  the contested-field resolution calls a fixed sequence of `query()` tools.
  A more agentic version would let Gemini itself decide which follow-up
  questions to ask and in what order, given the conflict — I kept the
  sequence deterministic here so the core logic stays reproducible and
  testable without depending on API availability, but exposing `query()`
  as a real function-calling tool for Gemini to drive is a natural next
  step.
