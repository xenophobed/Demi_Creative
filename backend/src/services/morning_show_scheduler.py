"""Daily Drop scheduler for Morning Show generation (#97)."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, time, timedelta
from typing import Optional

from ..api.models import AgeGroup, MorningShowRequest, NewsCategory
from ..services.database import db_manager, subscription_repo
from ..services.user_service import UserData


class DailyDropScheduler:
    """Simple in-process daily scheduler for subscription episode generation."""

    def __init__(self):
        schedule = os.getenv("DAILY_DROP_SCHEDULE", "02:00")
        hour, minute = self._parse_schedule(schedule)
        self._hour = hour
        self._minute = minute
        self._rate_limit_seconds = float(os.getenv("DAILY_DROP_RATE_LIMIT_SECONDS", "2"))
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def _parse_schedule(self, value: str) -> tuple[int, int]:
        try:
            parts = value.strip().split(":", maxsplit=1)
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            hour = max(0, min(23, hour))
            minute = max(0, min(59, minute))
            return hour, minute
        except Exception:
            return 2, 0

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="daily-drop-scheduler")
        print(f"⏰ Daily Drop scheduler started (runs at {self._hour:02d}:{self._minute:02d})")

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        print("⏹️ Daily Drop scheduler stopped")

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            now = datetime.now()
            next_run = datetime.combine(now.date(), time(self._hour, self._minute))
            if now >= next_run:
                next_run += timedelta(days=1)

            wait_seconds = max(1.0, (next_run - now).total_seconds())

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=wait_seconds)
                break
            except asyncio.TimeoutError:
                pass

            if self._stop_event.is_set():
                break

            await self.run_daily_drop()

    async def _already_generated_today(self, user_id: str, child_id: str, topic: str) -> bool:
        today = datetime.now().date().isoformat()
        row = await db_manager.fetchone(
            """
            SELECT story_id FROM stories
            WHERE user_id = ?
              AND child_id = ?
              AND story_type = 'morning_show'
              AND created_at LIKE ?
              AND analysis LIKE ?
            LIMIT 1
            """,
            (
                user_id,
                child_id,
                f"{today}%",
                f"%\"category\"%{topic}%",
            ),
        )
        return row is not None

    async def _resolve_child_age_group(self, child_id: str) -> AgeGroup:
        """Look up the child's age group from their most recent story.

        Falls back to AGE_6_8 when no history exists.
        """
        row = await db_manager.fetchone(
            """
            SELECT age_group FROM stories
            WHERE child_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (child_id,),
        )
        if row and row["age_group"] in AgeGroup._value2member_map_:
            return AgeGroup(row["age_group"])
        return AgeGroup.AGE_6_8

    async def _fetch_news_text(self, topic: str) -> str:
        """Return real headlines for *topic* from Tavily, or a stub if unavailable."""
        _STUB = (
            f"Daily Drop topic: {topic}. "
            "Today we found a kid-friendly update and a fun fact to discuss. "
            "If no major news is available, explain one practical discovery kids can try at home or school."
        )
        try:
            from ..mcp_servers import get_headlines_by_topic
            import json as _json

            result = await get_headlines_by_topic({"topic": topic, "max_results": 5})
            data = _json.loads(result["content"][0]["text"])
            headlines = data.get("headlines", [])
            if not headlines:
                return _STUB
            lines = [f"- {h['title']}: {h['description']}" for h in headlines if h.get("title")]
            return f"Today's news about {topic}:\n" + "\n".join(lines)
        except Exception:
            return _STUB

    async def run_daily_drop(self) -> None:
        """Generate one episode per active subscription (max 1/day/topic)."""
        subscriptions = await subscription_repo.list_all_active()
        if not subscriptions:
            print("📰 Daily Drop: no active subscriptions")
            return

        print(f"📰 Daily Drop: processing {len(subscriptions)} active subscriptions")

        # Local import avoids startup circular dependencies.
        from ..api.routes.morning_show import _build_episode

        for sub in subscriptions:
            user_id = sub["user_id"]
            child_id = sub["child_id"]
            topic = sub["topic"]

            try:
                if await self._already_generated_today(user_id, child_id, topic):
                    continue

                news_text = await self._fetch_news_text(topic)

                user = UserData(
                    user_id=user_id,
                    username=user_id,
                    email=f"{user_id}@local",
                    password_hash="",
                    display_name=None,
                    avatar_url=None,
                    is_active=True,
                    is_verified=True,
                    created_at="",
                    updated_at="",
                    last_login_at=None,
                )

                category = NewsCategory(topic) if topic in NewsCategory._value2member_map_ else NewsCategory.GENERAL
                age_group = await self._resolve_child_age_group(child_id)

                request = MorningShowRequest(
                    child_id=child_id,
                    age_group=age_group,
                    category=category,
                    news_text=news_text,
                    news_url=None,
                )

                await _build_episode(request, user)
                print(f"✅ Daily Drop generated for child={child_id} topic={topic}")

            except Exception as e:
                # Per-topic isolation: failures should not block other subscriptions.
                print(f"⚠️ Daily Drop failed for child={child_id} topic={topic}: {e}")

            await asyncio.sleep(self._rate_limit_seconds)


daily_drop_scheduler = DailyDropScheduler()

