# 品牌落地审计工具包（S6-BRAND-001 交付底座）

三个可独立运行的部分，产物即交付物：

| 文件 | 作用 | 产物 |
|---|---|---|
| `checklist.md` | 8 类检查表、严重级别判据、执行偏差/规范缺失判定流程 | 审计口径（随报告交付） |
| `contrast_check.py` | WCAG 2.1 AA 对比度实测（HEX 直算 或 截图取样） | `out/contrast_report.csv` |
| `build_audit.py` | 由发现项 CSV 生成偏差清单工作簿与章节化修订建议 | `out/brand_audit.xlsx`、`out/brand_audit_revision_notes.md` |

## 运行

```bash
pip install openpyxl pillow -i https://pypi.tuna.tsinghua.edu.cn/simple

# 1) 对比度：两种模式
python contrast_check.py --fg "#9E9E9E" --bg "#FFFFFF" --label miniapp-05 --position /pages/card/detail --out out/contrast_report.csv
python contrast_check.py --mode sample --image shot.png --fg 120,44 --bg 400,44 --large --out out/contrast_report.csv

# 2) 偏差清单 + 修订建议
python build_audit.py --findings sample_findings.csv --outdir out
```

## 发现项 CSV 列（`build_audit.py` 强制校验）

`id, screenshot, location, category, description, severity, occurrences, kind, evidence, suggestion`

- `category` ∈ 八类（见 `checklist.md`）
- `severity` ∈ `high|medium|low` → 输出为「高/中/低」
- `kind` ∈ `deviation|gap` → 输出为「执行偏差/规范缺失」
- `evidence` 写截图坐标或量测值，保证审核方可以复现标注

## 工作簿结构

1. **偏差清单**：10 列原始发现 + 冻结表头
2. **类别覆盖**：8 类逐一列问题数，证明没有漏扫类别
3. **汇总**：严重级别分布、执行偏差 vs 规范缺失占比
4. **高频问题**：按出现频次排序的前 10 条

修订建议 Markdown 以规范章节为骨架，每条含「现状 / 问题 / 建议条款 / 影响页面 / 优先级」，可直接作为 S6-BRAND-002~005 的输入。

## 说明

- `sample_findings.csv` 是虚构样例数据（10 条，覆盖 8 类 + 1 条达标样本 + 1 条规范缺失），用于验证脚本链路，不含任何真实企业或个人信息。
- 截图取样默认取 3×3 邻域均值，降低压缩伪影影响；正式审计需在报告中注明取样坐标。
- 全部脚本离线运行，不引入任何向境外发送数据的第三方 SDK。
