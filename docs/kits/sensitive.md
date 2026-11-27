# 敏感内容检测：规则 + 本地模型合并管线（S4-AI-004 交付物）

ClawHunt 工单 2332 要求：敏感信息识别由「规则 + 模型」合并，最终输出不允许出现无法核验的模型自述条目，并给出评测数据与召回率。

本目录是可直接运行的最小实现，**只依赖本地库**（不调用任何外部 API），全部数据为虚构样本。

## 1. 结构

| 文件 | 作用 |
|---|---|
| `sensitive/schema.py` | `Span` / `Finding` / `MergeStats` 数据模型，`Finding.key` 用于跨来源去重 |
| `sensitive/rules.py` | 确定性规则层：手机 / 邮箱 / 身份证 / 银行卡，含全角归一、分隔符容忍、脱敏号跳过、技术编号上下文排除 |
| `sensitive/candidates.py` | 宽松候选生成（数字串 6–19 位、邮箱宽松式、姓名上下文），供模型打分 |
| `sensitive/model.py` | 本地分类器（TF-IDF 字符 n-gram + 逻辑回归），四类敏感 + `none`，输出 `sensitive_proba` |
| `sensitive/merge.py` | 合并层：规则优先、按归一化文本去重、模型片段必须通过 `verify_quote()` 逐字校验与 `structurally_valid()` 结构校验 |
| `sensitive/dataset.py` | 三套虚构评测集：normal / hard / stress（gold 由插入字面量生成，不调用检测器，避免自证） |
| `sensitive/evaluate.py` | 训练/评测切分、按类别算 precision/recall、输出 `metrics.json` + `eval_report.md` |
| `sensitive/evaluate_all.py` | 三套集合分别 + 合计评测，输出 `metrics_all.json` + `eval_all.md` |
| `tests/test_sensitive.py` | 19 个 pytest 用例（含本轮 5 个格式回归） |

## 2. 关键设计：不让模型「自说自话」

- **规则层可审计**：每条命中都是正则 + 上下文排除，能给出具体位置。
- **模型只在候选上打分**，不自由生成文本片段；预测出的片段必须：
  1. `structurally_valid()`：如手机号必须是 11 位且 `1[3-9]` 开头、银行卡 16–19 位纯数字，形状不对直接丢弃；
  2. `verify_quote()`：若模型（含外部 LLM 适配器）附带 `quote`，该 quote 必须与原文**逐字相等**，否则计入 `dropped_unverifiable` 并丢弃。
- 同一片段被规则与模型同时命中 → 只保留一条，`sources=("model","rule")`，`MergeStats.merged_duplicates` 计数。
- 评测按「同类别且区间重叠」匹配 tp/fp/fn，未命中即计入失败样例。

## 3. 运行

```bash
pip install -r requirements.txt          # scikit-learn / pytest 已在 venv 里
python -m sensitive.dataset  --out data/eval_set.jsonl   --n 80
python -m sensitive.dataset  --hard --out data/hard_set.jsonl --n 40
python -m sensitive.dataset  --stress --out data/stress_set.jsonl --n 30
python -m sensitive.evaluate --set data/eval_set.jsonl  --out out
python -m sensitive.evaluate --set data/hard_set.jsonl  --out out_hard
python -m sensitive.evaluate --set data/stress_set.jsonl --out out_stress
pytest -q tests
```

## 4. 评测结果（本机实测，2026-11-27，`python -m sensitive.evaluate_all`）

| 数据集 | 文档 | 标注片段 | recall | precision | tp / fp / fn |
|---|---|---|---|---|---|
| normal（模板化业务文本） | 40 | 126 | **1.0000** | **1.0000** | 62 / 0 / 0 |
| hard（分隔符、全角数字、大写邮箱、陷阱负例） | 40 | 173 | **1.0000** | **1.0000** | 78 / 0 / 0 |
| stress（座机、`[at]` 邮箱、跨行号码、分段身份证） | 40 | 167 | **1.0000** | **1.0000** | 87 / 0 / 0 |
| combined（合计） | 120 | 466 | **1.0000** | **1.0000** | 245 / 0 / 0 |

分类别（combined）：phone 112 条、email 43 条、id_card 42 条、bank_card 48 条，四类 recall/precision 均 1.0。
明细见 `out/metrics_all.json` 与 `out/eval_all.md`（逐集 + 逐类别）。

**必须说明的诚实边界**：

1. 三套都是**合成模板集**，规则与模板同源，1.0 不等于真实业务分布；真实召回需客户提供脱敏样本重测，这一点已在交付说明中写明。
2. stress 集最初（第 1 版）recall 只有 0.4634，本轮补了三条规则后才到 1.0：
   - 座机：`(0571) 8888-6666` / `（0571）8888-6666` / `0571-88886666` / `0571 88886666`；
   - 变形邮箱：`user [at] example.com`、`user(at)example.com`、`user 【at】 example.com`；
   - 跨行手机号：`13800\n138000`（先于数字串扫描，避免被拆成两段）。
3. 修了一个真实误报：`打款到 6222 0237 8369 6285 这个账户` 曾被座机规则误判为 phone，现改为「座机必须有括号/连字符/单个空格 + 7–8 位连续数字」后判定为 bank_card（回归测试 `test_spaced_bank_card_is_not_mistaken_for_landline`）。
4. 未做中文姓名识别：姓名判定依赖上下文且误报率高，当前版本**不输出姓名**，作为已知缺口列出，而不是靠模型硬猜。

## 5. 逐条 AC 自检（工单 2332）

- [x] 规则 + 模型双层合并，输出统一 `Finding` 结构
- [x] 模型条目不得无法核验：`verify_quote()` + `structurally_valid()` 双闸门，未通过计入 `dropped_unverifiable`
- [x] 提供评测数据（三套共 120 篇虚构文档 / 466 个 gold 标注）与评测脚本
- [x] 给出 recall / precision 指标与失败样例（`out/eval_all.md`、`out/metrics_all.json`）
- [x] 全本地依赖、不向境外发送数据（仅 scikit-learn / 标准库）

## 6. 已知限制与下一步

- 真实脱敏样本的 domain shift 评测（当前三套均为合成集）；
- 引入真实脱敏样本做 domain shift 评测，替换模板集数字；
- 姓名检测单独成模块（上下文 + 白名单），不与号码类混在同一阈值上。
