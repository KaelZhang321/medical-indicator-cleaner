# Medical Indicator Cleaner

HIS 体检指标名称标准化系统 — 规则清洗 + 向量召回 + AI 复核 + 可视化分析

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  HIS 生产数据库 (MySQL, 3000万+ 记录)                         │
│  ods_tj_jcmxx(1956细项) / ods_tj_sfxm(2197大项) / ods_tj_hyb │
└─────────────┬───────────────────────────────────────────────┘
              │ sync_dict.py / db_data_source.py
              ▼
┌─────────────────────────────────────────────────────────────┐
│  标准字典 (1970指标 + 775参考范围 + 158风险权重)               │
└─────────────┬───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│  标准化 Pipeline                                             │
│  P0(预处理) → L1(规则清洗, 100%命中) → L2(向量召回)           │
│  → AI复核(doubao) → L4(置信度分层) → 反馈回灌                │
└─────────────┬───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI 接口 (:8000)              React 前端 (:5173)         │
│  /exam/{id}        体检查询        体检查询页(表格+异常高亮)    │
│  /patient/exams    历史列表        纵向对比页(折线图+趋势)      │
│  /patient/compare  纵向对比        四象限分析页(散点图)         │
│  /exam/quadrant    四象限分析      疗效预测页(雷达图)           │
│  /patient/features 预测特征                                   │
└─────────────────────────────────────────────────────────────┘
```

## 核心指标

| 指标 | 结果 |
|------|------|
| L1 命中率 | **100%** (50000条生产数据验证) |
| 标准字典 | 1970 条指标 (从 jcmxx 同步) |
| 参考范围 | 775 条 |
| 风险权重 | 158 条 |
| 后端测试 | 123 passed |
| API 接口 | 5 个 REST 端点 |
| 前端页面 | 4 个可视化页面 |

## 快速开始

### 环境准备

```bash
# Python 后端依赖
pip install -r requirements.txt

# 前端依赖
cd web && npm install && cd ..
```

### 环境变量

```bash
export DB_PASSWORD='数据库密码'
export ARK_API_KEY='火山方舟API Key'  # 可选，AI复核用
```

### 启动服务

```bash
# 启动后端 API
uvicorn api.main:app --host 0.0.0.0 --port 8000

# 启动前端开发服务器（新终端）
cd web && npm run dev
```

- 前端页面: http://localhost:5173
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

## 数据输入方式

### 1. 从数据库查询（推荐）

```bash
# 查单人单次体检
python3 scripts/run_clean.py db --study-id 2512125012

# 查某人所有历史体检
python3 scripts/run_clean.py db --patient 身份证号

# 按日期批量查询
python3 scripts/run_clean.py db --date-from 2025-01-01 --date-to 2025-12-31
```

### 2. 从文件输入

```bash
# JSON 文件（HIS 原始格式）
python3 scripts/run_clean.py file --input data/input/sample.json

# CSV 文件（含 item_name 列）
python3 scripts/run_clean.py file --input data/input/sample_dirty.csv

# 目录批量（所有 .json 文件）
python3 scripts/run_clean.py file --input data/input/
```

## API 接口

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/v1/exam/{study_id}` | 单次体检标准化结果 |
| GET | `/api/v1/patient/{sfzh}/exams` | 患者体检历史列表 |
| GET | `/api/v1/patient/{sfzh}/comparison` | 纵向对比（含趋势） |
| GET | `/api/v1/exam/{study_id}/quadrant` | 四象限风险分析 |
| GET | `/api/v1/patient/{sfzh}/features` | 疗效预测特征 |

## 前端页面

| 页面 | 功能 | 图表类型 |
|------|------|----------|
| 体检查询 | 输入 StudyID 查看标准化指标 | Ant Design 表格 + 异常高亮 |
| 纵向对比 | 输入身份证号看多次体检变化 | AntV G2Plot 折线图 + 参考范围线 |
| 四象限分析 | 偏离度 × 风险权重散点图 | AntV G2Plot 散点图 + 四象限标注 |
| 疗效预测 | 指标变化率特征可视化 | AntV G2Plot 雷达图 + 特征表格 |

## 清洗输出

| 文件 | 说明 |
|------|------|
| `auto_mapped.csv` | 置信度 ≥ 0.95，自动归一 |
| `need_review.csv` | 置信度 0.80~0.95，待人工审核 |
| `manual_required.csv` | 置信度 < 0.80，需人工处理 |
| `stats_report.txt` | 统计报告 |

## 字典同步

从 HIS 生产数据库同步字典并重建索引：

```bash
python3 scripts/sync_dict.py

# 只同步细项字典
python3 scripts/sync_dict.py --only standard

# 跳过索引重建
python3 scripts/sync_dict.py --skip-index
```

## 反馈回灌

人工审核后的映射会回灌到别名库，下次清洗时 L1 直接命中：

```bash
python3 scripts/review_feedback.py --input data/output/need_review_confirmed.csv
```

## AI 复核

使用火山方舟 doubao 模型对低置信度结果二次判断：

- 配置: `config/settings.yaml` → `ai_review.enabled: true`
- 认证: 环境变量 `ARK_API_KEY`
- 未配置时自动跳过，不影响主流程

## 数据资产补全

批量生成别名、参考范围、风险权重：

```bash
# LLM 生成 + 爬虫验证 + 合并校验
python3 scripts/data_enrichment/run_enrichment.py --all

# 分步执行
python3 scripts/data_enrichment/run_enrichment.py --llm-only
python3 scripts/data_enrichment/run_enrichment.py --crawl-only
python3 scripts/data_enrichment/run_enrichment.py --merge-only
```

## 项目结构

```
medical-indicator-cleaner/
├── api/                    # FastAPI REST 接口
│   ├── main.py             # 应用入口
│   ├── routers/            # 路由（exam/patient/analysis）
│   ├── schemas.py          # Pydantic 响应模型
│   └── deps.py             # 依赖注入
├── web/                    # React 前端
│   └── src/
│       ├── pages/          # 4个可视化页面
│       ├── api.ts          # API 调用封装
│       └── App.tsx         # 主布局+路由
├── src/                    # 后端核心模块
│   ├── pipeline.py         # 主流程编排
│   ├── p0_preprocessor.py  # 数据预处理
│   ├── l1_rule_cleaner.py  # L1 规则清洗
│   ├── l2_embedding_matcher.py  # L2 向量召回
│   ├── ai_review.py        # AI 复核层
│   ├── l4_review.py        # 输出分层
│   ├── db_connector.py     # 数据库连接
│   ├── db_data_source.py   # 数据库查询
│   ├── db_dict_sync.py     # 字典同步
│   ├── dict_manager.py     # 字典管理
│   ├── result_parser.py    # 结果值解析
│   ├── unit_normalizer.py  # 单位标准化
│   ├── abnormal_detector.py # 异常判定
│   ├── risk_analyzer.py    # 四象限分析
│   ├── indicator_aggregator.py # 指标聚合
│   └── major_item_normalizer.py # 大项标准化
├── scripts/                # CLI 脚本
│   ├── run_clean.py        # 执行清洗（file/db模式）
│   ├── build_index.py      # 构建 FAISS 索引
│   ├── sync_dict.py        # 字典同步+索引重建
│   ├── review_feedback.py  # 审核回灌
│   └── data_enrichment/    # 数据补全工具链
├── tests/                  # 20 个测试文件
├── config/
│   └── settings.yaml       # 全局配置
├── data/
│   ├── standard_dict.csv   # 1970 条标准指标
│   ├── major_item_dict.csv # 2197 条大项
│   ├── alias_dict.csv      # 别名库（持续积累）
│   ├── reference_range_standard.csv  # 775 条参考范围
│   ├── risk_weight.csv     # 158 条风险权重
│   └── aggregate_rules.yaml # 聚合规则
├── docs/                   # 方案/计划/接口文档
└── requirements.txt
```

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | Python 3.10+, FastAPI, pandas |
| 向量检索 | sentence-transformers, FAISS |
| AI 复核 | 火山方舟 doubao-seed-2-0-pro |
| 数据库 | MySQL (pymysql) |
| 前端 | React, TypeScript, Vite |
| UI | Ant Design |
| 图表 | AntV G2Plot |

## 注意事项

- 数据库密码和 API Key 均通过环境变量配置，不会写入仓库
- `data/risk_weight.csv` 和 `data/reference_range_standard.csv` 需要业务方确认口径
- arm64 (Apple Silicon) 环境下 FAISS + PyTorch 同进程有段错误，索引构建已用分进程方式规避
- 前端开发时需要后端 API 同时运行，或配置 `VITE_API_BASE` 指向远程 API
