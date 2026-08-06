"""Unit tests for backend.database (SQLAlchemy adapter)."""
import pytest

from backend.database import Database


@pytest.fixture
def db(tmp_path):
    d = Database(f"sqlite:///{tmp_path / 'test.db'}")
    d.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    d.execute("INSERT INTO users (name, age) VALUES ('Alice', 30), ('Bob', 25)")
    yield d
    d.close()


def test_execute_select(db):
    cols, rows = db.execute("SELECT * FROM users ORDER BY id")
    assert cols == ["id", "name", "age"]
    assert rows == [[1, "Alice", 30], [2, "Bob", 25]]


def test_execute_with_params(db):
    cols, rows = db.execute("SELECT name FROM users WHERE age > :min_age", {"min_age": 26})
    assert cols == ["name"]
    assert rows == [["Alice"]]


def test_execute_dml_with_params(db):
    db.execute_dml("UPDATE users SET age = age + 1 WHERE name = :n", {"n": "Alice"})
    _, rows = db.execute("SELECT age FROM users WHERE name = 'Alice'")
    assert rows == [[31]]


def test_execute_dml_many(db):
    db.execute_dml_many(
        "UPDATE users SET age = age + :delta WHERE name = :n",
        [{"delta": 10, "n": "Alice"}, {"delta": 5, "n": "Bob"}],
    )
    _, rows = db.execute("SELECT age FROM users ORDER BY id")
    assert rows == [[40], [30]]


def test_execute_ddl_returns_empty(db):
    cols, rows = db.execute("CREATE TABLE t2 (id INTEGER)")
    assert cols == [] and rows == []


def test_get_schema_text(db):
    schema = db.get_schema_text()
    assert "## users" in schema
    assert "id (" in schema
    assert "rows" in schema


def test_dialect_name(db):
    assert db.dialect_name == "sqlite"
