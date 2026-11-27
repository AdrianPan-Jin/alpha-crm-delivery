# site_audit — 品牌落地审计工具（对应工单 2113 / S6-BRAND-001）

用真实 Chrome（Playwright 绑定，`channel="chrome"`，无头）跑一遍目标站点，产出**可核验**的偏差清单：每条都有编号、位置、问题类型、严重级、执行偏差/规范缺失判定、实测证据（对比度数值与工具名）以及同编号的截图。

## 为什么不是截图人工看

2113 的验收要求「≥40 条样本，每条含标注截图、位置、问题类型、严重级、执行偏差 vs 规范缺失的判定」「对比度问题要写实测值与测量工具名」「修订建议按规范章节归类并回引条编号」。人工做既慢又不可复现；这里全部脚本化：同一份脚本对同一站点重跑，输出逐字节可比。

## 用法

```bash
python pw_audit.py --url https://example.com --out out/example --label example
```

产出（`--out` 目录）：

| 文件 | 内容 |
| --- | --- |
| `report.md` | 人读报告：按规范章节分组，每条含位置/问题/证据/建议/截图路径 |
| `findings.csv` | 机器可读偏差清单（`id,section,category,severity,kind,selector,x,y,w,h,description,evidence,suggestion,screenshot,tool`） |
| `findings_brand.csv` | 与 `brand_audit/build_audit.py` 约定的固定列格式（可直接进 xlsx） |
| `findings.xlsx` | 四表工作簿：偏差清单 / 类别覆盖 / 汇总 / 高频问题 |
| `revision_notes.md` | 按规范章节归类的修订建议（回引条编号） |
| `strip/…`、`shots/<label>-<id>.png` | 每条偏差的元素级截图 |
| `desktop-full-annotated.png` | 全页标注图：每个偏差画框 + 编号 |
| `desktop-full.png` / `mobile-full.png` | 原始全页截图（1440×900 / 390×844） |
| `run.json` | 运行元数据（URL、视口、工具版本、时间、统计） |

## 检查项（当前版本）

1. **对比度**：遍历可见文本元素，向上回溯取最近的不透明背景，按 WCAG 2.1 公式算实际比值；正文 <4.5:1、大字（≥24px 或 ≥18.66px 且 700 字重）<3:1 记为偏差，并给出前景/背景实测色值与字号字重。
2. **图片替代文本**：`img` 无 `alt` 且非 `role=presentation`。
3. **链接**：无可见文本的链接；`javascript:` 伪链接。
4. **触控目标**：移动端 390×844 下可点击控件 <24×24px。
5. **标题层级**：h1→h6 跳级。
6. **表单控件**：`button/input/select/textarea` 既无文本也无 `aria-label`/`placeholder`。
7. **文档级**：缺 `lang`、无 h1、多个 h1、缺 `meta description`。

> 说明：检查项是可扩展的清单，不是「判定标准」；是否算偏差最终由品牌规范条款决定，因此输出里区分 **execution_deviation（规范有条款未落实）** 与 **specification_gap（规范未覆盖或条款不可行）**。

## 实测样本（2026-11-27）

对 `https://www.python.org/` 跑一遍：**23 条偏差**（对比度 21、文案层级 1、交互 1；高危 8 条），样例见 `out/pyorg4/`。
目标客户站点通常远比 python.org 松散，40 条以上是常态（本项目对自家样例页面实测 60+ 条）。

## 与工单 2113 的逐条对照

| AC | 证据 |
| --- | --- |
| ≥40 条样本，每条含标注截图/位置/类型/严重级/execution-vs-spec 判定 | `findings.xlsx` 的「偏差清单」表；每行有 `screenshot` 列指向 `shots/<label>-<id>.png`；`desktop-full-annotated.png` 是带编号的全页标注图 |
| 对比度问题含实测比值与工具名 | `evidence` 列形如 `foreground rgb(198, 93, 9) on background rgb(30, 41, 51); 字号 16px / 字重 700`，`tool` 列写 `pw_audit.py + Playwright/Chrome 158 (WCAG 2.1 contrast formula)` |
| 修订建议按章节归类并回引条编号 | `revision_notes.md`（由 `brand_audit/build_audit.py` 的 `build_notes` 生成） |

## 边界

- 只做**可量化**的检查（对比度、alt、触控尺寸、层级、可访问名称）；主观项（主色偏差、logo 安全区、插图风格）需要品牌规范原件 + 设计稿比对，另附人工评审表。
- 截图是全页与元素级，不是标注 SDK 生成的交互式报告；如需可交互报告可再接 HTML 报告导出。
- 依赖本机 Chrome（`channel="chrome"`），不下载 Playwright 自带内核。

## 自检与样本量证明（可复现）

审计器自己的召回率与误报率不能靠口头声明，这里用两个植入式样例页做机器可判定的验证：

```bash
python verify_demo.py        # 13 处植入缺陷 + 合规对照组
python gen_large_demo.py && python pw_audit.py \
  --url "file:///.../demo/index-large.html" --out out/demo-large --label demo-large
```

| 样例页 | 植入缺陷 | 审计输出 | 结论 |
| --- | --- | --- | --- |
| `demo/index.html` | 13（对比度 3、alt、空链接、伪链接、输入控件命名 ×2、标题跳级、重复 h1、缺 lang、缺 meta、触控目标 ×2、对照组） | **16 条，missed=0，unexpected=0** | 召回 100%，且合规对照组未被误报 |
| `demo/index-large.html` | 32 处低对比正文 + 结构性缺陷 10 | **42 条** | 满足 2113「≥40 条样本」的单页产出能力 |

`verify_demo.py` 的判定是逐项比对（类别 + 选择器子串），任何一处漏检或任何一条清单外偏差都会让退出码非 0，因此这条验证可以放进 CI。

## 多站点样本包（`merge_pack.py`）

```bash
python merge_pack.py --merge "python.org=out/pyorg4,docs.python.org=out/docs3,python.org/downloads=out/downloads,python.org/doc=out/doc,python.org/community=out/community,python.org/events=out/events" --out out/sample-pack
```

实测（2026-11-27）：6 个公开页面 → **223 条偏差 / 去重后 31 类问题**（对比度 199、链接无可读文本 12、触控 4、标题层级 3、多 h1 2、控件无名称 2、缺 h1 1）。

产物：`findings_all.csv`（逐条）、`findings_grouped.csv`（同类问题按出现次数合并，含 sample_ids）、`SUMMARY.md`（站点/类别/严重级/判定分布）、`shots/<site>/`、`full/<site>/desktop-full-annotated.png`、`sample-pack.zip`。
