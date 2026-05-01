#!/usr/bin/env python3
"""Enable local-development CORS for the FastAPI backend.

This performs a tiny, auditable patch to apps/api-python/main.py:
- adds CORSMiddleware import
- adds middleware immediately after app creation

It is intentionally idempotent.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "apps" / "api-python" / "main.py"

IMPORT_FROM = "from fastapi import FastAPI, HTTPException, Query\n"
IMPORT_TO = "from fastapi import FastAPI, HTTPException, Query\nfrom fastapi.middleware.cors import CORSMiddleware\n"

APP_LINE = 'app = FastAPI(title="Universal Agent Runtime (UAR)", version="0.2.2")\n'
MIDDLEWARE = '''app = FastAPI(title="Universal Agent Runtime (UAR)", version="0.2.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
'''


def main() -> int:
    text = MAIN.read_text()
    original = text

    if "from fastapi.middleware.cors import CORSMiddleware" not in text:
        if IMPORT_FROM not in text:
            print("ERROR: FastAPI import anchor not found", file=sys.stderr)
            return 1
        text = text.replace(IMPORT_FROM, IMPORT_TO, 1)

    if "app.add_middleware(\n    CORSMiddleware," not in text:
        if APP_LINE not in text:
            print("ERROR: app creation anchor not found", file=sys.stderr)
            return 1
        text = text.replace(APP_LINE, MIDDLEWARE, 1)

    if text == original:
        print("Dev CORS already enabled.")
        return 0

    MAIN.write_text(text)
    print("Dev CORS enabled in apps/api-python/main.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
