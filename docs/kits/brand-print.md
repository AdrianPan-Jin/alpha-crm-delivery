# brand_print — 可印刷品牌物料生成器（ClawHunt BRAND 工单交付样例）

对应两个在投工单：

| 工单 | 任务 | 报价 | 交付物 |
|---|---|---|---|
| 2729 | 三款易拉宝 × 两尺寸（800×2000 / 850×2000 mm） | $55 | 6 个 CMYK 矢量 PDF + 6 张安全区标注图 + 印前检查图 + 版式说明 |
| 2727 | 活动主背景 6×3 / 4×2.5 / 3×2 m + 签到墙 + 双档大屏 | $100 | 3 个 1:10 矢量 PDF（5cm 出血）+ 3 张禁放区标注图 + 1920×1080 / 3840×1080 大屏 PNG + 印前检查图 + 版式说明 |

## 环境

```bash
VP=project-alpha/deliverables/_template/.venv/Scripts/python.exe
$VP -m pip install reportlab qrcode pillow pymupdf -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 生成

```bash
$VP project-alpha/deliverables/brand_print/rollup.py --member-count 128
$VP project-alpha/deliverables/brand_print/backdrop.py
```

产物在 `out/`：PDF、PNG、`*-spec.md`。

## 验收自检（可逐条对应工单 AC）

**易拉宝（2729）**
- 尺寸：MediaBox 806×2006 / 856×2006 mm，TrimBox 800×2000 / 850×2000 mm（`pymupdf` 可读）。
- 底部 200 mm：只放图形条与斜纹底纹，无任何文字（`--member-count` 改数只影响 CTA 与卖点行）。
- 正文 30 mm、主标题自适应（`min(120, (w-120)/最长行字数)`）。
- 会员规模为变量：`{{member_count}}` → 渲染时替换；`out/rollup-variation-proof.png` 给出 96 家 vs 128 家同版式对比。
- 二维码位 150×150 mm 可替换；全稿无电话号码。
- 色彩全 CMYK（无 RGB），文字字体嵌入（Microsoft YaHei 子集）。

**背景/签到墙（2727）**
- 三尺寸 1:10 PDF：MediaBox 700×400 / 500×350 / 400×300 mm，TrimBox 600×300 / 400×250 / 300×200 mm（出血 50 mm/边 = 实际 5 cm）。
- 关键信息全部在 25% 线以上（`out/backdrop-*-guard.png` 标注图）；底部 1/4 仅背景与斜纹。
- 协办方为虚线占位框 4 个（可增减 1–4，间距公式写在 `backdrop-spec.md`），无真实品牌。
- 大屏两档与印刷稿由同一 `draw_scene()` 渲染（单位 mm vs px），构图一致。

## 已知边界（如实）

- 不含 Figma 云源文件：交付的是可复跑脚本 + 矢量 PDF/PNG；改一处（参数表）全量重出，等价于「组件同步」。
- 展示用二维码指向 `example.invalid` 占位域名，正式交付时替换为客户真实落地页。
- 文案为虚构样例（活动名/日期/数字），中标后按客户文案替换。
