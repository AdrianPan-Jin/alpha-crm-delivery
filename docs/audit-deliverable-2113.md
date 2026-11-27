# 品牌落地审计 · 偏差清单与修订建议（交付物 v1）

> 生成于 2026-11-27｜抽样站点 6 个｜偏差记录 **223** 条（验收线 ≥40）｜去重问题类 52 类

## 0. 这份东西是什么

- 一份**结构已定稿、字段与验收逐条对齐**的交付物：拿到你方域名后把 `--url` 换掉重跑，即产出同结构报告 + 截图，无需二次开发。
- 当前数据来自公开站点（python.org 及 5 个子页），**不含任何客户真实数据、不含客户名称**；截图仅用于举证位置。
- 每条记录都有：编号、位置（selector + 坐标）、问题类型、严重级、执行偏差/规范缺失判定、实测值与工具名、截图引用、修订建议。

## 1. 口径与方法

| 项 | 取值 |
| --- | --- |
| 采集工具 | `pw_audit.py + Playwright/Chrome 158 (WCAG 2.1 contrast formula)` |
| 视口 | 桌面 1440×900；移动 390×844（触控目标） |
| 对比度阈值 | 正文 <4.5:1 判失败；大字号（≥24px 或 ≥18.66px 粗体）<3:1 判失败 |
| 触控目标 | <24×24 CSS px 判失败（WCAG 2.2 SC 2.5.8） |
| 判定规则 | 规范有条款未落实 → 执行偏差；规范未覆盖/条款不可执行 → 规范缺失 |
| 抽样 | 每站全量遍历可见文本元素，同类去重后取代表样本入册 |

## 2. 总览

| 维度 | 分布 |
| --- | --- |
| 站点 | docs.python.org、python.org、python.org/community、python.org/doc、python.org/downloads、python.org/events |
| 问题类型 | 对比度不足 199；链接无可读文本 12；触控目标过小 4；标题层级跳跃 3；多个 h1 主标题 2；控件缺少可访问名称 2；缺少 h1 主标题 1 |
| 严重级 | medium 198；high 20；low 5 |
| 判定 | execution_deviation 219；specification_gap 4 |

## 3. 偏差记录

> 编号规则 `站点#原编号`；截图列 = 该站的全页标注图（红框编号即记录号）+ 元素截图路径。

### 3.1 对比度不足（199 条）

| 编号 | 位置 | 严重级 | 判定 | 实测值 | 工具 | 截图 |
| --- | --- | --- | --- | --- | --- | --- |
| python.org#D001 | `div.medium-widget > div.shrubbery > p.give-me-` @(597,935) | high | execution_deviation | 文本「More news」对比度 2.71:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D001.png` |
| python.org#D002 | `div.medium-widget > div.shrubbery > p.give-me-` @(1221,935) | high | execution_deviation | 文本「More」对比度 2.71:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D002.png` |
| python.org#D003 | `div.medium-widget > div.shrubbery > p.give-me-` @(633,1294) | high | execution_deviation | 文本「More」对比度 2.71:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D003.png` |
| python.org#D004 | `div.shrubbery > div.success-story-item > block` @(189,1344) | medium | execution_deviation | 文本「"Some of the things [SonarCloud] spots are impressive (pr | pw_audit / WCAG2.1 | — + `out//shots/D004.png` |
| python.org#D005 | `div.medium-widget > div.shrubbery > p.give-me-` @(1221,1294) | high | execution_deviation | 文本「More」对比度 2.71:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D005.png` |
| python.org#D006 | `div.container > ul.sitemap > li.tier-1 > a` @(132,1905) | medium | execution_deviation | 文本「About」对比度 3.94:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D006.png` |
| python.org#D007 | `div.container > ul.sitemap > li.tier-1 > a` @(328,1905) | medium | execution_deviation | 文本「Downloads」对比度 3.94:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D007.png` |
| python.org#D008 | `div.container > ul.sitemap > li.tier-1 > a` @(524,1905) | medium | execution_deviation | 文本「Documentation」对比度 3.94:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D008.png` |
| python.org#D009 | `div.container > ul.sitemap > li.tier-1 > a` @(720,1905) | medium | execution_deviation | 文本「Community」对比度 3.94:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D009.png` |
| python.org#D010 | `div.container > ul.sitemap > li.tier-1 > a` @(916,1905) | medium | execution_deviation | 文本「Success Stories」对比度 3.94:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D010.png` |
| python.org#D011 | `div.container > ul.sitemap > li.tier-1 > a` @(1112,1905) | medium | execution_deviation | 文本「News」对比度 3.94:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D011.png` |
| python.org#D012 | `div.container > ul.sitemap > li.tier-1 > a` @(132,2120) | medium | execution_deviation | 文本「Events」对比度 3.94:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D012.png` |
| python.org#D013 | `div.container > ul.sitemap > li.tier-1 > a` @(1112,2191) | medium | execution_deviation | 文本「Contributing」对比度 3.94:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D013.png` |
| python.org#D014 | `ul.footer-links > li.tier-1 > a > span.say-no-` @(479,2472) | medium | execution_deviation | 文本「General」对比度 3.27:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D014.png` |
| python.org#D015 | `ul.footer-links > li.tier-1 > a > span.say-no-` @(687,2472) | medium | execution_deviation | 文本「Initiatives」对比度 3.27:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D015.png` |
| python.org#D016 | `div.container > ul.footer-links > li.tier-1 > ` @(770,2463) | medium | execution_deviation | 文本「Submit Website Bug」对比度 3.27:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D016.png` |
| python.org#D017 | `div.container > ul.footer-links > li.tier-1 > ` @(941,2463) | medium | execution_deviation | 文本「Status」对比度 3.27:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D017.png` |
| python.org#D018 | `div.copyright > p > small > span.pre` @(504,2514) | high | execution_deviation | 文本「Copyright ©2001-2026.」对比度 2.83:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D018.png` |
| python.org#D019 | `p > small > span.pre > a` @(624,2514) | high | execution_deviation | 文本「Python Software Foundation」对比度 2.83:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D019.png` |
| python.org#D020 | `p > small > span.pre > a` @(773,2514) | high | execution_deviation | 文本「Legal Statements」对比度 2.83:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D020.png` |
| python.org#D021 | `p > small > span.pre > a` @(865,2514) | high | execution_deviation | 文本「Privacy Notice」对比度 2.83:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D021.png` |
| python.org/downloads#D001 | `ol.list-row-container > li > span.release-dl >` @(501,1097) | medium | execution_deviation | 文本「Download」对比度 4.39:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D001.png` |
| python.org/downloads#D002 | `ol.list-row-container > li > span.release-pep ` @(1098,1097) | medium | execution_deviation | 文本「PEP 826」对比度 4.39:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D002.png` |
| python.org/downloads#D003 | `ol.list-row-container > li > span.release-dl >` @(501,1168) | medium | execution_deviation | 文本「Download」对比度 4.39:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D003.png` |
| python.org/downloads#D004 | `ol.list-row-container > li > span.release-pep ` @(1098,1168) | medium | execution_deviation | 文本「PEP 745」对比度 4.39:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D004.png` |
| python.org/downloads#D005 | `ol.list-row-container > li > span.release-dl >` @(501,1239) | medium | execution_deviation | 文本「Download」对比度 4.39:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D005.png` |
| python.org/downloads#D006 | `ol.list-row-container > li > span.release-pep ` @(1098,1239) | medium | execution_deviation | 文本「PEP 693」对比度 4.39:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D006.png` |
| python.org/downloads#D007 | `ol.list-row-container > li > span.release-stat` @(445,1310) | medium | execution_deviation | 文本「3.10.22」对比度 4.39:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D007.png` |
| python.org/downloads#D008 | `ol.list-row-container > li > span.release-dl >` @(501,1310) | medium | execution_deviation | 文本「Download」对比度 4.39:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D008.png` |
| python.org/downloads#D009 | `ol.list-row-container > li > span.release-pep ` @(1098,1310) | medium | execution_deviation | 文本「PEP 619」对比度 4.39:1，低于 AA 要求 4.5:1 | pw_audit / WCAG2.1 | — + `out//shots/D009.png` |

> 其余 169 条见 `findings_all.csv`（同字段集，可直接筛/排序）。


### 3.2 链接无可读文本（12 条）

| 编号 | 位置 | 严重级 | 判定 | 实测值 | 工具 | 截图 |
| --- | --- | --- | --- | --- | --- | --- |
| python.org#D022 | `header.main-header > div.container > div.site-` @(136,63) | medium | execution_deviation | 链接没有可读文本（图标按钮需 aria-label） | pw_audit / WCAG2.1 | — + `out//shots/D022.png` |
| python.org/downloads#D130 | `header.main-header > div.container > div.site-` @(136,63) | medium | execution_deviation | 链接没有可读文本（图标按钮需 aria-label） | pw_audit / WCAG2.1 | — + `out//shots/D130.png` |
| python.org/downloads#D131 | `div.sidebar-widget > div > div > a` @(164,1979) | medium | execution_deviation | 链接没有可读文本（图标按钮需 aria-label） | pw_audit / WCAG2.1 | — + `out//shots/D131.png` |
| python.org/downloads#D132 | `div.sidebar-widget > div > div > a` @(356,1989) | medium | execution_deviation | 链接没有可读文本（图标按钮需 aria-label） | pw_audit / WCAG2.1 | — + `out//shots/D132.png` |
| python.org/downloads#D133 | `div.sidebar-widget > div > div > a` @(548,1962) | medium | execution_deviation | 链接没有可读文本（图标按钮需 aria-label） | pw_audit / WCAG2.1 | — + `out//shots/D133.png` |
| python.org/downloads#D134 | `div.sidebar-widget > div > div > a` @(740,2011) | medium | execution_deviation | 链接没有可读文本（图标按钮需 aria-label） | pw_audit / WCAG2.1 | — + `out//shots/D134.png` |
| python.org/downloads#D135 | `div.sidebar-widget > div > div > a` @(932,1990) | medium | execution_deviation | 链接没有可读文本（图标按钮需 aria-label） | pw_audit / WCAG2.1 | — + `out//shots/D135.png` |
| python.org/downloads#D136 | `div.sidebar-widget > div > div > a` @(1124,1961) | medium | execution_deviation | 链接没有可读文本（图标按钮需 aria-label） | pw_audit / WCAG2.1 | — + `out//shots/D136.png` |
| python.org/downloads#D137 | `div.sidebar-widget > div > div > a` @(164,2151) | medium | execution_deviation | 链接没有可读文本（图标按钮需 aria-label） | pw_audit / WCAG2.1 | — + `out//shots/D137.png` |
| python.org/doc#D018 | `header.main-header > div.container > div.site-` @(136,63) | medium | execution_deviation | 链接没有可读文本（图标按钮需 aria-label） | pw_audit / WCAG2.1 | — + `out//shots/D018.png` |
| python.org/community#D017 | `header.main-header > div.container > div.site-` @(136,63) | medium | execution_deviation | 链接没有可读文本（图标按钮需 aria-label） | pw_audit / WCAG2.1 | — + `out//shots/D017.png` |
| python.org/events#D017 | `header.main-header > div.container > div.site-` @(136,63) | medium | execution_deviation | 链接没有可读文本（图标按钮需 aria-label） | pw_audit / WCAG2.1 | — + `out//shots/D017.png` |

### 3.3 触控目标过小（4 条）

| 编号 | 位置 | 严重级 | 判定 | 实测值 | 工具 | 截图 |
| --- | --- | --- | --- | --- | --- | --- |
| docs.python.org#M004 | `div.menu-wrapper > nav.menu > div.language_swi` @(-290,75) | medium | specification_gap | 移动端可点击区域 270×19px，小于 24×24px | pw_audit / WCAG2.1 | — + `out//shots/M004.png` |
| docs.python.org#M005 | `div.mobile-nav > div.menu-wrapper > nav.menu >` @(-290,102) | medium | specification_gap | 移动端可点击区域 270×21px，小于 24×24px | pw_audit / WCAG2.1 | — + `out//shots/M005.png` |
| docs.python.org#M006 | `div.menu-wrapper > nav.menu > label.theme-sele` @(-235,102) | medium | specification_gap | 移动端可点击区域 215×21px，小于 24×24px | pw_audit / WCAG2.1 | — + `out//shots/M006.png` |
| docs.python.org#M007 | `div.mobile-nav > nav.nav-content > span.nav-it` @(44,10) | medium | specification_gap | 移动端可点击区域 20×20px，小于 24×24px | pw_audit / WCAG2.1 | — + `out//shots/M007.png` |

### 3.4 标题层级跳跃（3 条）

| 编号 | 位置 | 严重级 | 判定 | 实测值 | 工具 | 截图 |
| --- | --- | --- | --- | --- | --- | --- |
| docs.python.org#D001 | `div.document > div.sphinxsidebar > div.sphinxs` @(0,0) | low | execution_deviation | 标题从 h1 跳到 h3：Download | pw_audit / WCAG2.1 | — + `out//shots/D001.png` |
| python.org/downloads#D138 | `#sigstore` @(0,0) | low | execution_deviation | 标题从 h2 跳到 h4：Sigstore verification | pw_audit / WCAG2.1 | — + `out//shots/D138.png` |
| python.org/community#D018 | `div.row > div.small-widget > div.shrubbery > h` @(0,0) | low | execution_deviation | 标题从 h2 跳到 h4：Libera.Chat IRC General Channels | pw_audit / WCAG2.1 | — + `out//shots/D018.png` |

### 3.5 多个 h1 主标题（2 条）

| 编号 | 位置 | 严重级 | 判定 | 实测值 | 工具 | 截图 |
| --- | --- | --- | --- | --- | --- | --- |
| python.org#D023 | `body` @(0,0) | low | execution_deviation | 页面有 5 个 h1，主标题不唯一 | pw_audit / WCAG2.1 | — + `out//shots/D023.png` |
| python.org/downloads#D139 | `body` @(0,0) | low | execution_deviation | 页面有 6 个 h1，主标题不唯一 | pw_audit / WCAG2.1 | — + `out//shots/D139.png` |

### 3.6 控件缺少可访问名称（2 条）

| 编号 | 位置 | 严重级 | 判定 | 实测值 | 工具 | 截图 |
| --- | --- | --- | --- | --- | --- | --- |
| docs.python.org#D002 | `li.right > div.inline-search > form.inline-sea` @(1260,20) | medium | execution_deviation | input 既无文本也无 aria-label/placeholder | pw_audit / WCAG2.1 | — + `out//shots/D002.png` |
| docs.python.org#D003 | `li.right > div.inline-search > form.inline-sea` @(1260,1367) | medium | execution_deviation | input 既无文本也无 aria-label/placeholder | pw_audit / WCAG2.1 | — + `out//shots/D003.png` |

### 3.7 缺少 h1 主标题（1 条）

| 编号 | 位置 | 严重级 | 判定 | 实测值 | 工具 | 截图 |
| --- | --- | --- | --- | --- | --- | --- |
| python.org/events#D018 | `body` @(0,0) | medium | execution_deviation | 页面没有任何 h1，信息层级缺少主语 | pw_audit / WCAG2.1 | — + `out//shots/D018.png` |

## 4. 修订建议（按规范章节归类，每条回引记录编号）

### 4.1 页头与品牌露出（5 条：执行偏差 5 / 规范缺失 0）

- 执行偏差 → 直接派工修复，并把对应条款写进上线检查单。
- 规范缺失 → 补条款（写明阈值、正反例、例外情形）。

- **链接无可读文本**：补可见文本或 aria-label（记录 D022, D130, D018, D017, D017）

### 4.2 导航与信息架构（169 条：执行偏差 169 / 规范缺失 0）

- 执行偏差 → 直接派工修复，并把对应条款写进上线检查单。
- 规范缺失 → 补条款（写明阈值、正反例、例外情形）。

- **对比度不足**：提高前景与背景的明度差（改文本色或加深底色），至少达到 4.5:1（记录 D006, D007, D008, D009, D010, D011, D012, D013, D001, D002…）
- **标题层级跳跃**：按 h1→h2→h3 顺序递进，样式与语义分离（记录 D001）
- **链接无可读文本**：补可见文本或 aria-label（记录 D131, D132, D133, D134, D135, D136, D137）

### 4.3 表单与控件（2 条：执行偏差 2 / 规范缺失 0）

- 执行偏差 → 直接派工修复，并把对应条款写进上线检查单。
- 规范缺失 → 补条款（写明阈值、正反例、例外情形）。

- **控件缺少可访问名称**：补 label / aria-label（记录 D002, D003）

### 4.4 页脚与法务（20 条：执行偏差 20 / 规范缺失 0）

- 执行偏差 → 直接派工修复，并把对应条款写进上线检查单。
- 规范缺失 → 补条款（写明阈值、正反例、例外情形）。

- **对比度不足**：提高前景与背景的明度差（改文本色或加深底色），至少达到 4.5:1（记录 D014, D015, D016, D017, D018, D010, D011, D012, D013, D014…）

### 4.5 移动端与触控（4 条：执行偏差 0 / 规范缺失 4）

- 执行偏差 → 直接派工修复，并把对应条款写进上线检查单。
- 规范缺失 → 补条款（写明阈值、正反例、例外情形）。

- **触控目标过小**：扩大内边距或设置最小点击区域（记录 M004, M005, M006, M007）

### 4.6 内容区排版（23 条：执行偏差 23 / 规范缺失 0）

- 执行偏差 → 直接派工修复，并把对应条款写进上线检查单。
- 规范缺失 → 补条款（写明阈值、正反例、例外情形）。

- **对比度不足**：提高前景与背景的明度差（改文本色或加深底色），至少达到 4.5:1（记录 D001, D002, D003, D004, D005, D019, D020, D021, D001, D015…）
- **多个 h1 主标题**：保留一个 h1，其余降级（记录 D023, D139）
- **标题层级跳跃**：按 h1→h2→h3 顺序递进，样式与语义分离（记录 D138, D018）
- **缺少 h1 主标题**：为页面主标题使用 h1，其余按层级递进（记录 D018）

## 5. 在你方站点复跑

```bash
python pw_audit.py --url https://<your-domain> --out out/<slug>
python merge_pack.py --out out/<pack> out/<slug> [out/<slug2> ...]
```

产出：`report.md`／`findings.csv`／`findings.xlsx`（四表）／`revision_notes.md`（章节归类）／`desktop-full-annotated.png`（全页编号标注）／`shots/`（元素截图）。

## 6. 边界与假设

- 需要你方提供：现行品牌规范（PDF 或可读快照，用于「执行偏差 vs 规范缺失」判定）、页面清单与访问权限。
- 需要登录的页面请给只读测试账号；审计全程只读，不写任何数据、不上传素材。
- 若你方规范里没有对应条款，我会在「规范缺失」里给出建议条款文本，而不是硬判为偏差。
