# 播客归因指标口径（S6-POD-041）

本文件与「收听汇总」指标定义文档同册，新增以下 7 个指标。所有时间为 UTC，
`stat_date` 为**转化发生日**（不是点击日、不是统计作业运行日）。

## 一、直接归因（episode_conversion_stats 前 3 列）

数据源：`podcast_intro_requests`（剧集页「请平台引荐嘉宾」按钮创建）。

| 指标 | 定义 | 判定字段 |
| --- | --- | --- |
| `intro_requests` | 当日新建的引荐请求数 | `created_at::date = stat_date` |
| `intro_staff_approved` | 当日由工作人员审批通过的请求数 | `decided_at::date = stat_date AND status IN ('staff_approved','accepted')` |
| `intro_accepted` | 当日嘉宾接受引荐的请求数 | `accepted_at::date = stat_date AND status = 'accepted'` |

- 一个请求可以同时落入不同日期的不同指标（创建日计 requests、审批日计 approved、
  接受日计 accepted），三列**不做去重**，这是漏斗口径。
- 软删除（`deleted_at` 非空）的请求不计入任何一列。

## 二、辅助归因（episode_conversion_stats 后 3 列）

数据源：
- `podcast_related_clicks`：剧集页相关推荐（关联活动 / 课程 / 公开机会）的点击。
- 其他模块的转化（本工单用接口桩）：
  - `event_signup`：报名同一活动
  - `course_signup`：报名同一课程
  - `opportunity_request`：对同一公开机会发起对接

判定规则：

1. **时间窗**：点击时刻 `T`，转化时刻 `C`，当 `0 ≤ C − T ≤ 24h` 时该次点击可辅助该转化。
   窗口在 24 小时处**闭合**：`C − T = 24h` 计入，`= 25h` 不计。
2. **最近点击优先**：同一用户对同一对象多次点击时，只取 `C` 之前最近的那次点击；
   若该转化同时满足多个剧集，只归给最近点击所属的剧集。
   并列（同一时刻点击）时按 `episode_id` 升序取一个，保证结果确定。
3. **类别一一对应**：`event_signup → 活动`、`course_signup → 课程`、
   `opportunity_request → 公开机会`；跨类别不互相辅助。
4. **个性化推荐关闭的用户**：其转化仍计入 `episode_conversion_stats` 的总数，
   但不写入 `episode_conversion_events`（个体明细里不会出现该用户）。
5. **同一转化只计一次**：`episode_conversion_events` 上有唯一约束
   `(org_id, episode_id, kind, target_id, user_id)`。

## 三、口径边界（写清楚，避免以后扯皮）

- 归因只看**点击**，不看曝光/播放；「收听过该剧集再转化」不算辅助归因。
- 同一用户在同一天内为同一对象重复报名（例如取消后重报）只保留一条明细，
  但报名模块若上报两条转化，则总数会是 2（总量以源模块为准，明细唯一约束兜底）。
- 跨日窗口：23:50 点击、次日 00:05 转化，明细的 `stat_date` 记为次日（转化日）。
- 回填（`--backfill`）按日重算并**整日覆盖**，不会与增量结果叠加。
