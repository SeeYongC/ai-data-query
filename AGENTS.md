# AGENTS.md — ai-data-query (DataAgent)

AI 原生数据问询系统：自然语言提问 → LLM 生成 SQL → 查询多数据库 → 表格/图表可视化，内置口径治理（Metric Governance）。FastAPI 后端 + 零框架单文件前端。

## Project
- 后端：Python 3.10+ / FastAPI / SQLAlchemy / openai SDK；入口 `backend/main.py`（uvicorn）
- 前端：`frontend/index.html` 单文件 SPA（无构建步骤，Chart.js 走 CDN）
- 数据：SQLite `data/ecommerce.db`（模拟电商，5 表）；可连 MySQL/PostgreSQL/ClickHouse
- 配置：`connections.json`（gitignore，含密码）；API key 走环境变量 `DEEPSEEK_API_KEY` / `OPENAI_API_KEY`

## Commands
```powershell
# 测试（Windows venv）
.venv\Scripts\python.exe -m pytest tests -q

# 本地运行
cd backend; python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Docker 运行
docker compose up -d --build     # 访问 http://localhost:8000

# 数据/口径种子
python scripts/generate_mock_data.py
python scripts/seed_metrics.py
```

## Architecture
- `backend/main.py` — FastAPI 入口 + 全部 REST 端点；`_ensure_db` 按 connections.json 签名重建引擎；`SESSIONS`（进程内会话记忆，LRU：MAX_SESSIONS=100 / MAX_HISTORY=12，重启丢失）
- `backend/agent.py` — Agent 引擎：prompt 构建（schema + 会话历史 + 口径注入）、`_call_llm`、`_is_read_only` 只读防护、`_validate_sql_tables` 表名校验、失败自愈重试
- `backend/database.py` — SQLAlchemy 适配层（SQLite/MySQL/PG/ClickHouse 统一接口）
- `backend/config_manager.py` — `connections.json` CRUD（id 自增、URL 构建、明文密码不入 list 响应但 url 字段仍含密码）
- `backend/governance.py` — 口径治理：metric_definitions 表、冲突检测、偏好存储
- `frontend/index.html` — SPA：双主题、连接管理、口径冲突卡片、多库选择、Chart.js 渲染

## Conventions
- **提交**：本机无 GPG 密钥，必须 `git commit --no-gpg-sign -m "..."`（否则报 signing failed）
- **只读防护**：`_is_read_only` 只放行 SELECT/WITH 开头；改 `READ_WRITE_KW`/`_strip_literals` 时注意注释剥离边界（`/*x*/` 紧贴可拼词绕过 `\b`）和 `#` 注释未剥离（误报）
- **表名校验**：`_validate_sql_tables` 已知会把 CTE 名误报为不存在的表；`kw` 集合含 order/group 等词，真实表名撞词会漏检
- **测试**：不依赖真实 LLM/外部 DB；mock `Agent._call_llm` + `TestClient`；模块级全局状态（`_databases`/`agent`/`SESSIONS`/`CONFIG_PATH`）必须在 fixture 中清理，否则用例互相污染
- **安全**：`connections.json` 含明文密码，已被 gitignore——不要提交；新端点不要把连接 `url`（含密码）暴露给前端
- **语言**：UI 与用户可见错误消息用中文；代码注释中文
- **分支**：`docs/update-readme` = README 重写+地址修复（PR #4 已开）；`feat/docker-conversation` = Docker + 会话记忆 + 路线图更新（当前分支，未推送）。功能开发勿混入 docs 分支

## Notes
（待补充：多步推理、前端框架化 v0.8 等后续方向）
