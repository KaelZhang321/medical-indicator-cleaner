# HIS 体检指标标准化系统 — 技术方案（Codex 实施指南）

## 1. 目标

将 HIS 体检系统返回的 JSON 数据中的指标名称标准化，使得不同时间、不同机构、不同写法的同一指标能被程序自动归为一类，支持纵向对比展示。

## 2. 真实数据结构分析

### 2.1 API 返回结构

```json
{
  "data": {
    "studyId": "2512125012",
    "packageName": "海-033VIPGB女-丽滋高致精筛套餐",
    "departments": [
      {
        "departmentCode": "HY",           // 科室代码
        "departmentName": "化验室",         // 科室名称
        "sourceTable": "ods_tj_hyb",       // 来源表
        "items": [
          {
            "majorItemCode": "955057",     // 大项编码（检查套餐）
            "majorItemName": "H-女性肿瘤标志物全项",  // 大项名称
            "itemCode": "040702",          // 指标编码
            "itemName": "★甲胎蛋白(AFP)",   // 指标名称 ← 需要标准化的核心字段
            "itemNameEn": "AFP",           // 英文名（有时为空）
            "resultValue": "1.74",         // 结果值
            "unit": "IU/mL",              // 单位
            "referenceRange": "0.00-5.800", // 参考范围
            "abnormalFlag": "0"            // 异常标记: 0=正常, 1=偏低, 2=偏高, null=无
          }
        ]
      }
    ]
  }
}
```

### 2.2 科室分类

| 科室代码 | 科室名称 | 数据特征 | 是否需要标准化 |
|----------|----------|----------|---------------|
| HY | 化验室 | 定量/定性检验结果，有 majorItemName 分组 | **是（核心）** |
| YB | 一般检查 | 身高体重血压等基础测量 | **是** |
| ER | 人体成份 | 体脂分析数据，resultValue 混入单位 | **是（需特殊处理）** |
| US | 彩超室 | 影像结论文本，非结构化 | 否（文本类，二期处理） |
| WK | 外科 | 体查描述，非量化 | 否 |
| FK | 妇科 | 体查描述+问诊结论 | 否 |
| EY | 妇科总检室 | 综合结论文本 | 否 |
| EZ | TS检查 | 检查结论引用 | 否 |
| WZ | 健康问诊 | 病史问答，resultValue 为 0/1 | 否（非检验数据） |

### 2.3 已发现的数据质量问题

#### A. itemName（指标名称）问题

| 问题类型 | 示例 | 数量 |
|----------|------|------|
| ★前缀标记 | `★甲胎蛋白(AFP)` → 应为 `甲胎蛋白` | 22 个 |
| 括号内含英文缩写 | `总胆固醇(TC)` → 标准名 `总胆固醇`，缩写 `TC` | 84 个 |
| 全角半角括号混用 | `★类风湿因子(RF）` — 左半角右全角 | 1+ 个 |
| 全角括号 | `鱼（鳕鱼）特异性IgG抗体` | 4 个 |
| 名称含斜杠 | `肾结石/肾囊肿`、`胃胀/胃疼/嗳气/反酸` | 7 个 |

#### B. majorItemName（大项名称）问题

| 问题类型 | 示例 |
|----------|------|
| H- 前缀 | 所有大项都有 `H-` 前缀，如 `H-血脂七项` |
| 括号混用 | `H-人乳头瘤病毒（HPV）核酸检测（17加6）` vs `H-巨细胞病毒IgM抗体定量(W)` |

#### C. resultValue（结果值）问题

| 问题类型 | 示例 | 涉及科室 |
|----------|------|----------|
| 混入单位 | `28.2kg`、`1198kcal` | ER 人体成份 |
| 混入参考范围+判断 | `7.4kg  (7.7-9.4)   偏低` | ER 人体成份 |
| 混入百分号 | `31.8%(18.0-28.0) 偏高` | ER 人体成份 |
| 含前缀符号 | `< 2.30`、`<0.0250` | HY 化验室 |
| 含定性描述 | `0.07（阴性 -）`、`阳性（+）` | HY 化验室 |
| 逗号分隔 | `80.8,正常` | ER 人体成份 |

#### D. referenceRange（参考范围）问题

| 问题类型 | 示例 |
|----------|------|
| 空白/无效 | ` ~ `（401/504 条） |
| 多期参考值 | `卵泡期:0.057-0.893；排卵期：0.121-12.0；黄体期:1.83-23.9` |
| 含条件说明 | `<1(美国CDC推荐:S/CO>5.0时...)` |
| 含年龄/性别条件 | `成年女性（绝经期前）:6.9-282.5；成年女性（绝经期后）:14-233.1` |

#### E. 其他问题

- **大量重复记录**：178 组 (同一 itemCode + itemName + 科室出现 2 次)
- **unit 字段缺失**：ER 科室全部 unit 为空，实际单位混在 resultValue 中
- **abnormalFlag 大量为 null**：397/504 条无标记

## 3. 系统架构

```
原始 JSON 数据
    │
    ▼
┌─────────────────────────────────┐
│  P0 数据预处理层                  │
│  - 过滤非检验科室（WZ/FK/WK/EY/EZ）│
│  - 去重（相同 itemCode + dept）    │
│  - resultValue 解析（拆值/单位/判断）│
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  L1 规则清洗层                    │
│  - 去 ★ 前缀                     │
│  - 全半角统一                     │
│  - 括号内缩写提取并去除            │
│  - 去无意义标点                   │
│  - 去内部空格                     │
│  - 大项名称去 H- 前缀             │
│  - 别名词库精确匹配               │
└─────────────┬───────────────────┘
              │ 未命中
              ▼
┌─────────────────────────────────┐
│  L2 向量召回层                    │
│  - Sentence-BERT 编码             │
│  - FAISS Top-5 检索               │
│  - 返回候选 + 余弦相似度           │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  L4 输出分层                      │
│  - ≥0.95 自动归一                 │
│  - 0.80~0.95 待审核               │
│  - <0.80 人工处理                 │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│  L5 反馈回灌                      │
│  - 审核结果 → 别名库               │
│  - 下次 L1 直接命中               │
└─────────────────────────────────┘
```

## 4. 详细模块设计

### 4.1 项目结构

```
medical-indicator-cleaner/
├── config/
│   └── settings.yaml
├── data/
│   ├── standard_dict.csv          # 标准指标字典
│   ├── alias_dict.csv             # 别名词库
│   ├── dept_filter.yaml           # 科室过滤配置
│   ├── input/                     # 原始 JSON 数据
│   ├── output/                    # 清洗结果
│   └── faiss_index/               # 向量索引
├── src/
│   ├── __init__.py
│   ├── pipeline.py                # 主流程
│   ├── p0_preprocessor.py         # P0 数据预处理
│   ├── l1_rule_cleaner.py         # L1 规则清洗
│   ├── l2_embedding_matcher.py    # L2 向量召回
│   ├── l4_review.py               # L4 输出分层
│   ├── dict_manager.py            # 字典管理
│   ├── result_parser.py           # resultValue 解析器
│   └── utils.py                   # 工具函数
├── scripts/
│   ├── build_index.py             # 构建向量索引
│   ├── run_clean.py               # 执行清洗
│   └── review_feedback.py         # 审核回灌
├── tests/
│   ├── test_p0_preprocessor.py
│   ├── test_l1_cleaner.py
│   ├── test_result_parser.py
│   └── test_pipeline.py
├── requirements.txt
└── README.md
```

### 4.2 P0 数据预处理层 `p0_preprocessor.py`

**输入**：原始 JSON（单人或批量）
**输出**：扁平化 DataFrame，每行一个指标

```python
class P0Preprocessor:
    """将 HIS JSON 数据预处理为标准化的扁平 DataFrame"""
    
    # 需要处理的科室白名单
    DEPT_WHITELIST = {'HY', 'YB', 'ER'}
    
    def process(self, json_data: dict) -> pd.DataFrame:
        """
        主处理流程:
        1. 提取 departments -> items 扁平化
        2. 过滤科室（只保留 HY/YB/ER）
        3. 去重（相同 study_id + dept + itemCode + itemName 只保留一条）
        4. 调用 ResultParser 解析 resultValue
        5. 输出标准 DataFrame
        """
        
    def _flatten_items(self, json_data: dict) -> pd.DataFrame:
        """将嵌套 JSON 展开为扁平行"""
        # 输出列：study_id, dept_code, dept_name, major_item_code, 
        #         major_item_name, item_code, item_name, item_name_en,
        #         result_value_raw, unit_raw, reference_range_raw, abnormal_flag
        
    def _deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """去除完全重复的记录，保留第一条"""
        # 去重键：study_id + dept_code + item_code + item_name
```

### 4.3 ResultValue 解析器 `result_parser.py`

专门处理 resultValue 中混入的信息。

```python
class ResultParser:
    """解析 resultValue 字段，拆分出数值、单位、定性判断"""
    
    # 已知单位模式
    UNIT_PATTERNS = [
        r'(kg/平方米)', r'(kcal)', r'(kg)', r'(cm)', r'(mmHg)',
        r'(bpm)', r'(%)', r'(L)', r'(ml)',
    ]
    
    def parse(self, raw_value: str, existing_unit: str) -> dict:
        """
        返回:
        {
            'numeric_value': float|None,  # 数值（如 7.4）
            'text_value': str|None,       # 文本结果（如 '阴性'、'O型'）
            'unit': str,                  # 单位（优先用已有 unit，否则从值中提取）
            'qualifier': str|None,        # 修饰符（如 '<'、'>'）
            'judgment': str|None,         # 判断（如 '偏低'、'正常'、'偏高'）
            'ref_in_value': str|None,     # 值中包含的参考范围（如 '7.7-9.4'）
        }
        """
    
    # 需要处理的模式:
    # "7.4kg  (7.7-9.4)   偏低"  → value=7.4, unit=kg, ref=7.7-9.4, judgment=偏低
    # "31.8%(18.0-28.0) 偏高"    → value=31.8, unit=%, ref=18.0-28.0, judgment=偏高
    # "< 2.30"                   → value=2.30, qualifier=<
    # "0.07（阴性 -）"            → value=0.07, text=阴性
    # "80.8,正常"                → value=80.8, judgment=正常
    # "阳性（+）"                 → text=阳性
    # "O型"                      → text=O型
    # "清亮"                      → text=清亮
    # "0 级"                     → text=0级
    # "0      阴性-"             → value=0, text=阴性
```

### 4.4 L1 规则清洗层 `l1_rule_cleaner.py`

```python
class L1RuleCleaner:
    """链式规则清洗"""
    
    def __init__(self, dict_manager: DictManager):
        self.dict_manager = dict_manager
        self.rules = [
            self._strip,
            self._remove_star_prefix,
            self._fullwidth_to_halfwidth,
            self._extract_abbreviation_from_brackets,
            self._remove_trailing_punctuation,
            self._normalize_brackets,
            self._remove_internal_spaces,
            self._uppercase_english,
        ]
    
    def clean(self, item_name: str) -> CleanResult:
        """
        返回 CleanResult:
        {
            'original': str,          # 原始名称
            'cleaned': str,           # 清洗后名称
            'abbreviation': str|None, # 提取出的缩写（如 TC, AFP）
            'standard_name': str|None,# 如果别名库命中则有值
            'standard_code': str|None,
            'confidence': float,      # 1.0 = 别名库命中, 0.0 = 未匹配
            'match_source': str,      # 'alias_exact' | 'unmatched'
        }
        """
    
    def _strip(self, name: str) -> str:
        """去前后空格、制表符、换行"""
        return name.strip()
    
    def _remove_star_prefix(self, name: str) -> str:
        """去 ★ 前缀标记"""
        # ★甲胎蛋白(AFP) → 甲胎蛋白(AFP)
        return name.lstrip('★').lstrip()
    
    def _fullwidth_to_halfwidth(self, name: str) -> str:
        """全角字符转半角"""
        # （ → (  ） → )  ： → :  ， → ,  ； → ;
        # 使用 unicodedata.normalize 或手动映射
        FULL_TO_HALF = {
            '（': '(', '）': ')', '：': ':', '，': ',',
            '；': ';', '【': '[', '】': ']', '！': '!',
            '０': '0', '１': '1', # ... 等全角数字
        }
        for f, h in FULL_TO_HALF.items():
            name = name.replace(f, h)
        return name
    
    def _extract_abbreviation_from_brackets(self, name: str) -> tuple[str, str|None]:
        """
        从括号中提取英文缩写，返回 (清洗后名称, 缩写)
        
        总胆固醇(TC)     → ('总胆固醇', 'TC')
        尿酸碱度(PH)     → ('尿酸碱度', 'PH')
        D-二聚体(D-Dimer) → ('D-二聚体', 'D-Dimer')
        鱼(鳕鱼)特异性IgG抗体 → 不动（括号内是中文补充说明，不是缩写）
        """
        import re
        # 只处理末尾的 (英文/数字/连字符) 模式
        match = re.match(r'^(.+?)\(([A-Za-z0-9\-\.β]+)\)$', name)
        if match:
            return match.group(1).rstrip(), match.group(2)
        return name, None
    
    def _remove_trailing_punctuation(self, name: str) -> str:
        """去掉末尾无意义标点"""
        # 血脂. → 血脂
        return name.rstrip('.。,，、-_/')
    
    def _normalize_brackets(self, name: str) -> str:
        """统一中文括号补充说明为半角"""
        # 处理括号内是中文内容的情况（不去除，只统一格式）
        return name.replace('【', '[').replace('】', ']')
    
    def _remove_internal_spaces(self, name: str) -> str:
        """去中文字符间的多余空格"""
        import re
        # 血 糖 → 血糖（只去中文间空格，保留中英文间合理空格）
        name = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', name)
        return name
    
    def _uppercase_english(self, name: str) -> str:
        """英文部分统一大写（用于后续匹配）"""
        # 注意：只在匹配查找时使用大写，存储保留原始大小写
        return name  # 实际匹配时使用 .upper()
    
    def clean_major_item_name(self, name: str) -> str:
        """清洗 majorItemName（大项名称）"""
        if not name:
            return name
        # 去 H- 前缀
        if name.startswith('H-'):
            name = name[2:]
        # 统一括号
        name = self._fullwidth_to_halfwidth(name)
        return name.strip()
```

### 4.5 字典管理器 `dict_manager.py`

```python
class DictManager:
    """标准字典和别名库管理"""
    
    def __init__(self, standard_dict_path: str, alias_dict_path: str):
        self.standard_dict = self._load_standard_dict(standard_dict_path)
        self.alias_dict = self._load_alias_dict(alias_dict_path)
        self._build_lookup_index()
    
    def _build_lookup_index(self):
        """
        构建查找索引，支持多种匹配方式:
        1. name_to_standard: 标准名/别名 → standard_code (精确匹配)
        2. abbr_to_standard: 缩写(如 TC, AFP) → standard_code (精确匹配)
        3. name_upper_to_standard: 大写版本 → standard_code (大小写不敏感)
        
        注意: 索引中的 key 都是清洗后的（去★、统一括号等）
        """
    
    def lookup(self, cleaned_name: str, abbreviation: str = None) -> dict | None:
        """
        查找标准名。优先级:
        1. 清洗后名称精确匹配
        2. 缩写精确匹配
        3. 大写不敏感匹配
        返回 {'standard_code': ..., 'standard_name': ..., 'category': ...} 或 None
        """
    
    def add_alias(self, alias: str, standard_code: str):
        """新增别名映射（人工审核回灌时调用）"""
```

### 4.6 标准字典格式 `standard_dict.csv`

```csv
code,standard_name,abbreviation,aliases,category,common_unit,result_type
HY-BC-001,白细胞计数,WBC,"白细胞;白血球",血常规,10^9/L,numeric
HY-BC-002,红细胞计数,RBC,"红细胞;红血球",血常规,10^12/L,numeric
HY-BC-003,血红蛋白,HGB,"血红蛋白浓度;Hb",血常规,g/L,numeric
HY-BC-004,血小板计数,PLT,"血小板",血常规,10^9/L,numeric
HY-BC-005,血小板分布宽度,PDW,,血常规,fL,numeric
HY-BZ-001,总胆固醇,TC,"胆固醇;CHOL;总胆固醇测定",血脂,mmol/L,numeric
HY-BZ-002,甘油三酯,TG,"甘油三脂;三酸甘油酯;甘油三酯测定",血脂,mmol/L,numeric
HY-BZ-003,高密度脂蛋白胆固醇,HDL-C,"HDL;高密度脂蛋白",血脂,mmol/L,numeric
HY-BZ-004,低密度脂蛋白胆固醇,LDL-C,"LDL;低密度脂蛋白",血脂,mmol/L,numeric
HY-BZ-005,载脂蛋白A,APO-A,"APOA;ApoA1;载脂蛋白A1",血脂,g/L,numeric
HY-BZ-006,载脂蛋白B,APO-B,"APOB;ApoB",血脂,g/L,numeric
HY-BZ-007,脂蛋白a,LP(a),"Lp(a);脂蛋白(a)",血脂,mg/L,numeric
HY-GG-001,丙氨酸氨基转移酶,ALT,"谷丙转氨酶;SGPT",肝功能,U/L,numeric
HY-GG-002,天门冬氨酸氨基转移酶,AST,"谷草转氨酶;SGOT",肝功能,U/L,numeric
HY-GG-003,γ-谷氨酰转肽酶,GGT,"谷氨酰转肽酶;γ-GT",肝功能,U/L,numeric
HY-GG-004,碱性磷酸酶,ALP,"碱性磷酸酶测定",肝功能,U/L,numeric
HY-GG-005,总胆红素,TBIL,"胆红素总量",肝功能,μmol/L,numeric
HY-GG-006,直接胆红素,DBIL,"结合胆红素",肝功能,μmol/L,numeric
HY-GG-007,间接胆红素,IBIL,,肝功能,μmol/L,numeric
HY-GG-008,总蛋白,TP,,肝功能,g/L,numeric
HY-GG-009,白蛋白,ALB,"清蛋白",肝功能,g/L,numeric
HY-GG-010,球蛋白,GLB,,肝功能,g/L,numeric
HY-SG-001,尿素氮,BUN,"尿素;UREA",肾功能,mmol/L,numeric
HY-SG-002,肌酐,Cr,"CREA;血肌酐",肾功能,μmol/L,numeric
HY-SG-003,尿酸,UA,"血尿酸",肾功能,μmol/L,numeric
HY-SG-004,胱抑素C,Cys-C,"半胱氨酸蛋白酶抑制剂C",肾功能,mg/L,numeric
HY-XT-001,空腹血糖,FPG,"空腹葡萄糖;GLU;血糖",血糖,mmol/L,numeric
HY-XT-002,糖化血红蛋白,HbA1c,"糖化血红蛋白A1c;GHb",血糖,%,numeric
HY-NC-001,尿浊度,TUR,,尿常规,,qualitative
HY-NC-002,尿酸碱度,PH,"尿pH",尿常规,,numeric
HY-NC-003,尿亚硝酸盐,NIT,,尿常规,,qualitative
HY-NC-004,尿比重,SG,,尿常规,,numeric
HY-NC-005,尿蛋白质,PRO,"尿蛋白",尿常规,,qualitative
HY-NC-006,尿胆红素,BIL,"尿BIL",尿常规,,qualitative
HY-NC-007,尿胆原,URO,,尿常规,,qualitative
HY-NC-008,尿酮体,KET,,尿常规,,qualitative
HY-NC-009,尿液颜色,COL,,尿常规,,qualitative
HY-NC-010,尿白细胞,LEU,,尿常规,,qualitative
HY-NC-011,尿隐血,BLD,"尿潜血",尿常规,,qualitative
HY-NC-012,尿葡萄糖,uGLU,"尿糖",尿常规,,qualitative
HY-JG-001,超敏促甲状腺激素,TSH,"促甲状腺激素",甲状腺功能,μU/ml,numeric
HY-JG-002,游离甲状腺素,FT4,"游离T4",甲状腺功能,pmol/L,numeric
HY-JG-003,游离三碘甲状腺原氨酸,FT3,"游离T3",甲状腺功能,pmol/L,numeric
HY-JG-004,抗甲状腺过氧化物酶抗体,TPO-Ab,"TPOAb;抗TPO抗体",甲状腺功能,U/ml,numeric
HY-JG-005,抗甲状腺球蛋白抗体,TG-Ab,"TGAb;抗TG抗体",甲状腺功能,IU/ml,numeric
HY-ZL-001,甲胎蛋白,AFP,,肿瘤标志物,IU/mL,numeric
HY-ZL-002,癌胚抗原,CEA,,肿瘤标志物,ng/ml,numeric
HY-ZL-003,糖类抗原12-5,CA12-5,"CA125;CA-125",肿瘤标志物,U/ml,numeric
HY-ZL-004,糖类抗原19-9,CA19-9,"CA199;CA-199",肿瘤标志物,U/ml,numeric
HY-ZL-005,糖类抗原15-3,CA15-3,"CA153;CA-153",肿瘤标志物,U/ml,numeric
HY-ZL-006,糖类抗原72-4,CA72-4,"CA724;CA-724",肿瘤标志物,U/ml,numeric
HY-ZL-007,神经元特异性烯醇化酶,NSE,,肿瘤标志物,ng/ml,numeric
HY-ZL-008,鳞状上皮细胞癌抗原,SCC,,肿瘤标志物,ng/mL,numeric
HY-ZL-009,细胞角蛋白19片段,CYFRA21-1,,肿瘤标志物,ng/ml,numeric
HY-ZL-010,铁蛋白,FER,"SF;血清铁蛋白",肿瘤标志物,ng/mL,numeric
HY-ZL-011,人附睾蛋白,HE4,,肿瘤标志物,pmol/L,numeric
HY-ZL-012,胃泌素释放肽前体,ProGRP,,肿瘤标志物,pg/ml,numeric
HY-NX-001,泌乳素,PRL,,女性激素,ng/mL,numeric
HY-NX-002,睾酮,TESTO,"T",女性激素,ng/mL,numeric
HY-NX-003,孕酮,PROG,"P",女性激素,ng/mL,numeric
HY-NX-004,雌二醇,E2,,女性激素,pg/mL,numeric
HY-NX-005,促黄体生成素,LH,,女性激素,mIU/mL,numeric
HY-NX-006,促卵泡素,FSH,"促卵泡刺激素",女性激素,mIU/mL,numeric
HY-NX-007,硫酸脱氢表雄酮,DHEA-S,"DHEAS",女性激素,ug/dl,numeric
HY-NX-008,β-人绒毛膜促性腺激素,β-HCG,"HCG;人绒毛膜促性腺激素",女性激素,mIU/mL,numeric
HY-NB-001,活化部分凝血活酶时间,APTT,,凝血功能,秒,numeric
HY-NB-002,凝血酶原时间,PT,,凝血功能,秒,numeric
HY-NB-003,纤维蛋白原,Fbg,"FIB;纤维蛋白原定量",凝血功能,g/L,numeric
HY-NB-004,凝血酶时间,TT,,凝血功能,秒,numeric
HY-NB-005,国际标准化比值,PT.INR,"INR",凝血功能,,numeric
HY-NB-006,抗凝血酶活性测定,AT-III,"AT Ⅲ;AT3",凝血功能,%,numeric
HY-NB-007,百分活动度,PT%,"PTA",凝血功能,%,numeric
HY-NB-008,D-二聚体,D-Dimer,"D二聚体;DDimer",凝血功能,mg/L,numeric
HY-MY-001,人类免疫缺陷病毒抗体,HIV-Ab,"HIV抗体;艾滋病毒抗体",免疫检测,S/CO,qualitative
HY-MY-002,梅毒密螺旋体抗体,TP-Ab,"梅毒抗体;梅毒螺旋体抗体",免疫检测,,qualitative
HY-MY-003,丙型肝炎抗体,HCV-Ab,"丙肝抗体;丙型肝炎抗体IgG-IgM",免疫检测,,qualitative
HY-MY-004,免疫球蛋白E,IgE,,免疫检测,U/ml,numeric
HY-MY-005,类风湿因子,RF,,免疫检测,U/ml,numeric
HY-MY-006,抗链球菌溶血素,ASO,,免疫检测,U/ml,numeric
HY-MY-007,抗环瓜氨酸肽抗体,A-CCP,"CCP;抗CCP抗体",免疫检测,U/ml,numeric
HY-YY-001,叶酸,FOL,"FOLIC",营养元素,ng/mL,numeric
HY-YY-002,维生素B12,VitB12,"B12;维生素B-12",营养元素,pmol/L,numeric
HY-YY-003,25-羟基维生素D,25-OH-VitD,"25OHD;维生素D;25羟基维生素D",营养元素,ng/ml,numeric
HY-QT-001,抗缪勒管激素,AMH,,其他,ng/ml,numeric
HY-QT-002,巨细胞病毒IgM抗体,CMV-Ab,"CMV-IgM",其他,AU/mL,qualitative
HY-QT-003,C13呼气试验,13CO2,"碳13呼气试验;C13;幽门螺杆菌",其他,,qualitative
HY-QT-004,ABO血型,ABO,,其他,,qualitative
HY-QT-005,RH(D)血型,RH,"Rh血型",其他,,qualitative
HY-QT-006,细菌性阴道病,BV,,其他,,qualitative
HY-QT-007,随机尿微量白蛋白,RUmALB,,其他,mg/L,numeric
HY-QT-008,随机尿肌酐,RUCr,,其他,μmol/L,numeric
HY-BD-001,霉菌,Fungus,,白带常规,,qualitative
HY-BD-002,滴虫,Trich,,白带常规,,qualitative
HY-BD-003,清洁度,QJD,,白带常规,,qualitative
ER-001,身体总水分,TBW,,人体成分,kg,numeric
ER-002,体脂百分比,PBF,"体脂率",人体成分,%,numeric
ER-003,身体质量指数,BMI,"体重指数;体质指数",人体成分,kg/m²,numeric
ER-004,基础代谢率,BMR,,人体成分,kcal,numeric
ER-005,内脏脂肪面积,VFA,,人体成分,cm²,numeric
ER-006,骨骼肌,SMM,"骨骼肌量",人体成分,kg,numeric
ER-007,体脂肪量,BFM,"体脂肪",人体成分,kg,numeric
ER-008,腰臀比,WHR,,人体成分,,numeric
YB-001,收缩压,SBP,"高压",一般检查,mmHg,numeric
YB-002,舒张压,DBP,"低压",一般检查,mmHg,numeric
YB-003,身高,Height,,一般检查,cm,numeric
YB-004,体重,Weight,,一般检查,kg,numeric
YB-005,脉搏,Pulse,"心率",一般检查,次/分,numeric
```

> 注意: 以上仅为初始字典的核心子集。完整字典需要根据实际数据持续补充。`aliases` 字段用 `;` 分隔。

### 4.7 L2 向量召回层 `l2_embedding_matcher.py`

```python
class L2EmbeddingMatcher:
    """基于 Sentence-BERT 的向量相似度召回"""
    
    def __init__(self, model_name: str = 'shibing624/text2vec-base-chinese-sentence'):
        self.model = SentenceTransformer(model_name)
        self.index = None           # FAISS index
        self.index_labels = []      # 每个向量对应的 standard_code
        self.index_names = []       # 每个向量对应的名称（用于调试）
    
    def build_index(self, dict_manager: DictManager):
        """
        从标准字典构建向量索引:
        1. 对每个标准项，编码 standard_name + abbreviation + 每个 alias
        2. 所有向量 L2 归一化
        3. 存入 FAISS IndexFlatIP
        4. 记录每个向量对应的 standard_code
        
        示例: 总胆固醇 会产生多个向量:
          - "总胆固醇" → vector1 → HY-BZ-001
          - "TC" → vector2 → HY-BZ-001
          - "胆固醇" → vector3 → HY-BZ-001
          - "CHOL" → vector4 → HY-BZ-001
        """
    
    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        查询 top_k 个最相似的标准项
        返回: [
            {
                'standard_code': 'HY-BZ-001',
                'standard_name': '总胆固醇',
                'matched_text': 'TC',  # 命中的是哪个别名/标准名
                'score': 0.96,         # 余弦相似度
            },
            ...
        ]
        
        注意: 同一 standard_code 可能通过不同别名多次命中，
              需要去重并保留最高分。
        """
    
    def save_index(self, path: str):
        """持久化索引到磁盘"""
        # 保存 FAISS index + labels + names
    
    def load_index(self, path: str):
        """从磁盘加载索引"""
```

### 4.8 L4 输出分层 `l4_review.py`

```python
class L4Review:
    """按置信度分层输出"""
    
    # 阈值配置（从 settings.yaml 读取）
    AUTO_THRESHOLD = 0.95       # ≥ 自动归一
    REVIEW_THRESHOLD = 0.80     # ≥ 待人工审核
    # < REVIEW_THRESHOLD        # 人工处理
    
    def classify(self, results: list[dict]) -> dict:
        """
        输入: pipeline 处理后的所有结果
        输出: {
            'auto_mapped': [...],      # 自动归一的记录
            'need_review': [...],      # 待审核的记录
            'manual_required': [...],  # 需人工处理的记录
            'stats': {                 # 统计信息
                'total': int,
                'auto_count': int,
                'review_count': int,
                'manual_count': int,
                'l1_hit_rate': float,  # L1 命中率
                'l2_hit_rate': float,  # L2 命中率（≥REVIEW）
            }
        }
        """
    
    def export_csv(self, classified: dict, output_dir: str):
        """
        输出三个 CSV:
        - auto_mapped.csv
        - need_review.csv (包含 top3 候选供人选择)
        - manual_required.csv (包含 top5 候选参考)
        
        共同列: original_name, cleaned_name, abbreviation,
                standard_name, standard_code, category,
                confidence, match_source, top_candidates
        """
```

### 4.9 主流程 `pipeline.py`

```python
class StandardizationPipeline:
    """主流程编排"""
    
    def __init__(self, config_path: str = 'config/settings.yaml'):
        self.config = load_config(config_path)
        self.dict_manager = DictManager(...)
        self.preprocessor = P0Preprocessor()
        self.cleaner = L1RuleCleaner(self.dict_manager)
        self.matcher = L2EmbeddingMatcher(...)
        self.reviewer = L4Review(...)
    
    def run(self, input_path: str, output_dir: str):
        """
        完整流程:
        1. 加载输入数据（JSON 或 CSV）
        2. P0 预处理（展开、过滤、去重、解析 resultValue）
        3. L1 规则清洗（逐条处理）
           - 命中 → confidence=1.0，标记 match_source='alias_exact'
           - 未命中 → 进入 L2
        4. L2 向量召回（批量处理未命中项）
           - 返回 top-5 + 相似度分数
        5. L4 分层输出
        6. 生成统计报告
        """
    
    def run_batch_json(self, json_files: list[str], output_dir: str):
        """批量处理多个 JSON 文件"""
        
    def run_csv(self, csv_path: str, output_dir: str):
        """处理 CSV 格式输入（itemName 列表）"""
```

### 4.10 配置文件 `config/settings.yaml`

```yaml
# 模型配置
model:
  name: "shibing624/text2vec-base-chinese-sentence"
  cache_dir: "./models"     # 模型缓存目录
  device: "cpu"             # cpu 或 cuda

# 索引配置
index:
  path: "./data/faiss_index"
  top_k: 5

# 阈值配置
thresholds:
  auto_map: 0.95           # ≥ 此值自动归一
  need_review: 0.80        # ≥ 此值待审核，< 此值人工处理

# 数据路径
data:
  standard_dict: "./data/standard_dict.csv"
  alias_dict: "./data/alias_dict.csv"
  input_dir: "./data/input"
  output_dir: "./data/output"

# 科室过滤
departments:
  whitelist:
    - HY    # 化验室
    - YB    # 一般检查
    - ER    # 人体成份
  # blacklist 中的科室直接跳过
  blacklist:
    - WZ    # 健康问诊（非检验数据）
    - EY    # 妇科总检室（综合结论）
    - EZ    # TS检查

# 预处理
preprocessing:
  deduplicate: true
  parse_result_value: true
```

## 5. 工作任务拆解

### Task 1: 项目骨架 + 配置
- [ ] 创建完整目录结构
- [ ] 编写 `config/settings.yaml`
- [ ] 编写 `requirements.txt`
- [ ] 编写 `src/__init__.py`
- [ ] 编写 `src/utils.py`（配置加载、日志等）

### Task 2: 标准字典
- [ ] 编写 `data/standard_dict.csv`（上面的完整版本）
- [ ] 编写 `data/alias_dict.csv`（初始为空，仅表头）
- [ ] 编写 `src/dict_manager.py`（加载、索引构建、查找、新增别名）
- [ ] 编写 `tests/test_dict_manager.py`

### Task 3: P0 数据预处理
- [ ] 编写 `src/p0_preprocessor.py`（JSON 展开、科室过滤、去重）
- [ ] 编写 `src/result_parser.py`（resultValue 拆分）
- [ ] 编写 `tests/test_p0_preprocessor.py`
- [ ] 编写 `tests/test_result_parser.py`
- [ ] 用真实 JSON 数据验证

### Task 4: L1 规则清洗
- [ ] 编写 `src/l1_rule_cleaner.py`（8 条链式规则 + 别名查找）
- [ ] 编写 `tests/test_l1_cleaner.py`（覆盖所有已知脏数据模式）
- [ ] 验证 L1 命中率

### Task 5: L2 向量召回
- [ ] 编写 `src/l2_embedding_matcher.py`
- [ ] 编写 `scripts/build_index.py`
- [ ] 首次下载模型 + 构建索引
- [ ] 验证 Top-5 召回质量

### Task 6: L4 输出 + Pipeline
- [ ] 编写 `src/l4_review.py`
- [ ] 编写 `src/pipeline.py`
- [ ] 编写 `scripts/run_clean.py`（CLI 入口）

### Task 7: 端到端测试
- [ ] 用真实 JSON 数据跑完整 pipeline
- [ ] 检查三档输出
- [ ] 编写 `tests/test_pipeline.py`

### Task 8: 反馈回灌
- [ ] 编写 `scripts/review_feedback.py`
- [ ] 验证回灌后 L1 命中率提升

## 6. 关键依赖

```
pandas>=2.0
sentence-transformers>=2.2
faiss-cpu>=1.7
pyyaml
tqdm
```

## 7. 验证标准

1. P0: 504 条原始数据 → 过滤后约 140 条（HY+YB+ER 去重后）
2. L1 规则清洗命中率 > 60%（基于标准字典+别名）
3. L2 Top-5 命中率 > 90%（正确答案在前 5 中）
4. 自动归一（≥0.95）准确率 > 95%
5. 反馈回灌后重跑，L1 命中率提升 > 10%
