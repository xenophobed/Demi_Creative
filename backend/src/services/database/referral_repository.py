"""
Referral Repository (#347)

CRUD operations for referral tracking.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from .connection import db_manager


class ReferralRepository:
    """Repository for referral records."""

    def __init__(self):
        self._db = db_manager

    async def create_referral(
        self,
        referrer_user_id: str,
        referred_user_id: str,
        referral_code: str,
    ) -> Dict[str, Any]:
        """Create a referral record."""
        now = datetime.now().isoformat()
        await self._db.execute(
            """
            INSERT INTO referrals (
                referrer_user_id, referred_user_id, referral_code,
                is_qualified, created_at
            ) VALUES (?, ?, ?, 0, ?)
            """,
            (referrer_user_id, referred_user_id, referral_code, now)
        )
        await self._db.commit()
        return {
            "referrer_user_id": referrer_user_id,
            "referred_user_id": referred_user_id,
            "referral_code": referral_code,
            "is_qualified": 0,
            "created_at": now,
            "qualified_at": None,
        }

    async def qualify_referral(self, referred_user_id: str) -> bool:
        """Mark a referral as qualified (referred user verified email)."""
        now = datetime.now().isoformat()
        cursor = await self._db.execute(
            """
            UPDATE referrals
            SET is_qualified = 1, qualified_at = ?
            WHERE referred_user_id = ? AND is_qualified = 0
            """,
            (now, referred_user_id)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def get_referral_count(
        self, referrer_user_id: str, qualified_only: bool = False
    ) -> int:
        """Count referrals for a user."""
        if qualified_only:
            row = await self._db.fetchone(
                "SELECT COUNT(*) as cnt FROM referrals WHERE referrer_user_id = ? AND is_qualified = 1",
                (referrer_user_id,)
            )
        else:
            row = await self._db.fetchone(
                "SELECT COUNT(*) as cnt FROM referrals WHERE referrer_user_id = ?",
                (referrer_user_id,)
            )
        return row['cnt'] if row else 0

    async def get_referrals_by_user(
        self, referrer_user_id: str, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List referrals for a user."""
        rows = await self._db.fetchall(
            """
            SELECT * FROM referrals
            WHERE referrer_user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (referrer_user_id, limit, offset)
        )
        return [dict(row) for row in rows]

    async def get_referral_by_referred_user(
        self, referred_user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Look up a referral by the referred user."""
        row = await self._db.fetchone(
            "SELECT * FROM referrals WHERE referred_user_id = ?",
            (referred_user_id,)
        )
        return dict(row) if row else None

    async def check_upgrade_eligible(
        self, referrer_user_id: str, threshold: int = 10
    ) -> bool:
        """Check if a user has enough qualified referrals to upgrade."""
        count = await self.get_referral_count(referrer_user_id, qualified_only=True)
        return count >= threshold


# Global referral repository instance
referral_repo = ReferralRepository()
