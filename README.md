# 掌柜问数（data-agent）

面向电商业务的对话式 **NL2SQL 取数系统**。商家 / 运营以自然语言提问（如「统计华北地区销售总额」「Q2 各品类销量 Top10」），系统经 **LangGraph 12 节点编排流水线**自动完成关键词抽取 → 元数据三路召回 → Schema 裁剪 → SQL 生成 → `EXPLAIN` 预校验 → 执行错误驱动纠偏 → 最终执行，并以 **SSE 流式**推送各阶段进度与结果表格。

核心设计是「**元数据知识库**」：表 / 字段 / 指标的中文描述与别名向量化入 **Qdrant**，字段取值入 **Elasticsearch**（`ik_max_word` 中文分词）做全文召回，从源头解决自然语言与数据库 Schema 之间的语义鸿沟；配合白名单约束 + 预校验 + 纠偏闭环抑制 SQL 幻觉。

---

## ✨ 功能特性

- **对话式取数**：自然语言提问，自动生成 SQL 并返回结果表格。
- **12 节点流水线**：基于 LangGraph 的 `StateGraph` 编排，`extract_keywords → 三路并行召回 → merge → filter → add_extra_context → generate_sql → validate_sql →（条件纠偏）→ execute_sql`。
- **元数据三路召回**：字段向量召回（Qdrant）、指标向量召回（Qdrant）、字段值全文召回（ES），每条召回路径先经 LLM 扩展关键词再检索。
- **防 SQL 幻觉**：SQL 生成 prompt 硬约束（白名单字段、禁写、主外键关联、单条纯 SQL）+ `EXPLAIN` 预校验 + 执行报错最小必要修复闭环，`temperature=0`，指标口径绑定 `relevant_columns`。
- **流式交互**：SSE（`text/event-stream`）+ LangGraph `astream(stream_mode="custom")` 逐事件推送，前端实时渲染 12 阶段执行状态（running / success / error 三态）与结果表格。

---

## 🧱 技术栈

| 分类 | 技术 |
| --- | --- |
| 后端框架 | FastAPI（`lifespan` + 依赖注入） |
| Agent 编排 | LangGraph、LangChain、langchain-deepseek |
| LLM | DeepSeek（`deepseek-chat`） |
| 向量检索 | Qdrant（1024 维） |
| 全文检索 | Elasticsearch 8（`ik_max_word` 中文分词） |
| 向量模型 | `BAAI/bge-large-zh-v1.5`（TEI 本地推理） |
| 数据库 | MySQL 8（SQLAlchemy 2.x async + asyncmy，`meta` / `dw` 双库） |
| 分词 | jieba（TF-IDF 关键词抽取） |
| 前端 | Vue 3 + Vite 7（`fetch` + `ReadableStream` 手写 SSE 解析） |
| 工程化 | uv、OmegaConf、loguru、PyYAML |

---

## 🏗️ 系统架构

### 12 节点编排流水线

```
START
  └─▶ extract_keywords        # jieba TF-IDF + 原句兜底，抽取关键词
        ├─▶ recall_column     # 三路并行召回：字段向量（Qdrant）
        ├─▶ recall_metric     # 指标向量（Qdrant）
        └─▶ recall_value      # 字段值全文（ES）
        └─▶ merge_retrieved_info  # 去重合并 + 补指标关联列 / 字段值 examples / 主外键
              ├─▶ filter_table     # LLM 裁剪无关表 schema
              └─▶ filter_metric    # LLM 裁剪无关指标
              └─▶ add_extra_context  # 注入日期/星期/季度 + DB 版本方言
                    └─▶ generate_sql   # 生成 SQL
                          └─▶ validate_sql # EXPLAIN 预校验
                                ├─ 无错误 ──▶ execute_sql   # 执行并返回结果
                                └─ 有错误 ──▶ correct_sql   # 最小必要修复 → execute_sql
                                                    └─▶ END
```

节点通过 `runtime.stream_writer` 推送 `stage` 进度事件，由 `graph.astream(stream_mode="custom")` 逐事件输出，最终以 SSE 返回前端。

### 元数据知识库（离线构建）

`meta_config.yaml` 声明式建模（表 / 字段的 `role` 主外键维度度量、中文描述、别名、`sync` 开关；指标 GMV / AOV 的业务口径与 `relevant_columns` 绑定），构建脚本自动从数仓抽取字段类型（`SHOW COLUMNS`）与 distinct 值，三向落库：

- **MySQL `meta` 库**：结构化持久化元数据。
- **Qdrant**：多文本向量（`name + description + alias` 各自 embedding），支持语义与别名双路召回。
- **Elasticsearch**：字段值全文索引（仅 `sync=true` 的维度列，单列上限 1 万）。

---

## 📁 目录结构

```
data-agent/
├── main.py                      # FastAPI 入口（含 request_id 中间件）
├── pyproject.toml               # 依赖声明（uv 管理）
├── conf/
│   ├── app_config.yaml          # 外部依赖配置（MySQL/Qdrant/ES/Embedding/LLM）
│   ├── meta_config.yaml         # 元数据知识库声明式建模
│   └── text_conf.yaml           # 文本配置（示例占位）
├── prompts/                     # SQL 生成等 LLM 提示词模板
└── app/
    ├── agent/                   # LangGraph 编排
    │   ├── graph.py             # 12 节点流水线定义
    │   ├── state.py             # 图状态（TypedDict）
    │   ├── context.py           # 图上下文（注入 repository / client）
    │   └── nodes/               # 各节点实现
    ├── api/                     # FastAPI 路由与请求 schema
    ├── clients/                 # 外部依赖客户端单例（MySQL/Qdrant/ES/Embedding）
    ├── conf/                    # 配置 dataclass（OmegaConf 绑定）
    ├── core/                    # lifespan / loguru / request_id
    ├── models/                  # MySQL / ES / Qdrant 数据模型
    ├── repositories/            # 存储层（隔离存储细节）
    ├── services/                # 业务层（query / meta_knowledge）
    ├── scripts/                 # build_meta_knowledge.py 离线构建脚本
    └── prompt/                  # 提示词加载器

date-agent-frontend/
├── package.json
├── vite.config.js               # Vite 代理（SSE 长连接 no-cache / keep-alive）
└── src/
    ├── App.vue                  # 聊天主界面（步骤条 + 结果表格）
    └── main.js
```

---

## 🚀 快速开始

### 前置条件

- Python 3.11+（推荐使用 [uv](https://docs.astral.sh/uv/)）
- Node.js 18+
- 已启动的外部服务：
  - MySQL 8（`meta` 元数据库 + `dw` 数仓库）
  - Qdrant（默认 6333 端口）
  - Elasticsearch 8（默认 9200 端口，需安装 `ik` 中文分词插件）
  - TEI 本地向量推理服务（默认 8081 端口，加载 `BAAI/bge-large-zh-v1.5`）
  - DeepSeek API Key

### 1. 安装后端依赖

```bash
cd data-agent
uv sync
```

### 2. 配置外部依赖

编辑 [conf/app_config.yaml](data-agent/conf/app_config.yaml)，填写各服务的连接信息（`db_meta`、`db_dw`、`qdrant`、`embedding`、`es`、`llm` 等）。注意 `llm.api_key` 为敏感信息，请使用环境变量或本地密钥管理，勿提交到仓库。

### 3. 构建元数据知识库

在 [conf/meta_config.yaml](data-agent/conf/meta_config.yaml) 中声明表 / 字段 / 指标，然后执行：

```bash
uv run python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml
```

脚本会自动从数仓抽取字段类型与 distinct 值，并三向落库（MySQL / Qdrant / ES）。

### 4. 启动后端

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

启动时由 `lifespan` 统一初始化各客户端，关闭时优雅释放资源。

### 5. 启动前端

```bash
cd date-agent-frontend
npm install
npm run dev
```

浏览器访问 Vite 开发地址，即可输入自然语言提问。

---

## 🔌 API 接口

### `POST /api/query`

对话式取数主接口，返回 `text/event-stream` 流。

请求体：

```json
{ "query": "统计华北地区销售总额" }
```

SSE 事件格式（每条事件为 `data: {json}\n\n`）：

| 事件字段 | 说明 |
| --- | --- |
| `{ "stage": "..." }` | 阶段进度事件，前端据此更新步骤条 |
| `{ "result": [ ... ] }` | 最终结果表格（数组形式） |
| `{ "error": "..." }` | 执行错误 |

### `GET /api/stream`

SSE 连通性测试接口。

---

## 🛡️ 防幻觉与 Schema 约束

- **SQL 生成 prompt 硬约束**：仅允许使用召回到的表字段、禁止写操作、多表关联必须走主外键、只输出单条纯 SQL、严禁 Markdown 包裹。
- **`EXPLAIN` 预校验**：不真正执行、不落库，仅校验语法正确性。
- **错误驱动纠偏**：执行报错时携错误信息 + 原 SQL 做最小必要修复，保持业务语义不变。
- **`temperature=0`**：确定性生成，抑制随机性幻觉。
- **指标口径绑定**：指标通过 `relevant_columns` 绑定具体字段，防止 LLM 自造计算逻辑。

---

## 🧩 工程化分层

- **配置管理**：OmegaConf + dataclass 统一管理五类外部依赖（meta MySQL / dw MySQL / Qdrant / ES / Embedding 本地推理服务）。
- **客户端生命周期**：client manager 单例 + FastAPI `lifespan` 统一初始化与优雅释放。
- **依赖注入**：`Depends` 组装 repository → service 依赖链。
- **Repository 模式**：隔离存储细节（MySQL / Qdrant / ES）。
- **可观测性**：loguru 日志 + `request_id` 中间件全链路可追踪。
