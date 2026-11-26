"""Seed six deterministic E2E scenarios into the membership database.

Scenarios
  empty         : nothing is written (the database stays clean)
  single        : one company with one primary contact
  bulk        : N companies x M contacts (default 50 x 2)
  duplicate   : two rows sharing the same external_key (idempotent upsert target)
  soft-deleted: one company already soft deleted + one alive company
  mixed       : all of the above in a single run

Guarantees
  * idempotent: every row's external_key is prefixed with the run id, and a second
    invocation with the same --run-id updates instead of inserting
  * E2E_ENV=prod: exits 0 without opening a database connection
  * a manifest is written to out/seed-<run_id>.json with every created id
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402

from scripts.common import (  # noqa: E402
    database_url,
    new_run_id,
    org_id,
    refuse_in_prod,
    write_manifest,
)

SCENARIOS = ("empty", "single", "bulk", "duplicate", "soft-deleted", "mixed")

COMPANIES = [
    ("杭州云帆科技有限公司", "91330100MA2H8K7X1A", "软件和信息技术服务业", "gold"),
    ("上海禾木供应链有限公司", "91310115MA1K4R2T3B", "批发业", "normal"),
    ("深圳前海数智科技有限公司", "91440300MA5F7Y6Q2C", "软件和信息技术服务业", "platinum"),
    ("成都锦里文化传媒有限公司", "91510100MA6C9P4W5D", "商务服务业", "silver"),
    ("北京天成医疗器械有限公司", "91110108MA01J3S8E", "批发业", "normal"),
]


def _contact(company_idx: int, i: int) -> tuple[str, str, str]:
    names = ["张伟", "李娜", "王强", "刘洋", "陈静"]
    phones = [f"1380013{company_idx:02d}{i:02d}", f"1390013{company_idx:02d}{i:02d}"]
    return names[(company_idx + i) % len(names)], phones[i % 2], ["总经理", "采购总监", "技术负责人"][i % 3]


async def _upsert_company(cur, run_id: str, idx: int, org: uuid.UUID, deleted: bool = False) -> uuid.UUID:
    name, code, industry, level = COMPANIES[idx % len(COMPANIES)]
    external_key = f"{run_id}:company:{idx}"
    await cur.execute(
        """
        INSERT INTO companies (org_id, name, unified_credit_code, industry, level, external_key, deleted_at)
        VALUES (%s, %s, %s, %s, %s, %s, CASE WHEN %s THEN now() ELSE NULL END)
        ON CONFLICT (org_id, external_key) DO UPDATE
            SET name = EXCLUDED.name,
                industry = EXCLUDED.industry,
                level = EXCLUDED.level,
                updated_at = now()
        RETURNING id
        """,
        (org, name, code, industry, level, external_key, deleted),
    )
    return (await cur.fetchone())[0]


async def _upsert_contact(cur, run_id: str, org: uuid.UUID, company_id: uuid.UUID, idx: int, i: int) -> uuid.UUID:
    name, phone, title = _contact(idx, i)
    await cur.execute(
        """
        INSERT INTO contacts (org_id, company_id, name, phone, title, is_primary)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (org_id, phone) WHERE deleted_at IS NULL DO UPDATE
            SET name = EXCLUDED.name, title = EXCLUDED.title, updated_at = now()
        RETURNING id
        """,
        (org, company_id, name, phone, title, i == 0),
    )
    return (await cur.fetchone())[0]


async def run(scenario: str, run_id: str, bulk_companies: int, bulk_contacts: int) -> dict:
    org = org_id()
    if scenario == "empty":
        return {"run_id": run_id, "scenario": scenario, "companies": [], "contacts": []}

    manifest: dict = {"run_id": run_id, "scenario": scenario, "org_id": str(org), "companies": [], "contacts": []}
    async with await psycopg.AsyncConnection.connect(database_url()) as conn:
        async with conn.cursor() as cur:
            if scenario in ("single", "mixed"):
                cid = await _upsert_company(cur, run_id, 0, org)
                manifest["companies"].append(str(cid))
                manifest["contacts"].append(str(await _upsert_contact(cur, run_id, org, cid, 0, 0)))

            if scenario in ("bulk", "mixed"):
                for idx in range(bulk_companies):
                    cid = await _upsert_company(cur, run_id, idx, org)
                    manifest["companies"].append(str(cid))
                    for i in range(bulk_contacts):
                        manifest["contacts"].append(str(await _upsert_contact(cur, run_id, org, cid, idx, i)))

            if scenario in ("duplicate", "mixed"):
                cid = await _upsert_company(cur, run_id, 1, org)  # same external_key as bulk row #1
                manifest["companies"].append(str(cid))

            if scenario in ("soft-deleted", "mixed"):
                cid = await _upsert_company(cur, run_id, 2, org, deleted=True)
                manifest["companies"].append(str(cid))
                alive = await _upsert_company(cur, run_id, 3, org)
                manifest["companies"].append(str(alive))

        await conn.commit()
    manifest["counts"] = {"companies": len(manifest["companies"]), "contacts": len(manifest["contacts"])}
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="mixed", choices=SCENARIOS + ("all",))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--companies", type=int, default=50, help="bulk scenario: number of companies")
    parser.add_argument("--contacts-per-company", type=int, default=2)
    args = parser.parse_args(argv)

    if refuse_in_prod("seed.py"):
        return 0

    run_id = args.run_id or new_run_id()
    scenarios = [s for s in SCENARIOS if s != "empty"] if args.scenario == "all" else [args.scenario]

    for scenario in scenarios:
        manifest = asyncio.run(run(scenario, run_id, args.companies, args.contacts_per_company))
        path = write_manifest(f"{run_id}-{scenario}", manifest)
        print(json.dumps({"scenario": scenario, **manifest["counts"], "manifest": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
