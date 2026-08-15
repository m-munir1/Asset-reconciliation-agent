# Asset State Reconciliation Agent

An agent that pulls asset-state reports from four independent, conflicting
data sources and produces a single reconciled record — with a fully
auditable explanation of *why* it trusted what it trusted for every field.

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

