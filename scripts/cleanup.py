"""Remove everything a seed run created, in two explicit phases.

Phase 1 (soft): mark the run's companies deleted_at = now()
Phase 2 (hard): physically delete those companies and their contacts

Rows are selected by the external_key prefix "<run_id>:", which is exactly what
seed.py writes, so unrelated production data is never touched.

  python scripts/cleanup.py --run-id run-abc --dry-run
  python scripts/cleanup.py --run-id run-abc            # soft then hard
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402

from scripts.common import database_url, refuse_in_prod  # noqa: E402


async def cleanup(run_id: str, dry_run: bool, skip_hard: bool) -> dict:
    pattern = f"{run_id}%"
    counts = {"companies_soft_deleted": 0, "contacts_soft_deleted": 0, "companies_hard_deleted": 0, "contacts_hard_deleted": 0}
    async with await psycopg.AsyncConnection.connect(database_url()) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM companies WHERE external_key LIKE %s", (pattern,))
            company_ids = [row[0] for row in await cur.fetchall()]
            counts["matched_companies"] = len(company_ids)
            if not company_ids or dry_run:
                await conn.rollback()
                return counts

            await cur.execute(
                "UPDATE companies SET deleted_at = now() WHERE id = ANY(%s) AND deleted_at IS NULL RETURNING id",
                (company_ids,),
            )
            counts["companies_soft_deleted"] = len(await cur.fetchall())

            await cur.execute(
                "UPDATE contacts SET deleted_at = now() WHERE company_id = ANY(%s) AND deleted_at IS NULL RETURNING id",
                (company_ids,),
            )
            counts["contacts_soft_deleted"] = len(await cur.fetchall())

            if not skip_hard:
                await cur.execute("DELETE FROM contacts WHERE company_id = ANY(%s)", (company_ids,))
                counts["contacts_hard_deleted"] = cur.rowcount
                await cur.execute("DELETE FROM companies WHERE id = ANY(%s)", (company_ids,))
                counts["companies_hard_deleted"] = cur.rowcount

        await conn.commit()
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--dry-run", action="store_true", help="only report how many rows would be affected")
    parser.add_argument("--skip-hard", action="store_true", help="stop after the soft delete phase")
    args = parser.parse_args(argv)

    if refuse_in_prod("cleanup.py"):
        return 0

    counts = asyncio.run(cleanup(args.run_id, args.dry_run, args.skip_hard))
    print(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
