"""
Hub Group Repository (#447)

CRUD operations for the hub_groups and hub_group_memberships tables.
Foundation for Epic #437 (Content Hub).

Design notes:
- group_id is a UUID-style surrogate. slug is generated from name with a
  numeric suffix on collision (e.g. "dragons", "dragons-2", ...).
- Public groups have invite_token = NULL; private groups get a 16-byte
  url-safe token at creation time.
- All timestamps are ISO 8601 (UTC-naive isoformat), matching the
  convention used by user_repository / agent_repository.
- Member count is denormalized on hub_groups.member_count and updated
  atomically by the join/leave methods. Read paths NEVER recount on the
  fly.
"""

from dataclasses import dataclass
from datetime import datetime
from secrets import token_urlsafe
from typing import List, Optional
from uuid import uuid4

from .connection import db_manager


_SLUG_KEEP = set("abcdefghijklmnopqrstuvwxyz0123456789-")


def _slugify(name: str) -> str:
    """Lowercase, ASCII-ish, kebab-case slug. Collisions resolved by caller."""
    cleaned = name.strip().lower()
    out = []
    last_dash = False
    for ch in cleaned:
        if ch.isalnum():
            out.append(ch)
            last_dash = False
        elif ch in (" ", "-", "_", "."):
            if not last_dash:
                out.append("-")
                last_dash = True
        # drop other characters
    slug = "".join(out).strip("-")
    # Filter to safe set (defensive — should already be safe).
    slug = "".join(c for c in slug if c in _SLUG_KEEP)
    return slug or "group"


@dataclass
class GroupData:
    group_id: str
    slug: str
    name: str
    description: Optional[str]
    theme: Optional[str]
    visibility: str  # 'public' | 'private'
    invite_token: Optional[str]
    created_by_user_id: str
    created_at: str
    member_count: int


@dataclass
class MembershipData:
    group_id: str
    user_id: str
    child_id: str
    role: str  # 'owner' | 'member'
    joined_at: str


class GroupRepository:
    """Repository for hub_groups + hub_group_memberships."""

    def __init__(self, db=None):
        self._db = db if db is not None else db_manager

    # --- helpers ----------------------------------------------------------

    @staticmethod
    def _row_to_group(row) -> GroupData:
        return GroupData(
            group_id=row["group_id"],
            slug=row["slug"],
            name=row["name"],
            description=row["description"],
            theme=row["theme"],
            visibility=row["visibility"],
            invite_token=row["invite_token"],
            created_by_user_id=row["created_by_user_id"],
            created_at=row["created_at"],
            member_count=row["member_count"],
        )

    @staticmethod
    def _row_to_membership(row) -> MembershipData:
        return MembershipData(
            group_id=row["group_id"],
            user_id=row["user_id"],
            child_id=row["child_id"],
            role=row["role"],
            joined_at=row["joined_at"],
        )

    async def _next_available_slug(self, base: str) -> str:
        """Return base, base-2, base-3, ... — the first not present in hub_groups.slug."""
        candidate = base
        suffix = 2
        while True:
            row = await self._db.fetchone(
                "SELECT 1 FROM hub_groups WHERE slug = ?", (candidate,)
            )
            if row is None:
                return candidate
            candidate = f"{base}-{suffix}"
            suffix += 1

    # --- read -------------------------------------------------------------

    async def get_by_id(self, group_id: str) -> Optional[GroupData]:
        row = await self._db.fetchone(
            """
            SELECT group_id, slug, name, description, theme, visibility,
                   invite_token, created_by_user_id, created_at, member_count
            FROM hub_groups
            WHERE group_id = ?
            """,
            (group_id,),
        )
        return self._row_to_group(row) if row else None

    async def get_by_slug(self, slug: str) -> Optional[GroupData]:
        row = await self._db.fetchone(
            """
            SELECT group_id, slug, name, description, theme, visibility,
                   invite_token, created_by_user_id, created_at, member_count
            FROM hub_groups
            WHERE slug = ?
            """,
            (slug,),
        )
        return self._row_to_group(row) if row else None

    async def list_public(self, limit: int = 50, offset: int = 0) -> List[GroupData]:
        rows = await self._db.fetchall(
            """
            SELECT group_id, slug, name, description, theme, visibility,
                   invite_token, created_by_user_id, created_at, member_count
            FROM hub_groups
            WHERE visibility = 'public'
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        return [self._row_to_group(r) for r in rows]

    async def list_for_member(
        self, user_id: str, child_id: str
    ) -> List[GroupData]:
        rows = await self._db.fetchall(
            """
            SELECT g.group_id, g.slug, g.name, g.description, g.theme,
                   g.visibility, g.invite_token, g.created_by_user_id,
                   g.created_at, g.member_count
            FROM hub_groups g
            JOIN hub_group_memberships m ON m.group_id = g.group_id
            WHERE m.user_id = ? AND m.child_id = ?
            ORDER BY g.created_at DESC
            """,
            (user_id, child_id),
        )
        return [self._row_to_group(r) for r in rows]

    async def get_membership(
        self, group_id: str, user_id: str, child_id: str
    ) -> Optional[MembershipData]:
        row = await self._db.fetchone(
            """
            SELECT group_id, user_id, child_id, role, joined_at
            FROM hub_group_memberships
            WHERE group_id = ? AND user_id = ? AND child_id = ?
            """,
            (group_id, user_id, child_id),
        )
        return self._row_to_membership(row) if row else None

    # --- write ------------------------------------------------------------

    async def create_group(
        self,
        *,
        name: str,
        visibility: str,
        created_by_user_id: str,
        owner_child_id: str,
        description: Optional[str] = None,
        theme: Optional[str] = None,
    ) -> GroupData:
        """Create a group + auto-create owner membership.

        For private groups, generates a 16-byte url-safe invite token.
        Public groups always have invite_token = NULL.
        """
        if visibility not in ("public", "private"):
            raise ValueError("visibility must be 'public' or 'private'")

        group_id = uuid4().hex
        base_slug = _slugify(name)
        slug = await self._next_available_slug(base_slug)
        now = datetime.now().isoformat()
        invite_token = token_urlsafe(16) if visibility == "private" else None

        await self._db.execute(
            """
            INSERT INTO hub_groups (
                group_id, slug, name, description, theme,
                visibility, invite_token, created_by_user_id, created_at,
                member_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                group_id,
                slug,
                name,
                description,
                theme,
                visibility,
                invite_token,
                created_by_user_id,
                now,
                1,  # owner counts as the first member
            ),
        )
        await self._db.execute(
            """
            INSERT INTO hub_group_memberships (
                group_id, user_id, child_id, role, joined_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (group_id, created_by_user_id, owner_child_id, "owner", now),
        )
        await self._db.commit()

        return GroupData(
            group_id=group_id,
            slug=slug,
            name=name,
            description=description,
            theme=theme,
            visibility=visibility,
            invite_token=invite_token,
            created_by_user_id=created_by_user_id,
            created_at=now,
            member_count=1,
        )

    async def join_group(
        self,
        *,
        group_id: str,
        user_id: str,
        child_id: str,
        invite_token: Optional[str] = None,
        role: str = "member",
    ) -> MembershipData:
        """
        Join a group.

        Public groups: open join (invite_token ignored).
        Private groups: invite_token must match hub_groups.invite_token.

        Idempotent: if a membership row already exists for the
        (group, user, child) triple, returns it unchanged.

        Raises:
            LookupError: group does not exist.
            PermissionError: private group requires a matching invite_token.
        """
        group = await self.get_by_id(group_id)
        if group is None:
            raise LookupError(f"group {group_id} not found")

        if group.visibility == "private":
            if not invite_token or invite_token != group.invite_token:
                raise PermissionError("invalid or missing invite token")

        existing = await self.get_membership(group_id, user_id, child_id)
        if existing is not None:
            return existing

        now = datetime.now().isoformat()
        await self._db.execute(
            """
            INSERT INTO hub_group_memberships (
                group_id, user_id, child_id, role, joined_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (group_id, user_id, child_id, role, now),
        )
        # Bump member_count atomically.
        await self._db.execute(
            "UPDATE hub_groups SET member_count = member_count + 1 WHERE group_id = ?",
            (group_id,),
        )
        await self._db.commit()

        return MembershipData(
            group_id=group_id,
            user_id=user_id,
            child_id=child_id,
            role=role,
            joined_at=now,
        )


# Singleton bound to the global db_manager.
group_repo = GroupRepository()
