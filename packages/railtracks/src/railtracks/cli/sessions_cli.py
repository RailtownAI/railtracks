"""`railtracks sessions ...` and `railtracks migrate-json-to-sqlite`.

Recovers the debugging ergonomics that raw JSON files provided:
``sessions show <id>`` re-emits the legacy JSON shape (pipe to jq),
``sessions sql`` drops into a sqlite3 REPL on the workspace DB, and the
migrate command imports pre-cut JSON session files.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from railtracks.paths import resolve_railtracks_home

from .io import print_error, print_status, print_success


def _engine():
    from sqlmodel import SQLModel

    from railtracks.persistence.connection import get_engine

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    return engine


def sessions_command(args: list[str]) -> None:
    """Dispatch `railtracks sessions <subcommand>`."""
    if not args:
        print_error("Usage: railtracks sessions <list|show|sql>")
        sys.exit(1)

    subcommand, rest = args[0], args[1:]
    if subcommand == "list":
        _list_sessions()
    elif subcommand == "show":
        if not rest:
            print_error("Usage: railtracks sessions show <session-id>")
            sys.exit(1)
        _show_session(rest[0])
    elif subcommand == "sql":
        _open_sql_repl()
    else:
        print_error(f"Unknown sessions subcommand: {subcommand}")
        print_status("Available: list, show <id>, sql")
        sys.exit(1)


def _list_sessions() -> None:
    from sqlalchemy import func
    from sqlmodel import Session as DBSession
    from sqlmodel import select

    from railtracks.persistence.models import LLMCallRow, SessionRow

    with DBSession(_engine()) as s:
        sessions = s.exec(
            select(SessionRow).order_by(SessionRow.start_time.desc())
        ).all()
        costs = dict(
            s.exec(
                select(
                    LLMCallRow.session_id, func.sum(LLMCallRow.total_cost)
                ).group_by(LLMCallRow.session_id)
            ).all()
        )

    if not sessions:
        print_status("No sessions in the workspace database.")
        return

    header = f"{'SESSION ID':<38} {'FLOW':<24} {'STATUS':<11} {'STARTED':<20} {'COST':>10}"
    print(header)
    print("-" * len(header))
    for row in sessions:
        started = datetime.fromtimestamp(row.start_time).strftime("%Y-%m-%d %H:%M:%S")
        # never-closed sessions read as abandoned, not silently 'open'
        status = "abandoned" if (row.status == "open" and row.end_time is None) else row.status
        cost = costs.get(row.session_id)
        cost_str = f"${cost:.5f}" if cost else "-"
        print(
            f"{row.session_id:<38} {(row.flow_name or '-'):<24} {status:<11} {started:<20} {cost_str:>10}"
        )


def _show_session(session_id: str) -> None:
    from railtracks.persistence.export import legacy_session_payload

    payload = legacy_session_payload(_engine(), session_id)
    if payload is None:
        print_error(f"Session not found: {session_id}")
        sys.exit(1)
    print(json.dumps(payload, indent=2, default=str))


def _open_sql_repl() -> None:
    db_path = resolve_railtracks_home() / "data" / "railtracks.db"
    if not db_path.exists():
        print_error(f"No workspace database at {db_path}")
        sys.exit(1)
    print_status(f"Opening sqlite3 on {db_path} (Ctrl+D to exit)")
    os.execvp("sqlite3", ["sqlite3", str(db_path)])


def migrate_json_command(args: list[str]) -> None:
    """`railtracks migrate-json-to-sqlite [path]` — import legacy JSON files."""
    from railtracks.persistence.importer import import_legacy_files

    if args:
        target = Path(args[0])
    else:
        target = resolve_railtracks_home() / "data" / "sessions"

    if target.is_file():
        paths = [target]
    elif target.is_dir():
        paths = sorted(target.glob("*.json"))
    else:
        print_error(f"Path not found: {target}")
        sys.exit(1)

    if not paths:
        print_status(f"No .json files found in {target}")
        return

    imported, skipped = import_legacy_files(_engine(), paths)
    if imported:
        print_success(f"Imported {len(imported)} session(s) into the workspace DB.")
    for name in skipped:
        print_status(f"Skipped {name} (already imported, no session_id, or unreadable)")
