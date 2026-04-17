# Medical Indicator Cleaner

HIS 体检指标名称标准化系统 — 将医疗体检中不规范的指标名称归一化到标准名称。

## 问题

HIS 系统中同一个指标存在多种写法：`血脂.`、`血脂`、`血 脂` 实际上是同一项，但程序无法自动归类。

## 方案

**规则清洗 + 向量召回 + 人工兜底**，不是纯靠大模型。

```
脏数据 → L1 规则清洗 → 别名精确匹配 → L2 向量召回 Top-5 → 按置信度分层 → 人工审核回灌
```

详细设计见 [docs/方案设计.md](docs/方案设计.md) | 实施计划见 [docs/实施计划.md](docs/实施计划.md)

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 构建向量索引
python scripts/build_index.py

# 执行清洗（将脏数据放入 data/input/）
python scripts/run_clean.py --input data/input/your_data.csv

# 审核结果回灌
python scripts/review_feedback.py --input data/output/need_review_confirmed.csv
```

## 输出

| 文件 | 说明 |
|------|------|
| `auto_mapped.csv` | 置信度 ≥ 0.95，自动归一 |
| `need_review.csv` | 置信度 0.80~0.95，待人工审核 |
| `manual_required.csv` | 置信度 < 0.80，需人工处理 |

## 技术栈

- Python 3.10+
- sentence-transformers (text2vec-base-chinese-sentence)
- FAISS
- pandas
