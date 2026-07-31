"""Unified database adapter supporting SQLite, MySQL, PostgreSQL, ClickHouse via SQLAlchemy.

Usage:
    db = Database("sqlite:///path/to/db.sqlite")                    # SQLite (default)
    db = Database("mysql+pymysql://user:pass@host:3306/dbname")     # MySQL
    db = Database("postgresql+psycopg2://user:pass@host:5432/dbname") # PostgreSQL
    db = Database("clickhouse://user:pass@host:8123/dbname")       # ClickHouse

Or set the DATABASE_URL environment variable and use Database() with no arguments.
"""
import os
from typing import Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


DEFAULT_SQLITE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ecommerce.db"
)


class Database:
    def __init__(self, url: Optional[str] = None):
        if url is None:
            url = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")
        self.url = url
        self._dialect = url.split("://")[0].split("+")[0] if "://" in url else "sqlite"
        connect_args = {}
        if self._dialect == "sqlite":
            connect_args["check_same_thread"] = False
        self.engine: Engine = create_engine(url, connect_args=connect_args, echo=False)
        self._inspector = None

    @property
    def inspector(self):
        if self._inspector is None:
            self._inspector = inspect(self.engine)
        return self._inspector

    @property
    def dialect_name(self) -> str:
        return self._dialect

    def get_schema(self) -> str:
        """Return CREATE TABLE statements for all user tables."""
        if self._dialect == "sqlite":
            return self._get_schema_sqlite()
        else:
            return self._get_schema_generic()

    def _get_schema_sqlite(self) -> str:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'metric_%' AND name NOT LIKE 'user_metric_%' ORDER BY name"
            )).fetchall()
            return "\n\n".join(row[1] for row in rows if row[1])

    def _get_schema_generic(self) -> str:
        """Read schema from information_schema (MySQL/PG) or system.columns (ClickHouse)."""
        tables = self.inspector.get_table_names()
        # Filter out metric governance tables
        tables = [t for t in tables if not t.startswith("metric_") and not t.startswith("user_metric_")]
        parts = []
        for table in sorted(tables):
            cols = self.inspector.get_columns(table)
            col_defs = []
            for c in cols:
                col_type = str(c["type"])
                nullable = "" if c.get("nullable", True) else " NOT NULL"
                default = f" DEFAULT {c['default']}" if c.get("default") else ""
                pk = " PRIMARY KEY" if c.get("primary_key") else ""
                col_defs.append(f"  {c['name']} {col_type}{nullable}{default}{pk}")
            parts.append(f"CREATE TABLE {table} (\n" + ",\n".join(col_defs) + "\n);")
        return "\n\n".join(parts)

    def get_schema_text(self) -> str:
        """Return human-readable schema description with row counts."""
        tables = self.inspector.get_table_names()
        tables = [t for t in tables if not t.startswith("metric_") and not t.startswith("user_metric_")]
        lines = []
        for table in sorted(tables):
            cols = self.inspector.get_columns(table)
            lines.append(f"## {table}")
            for c in cols:
                col_type = str(c["type"])
                pk = " PRIMARY KEY" if c.get("primary_key") else ""
                nullable = "" if c.get("nullable", True) else " NOT NULL"
                lines.append(f"  - {c['name']} ({col_type}{pk}{nullable})")
            lines.append("")
            try:
                with self.engine.connect() as conn:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {self._quote(table)}")).scalar()
                lines.append(f"  ({count} rows)")
            except Exception:
                lines.append("  (rows unknown)")
            lines.append("")
        return "\n".join(lines)

    def execute(self, sql: str) -> tuple[list[str], list]:
        """Execute a query; returns (column_names, rows). Handles both SELECT and DDL."""
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            if result.returns_rows:
                columns = list(result.keys())
                rows = [list(row) for row in result.fetchall()]
                conn.commit()
                return columns, rows
            else:
                conn.commit()
                return [], []

    def execute_dml(self, sql: str, params: Optional[dict] = None):
        """Execute INSERT/UPDATE/DELETE with optional parameters."""
        with self.engine.connect() as conn:
            if params:
                conn.execute(text(sql), params)
            else:
                conn.execute(text(sql))
            conn.commit()

    def execute_dml_many(self, sql: str, params_list: list):
        """Execute multiple DML statements."""
        with self.engine.connect() as conn:
            for params in params_list:
                conn.execute(text(sql), params)
            conn.commit()

    def _quote(self, name: str) -> str:
        """Quote a table/column name for the current dialect."""
        if self._dialect == "mysql":
            return f"`{name}`"
        elif self._dialect == "postgresql":
            return f'"{name}"'
        else:
            return name

    def close(self):
        self.engine.dispose()
