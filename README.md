# SmartRoute Agent 系统

基于大语言模型的本地智能路线规划系统，通过多Agent协同架构，将用户的自然语言意图转化为可直接执行的个性化路线方案。

## 项目概述

SmartRoute Agent 系统采用**多Agent协同架构**，将复杂的路线规划任务分解为六个专职Agent，由Orchestrator统一调度。

### 核心特性

- **零门槛输入**：用户以自然语言描述需求，无需填写结构化表单
- **多维度最优**：综合时间、距离、口碑、偏好、预算等多重约束生成最优方案
- **可执行输出**：生成的方案包含具体时间安排、交通方式、注意事项
- **动态调整**：支持多轮对话式调整，局部修改无需重新规划全程

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          接入层                                  │
│   Nginx/Kong 网关  │  FastAPI 服务  │  Sentinel 限流  │  认证    │
├─────────────────────────────────────────────────────────────────┤
│                         编排层                                   │
│   LangGraph Orchestrator  │  Redis Session  │  OpenTelemetry    │
├─────────────────────────────────────────────────────────────────┤
│                         Agent 层                                 │
│  Intent │ Profile │ Retrieval │ UGC Insight │ Route │ Present   │
├─────────────────────────────────────────────────────────────────┤
│                       算法服务层                                  │
│  BGE Embedding  │  LightGBM  │  OR-Tools  │  HanLP  │  HDBSCAN │
├─────────────────────────────────────────────────────────────────┤
│                       外部 API 层                                │
│  OpenAI/Claude  │  高德/百度地图  │  大众点评/美团  │  天气 API  │
├─────────────────────────────────────────────────────────────────┤
│                       数据存储层                                  │
│  PostgreSQL  │  Milvus  │  Elasticsearch  │  Redis  │ClickHouse │
└─────────────────────────────────────────────────────────────────┘
```

## 核心Agent说明

### 1. Intent Agent（意图识别）
将用户的自由文本转化为结构化的意图信息，包括出行目的、时空约束、人员构成、偏好要求等。

### 2. Profile Agent（用户画像）
基于用户历史行为构建动态个性化偏好画像，注入到召回排序和方案生成中。

### 3. Retrieval Agent（POI召回）
从海量POI库中召回候选集，综合运用语义检索、地理围栏、协同过滤等多路召回策略。

### 4. UGC Insight Agent（评论洞察）
对候选POI的用户评论进行深度分析，提取多维度口碑、排队情况、适合场景等信息。

### 5. Route Planning Agent（路径规划）
在多重约束下求解POI访问序列，生成多个差异化方案。

### 6. Presentation Agent（方案生成）
将路线规划结果转化为用户友好的展示内容，生成个性化推荐理由。

## 项目结构

```
urban-mind-agents/
├── docs/                          # 项目文档
│   ├── SmartRoute Agent — 产品需求文档（PRD）.md
│   └── SmartRoute Agent 系统 — 全 Agent 详细技术方案文档.md
├── src/                           # 源代码
│   └── smartroute/
│       ├── agents/                # Agent实现
│       │   ├── intent.py         # 意图识别Agent
│       │   ├── profile.py        # 用户画像Agent
│       │   ├── retrieval.py      # POI召回Agent
│       │   ├── ugc_insight.py    # UGC洞察Agent
│       │   ├── route_planning.py # 路径规划Agent
│       │   └── presentation.py   # 方案生成Agent
│       ├── orchestrator/          # 编排层
│       │   ├── graph.py          # Orchestrator图
│       │   └── session.py        # Session管理
│       ├── schemas/               # 数据模型
│       │   ├── intent.py         # 意图相关Schema
│       │   ├── profile.py        # 用户画像Schema
│       │   ├── route.py          # 路线Schema
│       │   ├── poi.py            # POI Schema
│       │   ├── state.py          # 系统状态Schema
│       │   └── response.py       # 响应Schema
│       ├── services/              # 服务层
│       │   ├── llm/              # LLM服务
│       │   ├── vector_store/     # 向量存储
│       │   └── external_api/     # 外部API
│       ├── storage/               # 存储层
│       ├── api/                   # API接口
│       └── core/                  # 核心模块
│           ├── config.py         # 配置管理
│           ├── logging.py        # 日志系统
│           ├── exceptions.py     # 异常定义
│           └── utils.py          # 工具函数
├── tests/                         # 测试代码（TDD）
│   ├── agents/                   # Agent测试
│   ├── orchestrator/             # 编排器测试
│   ├── schemas/                  # Schema测试
│   ├── services/                 # 服务测试
│   ├── storage/                  # 存储测试
│   ├── api/                      # API测试
│   └── conftest.py               # pytest配置
├── config/                        # 配置文件
├── data/                          # 数据文件
├── models/                        # 模型文件
├── scripts/                       # 脚本文件
├── pytest.ini                     # pytest配置
├── pyproject.toml                 # 项目配置
└── requirements.txt               # 依赖管理

```

## TDD开发流程

本项目严格遵循**测试驱动开发（TDD）**流程：

### RED-GREEN-REFACTOR循环

1. **RED阶段**：先编写测试，运行确认失败
2. **GREEN阶段**：编写最小代码让测试通过
3. **REFACTOR阶段**：重构代码，保持测试通过

### 开发步骤

```bash
# 1. 运行所有测试（RED阶段）
pytest tests/ -v

# 2. 实现代码让测试通过（GREEN阶段）
# 编写最小实现代码

# 3. 再次运行测试确认通过
pytest tests/ -v

# 4. 重构代码（REFACTOR阶段）
# 优化代码结构，保持测试通过

# 5. 运行测试确保重构后仍然通过
pytest tests/ -v
```

## 快速开始

### 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd urban-mind-agents

# 安装依赖
pip install -r requirements.txt

# 安装开发依赖
pip install -r requirements-dev.txt
```

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/agents/test_intent_agent.py -v

# 运行特定测试类
pytest tests/agents/test_intent_agent.py::TestIntentAgent -v

# 运行特定测试方法
pytest tests/agents/test_intent_agent.py::TestIntentAgent::test_extract_simple_intent -v

# 运行测试并生成覆盖率报告
pytest tests/ -v --cov=src/smartroute --cov-report=html
```

### 代码质量检查

```bash
# 代码格式化
black src/ tests/

# 代码检查
flake8 src/ tests/

# 类型检查
mypy src/
```

## 技术栈

### 核心框架
- **Python 3.11+**
- **FastAPI** - API框架
- **LangGraph** - Agent编排框架
- **Pydantic v2** - 数据验证

### LLM相关
- **OpenAI GPT-4o** - 主力LLM
- **Claude 3.5 Sonnet** - 备选LLM
- **BGE-M3** - Embedding模型

### 数据存储
- **PostgreSQL + PostGIS** - 关系数据库+地理数据
- **Milvus** - 向量数据库
- **Elasticsearch** - 全文检索
- **Redis** - 缓存/Session

### 算法工具
- **OR-Tools** - 路线优化求解
- **LightGBM** - 排序模型
- **HDBSCAN** - 聚类算法

## 开发规范

### 代码规范
- 遵循PEP 8代码风格
- 使用类型注解
- 编写docstring文档

### 测试规范
- 测试覆盖率≥80%
- 所有测试必须通过
- 遵循TDD流程

### 提交规范
- 使用语义化提交信息
- 每次提交必须通过所有测试

## 许可证

[MIT License](LICENSE)

## 贡献指南

欢迎提交Issue和Pull Request！

## 联系方式

项目维护者：SmartRoute团队
