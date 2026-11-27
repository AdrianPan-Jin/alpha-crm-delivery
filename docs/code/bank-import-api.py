"""FastAPI surface for the bank import (S4-FIN-011).

`POST /api/finance/bank-imports` creates a batch row, schedules the parse+insert in
a background task and returns 202 with the batch id; the client polls
`GET /api/finance/bank-imports/{id}`. Swap `BackgroundTasks` for Celery/RQ in
production — the integration point is `_run_import`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import db
from .importer import Template, create_batch, ensure_template, import_file

ORG_ID = "11111111-1111-1111-1111-111111111111"


class CreateImport(BaseModel):
    template_id: str = Field(..., description="bank_statement_templates.id")
    file_path: str = Field(..., description="服务端可读的文件路径（CSV / XLSX）")
    org_id: str = ORG_ID


def _template_from_row(row: dict[str, Any]) -> Template:
    return Template.from_dict(
        {"code": row["code"], "name": row["name"], "account": row["account_no"], "columns": row["column_map"]}
    )


def _run_import(template: Template, file_path: str, org_id: str, batch_id: str) -> None:
    try:
        import_file(template, file_path, org_id=org_id, batch_id=batch_id)
    except Exception as exc:  # noqa: BLE001 - the batch row must carry the failure
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update bank_import_batches set status='failed', errors=%s::jsonb, finished_at=now() where id=%s",
                    (f'[{{"line": 0, "reason": {str(exc)!r}}}]'.replace("'", '"'), batch_id),
                )
                conn.commit()


def _batch_result(batch_id: str) -> dict[str, Any]:
    row = db.fetch_one(
        """
        select id, file_name, status, total_rows, added, skipped_duplicate, errors, started_at, finished_at
          from bank_import_batches where id = %s
        """,
        (batch_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="batch not found")
    return {
        "batch_id": str(row["id"]),
        "file_name": row["file_name"],
        "status": row["status"],
        "total_rows": row["total_rows"],
        "added": row["added"],
        "skipped_duplicate": row["skipped_duplicate"],
        "errors": row["errors"],
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        "finished_at": row["finished_at"].isoformat() if row["finished_at"] else None,
    }


def create_app() -> FastAPI:
    app = FastAPI(title="Bank statement import", version="1.0.0")

    @app.post("/api/finance/bank-imports", status_code=202)
    def create_import(payload: CreateImport, background: BackgroundTasks):
        row = db.fetch_one(
            "select id, code, name, account_no, column_map from bank_statement_templates "
            "where id = %s and deleted_at is null",
            (payload.template_id,),
        )
        if row is None:
            raise HTTPException(status_code=404, detail="template not found")
        if not Path(payload.file_path).exists():
            raise HTTPException(status_code=400, detail="file not found on server")
        template = _template_from_row(row)
        template_id = ensure_template(template, payload.org_id)
        batch_id = create_batch(payload.org_id, template_id, Path(payload.file_path).name)
        background.add_task(_run_import, template, payload.file_path, payload.org_id, batch_id)
        return {"batch_id": batch_id, "status": "running"}

    @app.get("/api/finance/bank-imports/{batch_id}")
    def get_import(batch_id: str):
        return _batch_result(batch_id)

    return app


app = create_app()
