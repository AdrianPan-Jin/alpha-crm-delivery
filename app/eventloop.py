"""Windows event loop policy helper.

psycopg's async mode refuses the ProactorEventLoop that Python uses by default on
Windows, so every entry point (app, alembic, scripts) must install the selector
policy before an event loop is created.
"""
from __future__ import annotations

import asyncio
import sys


def install() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
