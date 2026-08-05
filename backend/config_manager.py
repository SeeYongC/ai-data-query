"""Connection profile manager with multi-database support."""
import json, os
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

CONFIG_PATH = Path(__file__).resolve().parent.parent / "connections.json"

DIALECT_DRIVERS = {
    "mysql": "mysql+pymysql", "postgresql": "postgresql+psycopg2",
    "postgres": "postgresql+psycopg2", "sqlite": "sqlite", "clickhouse": "clickhouse",
}
DIALECT_DESCRIPTIONS = {
    "mysql": "MySQL / MariaDB", "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL", "sqlite": "SQLite (文件)", "clickhouse": "ClickHouse",
}
DIALECT_EXAMPLES = {
    "mysql": "mysql+pymysql://root:password@localhost:3306/mydb",
    "postgresql": "postgresql+psycopg2://user:password@localhost:5432/mydb",
    "sqlite": "sqlite:///C:/path/to/database.db",
    "clickhouse": "clickhouse://user:password@localhost:8123/mydb",
}


def build_url(dialect: str, host: str, port: int, user: str, password: str, database: str) -> str:
    if dialect == "sqlite":
        return f"sqlite:///{database.replace(chr(92), '/')}"
    driver = DIALECT_DRIVERS.get(dialect, dialect)
    ep = quote_plus(password) if password else ""
    eu = quote_plus(user) if user else ""
    return f"{driver}://{eu}:{ep}@{host}:{port}/{database}"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try: return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError: pass
    return {"connections": [], "active_ids": []}


def save_config(config: dict):
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def list_connections() -> list[dict]:
    config = load_config()
    result = []
    for c in config.get("connections", []):
        safe = {k: v for k, v in c.items() if k != "password"}
        safe["is_active"] = c.get("id") in config.get("active_ids", [])
        result.append(safe)
    return result


def add_connection(dialect: str, host: str, port: int, user: str, password: str, database: str, name: str = "") -> dict:
    config = load_config()
    # Generate a unique id even after deletions (len+1 could collide with an existing id).
    ids = [int(c["id"]) for c in config.get("connections", []) if str(c.get("id", "")).isdigit()]
    conn_id = str(max(ids) + 1) if ids else "1"
    if dialect == 'sqlite':
        BASE = Path(__file__).resolve().parent.parent; database = str(BASE / "data" / database) if not os.path.isabs(database) else database; database = os.path.abspath(database).replace(chr(92), chr(47))
    url = build_url(dialect, host, port, user, password, database)
    connection = {"id": conn_id, "name": name or f"{dialect} - {database}", "dialect": dialect, "host": host, "port": port, "user": user, "password": password, "database": database, "url": url}
    config["connections"].append(connection)
    if not config.get("active_ids"): config["active_ids"] = [conn_id]
    save_config(config)
    return {k: v for k, v in connection.items() if k != "password"}


def remove_connection(conn_id: str):
    config = load_config()
    config["connections"] = [c for c in config["connections"] if c.get("id") != conn_id]
    config["active_ids"] = [i for i in config.get("active_ids", []) if i != conn_id]
    save_config(config)


def toggle_connection(conn_id: str, enable: bool):
    """Enable or disable a connection for multi-database mode."""
    config = load_config()
    active_ids = config.get("active_ids", [])
    if enable and conn_id not in active_ids:
        active_ids.append(conn_id)
    elif not enable and conn_id in active_ids:
        active_ids.remove(conn_id)
    config["active_ids"] = active_ids
    save_config(config)


def get_active_connections() -> list[dict]:
    """Get all currently enabled connections."""
    config = load_config()
    active_ids = config.get("active_ids", [])
    result = []
    for c in config.get("connections", []):
        if c.get("id") in active_ids:
            safe = {k: v for k, v in c.items() if k != "password"}
            safe["url"] = c.get("url", "")
            result.append(safe)
    return result


def test_connection(dialect: str, host: str, port: int, user: str, password: str, database: str) -> dict:
    if dialect == 'sqlite':
        BASE = Path(__file__).resolve().parent.parent; database = str(BASE / "data" / database) if not os.path.isabs(database) else database; database = os.path.abspath(database).replace(chr(92), chr(47))
    url = build_url(dialect, host, port, user, password, database)
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 10} if dialect != "sqlite" else {"check_same_thread": False})
        insp = inspect(engine)
        tables = insp.get_table_names()
        user_tables = [t for t in tables if not t.startswith("sqlite_") and not t.startswith("sys_") and not t.startswith("pg_") and t not in ("information_schema", "performance_schema", "mysql")]
        total_rows = 0
        with engine.connect() as conn:
            for t in user_tables[:10]:
                try: total_rows += conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                except Exception: pass
        engine.dispose()
        return {"success": True, "dialect": dialect, "description": DIALECT_DESCRIPTIONS.get(dialect, dialect), "table_count": len(user_tables), "tables": sorted(user_tables)[:20], "estimated_rows": total_rows, "url": url}
    except SQLAlchemyError as e:
        return {"success": False, "error": str(e), "suggestion": _suggest_fix(str(e), dialect)}
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": _suggest_fix(str(e), dialect)}


def _suggest_fix(error: str, dialect: str) -> str:
    el = error.lower()
    if "access denied" in el or "password" in el or "authentication" in el: return "用户名或密码错误。"
    if "can't connect" in el or "connection refused" in el or "timeout" in el: return f"无法连接 {dialect} 服务器。请确认服务已启动，主机端口正确。"
    if "unknown database" in el or "does not exist" in el: return "数据库不存在。请在 Navicat 中确认库名。"
    if "driver" in el or "module" in el:
        dm = {"mysql": "pip install pymysql", "postgresql": "pip install psycopg2", "clickhouse": "pip install clickhouse-driver"}
        return f"缺少驱动。运行: {dm.get(dialect, 'pip install <驱动>')}"
    return "请检查连接参数或查看服务器日志。"
