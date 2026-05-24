#!/usr/bin/env python3
"""Set a local development user's role.

Usage:
    python backend/scripts/set_user_role.py demi2014 parent
    python backend/scripts/set_user_role.py demi2014 child
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "backend" / "data" / "creative_agent.db"
ALLOWED_ROLES = {"child", "parent"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set a local user's role.")
    parser.add_argument(
        "identifier",
        help="User id, username, or email to update.",
    )
    parser.add_argument(
        "role",
        choices=sorted(ALLOWED_ROLES),
        help="Role to assign.",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help=f"SQLite DB path. Defaults to {DEFAULT_DB}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT user_id, username, email, role
            FROM users
            WHERE user_id = ? OR username = ? OR email = ?
            """,
            (args.identifier, args.identifier, args.identifier),
        ).fetchone()

        if row is None:
            raise SystemExit(f"No user found for: {args.identifier}")

        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE users SET role = ?, updated_at = ? WHERE user_id = ?",
            (args.role, now, row["user_id"]),
        )
        conn.commit()

        print(
            f"Updated {row['username']} ({row['email']}) "
            f"from {row['role']} to {args.role}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
