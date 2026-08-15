#!/usr/bin/env python3
"""
Asset State Reconciliation Agent — entry point.

Usage:
    python main.py                     # reconcile the demo assets
    python main.py AST-1042            # reconcile one specific asset
    python main.py AST-1042 --query location   # print just one field's audit trail
"""

import json
import sys
from agent.reconciler import ReconciliationAgent
from agent.llm_narrator import narrate

DEMO_ASSETS = ["AST-1042", "AST-2077"]


def print_field_audit(reconciled_asset, field_name: str) -> None:
    f = reconciled_asset.query(field_name)
    if f is None:
        print(f"No such field '{field_name}' on {reconciled_asset.asset_id}")
        return
    print(json.dumps(f.to_dict(), indent=2, default=str))


def main():
    args = sys.argv[1:]
    query_field = None
    if "--query" in args:
        idx = args.index("--query")
        query_field = args[idx + 1]
        args = args[:idx]

    asset_ids = args if args else DEMO_ASSETS

    agent = ReconciliationAgent(verbose=True)

    for asset_id in asset_ids:
        result = agent.reconcile(asset_id)

        if query_field:
            print_field_audit(result, query_field)
            continue

        print("\n--- Reconciled Record (JSON) ---")
        print(json.dumps(result.to_dict(), indent=2, default=str))

        print("\n--- Reviewer Summary ---")
        print(narrate(result))
        print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
