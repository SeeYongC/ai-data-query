"""Metric governance: conflict detection, resolution, and preference storage.
Works with SQLite and MySQL via the Database adapter."""
from .database import Database


class Governance:
    def __init__(self, db: Database):
        self.db = db
        self._dialect = db.dialect_name
        self._ensure_tables()

    def _ensure_tables(self):
        """Create governance tables using dialect-appropriate SQL."""
        if self._dialect == "mysql":
            auto_pk = "INTEGER PRIMARY KEY AUTO_INCREMENT"
            ts = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        else:
            auto_pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
            ts = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"

        try:
            self.db.execute("SELECT 1 FROM metric_definitions LIMIT 1")
        except Exception:
            self.db.execute(f"""
                CREATE TABLE IF NOT EXISTS metric_definitions (
                    definition_id {auto_pk},
                    metric_key VARCHAR(100) NOT NULL,
                    metric_name VARCHAR(200) NOT NULL,
                    definition_name VARCHAR(200) NOT NULL,
                    owner_department VARCHAR(100),
                    data_source VARCHAR(200),
                    sql_condition TEXT NOT NULL,
                    sql_notes TEXT,
                    description TEXT NOT NULL,
                    business_rules TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at {ts}
                )
            """)
        try:
            self.db.execute("SELECT 1 FROM user_metric_preferences LIMIT 1")
        except Exception:
            self.db.execute(f"""
                CREATE TABLE IF NOT EXISTS user_metric_preferences (
                    preference_id {auto_pk},
                    user_identifier VARCHAR(200) NOT NULL,
                    metric_key VARCHAR(100) NOT NULL,
                    definition_id INTEGER NOT NULL,
                    last_used_at {ts},
                    UNIQUE(user_identifier, metric_key)
                )
            """)

    def detect_metrics(self, question: str) -> list[dict]:
        try:
            columns, rows = self.db.execute("""
                SELECT metric_key, metric_name, definition_id, definition_name,
                       owner_department, data_source, description,
                       sql_condition, sql_notes, business_rules
                FROM metric_definitions WHERE is_active=1
                ORDER BY metric_key, definition_id
            """)
            grouped = {}
            for row in rows:
                r = dict(zip(columns, row))
                key = r["metric_key"]
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(r)
            conflicts = []
            for key, defs in grouped.items():
                if len(defs) < 2:
                    continue
                metric_name = defs[0]["metric_name"]
                if metric_name in question:
                    conflicts.append({"metric_key": key, "metric_name": metric_name, "definitions": defs})
            return conflicts
        except Exception:
            return []

    def resolve(self, metric_key: str, definition_id: int) -> dict | None:
        try:
            columns, rows = self.db.execute(
                f"SELECT * FROM metric_definitions WHERE metric_key='{metric_key}' AND definition_id={definition_id} AND is_active=1"
            )
            if rows:
                return dict(zip(columns, rows[0]))
        except Exception:
            pass
        return None

    def save_preference(self, user_id: str, metric_key: str, definition_id: int):
        try:
            if self._dialect == "mysql":
                self.db.execute_dml(
                    f"REPLACE INTO user_metric_preferences (user_identifier, metric_key, definition_id, last_used_at) VALUES ('{user_id}', '{metric_key}', {definition_id}, NOW())"
                )
            else:
                self.db.execute_dml(
                    f"INSERT OR REPLACE INTO user_metric_preferences (user_identifier, metric_key, definition_id, last_used_at) VALUES ('{user_id}', '{metric_key}', {definition_id}, CURRENT_TIMESTAMP)"
                )
        except Exception:
            pass

    def get_preferences(self, user_id: str) -> dict[str, int]:
        try:
            columns, rows = self.db.execute(
                f"SELECT metric_key, definition_id FROM user_metric_preferences WHERE user_identifier='{user_id}'"
            )
            return {r[columns.index("metric_key")]: r[columns.index("definition_id")] for r in rows}
        except Exception:
            return {}

    def inject_context(self, selections: dict[str, int]) -> str:
        if not selections:
            return ""
        lines = ["## 已确认的指标口径（必须严格遵循）"]
        for metric_key, def_id in selections.items():
            try:
                columns, rows = self.db.execute(
                    f"SELECT * FROM metric_definitions WHERE metric_key='{metric_key}' AND definition_id={def_id} AND is_active=1"
                )
                if rows:
                    r = dict(zip(columns, rows[0]))
                    lines.append(f"- {r['metric_name']} ({r['definition_name']}): {r['description']}")
                    lines.append(f"  数据来源: {r['data_source']}")
                    lines.append(f"  SQL 条件: {r['sql_condition']}")
                    if r.get("sql_notes"):
                        lines.append(f"  备注: {r['sql_notes']}")
            except Exception:
                pass
        return "\n".join(lines)
