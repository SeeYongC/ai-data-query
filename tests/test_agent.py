"""Unit tests for backend.agent (SQL table validation + LLM response parsing)."""
import pytest

from backend.agent import Agent
from backend.database import Database


@pytest.fixture
def agent(tmp_path):
    d = Database(f"sqlite:///{tmp_path / 'agent.db'}")
    d.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, total REAL, status TEXT)")
    d.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    a = Agent(d, api_key="test-key")
    yield a
    d.close()


# ---- _validate_sql_tables ----

def test_validate_simple_select(agent):
    assert agent._validate_sql_tables("SELECT * FROM orders WHERE total > 100", agent.db) is None


def test_validate_join(agent):
    sql = "SELECT o.id FROM orders o JOIN users u ON u.id = o.id"
    assert agent._validate_sql_tables(sql, agent.db) is None


def test_validate_comma_separated_tables(agent):
    assert agent._validate_sql_tables("SELECT * FROM orders, users", agent.db) is None


def test_validate_schema_qualified_table(agent):
    """schema.table must resolve to the table name, not the schema."""
    assert agent._validate_sql_tables("SELECT * FROM main.orders", agent.db) is None


def test_validate_quoted_table(agent):
    assert agent._validate_sql_tables('SELECT * FROM "orders"', agent.db) is None


def test_validate_quoted_table_with_space_is_not_false_positive(agent):
    """Quoted identifiers containing spaces must not be truncated to the first word."""
    err = agent._validate_sql_tables('SELECT * FROM "orders"', agent.db)
    assert err is None
    # a genuinely missing quoted table is still caught
    err2 = agent._validate_sql_tables('SELECT * FROM "missing table"', agent.db)
    assert err2 and "missing table" in err2


def test_validate_missing_table_rejected(agent):
    err = agent._validate_sql_tables("SELECT * FROM nope", agent.db)
    assert err and "nope" in err


def test_validate_comma_list_catches_missing_table(agent):
    err = agent._validate_sql_tables("SELECT * FROM orders, missing_tbl", agent.db)
    assert err and "missing_tbl" in err


def test_validate_join_catches_missing_table(agent):
    err = agent._validate_sql_tables("SELECT * FROM orders JOIN ghost ON 1=1", agent.db)
    assert err and "ghost" in err


def test_validate_skips_subquery_inner_tables(agent):
    sql = "SELECT * FROM (SELECT id FROM orders) AS sub WHERE sub.id > 1"
    assert agent._validate_sql_tables(sql, agent.db) is None


def test_validate_lowercases_real_tables(agent):
    err = agent._validate_sql_tables("SELECT * FROM MISSING_TBL", agent.db)
    assert err is not None


# ---- _is_read_only / _execute_readonly ----

def test_read_only_accepts_select(agent):
    assert agent._is_read_only("SELECT * FROM orders") is True


def test_read_only_accepts_case_insensitive(agent):
    assert agent._is_read_only("  select * from orders;") is True


def test_read_only_rejects_multi_statement(agent):
    """SELECT 1; DROP ... must be rejected even though it starts with SELECT."""
    assert agent._is_read_only("SELECT 1; DROP TABLE orders") is False
    assert agent._is_read_only("SELECT 1; SELECT 2") is False


def test_read_only_with_string_literal_containing_keyword(agent):
    """Write keywords inside string literals must not cause a false rejection."""
    sql = "WITH x AS (SELECT 'drop' AS s) SELECT * FROM x"
    assert agent._is_read_only(sql) is True


def test_read_only_select_with_like_literal(agent):
    sql = "SELECT * FROM orders WHERE status = 'deleted' OR name LIKE '%update%'"
    assert agent._is_read_only(sql) is True


def test_read_only_accepts_parenthesized_select(agent):
    assert agent._is_read_only("(SELECT 1)") is True


def test_read_only_accepts_cte_select(agent):
    sql = "WITH recent AS (SELECT * FROM orders) SELECT * FROM recent"
    assert agent._is_read_only(sql) is True


def test_read_only_rejects_write_statements(agent):
    for sql in ("UPDATE orders SET total=0", "DELETE FROM orders", "INSERT INTO orders VALUES (1)",
                "DROP TABLE orders", "ALTER TABLE orders ADD COLUMN x", "CREATE TABLE t (id INT)"):
        assert agent._is_read_only(sql) is False, sql


def test_read_only_rejects_cte_write(agent):
    sql = "WITH x AS (SELECT * FROM orders) INSERT INTO orders SELECT * FROM x"
    assert agent._is_read_only(sql) is False


def test_read_only_rejects_empty(agent):
    assert agent._is_read_only("   ") is False


def test_execute_readonly_blocks_write(agent):
    with pytest.raises(ValueError):
        agent._execute_readonly(agent.db, "DELETE FROM orders")


def test_execute_readonly_runs_select(agent):
    cols, rows = agent._execute_readonly(agent.db, "SELECT COUNT(*) FROM orders")
    assert cols == ["COUNT(*)"] and rows == [[0]]


# ---- _parse ----

def test_parse_plain_json(agent):
    assert agent._parse('{"sql": "SELECT 1", "explanation": "x"}') == ("SELECT 1", "x")


def test_parse_markdown_codeblock(agent):
    t = '```json\n{"sql": "SELECT 2", "explanation": "y"}\n```'
    assert agent._parse(t) == ("SELECT 2", "y")


def test_parse_escaped_quotes_in_sql(agent):
    t = '{"sql": "SELECT * FROM t WHERE name=\\"a b\\"", "explanation": "z"}'
    assert agent._parse(t) == ('SELECT * FROM t WHERE name="a b"', "z")


def test_parse_fallback_with_surrounding_text(agent):
    sql, expl = agent._parse('Some prose "sql": "SELECT 3", "explanation": "w" trailing')
    assert sql == "SELECT 3" and expl == "w"


def test_parse_empty_returns_none(agent):
    sql, _ = agent._parse("")
    assert sql is None


def test_parse_garbage_returns_none(agent):
    sql, _ = agent._parse("no sql here at all")
    assert sql is None
