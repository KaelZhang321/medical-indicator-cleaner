# Medical Indicator Cleaner

HIS 体检指标名称标准化系统 — 将医疗体检中不规范的指标名称归一化到标准名称。

## 问题

HIS 系统中同一个指标存在多种写法：`血脂.`、`血脂`、`血 脂` 实际上是同一项，但程序无法自动归类。

## 方案

**规则清洗 + 向量召回 + 人工兜底**，不是纯靠大模型。

```
脏数据 → L1 规则清洗 → 别名精确匹配 → L2 向量召回 Top-5 → 按置信度分层 → 人工审核回灌
```

详细设计见 [docs/方案设计.md](docs/方案设计.md) | 实施计划见 [docs/实施计划.md](docs/实施计划.md) | 实现核对见 [docs/实现核对报告.md](docs/实现核对报告.md)

## 快速开始

```bash
# 安装依赖
python3 -m pip install -r requirements.txt

# 构建向量索引
python3 scripts/build_index.py --config config/settings.yaml

# 执行清洗（将脏数据放入 data/input/）
python3 scripts/run_clean.py --input data/input/your_data.csv --output data/output

# 审核结果回灌
python3 scripts/review_feedback.py --input data/output/need_review_confirmed.csv
```

如果还没有构建 FAISS 索引，`run_clean.py` 会自动以 **L1-only 模式**运行：规则和别名命中的指标会进入自动归一，未命中的指标进入人工处理，不会强制加载大模型。

## 输入格式

### JSON

支持 HIS 原始 JSON，入口字段为 `data.departments[].items[]`，核心字段包括：

| 字段 | 说明 |
|------|------|
| `itemName` | 原始指标名称 |
| `itemNameEn` | 英文缩写，可能为空 |
| `resultValue` | 原始结果值 |
| `unit` | 原始单位 |
| `referenceRange` | 原始参考范围 |

### CSV

CSV 至少需要一列：

| 字段 | 说明 |
|------|------|
| `item_name` | 待标准化的原始指标名称 |

示例数据见 `data/input/sample_dirty.csv`。

## 常用命令

```bash
# 运行端到端样本
python3 scripts/run_clean.py --input data/input/sample_dirty.csv --output data/output

# 批量处理目录下的 JSON
python3 scripts/run_clean.py --input data/input --output data/output

# 运行测试
python3 -m pytest

# 静态编译检查
python3 -m compileall src tests scripts
```

## 输出

| 文件 | 说明 |
|------|------|
| `auto_mapped.csv` | 置信度 ≥ 0.95，自动归一 |
| `need_review.csv` | 置信度 0.80~0.95，待人工审核 |
| `manual_required.csv` | 置信度 < 0.80，需人工处理 |
| `stats_report.txt` | 总数、三档数量、L1/L2 命中率 |

CSV 使用 `utf-8-sig` 编码，便于 Excel 直接打开中文。

## 反馈回灌

人工审核后的 CSV 必须包含：

| 字段 | 说明 |
|------|------|
| `original_name` | 原始名称或待新增别名 |
| `standard_code` | 人工确认的标准编码 |
| `confirmed` | `1` 表示确认写回，`0` 或空值跳过 |

执行：

```bash
python3 scripts/review_feedback.py --input data/output/need_review_confirmed.csv --config config/settings.yaml
```

脚本会通过 `DictManager.add_alias()` 写入 `data/alias_dict.csv`，自动跳过重复别名。再次运行清洗时，这些别名会在 L1 精确命中。

## 注意事项

- 医疗指标标准化不是纯大模型清洗，本项目采用规则优先、向量召回兜底、人工审核闭环。
- `data/standard_dict.csv` 是初始高覆盖字典，不代表生产全量标准；真实使用中需要持续补充 aliases。
- `data/alias_dict.csv` 是反馈回灌文件，应纳入版本管理或由业务侧建立审核流程。
- `scripts/build_index.py` 首次运行会下载 `shibing624/text2vec-base-chinese-sentence`，需要可访问 Hugging Face 或提前准备模型缓存。
- 当前环境下真实模型下载/索引构建可能受网络和 Python 运行时影响；核心 L2 逻辑已通过 deterministic fake encoder 测试覆盖。
- 未构建索引时，Pipeline 不会强制加载 L2 模型，会稳定执行 L1-only 清洗。
- `data/output/*.csv` 默认被忽略，不应提交实际清洗结果；`data/input/sample_dirty.csv` 是回归测试样本，已显式纳入版本管理。
- 变更 L1 正则、字典格式、CSV 输出列名时，应先补充对应回归测试。

## 当前验证状态

最近一次核对：

```text
python3 -m pytest
109 passed

python3 -m compileall src tests scripts
通过

python3 scripts/run_clean.py --input data/input/sample_dirty.csv --output /tmp/indicator-clean-check
通过
```

## 技术栈

- Python 3.10+
- sentence-transformers (text2vec-base-chinese-sentence)
- FAISS
- pandas
