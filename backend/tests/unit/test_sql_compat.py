"""Unit tests for SQL compatibility helpers (#681).

Parent Epic: #49

These helpers emit dialect-correct SQL for both SQLite (local dev) and
PostgreSQL (production). The group_concat_sql helper exists because raw
GROUP_CONCAT(...) is SQLite-only and 500s on Postgres.
"""

from src.services.database.sql_compat import group_concat_sql


class TestGroupConcatSql:
    """Both dialects must produce valid aggregate-concatenation SQL."""

    def test_sqlite_uses_group_concat(self):
        result = group_concat_sql("themes", "||", "sqlite")
        assert result == "GROUP_CONCAT(themes, '||')"

    def test_postgresql_uses_string_agg_with_text_cast(self):
        result = group_concat_sql("themes", "||", "postgresql")
        assert result == "string_agg(themes::text, '||')"

    def test_sqlite_respects_column_and_separator(self):
        result = group_concat_sql("story_type", ",", "sqlite")
        assert result == "GROUP_CONCAT(story_type, ',')"

    def test_postgresql_respects_column_and_separator(self):
        result = group_concat_sql("story_type", ",", "postgresql")
        assert result == "string_agg(story_type::text, ',')"
