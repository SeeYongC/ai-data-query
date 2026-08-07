"""Tests for conversation memory: history formatting, prompt injection, session storage."""
import pytest
from fastapi.testclient import TestClient

from backend import config_manager
from backend.agent import Agent
from backend.database import Database
import backend.main as main


@pytest.fixture
def agent(tmp_path):
    d = Database(f"sqlite:///{tmp_path / 'agent.db'}")
    d.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, total REAL)")
    a = Agent(d, api_key="test-key")
    yield a
    d.close()


# ---- _fmt_history ----

def test_fmt_history_empty(agent):
    assert agent._fmt_history(None) == "(no prior conversation)"
    assert agent._fmt_history([]) == "(no prior conversation)"


def test_fmt_history_renders_roles(agent):
    hist = [{"role": "user", "content": "上月销量?"},
            {"role": "assistant", "content": "SQL: SELECT 1"}]
    out = agent._fmt_history(hist)
    assert "User: 上月销量?" in out
    assert "Assistant: SQL: SELECT 1" in out


def test_fmt_history_skips_empty_content(agent):
    hist = [{"role": "user", "content": "  "}, {"role": "assistant", "content": "x"}]
    out = agent._fmt_history(hist)
    assert "User:" not in out and "Assistant: x" in out


# ---- prompt injection ----

def test_build_prompt_injects_history(agent):
    hist = [{"role": "user", "content": "上一轮问题"},
            {"role": "assistant", "content": "上一轮回答"}]
    prompt = agent._build_prompt(metric_ctx="", db_name=None, history=hist)
    assert "User: 上一轮问题" in prompt
    assert "Assistant: 上一轮回答" in prompt
    assert "CONVERSATION HISTORY" in prompt


def test_build_prompt_no_history_placeholder_filled(agent):
    prompt = agent._build_prompt()
    assert "(no prior conversation)" in prompt
    assert "{HISTORY}" not in prompt


# ---- session storage (main.SESSIONS) ----

@pytest.fixture
def clean_sessions():
    main.SESSIONS.clear()
    yield
    main.SESSIONS.clear()


def test_get_history_unknown_session(clean_sessions):
    assert main._get_history("nope") == []


def test_push_and_get_history(clean_sessions):
    main._push_history("s1", [{"role": "user", "content": "q"}])
    main._push_history("s1", [{"role": "assistant", "content": "a"}])
    hist = main._get_history("s1")
    assert len(hist) == 2
    assert hist[0]["content"] == "q" and hist[1]["content"] == "a"


def test_history_truncated_to_max(clean_sessions, monkeypatch):
    monkeypatch.setattr(main, "MAX_HISTORY", 4)
    for i in range(10):
        main._push_history("s1", [{"role": "user", "content": f"q{i}"}])
    hist = main._get_history("s1")
    assert len(hist) == 4
    assert hist[0]["content"] == "q6"  # 最旧的被裁剪


def test_sessions_evict_oldest(clean_sessions, monkeypatch):
    monkeypatch.setattr(main, "MAX_SESSIONS", 2)
    main._push_history("s1", [{"role": "user", "content": "a"}])
    main._push_history("s2", [{"role": "user", "content": "b"}])
    main._push_history("s3", [{"role": "user", "content": "c"}])
    assert "s1" not in main.SESSIONS
    assert "s2" in main.SESSIONS and "s3" in main.SESSIONS


# ---- end-to-end via /api/query ----

@pytest.fixture
def api_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager, "CONFIG_PATH", tmp_path / "connections.json")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    main._databases.clear()
    main._config_signature = None
    main.agent = None
    main.SESSIONS.clear()
    yield
    for db in main._databases.values():
        db.close()
    main._databases.clear()
    main._config_signature = None
    main.agent = None
    main.SESSIONS.clear()


def test_query_endpoint_records_and_reuses_history(api_env, monkeypatch):
    calls = []

    async def fake_call_llm(self, q, prompt):
        calls.append((q, prompt))
        return '{"sql": "SELECT 1", "explanation": "ok"}'

    monkeypatch.setattr(Agent, "_call_llm", fake_call_llm)
    client = TestClient(main.app)

    r1 = client.post("/api/query", json={"question": "第一轮问题", "session_id": "sess-1"})
    assert r1.status_code == 200 and r1.json()["success"] is True
    assert r1.json()["session_id"] == "sess-1"

    r2 = client.post("/api/query", json={"question": "第二轮问题", "session_id": "sess-1"})
    assert r2.status_code == 200 and r2.json()["success"] is True
    # 第二轮 prompt 应包含第一轮的历史
    q2, prompt2 = calls[1]
    assert q2 == "第二轮问题"
    assert "第一轮问题" in prompt2
    assert "SQL: SELECT 1" in prompt2


def test_query_without_session_id_gets_generated(api_env, monkeypatch):
    async def fake_call_llm(self, q, prompt):
        return '{"sql": "SELECT 1", "explanation": "ok"}'

    monkeypatch.setattr(Agent, "_call_llm", fake_call_llm)
    client = TestClient(main.app)
    r = client.post("/api/query", json={"question": "任意问题"})
    assert r.status_code == 200 and r.json()["success"] is True
    assert r.json()["session_id"]  # 后端生成并返回
