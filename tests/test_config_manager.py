"""Unit tests for backend.config_manager (connection CRUD + id uniqueness)."""
import pytest

from backend import config_manager


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager, "CONFIG_PATH", tmp_path / "connections.json")
    config_manager.save_config({"connections": [], "active_ids": []})
    return config_manager


def test_add_connection(cfg):
    c = cfg.add_connection("sqlite", "localhost", 0, "", "", "test.db", "测试库")
    assert c["id"] == "1"
    assert c["name"] == "测试库"
    assert c["url"].startswith("sqlite:///")
    assert "password" not in c  # never leak password via API


def test_add_connection_active_by_default(cfg):
    c1 = cfg.add_connection("sqlite", "localhost", 0, "", "", "a.db", "A")
    c2 = cfg.add_connection("sqlite", "localhost", 0, "", "", "b.db", "B")
    actives = cfg.get_active_connections()
    # only the first connection is auto-activated
    assert [a["id"] for a in actives] == [c1["id"]]


def test_remove_connection_cleans_active_ids(cfg):
    c1 = cfg.add_connection("sqlite", "localhost", 0, "", "", "a.db", "A")
    c2 = cfg.add_connection("sqlite", "localhost", 0, "", "", "b.db", "B")
    cfg.toggle_connection(c2["id"], True)
    cfg.remove_connection(c1["id"])
    remaining = cfg.list_connections()
    assert [r["id"] for r in remaining] == [c2["id"]]
    assert cfg.get_active_connections()[0]["id"] == c2["id"]


def test_toggle_connection(cfg):
    c = cfg.add_connection("sqlite", "localhost", 0, "", "", "a.db", "A")
    cfg.toggle_connection(c["id"], False)
    assert cfg.get_active_connections() == []
    cfg.toggle_connection(c["id"], True)
    assert len(cfg.get_active_connections()) == 1


def test_add_after_remove_generates_unique_id(cfg):
    """Regression: len(connections)+1 collided with an existing id after deletion."""
    c1 = cfg.add_connection("sqlite", "localhost", 0, "", "", "a.db", "A")
    c2 = cfg.add_connection("sqlite", "localhost", 0, "", "", "b.db", "B")
    cfg.remove_connection(c1["id"])
    c3 = cfg.add_connection("sqlite", "localhost", 0, "", "", "c.db", "C")
    ids = [c["id"] for c in cfg.list_connections()]
    assert c3["id"] not in (c1["id"], c2["id"])
    assert len(ids) == len(set(ids))


def test_remove_non_existent_is_noop(cfg):
    cfg.add_connection("sqlite", "localhost", 0, "", "", "a.db", "A")
    cfg.remove_connection("999")
    assert len(cfg.list_connections()) == 1


def test_load_config_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager, "CONFIG_PATH", tmp_path / "nope.json")
    assert config_manager.load_config() == {"connections": [], "active_ids": []}


def test_load_config_corrupt_file(tmp_path, monkeypatch):
    p = tmp_path / "connections.json"
    p.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(config_manager, "CONFIG_PATH", p)
    assert config_manager.load_config() == {"connections": [], "active_ids": []}
