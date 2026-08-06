"""Unit tests for backend.governance (metric governance, parameterized queries)."""
import pytest

from backend.database import Database
from backend.governance import Governance

METRIC_ROWS = [
    # (metric_key, metric_name, definition_name, owner_department, data_source, sql_condition, description)
    ("active_users", "活跃用户", "财务口径", "财务部", "orders", "u.user_id IN (...)", "近30天有交易"),
    ("active_users", "活跃用户", "运营口径", "运营部", "user_logins", "u.user_id IN (...)", "近7天有登录"),
    ("sales_revenue", "销售额", "财务口径", "财务部", "orders", "o.status='completed'", "已完成订单"),
]


@pytest.fixture
def gov(tmp_path):
    d = Database(f"sqlite:///{tmp_path / 'gov.db'}")
    g = Governance(d)
    d.execute_dml_many(
        "INSERT INTO metric_definitions (metric_key, metric_name, definition_name, owner_department, "
        "data_source, sql_condition, description, is_active) "
        "VALUES (:k, :n, :d, :o, :s, :sc, :de, 1)",
        [dict(k=r[0], n=r[1], d=r[2], o=r[3], s=r[4], sc=r[5], de=r[6]) for r in METRIC_ROWS],
    )
    yield g
    d.close()


def test_ensure_tables_creates_definitions_table(gov):
    columns, rows = gov.db.execute("SELECT COUNT(*) FROM metric_definitions")
    assert rows == [[len(METRIC_ROWS)]]


def test_detect_metrics_conflict(gov):
    conflicts = gov.detect_metrics("上月活跃用户有多少？")
    assert len(conflicts) == 1
    assert conflicts[0]["metric_key"] == "active_users"
    assert len(conflicts[0]["definitions"]) == 2


def test_detect_metrics_no_conflict_for_single_definition(gov):
    assert gov.detect_metrics("上月销售额？") == []


def test_detect_metrics_ignores_unrelated_question(gov):
    assert gov.detect_metrics("天气怎么样") == []


def test_resolve_returns_definition(gov):
    r = gov.resolve("active_users", 1)
    assert r is not None and r["metric_key"] == "active_users"


def test_resolve_unknown_returns_none(gov):
    assert gov.resolve("active_users", 999) is None


def test_resolve_sql_injection_safe(gov):
    """metric_key is user-controlled; must not inject or crash."""
    assert gov.resolve("x' OR '1'='1", 1) is None
    assert gov.resolve("active_users", 1) is not None


def test_save_and_get_preferences(gov):
    gov.save_preference("default", "active_users", 2)
    prefs = gov.get_preferences("default")
    assert prefs == {"active_users": 2}


def test_save_preference_injection_safe(gov):
    gov.save_preference("default", "active_users'; DROP TABLE metric_definitions;--", 1)
    # table still exists and no malicious row was stored
    _, rows = gov.db.execute("SELECT COUNT(*) FROM metric_definitions")
    assert rows == [[len(METRIC_ROWS)]]


def test_inject_context(gov):
    ctx = gov.inject_context({"active_users": 1})
    assert "活跃用户" in ctx
    assert "财务口径" in ctx
    assert "近30天有交易" in ctx


def test_inject_context_injection_safe(gov):
    ctx = gov.inject_context({"x'; DROP TABLE metric_definitions;--": 1})
    assert ctx != ""
    _, rows = gov.db.execute("SELECT COUNT(*) FROM metric_definitions")
    assert rows == [[len(METRIC_ROWS)]]
