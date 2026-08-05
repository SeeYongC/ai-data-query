"""FastAPI backend for DataAgent - production ready."""
import json, os, sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.database import Database
from backend.agent import Agent
from backend.governance import Governance
from backend.config_manager import (
    list_connections, add_connection, remove_connection,
    test_connection, toggle_connection, get_active_connections,
    DIALECT_DESCRIPTIONS, DIALECT_EXAMPLES, load_config, save_config,
)

app = FastAPI(title="DataAgent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_PATH = BASE_DIR / "frontend" / "index.html"
DB_PATH = str(BASE_DIR / "data" / "ecommerce.db")

_databases = {}
_config_signature = None
agent: Agent | None = None
governance: Governance | None = None


class QueryRequest(BaseModel):
    question: str
    metric_selections: dict[str, int] | None = None
    selected_database: str | None = None

class QueryResponse(BaseModel):
    success: bool; sql: str | None = None; explanation: str | None = None
    columns: list[str] | None = None; rows: list[list] | None = None
    row_count: int = 0; retried: bool = False
    error: str | None = None; first_error: str | None = None
    metric_conflict: bool | None = None; conflicts: list[dict] | None = None
    question: str | None = None; raw_response: str | None = None
    database_select: bool | None = None; databases: list[dict] | None = None

class ConnectionRequest(BaseModel):
    dialect: str = "mysql"; host: str = "localhost"; port: int = 3306
    user: str = "root"; password: str = ""; database: str = ""
    name: str = ""; conn_id: str = ""; enable: bool = True


def _ensure_db(force: bool = False):
    """Load databases from connections.json. Auto-add primary ecommerce.db if empty.

    Rebuilds only when the config signature changed (or force=True), so per-request
    calls reuse the existing engines instead of disposing and recreating them.
    """
    global _databases, _config_signature
    if not force:
        current = json.dumps(load_config(), sort_keys=True, ensure_ascii=False)
        if current == _config_signature and _databases:
            return
    for db in _databases.values():
        try: db.close()
        except Exception: pass
    _databases.clear()
    
    # Auto-add primary database if connections.json is empty
    config = load_config()
    if not config.get("connections"):
        add_connection("sqlite", "localhost", 0, "", "", DB_PATH, "电商数据库 (SQLite)")
    
    actives = get_active_connections()
    for c in actives:
        label = c.get("name", c.get("database", "unknown"))
        try:
            _databases[label] = Database(c["url"])
        except Exception as e:
            print(f"  FAILED: {label} - {e}")
    _config_signature = json.dumps(load_config(), sort_keys=True, ensure_ascii=False)


def _ensure_agent():
    global agent, governance
    _ensure_db()
    if not _databases:
        raise HTTPException(status_code=500, detail="没有可用的数据库。请在左侧添加连接并激活。")
    dk = os.environ.get("DEEPSEEK_API_KEY", "")
    ok = os.environ.get("OPENAI_API_KEY", "")
    if agent is None:
        first_db = list(_databases.values())[0]
        if dk:
            agent = Agent(first_db, api_key=dk, model="deepseek-chat", base_url="https://api.deepseek.com")
        elif ok:
            agent = Agent(first_db, api_key=ok, model="gpt-4o")
        else:
            raise HTTPException(status_code=500, detail="Set DEEPSEEK_API_KEY or OPENAI_API_KEY")
        governance = Governance(first_db)
        agent.set_governance(governance)
    agent.set_all_databases(_databases)


# ===== Connection Endpoints (all go through connections.json) =====

@app.get("/api/connections")
async def api_list_connections():
    return {"connections": list_connections(), "dialect_info": DIALECT_DESCRIPTIONS, "examples": DIALECT_EXAMPLES}

@app.post("/api/connections/test")
async def api_test_connection(req: ConnectionRequest):
    return test_connection(req.dialect, req.host, req.port, req.user, req.password, req.database)

@app.post("/api/connections")
async def api_add_connection(req: ConnectionRequest):
    try:
        conn = add_connection(req.dialect, req.host, req.port, req.user, req.password, req.database, req.name)
        _ensure_db(force=True)
        return {"success": True, "connection": conn}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/connections/{conn_id}")
async def api_remove_connection(conn_id: str):
    try:
        remove_connection(conn_id)
        _ensure_db(force=True)
        # Also clear agent to force re-init with remaining connections
        global agent; agent = None
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/connections/toggle")
async def api_toggle_connection(req: ConnectionRequest):
    try:
        toggle_connection(req.conn_id, req.enable)
        _ensure_db(force=True)
        global agent; agent = None
        return {"success": True, "active_count": len(_databases)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/connections/current")
async def api_current():
    actives = get_active_connections()
    return {"active_connections": actives, "count": len(actives)}

@app.post("/api/refresh")
async def api_refresh():
    global agent; agent = None
    _ensure_db(force=True)
    _ensure_agent()
    return {"success": True, "databases": len(_databases)}

@app.get("/api/health")
async def health():
    return {"status": "ok", "db_path": DB_PATH, "api_configured": bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"))}

@app.get("/api/schema")
async def schema():
    _ensure_agent()
    schemas = {}
    for name, db in _databases.items():
        try: schemas[name] = db.get_schema_text()
        except Exception as e: schemas[name] = f"Error: {e}"
    return {"schemas": schemas}

@app.post("/api/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    try:
        _ensure_agent()
        result = await agent.query(req.question, req.metric_selections, req.selected_database)
        return QueryResponse(**result)
    except HTTPException: raise
    except Exception as e: return QueryResponse(success=False, error=str(e))

@app.get("/", response_class=HTMLResponse)
async def index():
    if FRONTEND_PATH.exists(): return FileResponse(str(FRONTEND_PATH))
    return "<h1>DataAgent API is running</h1>"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
