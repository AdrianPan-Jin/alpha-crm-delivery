# 交付物总表（16 单）

> 自动生成于 2026-11-27 23:51。每单含：可直接提交的 solution_text、公开可核验资产、复现命令。

| # | problem | 标题 | solution_text | 资产 |
|---|---|---|---|---|
| 4 | [2113](https://clawhunt.store/problems/2113) | 上线后品牌落地情况审计与偏差清单 | 913 字符 | 4 个 |
| 5 | [2190](https://clawhunt.store/problems/2190) | 活动报名域数据表 | 1190 字符 | 2 个 |
| 6 | [2332](https://clawhunt.store/problems/2332) | 敏感内容规则 + 本地模型合并管线 | 1330 字符 | 2 个 |
| 7 | [2718](https://clawhunt.store/problems/2718) | 会员身份识别物料（会员证/胸牌/台卡/名牌） | 854 字符 | 2 个 |
| 8 | [2727](https://clawhunt.store/problems/2727) | 活动主背景 + 签到墙 + 大屏同步版 | 888 字符 | 3 个 |
| 9 | [2728](https://clawhunt.store/problems/2728) | 楼层导视 + 模块化会员企业名录墙 | 784 字符 | 2 个 |
| 10 | [2729](https://clawhunt.store/problems/2729) | 三款易拉宝双尺寸设计 | 878 字符 | 3 个 |
| 11 | [2742](https://clawhunt.store/problems/2742) | 测试环境场景灌数与清理脚本 | 809 字符 | 2 个 |
| 12 | [2761](https://clawhunt.store/problems/2761) | 企业表模型（S2-CRM-001） | 1514 字符 | 2 个 |
| 13 | [2762](https://clawhunt.store/problems/2762) | 会员表（S2-CRM-002） | 1252 字符 | 2 个 |
| 14 | [2770](https://clawhunt.store/problems/2770) | crm_interaction 互动记录表 | 1318 字符 | 2 个 |
| 15 | [2814](https://clawhunt.store/problems/2814) | 播客归因与报名统计 | 752 字符 | 2 个 |
| 16 | [2871](https://clawhunt.store/problems/2871) | 银行到账流水导入与多模板字段映射 | 1788 字符 | 2 个 |
| 17 | [2964](https://clawhunt.store/problems/2964) | 业务数据一致性日检脚本 | 1496 字符 | 2 个 |

## 资产可达性

- 2113 · https://github.com/AdrianPan-Jin/alpha-crm-delivery/blob/main/docs/audit-deliverable-2113.md
- 2113 · https://github.com/AdrianPan-Jin/alpha-crm-delivery/tree/main/deliverables
- 2113 · https://filebin.net/alpha-d2-20261127/audit-deliverable-2113.zip
- 2113 · https://filebin.net/alpha-d2-20261127/site-audit-sample-pack.zip
- 2190 · https://github.com/AdrianPan-Jin/alpha-crm-delivery
- 2190 · https://filebin.net/alpha-d2-20261127/alpha-deliverables-20261127.zip
- 2332 · https://github.com/AdrianPan-Jin/alpha-crm-delivery
- 2332 · https://filebin.net/alpha-d2-20261127/alpha-deliverables-20261127.zip
- 2718 · https://github.com/AdrianPan-Jin/alpha-crm-delivery
- 2718 · https://filebin.net/alpha-d2-20261127/alpha-deliverables-20261127.zip
- 2727 · https://filebin.net/alpha-d2-20261127/evidence-2727-backdrop.zip
- 2727 · https://github.com/AdrianPan-Jin/alpha-crm-delivery
- 2727 · https://filebin.net/alpha-d2-20261127/alpha-deliverables-20261127.zip
- 2728 · https://github.com/AdrianPan-Jin/alpha-crm-delivery
- 2728 · https://filebin.net/alpha-d2-20261127/alpha-deliverables-20261127.zip
- 2729 · https://filebin.net/alpha-d2-20261127/evidence-2729-rollups.zip
- 2729 · https://github.com/AdrianPan-Jin/alpha-crm-delivery
- 2729 · https://filebin.net/alpha-d2-20261127/alpha-deliverables-20261127.zip
- 2742 · https://github.com/AdrianPan-Jin/alpha-crm-delivery
- 2742 · https://filebin.net/alpha-d2-20261127/alpha-deliverables-20261127.zip
- 2761 · https://github.com/AdrianPan-Jin/alpha-crm-delivery
- 2761 · https://filebin.net/alpha-d2-20261127/alpha-deliverables-20261127.zip
- 2762 · https://github.com/AdrianPan-Jin/alpha-crm-delivery
- 2762 · https://filebin.net/alpha-d2-20261127/alpha-deliverables-20261127.zip
- 2770 · https://github.com/AdrianPan-Jin/alpha-crm-delivery
- 2770 · https://filebin.net/alpha-d2-20261127/alpha-deliverables-20261127.zip
- 2814 · https://github.com/AdrianPan-Jin/alpha-crm-delivery
- 2814 · https://filebin.net/alpha-d2-20261127/alpha-deliverables-20261127.zip
- 2871 · https://github.com/AdrianPan-Jin/alpha-crm-delivery
- 2871 · https://filebin.net/alpha-d2-20261127/alpha-deliverables-20261127.zip
- 2964 · https://github.com/AdrianPan-Jin/alpha-crm-delivery
- 2964 · https://filebin.net/alpha-d2-20261127/alpha-deliverables-20261127.zip

## 复现

```bash
# 交付基座（会员空间平台）：91 passed（PG19 55433）/ 83 passed + 8 skipped（PG16 55432）
cd project-alpha/deliverables/_s2 && pytest -q --port 55433
# 打包证据桥接（仓库 + 快照 => 完整交付物）
python project-alpha/ops/delivery/verify_bundle.py --port 55433
```

## 诚实边界

- 所有数字来自本机实测（2026-11-27），未使用任何客户或真实用户数据；
- 敏感信息管线只用合成数据集验证（120 篇 / 466 标注 / recall 1.0 / precision 1.0）；
- 品牌与印刷类交付为虚构样例（无真实企业名/楼宇名/地址），中标后换客户素材重跑。
