#!/usr/bin/env python3
"""CLI: report what still needs electrician review, or emit a review worksheet.

    python scripts/review_status.py              # human-readable status summary
    python scripts/review_status.py --worksheet  # per-assembly checklist (CSV) to stdout
    python scripts/review_status.py --json        # machine-readable summary

The reporting logic lives in ``quoteforge_api.review`` so it stays unit-tested.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make the package importable when run as a standalone script from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quoteforge_api.data_integrity import validate_data  # noqa: E402
from quoteforge_api.review import format_summary, summary, worksheet_csv  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report electrician-review status of QuoteForge data (§8/§21/§24.6)."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--worksheet", action="store_true",
        help="Emit a per-assembly review worksheet as CSV to stdout.",
    )
    group.add_argument(
        "--json", action="store_true", help="Emit the status summary as JSON.",
    )
    group.add_argument(
        "--validate", action="store_true",
        help="Check cross-file data integrity (SKUs, formula params); exit 1 on problems.",
    )
    args = parser.parse_args()

    if args.worksheet:
        sys.stdout.write(worksheet_csv())
    elif args.json:
        print(json.dumps(summary(), indent=2))
    elif args.validate:
        problems = validate_data()
        if problems:
            print(f"Data integrity: {len(problems)} problem(s)")
            for p in problems:
                print(f"  - {p}")
            sys.exit(1)
        print("Data integrity: OK")
    else:
        print(format_summary(summary()))


if __name__ == "__main__":
    main()
