# 事件表月分区 + 分区自动维护（S3-TRK-002 交付件）

对应任务：`track_event` 表按月分区 + 分区自动维护 + 越界时间戳告警。

## 结构

```
tracking.track_event            -- 父表，PARTITION BY RANGE (occurred_at)
tracking.track_event_YYYY_MM    -- 月分区，[月初, 次月初)
tracking.track_event_default    -- 默认分区，兜住越界/异常时间戳
ix_track_event_occurred         -- 时间范围扫描
ix_track_event_org_name         -- (org_id, event_name, occurred_at DESC)
```

主键是复合主键 `(id, occurred_at)`——PostgreSQL 要求分区键出现在主键里。

## 用法

```bash
# 本地一次装好（建 schema、父表、默认分区、索引、当月分区）
python partition_kit.py --init --dsn postgresql://postgres@127.0.0.1:55433/alpha_part

# 日常维护：保证「当月 + 未来 2 个月」分区存在，并报告默认分区里的异常行
python partition_kit.py --dsn postgresql://postgres@127.0.0.1:55433/alpha_part

# 只演练不落库
python partition_kit.py --dry-run --ahead 3
```

环境变量：`TE_SCHEMA`（默认 tracking）、`TE_TABLE`（默认 track_event）、`TE_MONTHS_AHEAD`（默认 2）、`DATABASE_URL`。

`--init` 与 `ensure_partitions()` 都是幂等的，可以放进定时任务每分钟跑，不会重复建表。

## 告警口径

`alerts()` 统计默认分区行数：有行即说明有事件的 `occurred_at` 落在已建分区之外（历史回填、时区错、客户端时钟漂移）。
返回 `{"alert": "events_outside_partition_range", "rows_in_default", "min_occurred_at", "max_occurred_at"}`，配 `--alert-threshold N` 可容忍少量历史数据。

## 验收测试

```bash
pytest tests -q      # 6 passed（建临时库 → init → 写入 → tableoid 断言 → 丢弃）
```

覆盖：init 建出父表/默认分区/当月分区；本月事件落到当月分区且不告警；2023 年的事件落默认分区并触发告警；`ensure_partitions` 幂等（ahead 2→4 只多建两个月）；ahead 建出当月 + 4 个月；`drop` 清空。

## 设计取舍

- **默认分区必须存在**：没有默认分区时，越界插入会直接报错并让上游写入失败；有默认分区则数据不丢、由告警兜住。
- **建分区不用 `CREATE TABLE IF NOT EXISTS ... PARTITION OF`**：先查 `pg_class` 再建，避免并发下两个进程同时建同一分区互相报错；并发场景可再加 `pg_advisory_lock`。
- **不做分区删除**：删历史分区属于数据生命周期策略，需要业务确认保留期，交给调用方按 `RETENTION_MONTHS` 自行 `DROP`。
