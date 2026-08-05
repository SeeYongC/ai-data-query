"""Unit tests for backend.main._ensure_db (connection pool lifecycle)."""
import pytest

from backend import config_manager
import backend.main as main


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Point connections.json at a temp file and reset module-level state."""
    monkeypatch.setattr(config_manager, "CONFIG_PATH", tmp_path / "connections.json")
    main._databases.clear()
    main._config_signature = None
    yield
    for db in main._databases.values():
        db.close()
    main._databases.clear()
    main._config_signature = None


def test_empty_config_auto_adds_default_db(isolated):
    assert config_manager.load_config() == {"connections": [], "active_ids": []}
    main._ensure_db()
    assert len(main._databases) == 1
    assert len(config_manager.list_connections()) == 1


def test_rebuild_skipped_when_config_unchanged(isolated):
    main._ensure_db()
    engines = list(main._databases.values())
    main._ensure_db()
    # no rebuild: same Database instances are reused
    assert list(main._databases.values()) == engines


def test_rebuild_on_config_change(isolated):
    main._ensure_db()
    old_db = list(main._databases.values())[0]
    c2 = config_manager.add_connection("sqlite", "localhost", 0, "", "", "b.db", "第二库")
    config_manager.toggle_connection(c2["id"], True)
    main._ensure_db()
    assert len(main._databases) == 2
    assert list(main._databases.values())[0] is not old_db  # engines recreated


def test_force_rebuild(isolated):
    main._ensure_db()
    old_db = list(main._databases.values())[0]
    main._ensure_db(force=True)
    assert list(main._databases.values())[0] is not old_db  # engines recreated


def test_deactivated_connection_is_dropped(isolated):
    main._ensure_db()
    first = config_manager.list_connections()[0]
    c2 = config_manager.add_connection("sqlite", "localhost", 0, "", "", "b.db", "第二库")
    config_manager.toggle_connection(c2["id"], True)
    main._ensure_db(force=True)
    assert len(main._databases) == 2
    config_manager.toggle_connection(first["id"], False)
    main._ensure_db()
    # only the still-active database remains
    assert len(main._databases) == 1
