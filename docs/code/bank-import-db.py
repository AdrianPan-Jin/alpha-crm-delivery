"""Database helpers: one psycopg connection factory, plus small SQL helpers."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row


def dsn() -> str:
    return os.environ.get("BANK_DATABASE_URL", "postgresql://postgres@127.0.0.1:55433/bank_demo")


@contextmanager
def connect(autocommit: bool = False) -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(dsn(), row_factory=dict_row, autocommit=autocommit)
    try:
        yield conn
    finally:
        conn.close()


def fetch_one(sql: str, params: tuple | None = None) -> dict | None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()


def execute(sql: str, params: tuple | None = None) -> int:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.rowcount
