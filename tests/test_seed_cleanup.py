from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def run_script(name: str, *args: str, db_url: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": db_url, "PYTHONIOENCODING": "utf-8", **(env_extra or {})}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def count_rows(db_url: str, table: str) -> int:
    import psycopg

    raw = db_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(raw) as conn:
        with conn.cursor() as cur:
            cur.execute(f"select count(*) from {table}")
            return cur.fetchone()[0]


@pytest.mark.parametrize("scenario", ["single", "bulk", "duplicate", "soft-deleted", "mixed"])
def test_seed_is_idempotent_and_cleanup_removes_everything(db_url, scenario):
    run_id = f"run-test-{scenario}"
    first = run_script("seed.py", "--scenario", scenario, "--run-id", run_id, "--companies", "5", db_url=db_url)
    assert first.returncode == 0, first.stderr
    companies_after_first = count_rows(db_url, "companies")
    contacts_after_first = count_rows(db_url, "contacts")

    second = run_script("seed.py", "--scenario", scenario, "--run-id", run_id, "--companies", "5", db_url=db_url)
    assert second.returncode == 0, second.stderr
    assert count_rows(db_url, "companies") == companies_after_first, "re-running must not insert duplicates"
    assert count_rows(db_url, "contacts") == contacts_after_first

    result = run_script("cleanup.py", "--run-id", run_id, db_url=db_url)
    assert result.returncode == 0, result.stderr
    assert count_rows(db_url, "companies") == 0
    assert count_rows(db_url, "contacts") == 0


def test_dry_run_changes_nothing(db_url):
    run_script("seed.py", "--scenario", "single", "--run-id", "run-dry", db_url=db_url)
    before = count_rows(db_url, "companies")
    result = run_script("cleanup.py", "--run-id", "run-dry", "--dry-run", db_url=db_url)
    assert result.returncode == 0, result.stderr
    assert count_rows(db_url, "companies") == before


def test_prod_env_sends_no_request(db_url):
    before = count_rows(db_url, "companies")
    result = run_script("seed.py", "--scenario", "mixed", db_url=db_url, env_extra={"E2E_ENV": "prod"})
    assert result.returncode == 0
    assert "E2E_ENV=prod" in result.stdout
    assert count_rows(db_url, "companies") == before
