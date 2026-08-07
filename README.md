<div align="center">

# 🧠 DataAgent

### AI 原生数据问询系统 — 让每个人都能直接向数据库提问

> 基于大语言模型(DeepSeek / OpenAI)的智能数据问询平台。用户用自然语言提问,系统自动完成
> **语义理解 → SQL 生成 → 数据库查询 → 可视化呈现** 的完整链路,并内置独创的 **口径治理(Metric Governance)** 能力。

<!-- GitHub 徽章 -->
![GitHub stars](https://img.shields.io/github/stars/SeeYongC/ai-data-query?style=for-the-badge&color=8250df)
![GitHub forks](https://img.shields.io/github/forks/SeeYongC/ai-data-query?style=for-the-badge&color=8250df)
![GitHub issues](https://img.shields.io/github/issues/SeeYongC/ai-data-query?style=for-the-badge&color=8250df)
![GitHub license](https://img.shields.io/github/license/SeeYongC/ai-data-query?style=for-the-badge&color=8250df)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Frontend](https://img.shields.io/badge/Frontend-Vanilla%20JS-F7DF1E?logo=javascript&logoColor=black)
![LLM](https://img.shields.io/badge/LLM-DeepSeek%20%7C%20OpenAI-4D6BFE)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?logo=sqlalchemy&logoColor=white)
![Chart.js](https://img.shields.io/badge/Chart.js-4.4-FF6384?logo=chartdotjs&logoColor=white)
![Database](https://img.shields.io/badge/DB-SQLite%20%7C%20MySQL%20%7C%20PostgreSQL%20%7C%20ClickHouse-4479A1)
![Version](https://img.shields.io/badge/version-v0.3-8250df)

</div>

---

## ✨ 核心特性

| | 特性 | 说明 |
|---|---|---|
| 🗣️ | **自然语言问数** | 中文提问直接出结果,无需懂 SQL,支持排名 / 对比 / 趋势 / 占比 / 用户偏好等分析类型 |
| 📐 | **口径治理(独创)** | 内置指标口径知识图谱,问题涉及多重定义的指标时,主动弹出冲突卡片让用户确认,杜绝"口径对不上" |
| 🗄️ | **多数据库管理** | 基于 SQLAlchemy 统一适配 SQLite / MySQL / PostgreSQL / ClickHouse,支持多库并行与独立开关 |
| 🛡️ | **SQL 表名校验** | 执行前校验 `FROM` / `JOIN` 表名,拦截 LLM 幻觉出的不存在的表,并回传真实表清单修正 |
| 🔧 | **SQL 自愈机制** | SQL 执行失败时自动携带错误信息重试修正,成功则标注「已自动修正」 |
| 📊 | **自动可视化** | 结果自动渲染为表格与图表:时间序列 → 折线图,分类数据 → 柱状图 |
| 🌗 | **双主题界面** | 暗黑 / 暖色双主题一键切换,偏好本地持久化 |
| ⚡ | **零框架单文件前端** | 无构建步骤,一个 `index.html` 即完整 SPA,轻量易部署 |

---

## 🎯 要解决的问题

在大中型企业中,数据部门每天面对大量取数需求:

> 「帮我拉一下上个月各区域的销售额」
> 「活跃用户有多少?按年龄段分一下」

传统链路是 **业务方提需求 → 数据团队理解口径 → 找表 → 写 SQL → 出结果 → 交付**,每个环节都是手工的,每个环节都可能出错:

| 痛点 | 具体表现 |
|---|---|
| **口径不统一** | 「活跃用户」在财务部、运营部、市场部有 3 种不同定义,每次取数都要来回确认 |
| **找表困难** | 数仓有几百上千张表,新人入职两周还在熟悉表结构 |
| **SQL 门槛** | 业务人员不懂 SQL,数据团队成了瓶颈,一个简单取数排期 3 天 |
| **重复劳动** | 相似的取数需求反复出现,每次都要重新写 SQL |

与市面 BI 工具(Tableau、Metabase)或 Text-to-SQL 工具(ThoughtSpot)不同,DataAgent 的核心设计是 **Agent 驱动** 而非规则驱动,并且独创了 **口径治理** 能力——不是"尽力生成 SQL",而是**先确认业务口径,再生成准确查询**。

---

## 🔄 工作原理

```
"上月销售额最高的五个品类?"
        │
        ▼
┌─────────────────────────────────────────────┐
│  Agent 引擎                                  │
│                                              │
│  1. 读取数据库 Schema(表结构 + 字段 + 行数)   │
│  2. 口径冲突检测(Governance)                  │
│     └─ 有冲突 → 弹出选择卡片让用户确认         │
│  3. 构造 System Prompt,注入 Schema + 业务规则 │
│  4. 调用 LLM(DeepSeek / OpenAI)生成 SQL      │
│  5. 表名校验:拦截不存在的表名并反馈修正        │
│  6. 执行 SQL(失败则携带错误自愈重试)           │
│  7. 返回 SQL + 数据 + 中文解释                │
└─────────────────────────────────────────────┘
        │
        ▼
表格 + 柱状图 + 中文解释
```

**示例**:用户问「上月活跃用户有多少?」,Agent 检测到「活跃用户」存在 3 种口径定义,不会直接查询,而是先让用户选择:

| 口径 | 部门 | 定义 | 数据来源 |
|---|---|---|---|
| 财务口径 | 财务部 | 近 30 天有交易行为的用户 | orders |
| 运营口径 | 运营部 | 近 7 天有登录行为的用户 | user_logins |
| 市场口径 | 市场部 | 近 90 天有点击行为的用户 | user_clicks |

选定后,对应口径的 SQL 条件被注入 Prompt,确保生成准确查询。系统内置 **9 个常见指标的 17 种口径定义**,可在 `scripts/seed_metrics.py` 中自定义扩展。

---

## 🚀 快速开始

### 使用 Docker 运行(推荐)

```bash
# 1. 克隆项目
git clone https://github.com/SeeYongC/ai-data-query.git
cd ai-data-query

# 2. 配置 API Key(二选一),写入 .env 文件
echo "DEEPSEEK_API_KEY=sk-your-api-key" > .env
# 或:echo "OPENAI_API_KEY=sk-your-api-key" > .env

# 3. 构建并启动
docker compose up -d --build
```

启动后浏览器访问 **http://localhost:8000**。SQLite 数据库通过 volume 持久化,重启容器数据不丢失。

### 环境要求(本地开发)

- Python 3.10+
- DeepSeek 或 OpenAI 的 API Key([申请地址](https://platform.deepseek.com/))
- (可选)MySQL / PostgreSQL / ClickHouse,用于连接外部数据库

### 安装

```bash
# 1. 克隆项目
git clone https://github.com/SeeYongC/ai-data-query.git
cd ai-data-query

# 2. 创建并激活虚拟环境(推荐)
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
# (可选)开发 / 测试依赖
pip install -r requirements-dev.txt

# 4. (可选)重新生成模拟数据 / 种子口径定义
python scripts/generate_mock_data.py
python scripts/seed_metrics.py
```

### 启动

```bash
# Windows PowerShell:
$env:DEEPSEEK_API_KEY="sk-your-api-key"
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Linux / macOS:
export DEEPSEEK_API_KEY="sk-your-api-key"
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

启动后浏览器访问 **http://localhost:8000**。系统在 `connections.json` 为空时会自动创建指向 `data/ecommerce.db`(模拟电商数据库:5 张表、180 商品、1K 用户、10K 订单)的默认连接,开箱即用。

### 运行测试

```bash
python -m pytest tests -v
```

测试覆盖数据库适配层(`database.py`)、口径治理(`governance.py`)、连接管理(`config_manager.py`)以及 Agent 的表名校验与响应解析(`agent.py`、`main.py`),不依赖真实 LLM 与外部数据库。

---

## 📚 使用指南

**基本问数** — 在底部输入框用自然语言提问,或直接点击示例问题:

```
这个数据库有哪些表?
上月销售额最高的五个品类?
各年龄段消费能力对比
今年各月销售额趋势
退款率最高的品类
```

**管理数据库连接** — 左侧「数据源」面板:每个数据库前有独立 toggle 开关,点击激活/关闭;「+ 添加」打开连接配置弹窗,支持测试连接后保存;悬停显示「x」删除;同时激活多个库时,提问会先弹出数据库选择卡片。

**处理口径冲突** — 输入涉及多重定义指标的问题(如「活跃用户有多少?」),系统弹出紫色口径冲突卡片,选择定义后点击「确认口径,继续查询」,系统将选中口径的 SQL 条件注入 Prompt 生成准确查询。

**切换主题** — 点击右上角「☀ 暖色调」/「☾ 暗黑」按钮切换,偏好保存在浏览器 localStorage。

---

## 🏗️ 系统架构

```mermaid
flowchart TB
    subgraph Client["浏览器 (SPA)"]
        UI["Chart.js 图表 · Schema 面板 · 示例问题<br/>双主题 · 连接管理 · 冲突卡片"]
    end

    subgraph Server["FastAPI 后端"]
        API["/api/query · /api/schema<br/>/api/connections · /api/health"]
        AGENT["Agent 引擎<br/>SQL 生成 · 口径检测 · 表名校验 · 自愈重试"]
    end

    subgraph Data["数据层"]
        GOV["口径治理 (Governance)<br/>metric_definitions 表"]
        DB[("SQLite / MySQL /<br/>PostgreSQL / ClickHouse")]
    end

    UI -->|"HTTP / JSON"| API
    API --> AGENT
    AGENT --> GOV
    AGENT --> DB
```

---

## 🛠️ 技术栈

| 层级 | 技术 | 版本 | 说明 |
|---|---|---|---|
| 前端 | HTML5 + CSS3 + JavaScript | — | 零框架,单文件 SPA,无构建步骤 |
| 图表 | Chart.js | 4.4 | CDN 引入,自动选择折线 / 柱状图 |
| 后端框架 | FastAPI | 0.115 | 异步,自动 OpenAPI 文档 |
| 服务器 | Uvicorn | 0.30 | ASGI 服务器 |
| LLM SDK | openai | 1.50 | 兼容多厂商(base_url 可切换) |
| 大模型 | DeepSeek-chat / GPT-4o | — | 默认 DeepSeek,可切换 OpenAI |
| 数据库适配 | SQLAlchemy | 2.0 | 统一 SQLite / MySQL / PG / ClickHouse 接口 |
| 数据校验 | Pydantic | 2.9 | 请求 / 响应模型 |

---

## 📁 项目结构

```
ai-data-query/
├── backend/
│   ├── main.py              # FastAPI 应用入口与全部 REST 端点
│   ├── agent.py             # LLM Agent:SQL 生成 + 表名校验 + 自愈
│   ├── database.py          # SQLAlchemy 适配层(SQLite/MySQL/PG/CH)
│   ├── config_manager.py    # 连接配置管理(connections.json CRUD)
│   └── governance.py        # 口径治理:冲突检测 + 注入 + 偏好存储
├── frontend/
│   └── index.html           # SPA:双主题 + 连接管理 + 冲突卡片
├── data/
│   ├── ecommerce.db         # 模拟电商(5 表,180 商品,1K 用户,10K 订单)
│   └── test_shop.db         # 轻量测试(2 表,7 行)
├── scripts/
│   ├── generate_mock_data.py  # 生成模拟电商数据
│   └── seed_metrics.py        # 种子口径定义
├── tests/                   # 单元测试(不依赖真实 LLM 与外部数据库)
├── connections.example.json # 连接配置模板(无真实密码)
├── connections.json         # 真实连接配置(.gitignore 已排除)
├── requirements.txt         # Python 依赖
└── README.md
```

---

## 🔌 API 概览

### 核心端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 返回前端 SPA 页面 |
| GET | `/api/health` | 健康检查(含 API Key 配置状态) |
| GET | `/api/schema` | 返回所有激活数据库的表结构 |
| POST | `/api/query` | **核心接口**:提交自然语言问题,返回 SQL + 数据 |

### 查询请求

```json
POST /api/query
{
  "question": "上月销售额最高的品类?",
  "metric_selections": {"active_users": 1},
  "selected_database": "电商数据库 (SQLite)"
}
```

### 查询响应(成功)

```json
{
  "success": true,
  "sql": "SELECT c.category_name, ROUND(SUM(o.total_amount), 2) as revenue FROM ...",
  "explanation": "查询上月各品类已完成订单的销售额,降序排列",
  "columns": ["category_name", "revenue"],
  "rows": [["电子产品", 1234567.89], ["服装鞋帽", 987654.32]],
  "row_count": 5,
  "retried": false
}
```

### 查询响应(口径冲突 / 多库选择)

```json
{
  "metric_conflict": true,
  "conflicts": [{
    "metric_name": "活跃用户",
    "metric_key": "active_users",
    "definitions": [
      {"definition_name": "财务口径", "description": "近30天有交易行为", "owner_department": "财务部"}
    ]
  }],
  "question": "上月活跃用户有多少?"
}
```

```json
{
  "database_select": true,
  "databases": [
    {"name": "电商数据库 (SQLite)", "table_count": 5, "tables": ["categories", "orders", "products", "users", "order_items"]}
  ],
  "question": "这个数据库有哪些表?"
}
```

### 连接管理端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/connections` | 列出所有连接及方言信息 |
| POST | `/api/connections` | 添加连接 |
| DELETE | `/api/connections/{id}` | 删除连接 |
| POST | `/api/connections/test` | 测试连接 |
| POST | `/api/connections/toggle` | 切换激活状态 |
| GET | `/api/connections/current` | 获取当前激活的连接 |
| POST | `/api/refresh` | 强制刷新数据库连接与 Agent |

---

## ⚙️ 配置说明

### 环境变量

| 变量 | 说明 | 必填 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥(默认模型 `deepseek-chat`) | 是(二选一) |
| `OPENAI_API_KEY` | OpenAI API 密钥(模型 `gpt-4o`) | 否(备选) |
| `PYTHONIOENCODING` | Python 编码,Windows 下建议设为 `utf-8` | 推荐 |

### 数据库配置

系统默认连接 `data/ecommerce.db`。要连接其他数据库,有两种方式:

- **方式一(推荐)**:在 UI 左侧点击「+ 添加」→ 选择数据库类型 → 填写信息 → 测试连接 → 保存
- **方式二**:编辑 `connections.json`(参考 `connections.example.json` 模板),重启服务器生效

```json
{
  "connections": [{
    "id": "1",
    "name": "生产数据库",
    "dialect": "mysql",
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "your_password",
    "database": "your_database",
    "url": "mysql+pymysql://root:your_password@localhost:3306/your_database"
  }],
  "active_ids": ["1"]
}
```

> 连接 MySQL 需先 `pip install pymysql`,PostgreSQL 需 `pip install psycopg2`,ClickHouse 需 `pip install clickhouse-driver`。

### 自定义口径定义

口径数据存储在 SQLite 的 `metric_definitions` 表中。编辑 `scripts/seed_metrics.py`,在 `METRICS` 列表中添加新条目后运行 `python scripts/seed_metrics.py` 更新数据库:

```python
(metric_key, metric_name, definition_name, owner_department, data_source,
 sql_condition, sql_notes, description, business_rules)
```

---

## 🗺️ 路线图

| 阶段 | 目标 | 状态 |
|---|---|---|
| v0.4 | 会话记忆:Agent 记住上下文,支持追问 | ✅ 已完成 |
| v0.5 | 多步推理:复杂分析问题自动拆解为多步 SQL | 待做 |
| v0.6 | 数据质量监控:自动发现空值突增、环比突变 | 待做 |
| v0.7 | 用户认证与多租户 | 待做 |
| v0.8 | 前端框架化:迁移至 Vue / React 等组件化框架,引入 Vite 等构建流程,替代零框架单文件前端 | 待做 |
| v1.0 | Docker 部署 | ✅ 已完成 |
| v1.1 | SaaS 化 | 待做 |

---

## 🤝 贡献

欢迎贡献代码、报告 Issue 或提出改进建议!

1. Fork 本仓库并创建你的特性分支
2. 提交改动(遵循现有代码风格,重要改动请补充单元测试)
3. 发起 Pull Request

## 📄 License

[MIT](LICENSE) © DataAgent

---

<div align="center">

**DataAgent — Make data askable.**

让数据可以被直接提问。

⭐ 如果这个项目对你有帮助,欢迎 Star 支持!

</div>
