"""Load the synthetic demo dataset through the public API (SPEC §6).

Seeding deliberately goes through POST /api/v1/entity-plans and
POST /api/v1/broker-submissions rather than writing to the database, so a
seed run is also an end-to-end proof of the ingestion path.

Usage:
    uvicorn app.main:app &          # start the API first
    python scripts/seed.py [--base-url http://127.0.0.1:8000] [--api-key demo-key]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.demo_data import batched, generate_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the Broker Intelligence demo API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="demo-key")
    args = parser.parse_args()

    api = f"{args.base_url.rstrip('/')}/api/v1"
    headers = {"X-API-Key": args.api_key}
    started = time.monotonic()

    dataset = generate_dataset()
    print(
        f"Generated {len(dataset['brokers'])} brokers, {len(dataset['plans'])} plans, "
        f"{len(dataset['submissions'])} submissions (seed 42)."
    )

    with httpx.Client(headers=headers, timeout=120) as client:
        health = client.get(f"{api}/health")
        health.raise_for_status()

        totals = {"accepted": 0, "updated": 0, "rejected": 0}

        response = client.post(f"{api}/reference/brokers", json={"records": dataset["brokers"]})
        response.raise_for_status()

        for name, records, batch_size in (
            ("entity-plans", dataset["plans"], 500),
            ("broker-submissions", dataset["submissions"], 1000),
        ):
            for chunk in batched(records, batch_size):
                response = client.post(f"{api}/{name}", json={"records": chunk})
                response.raise_for_status()
                report = response.json()
                totals["accepted"] += report["accepted"]
                totals["updated"] += report["updated"]
                totals["rejected"] += len(report["rejected"])
                if report["rejected"]:
                    for reject in report["rejected"][:5]:
                        print(f"  REJECTED {name}[{reject['index']}] {reject['key']}: "
                              f"{reject['errors']}")

    elapsed = time.monotonic() - started
    print(
        f"Done in {elapsed:.1f}s — accepted {totals['accepted']}, updated {totals['updated']}, "
        f"rejected {totals['rejected']}."
    )
    return 1 if totals["rejected"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
