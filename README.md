# DataAgent — AI 原生数据问询系统

基于大语言模型（DeepSeek / OpenAI）的智能数据问询平台。用户用自然语言提问，系统自动完成 **语义理解 → SQL 生成 → 数据库查询 → 可视化呈现** 的完整链路，让不懂 SQL 的人也能直接从数据库获取答案。

---

## 目录

- [一、项目背景与要解决的问题](#一项目背景与要解决的问题)
- [二、核心功能](#二核心功能)
- [三、系统架构](#三系统架构)
- [四、技术栈](#四技术栈)
- [五、项目结构](#五项目结构)
- [六、安装与运行](#六安装与运行)
- [七、使用指南](#七使用指南)
- [八、API 文档](#八api-文档)
- [九、配置说明](#九配置说明)
- [十、后续规划](#十后续规划)

---

## 一、项目背景与要解决的问题

### 1.1 痛点

在大中型企业中，数据部门每天面对大量取数需求：

> 「帮我拉一下上个月各区域的销售额」
> 「活跃用户有多少？按年龄段分一下」

这条链路的典型流程是：**业务方提需求 → 数据团队理解口径 → 找表 → 写 SQL → 出结果 → 交付**。每个环节都是手工的，每个环节都可能出错：

| 痛点 | 具体表现 |
|---|---|
| **口径不统一** | 「活跃用户」在财务部、运营部、市场部有 3 种不同定义，每次取数都要来回确认 |
| **找表困难** | 数仓有几百上千张表，新人入职两周还在熟悉表结构 |
| **SQL 门槛** | 业务人员不懂 SQL，数据团队成了瓶颈，一个简单取数排期 3 天 |
| **重复劳动** | 相似的取数需求反复出现，每次都要重新写 SQL |

### 1.2 解决思路

DataAgent 用 **AI Agent** 替代人工数据查询链路：

1. **自然语言输入**：业务人员直接用中文描述需求，不需要懂 SQL
2. **自动 Schema 感知**：Agent 连接数据库后自动读取表结构，注入 LLM Prompt
3. **口径冲突检测**：当问题涉及有多重定义的指标时，Agent 主动弹出选择卡片让用户确认
4. **SQL 自愈**：生成的 SQL 执行失败时，Agent 将错误信息和真实表清单反馈给 LLM 重试修正
5. **可视化呈现**：查询结果自动渲染为表格和图表

与市面上 BI 工具（Tableau、Metabase）或 Text-to-SQL 工具（ThoughtSpot）不同，DataAgent 的核心设计是 **Agent 驱动** 而非规则驱动，并且独创了 **口径治理** 能力。

---

## 二、核心功能

### 2.1 智能自然语言问数

用户打字提问，Agent 自动完成全流程：

```
"上月销售额最高的五个品类？"
        │
        ▼
Agent 读取数据库 Schema（表结构 + 字段 + 行数）
        │
        ▼
构造 System Prompt，注入 Schema + 业务规则
        │
        ▼
调用 DeepSeek / GPT-4o 生成 SQL
        │
        ▼
解析 SQL，执行查询
        │
        ▼
返回表格 + 柱状图 + 中文解释
```

支持的分析类型：
- **排名 Top-N**：「销售额最高的品类」「卖得最好的商品」
- **对比分析**：「北京和上海客单价对比」「各年龄段人均消费」
- **时间趋势**：「今年各月销售额趋势」「双十一订单量」
- **比率分布**：「各支付方式占比」「退款率最高的品类」
- **用户偏好**：「25-34 岁用户最喜欢的品类」

### 2.2 口径治理

这是 DataAgent 的核心差异化功能。系统内置口径知识图谱，当用户的问题涉及有多重定义的指标时，**不会直接生成 SQL**，而是先弹出冲突卡片让用户确认。

**示例**：用户问「上月活跃用户有多少？」

Agent 检测到「活跃用户」在数据库中有 3 种口径定义：

| 口径 | 部门 | 定义 | 数据来源 |
|---|---|---|---|
| 财务口径 | 财务部 | 近 30 天有交易行为的用户 | orders |
| 运营口径 | 运营部 | 近 7 天有登录行为的用户 | user_logins |
| 市场口径 | 市场部 | 近 90 天有点击行为的用户 | user_clicks |

前端弹出紫色卡片，用户选择后，对应口径的 SQL 条件会被注入 Prompt，确保生成准确的 SQL。

系统内置了 9 个常见指标的 17 种口径定义，可在 `scripts/seed_metrics.py` 中自定义扩展。

### 2.3 多数据库管理

通过 SQLAlchemy 统一适配层，DataAgent 可同时连接多种数据库：

| 数据库 | 连接方式 |
|---|---|
| SQLite | 零配置，直接指定文件路径 |
| MySQL | `pip install pymysql`，通过 UI 或配置文件连接 |
| PostgreSQL | `pip install psycopg2`，通过 UI 或配置文件连接 |
| ClickHouse | `pip install clickhouse-driver` |

前端左侧面板支持：
- **独立 Toggle 开关**：每个数据库可单独开启/关闭
- **多库并行**：同时激活多个数据库时，Agent 会弹出选择卡片
- **一键删除**：x 按钮删除不用的连接

### 2.4 SQL 表名校验

LLM 生成的 SQL 可能包含不存在的表名或字段名。DataAgent 在执行前会：

1. 提取 SQL 中 `FROM` / `JOIN` 后的表名
2. 对照数据库真实表清单
3. 如果表名不存在，拦截 SQL 并将真实表名列表反馈给 LLM
4. LLM 基于反馈重写 SQL

### 2.5 SQL 自愈机制

SQL 执行失败时，DataAgent 不会直接报错，而是：

1. 捕获错误信息（如表不存在、语法错误等）
2. 将错误信息 + 数据库真实表清单注入重试 Prompt
3. LLM 分析错误原因并生成修正后的 SQL
4. 二次执行，成功则标注「已自动修正」

### 2.6 可视化

- 查询结果自动渲染为表格（数字格式化、NULL 处理）
- 根据数据类型自动选择图表：时间序列 → 折线图，分类数据 → 柱状图
- 前端支持 **暗黑模式** 和 **暖色模式** 双主题，一键切换

---

## 三、系统架构

```
┌──────────────────────────────────────────┐
│              浏览器 (SPA)                 │
│  Chart.js 图表 / Schema 面板 / 示例问题     │
└──────────────┬───────────────────────────┘
               │ HTTP
┌──────────────▼───────────────────────────┐
│            FastAPI 后端                    │
│  /api/query  /api/schema  /api/connections │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼───────────────────────────┐
│           Agent 引擎                      │
│  ┌─────────────────────────────────────┐ │
│  │ 1. 接收自然语言问题                  │ │
│  │ 2. 读取数据库 Schema                 │ │
│  │ 3. 口径冲突检测（Governance）         │ │
│  │ 4. 构造 System Prompt                │ │
│  │ 5. 调用 LLM（DeepSeek / OpenAI）     │ │
│  │ 6. 解析 JSON 提取 SQL               │ │
│  │ 7. 表名校验（Validate Tables）       │ │
│  │ 8. 执行 SQL（失败则自愈重试）         │ │
│  │ 9. 返回 SQL + 数据 + 解释            │ │
│  └─────────────────────────────────────┘ │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼───────────────────────────┐
│       数据库适配层 (SQLAlchemy)           │
│   SQLite / MySQL / PostgreSQL / ClickHouse │
└──────────────────────────────────────────┘
```

### 请求生命周期

以用户问「上月销售额最高的品类？」为例：

```
1. 用户输入问题，点击发送
2. 前端 POST /api/query → {"question": "上月销售额最高的品类？"}
3. FastAPI → _ensure_agent() → 初始化/更新 Agent
4. Agent.governance.detect_metrics(question) → 无冲突，跳过
5. Agent._build_prompt() → 读取 Schema → 注入 Prompt
6. Agent._call_llm() → 调用 DeepSeek API → 返回 JSON
7. Agent._parse_response() → 提取 SQL
8. Agent._validate_sql_tables() → 检查表名存在
9. Database.execute(sql) → SQLAlchemy 执行查询
10. 返回 {success: true, sql, columns, rows, explanation}
11. 前端渲染表格 + 图表
```

---

## 四、技术栈

| 层级 | 技术 | 版本 | 说明 |
|---|---|---|---|
| 前端 | HTML5 + CSS3 + JavaScript | - | 零框架，单文件 SPA |
| 图表 | Chart.js | 4.4 | CDN 引入 |
| 后端框架 | FastAPI | 0.115 | 异步，自动 OpenAPI |
| 服务器 | Uvicorn | 0.30 | ASGI |
| LLM SDK | openai | 1.50 | 兼容多厂商 |
| 大模型 | DeepSeek-chat | - | 默认，可通过 base_url 切换 |
| 数据库适配 | SQLAlchemy | 2.0 | 统一多库接口 |
| 数据校验 | Pydantic | 2.9 | 请求/响应模型 |

---

## 五、项目结构

```
data-agent/
├── backend/
│   ├── main.py              # FastAPI 应用入口，数据库硬编码
│   ├── agent.py             # LLM Agent：SQL 生成 + 表名校验 + 自愈
│   ├── database.py          # SQLAlchemy 适配层（SQLite/MySQL/PG/CH）
│   ├── config_manager.py    # 连接配置管理（connections.json CRUD）
│   └── governance.py        # 口径治理：冲突检测 + 注入 + 偏好存储
├── frontend/
│   └── index.html           # SPA：双主题 + 连接管理 + 冲突卡片
├── data/
│   ├── ecommerce.db         # 模拟电商（5 表，180 商品，1K 用户，10K 订单）
│   └── test_shop.db         # 轻量测试（2 表，7 行）
├── scripts/
│   ├── generate_mock_data.py  # 生成模拟电商数据
│   └── seed_metrics.py        # 种子口径定义
├── connections.example.json # 连接配置模板（无真实密码）
├── connections.json         # 真实连接配置（.gitignore 已排除）
├── requirements.txt         # Python 依赖
├── .gitignore
└── README.md
```

---

## 六、安装与运行

### 6.1 环境要求

- Python 3.10+
- DeepSeek API Key（[申请地址](https://platform.deepseek.com/)）
- （可选）MySQL / PostgreSQL / ClickHouse 用于连接外部数据库

### 6.2 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/yourname/data-agent.git
cd data-agent

# 2. 创建虚拟环境（推荐）
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. （可选）重新生成模拟数据
python scripts/generate_mock_data.py

# 5. （可选）种子口径定义
python scripts/seed_metrics.py
```

### 6.3 启动服务

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

启动后打开浏览器访问 `http://localhost:8000`。

### 6.4 连接 MySQL（可选）

```bash
pip install pymysql
```

然后在页面左侧「数据源」面板点击「+ 添加」，选择 MySQL，填写连接信息。或在 `connections.json` 中直接配置：

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

### 6.5 常见问题

**Q: 启动后页面打开，但左侧 Schema 面板为空？**

确保 `connections.json` 中至少有一个连接且 `active_ids` 包含其 ID。系统会在 `connections.json` 为空时自动创建指向 `data/ecommerce.db` 的默认连接。

**Q: 查询报错 "no such table: xxx"？**

LLM 幻觉了不存在的表名。系统会自动将错误和真实表清单反馈给 LLM 重试。如果仍然失败，请用更明确的问题重试，例如指定数据库名。

**Q: 页面中文显示为乱码？**

确保以 UTF-8 编码保存文件。如使用 PowerShell，设置 `$env:PYTHONIOENCODING="utf-8"`。

---

## 七、使用指南

### 7.1 基本问数

在页面底部输入框用自然语言提问：

```
这个数据库有哪些表？
上月销售额最高的五个品类？
各年龄段消费能力对比
今年各月销售额趋势
退款率最高的品类
```

点击示例问题可快速体验。

### 7.2 管理数据库连接

1. 左侧「数据源」面板显示所有已配置的数据库
2. 每个数据库前有 **toggle 开关**，点击激活/关闭
3. 点击「+ 添加」打开连接配置弹窗
4. 选择数据库类型，填写连接信息，点击「测试连接」验证
5. 验证通过后点击「保存并连接」
6. 悬停连接项显示「x」按钮，点击删除

### 7.3 处理口径冲突

1. 输入涉及多重定义指标的问题（如「活跃用户有多少？」）
2. 系统弹出紫色口径冲突卡片，列出所有可用定义
3. 点击选择需要的口径定义
4. 点击「确认口径，继续查询」
5. 系统将选中口径的 SQL 条件注入 Prompt，生成准确查询

### 7.4 切换主题

点击页面右上角的「☀ 暖色调」/「☾ 暗黑」按钮切换主题。主题偏好保存在浏览器 localStorage 中。

### 7.5 多数据库查询

同时激活多个数据库（toggle 开关打开），提问时系统会弹出数据库选择卡片，列出每个库的表数和表名，选择目标库后继续查询。

---

## 八、API 文档

### 8.1 核心端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 返回前端 SPA 页面 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/schema` | 返回所有激活数据库的表结构 |
| POST | `/api/query` | 核心接口：提交自然语言问题，返回 SQL + 数据 |

### 8.2 查询接口

**POST** `/api/query`

请求体：
```json
{
  "question": "上月销售额最高的品类？",
  "metric_selections": {"active_users": 1},
  "selected_database": "电商数据库 (SQLite)"
}
```

成功响应：
```json
{
  "success": true,
  "sql": "SELECT c.category_name, ROUND(SUM(o.total_amount), 2) as revenue FROM ...",
  "explanation": "查询上月各品类已完成订单的销售额，降序排列",
  "columns": ["category_name", "revenue"],
  "rows": [["电子产品", 1234567.89], ["服装鞋帽", 987654.32]],
  "row_count": 5,
  "retried": false
}
```

口径冲突响应：
```json
{
  "metric_conflict": true,
  "conflicts": [{
    "metric_name": "活跃用户",
    "metric_key": "active_users",
    "definitions": [
      {"definition_name": "财务口径", "description": "近30天有交易行为", "owner_department": "财务部"},
      {"definition_name": "运营口径", "description": "近7天有登录行为", "owner_department": "运营部"}
    ]
  }],
  "question": "上月活跃用户有多少？"
}
```

多库选择响应：
```json
{
  "database_select": true,
  "databases": [
    {"name": "电商数据库 (SQLite)", "table_count": 5, "tables": ["categories", "orders", "products", "users", "order_items"]},
    {"name": "测试商店 (SQLite)", "table_count": 2, "tables": ["users", "orders"]}
  ],
  "question": "这个数据库有哪些表？"
}
```

### 8.3 连接管理端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/connections` | 列出所有连接 |
| POST | `/api/connections` | 添加连接 |
| DELETE | `/api/connections/{id}` | 删除连接 |
| POST | `/api/connections/test` | 测试连接 |
| POST | `/api/connections/toggle` | 切换激活状态 |
| GET | `/api/connections/current` | 获取当前激活的连接 |

---

## 九、配置说明

### 9.1 环境变量

| 变量 | 说明 | 必填 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | 是（或 `OPENAI_API_KEY`） |
| `OPENAI_API_KEY` | OpenAI API 密钥 | 否（备选） |
| `PYTHONIOENCODING` | Python 编码，Windows 下建议设为 `utf-8` | 推荐 |

### 9.2 数据库配置

系统默认连接 `data/ecommerce.db`。要连接其他数据库：

**方式一：通过 UI**（推荐）
点击「+ 添加」→ 选择数据库类型 → 填写信息 → 测试连接 → 保存

**方式二：编辑 `connections.json`**
手动编辑 `connections.json`，参考 `connections.example.json` 模板，重启服务器后生效。

### 9.3 口径定义

口径数据存储在 SQLite 数据库的 `metric_definitions` 表中。要添加自定义口径：

1. 编辑 `scripts/seed_metrics.py`，在 `METRICS` 列表中添加新条目
2. 运行 `python scripts/seed_metrics.py` 更新数据库

每条口径的定义格式：
```python
(metric_key, metric_name, definition_name, owner_department, data_source,
 sql_condition, sql_notes, description, business_rules)
```

---

## 十、后续规划

| 阶段 | 目标 |
|---|---|
| v0.4 | 会话记忆：Agent 记住上下文，支持追问 |
| v0.5 | 多步推理：复杂分析问题自动拆解为多步 SQL |
| v0.6 | 数据质量监控：自动发现空值突增、环比突变 |
| v0.7 | 用户认证与多租户 |
| v1.0 | Docker 部署 + SaaS 化 |

---

**DataAgent — Make data askable.**

让数据可以被直接提问。
