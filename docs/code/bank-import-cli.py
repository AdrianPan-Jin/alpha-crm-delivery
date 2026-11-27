"""CLI: import one file with one template and print the batch summary as JSON."""
from __future__ import annotations

import argparse
import json
import sys

from .importer import Template, import_file


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="app.bank.cli")
    ap.add_argument("--template", required=True, help="模板 JSON 路径")
    ap.add_argument("--file", required=True, help="流水文件（CSV 或 XLSX）")
    ap.add_argument("--org-id", default="11111111-1111-1111-1111-111111111111")
    a = ap.parse_args(argv)

    template = Template.from_file(a.template)
    result = import_file(template, a.file, org_id=a.org_id)
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    return 0 if not result.errors else 1


if __name__ == "__main__":
    sys.exit(main())
