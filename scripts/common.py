"""Shared helpers for the E2E data scripts (seed / cleanup).

Everything is driven by environment variables:
  DATABASE_URL  postgresql+psycopg://user@host:port/db   (SQLAlchemy form is accepted,
                the "+psycopg" driver suffix is stripped for psycopg's own parser)
  E2E_ENV       when set to "prod" the scripts refuse to touch the database
  E2E_ORG_ID    organisation uuid used for every inserted row (defaults to a fixed uuid)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

if sys.platform == "win32":  # psycopg async cannot run on the Proactor loop
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

DEFAULT_ORG = uuid.UUID("11111111-1111-1111-1111-111111111111")
MANIFEST_DIR = Path(__file__).resolve().parent.parent / "out"


def database_url() -> str:
    raw = os.environ.get("DATABASE_URL", "postgresql://postgres@127.0.0.1:55432/alpha")
    return raw.replace("+psycopg", "").replace("+asyncpg", "")


def org_id() -> uuid.UUID:
    return uuid.UUID(os.environ.get("E2E_ORG_ID", str(DEFAULT_ORG)))


def is_prod() -> bool:
    return os.environ.get("E2E_ENV", "").strip().lower() == "prod"


def refuse_in_prod(script: str) -> bool:
    """Return True (and exit 0 without touching the network) when running against prod."""
    if is_prod():
        print(f"{script}: E2E_ENV=prod -> refusing to write, no request sent")
        return True
    return False


def new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:12]}"


def manifest_path(run_id: str) -> Path:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    return MANIFEST_DIR / f"seed-{run_id}.json"


def write_manifest(run_id: str, payload: dict) -> Path:
    path = manifest_path(run_id)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_manifest(run_id: str) -> dict:
    path = manifest_path(run_id)
    if not path.exists():
        raise SystemExit(f"manifest for {run_id} not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def log(msg: str) -> None:
    print(msg, file=sys.stderr)
