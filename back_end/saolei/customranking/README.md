# `pLuck`排行榜开发文档

个人纪录与排行仅保存在 Redis，不再维护 MySQL 纪录表。`VideoModel.pluck` 仍是录像事实来源，补位及主动重建从录像库查询，不重新解析文件。

## 录像规则

准入使用 `CUSTOM_PLUCK_CONFIGS` 的四种自定义配置，模式为 STD 或 RKC、状态为 OFFICIAL、非隐藏比赛录像且 Pluck 非空。个人最佳按 `(pluck, timems, upload_time)` 升序选择；Pluck 越小越好，同分取用时更短、上传更早的录像。不区分 NF。

## 缓存结构

每个自定义配置有两张缓存表：RANK、DETAIL。RANK用于排序，DETAIL用于存储展示数据。缓存由`cache.py`提供的`PLuckRankingCache`类管理。

RANK是有序集zset，`member`直接使用`player_id`，因此同一用户天然去重。排序键`score`通常是`pluck`；当`pluck > 0`时`score = pluck`，当`pluck == 0`时`score = timems - MAX_TIMEMS`。这个规则放弃正数`pluck`碰撞时的严格 tie-breaker，但能处理最主要的`pluck == 0`碰撞风险。

DETAIL是查找表hset，主键是RANK的`member`，字段为`video_id`、`timems`、`upload_time`。展示用的`mode`、`timems`和`bv`由前端录像缓存补全，排行API只返回录像ID、玩家、pluck和上传时间。`pluck`由RANK的`score`还原：`pluck = max(0, score)`。排行不存储或返回 NF 信息。

## 功能支持

### 录像事件与批量更新

`VideoModel` 保存和删除信号通过 `sync_video` 注册提交后回调，复用 `_old_values` 中的旧玩家、级别，不额外查询旧录像。回调读取已保存的当前录像，改善时比较缓存纪录；变差、失效或删除时，仅对由该录像保持的纪录查库补位。归属或级别变化同时处理旧、新分类。无候选时同时清除 zset/hash。

标识绑定、解绑及比赛批量公开复用 `add_videos_to_custom_pluck_ranks` / `remove_videos_from_custom_pluck_ranks`。传入固定录像 id 或稳定范围定位的 queryset；批量增加用窗口函数按 `(player_id, level)` 选最佳，移除只重建缓存纪录录像位于失效集合的分类。按玩家分段，通过共用 pipeline 读取和写入，不逐条保存录像。离线快照初始化在导入事务结束后吸收全库录像，不延迟到初始化结束。

回滚不发布排行更新。提交后回调使用 `robust=True`，失败记录上下文与堆栈，不回退录像提交，也不阻断其他回调。不新增 WATCH、锁或重试，并发覆盖通过管理员修复处理。

### 缓存接口
- 用户请求排行榜区间时只读取缓存，不回源数据库。
- 缓存不限制长度，保存所有有合格纪录的用户。
- `read_records` 供更新使用，只在 zset/hash 均缺失时视为无纪录；半缺失记录错误，由管理员刷新修复。零 score 是合法值，不代表缺失。

### 主动修复与部署

- `POST /api/customranking/pluck/refresh` 从录像库重算用户 id 闭区间内的所有配置，同时清理已无候选的旧项；起止 id 相同即可修复单个用户。
- `rebuild_custom_pluck_cache` 从 `VideoModel` 分组取最佳录像，支持 `--level`、`--batch-size`。手动重建先清空对应 key，再批量写入；执行期间暂停相关写入，失败后排查并重跑。
- 正常部署只删除 MySQL 纪录表，直接复用现有 Redis 数据，不清空或重建缓存，不更改 key、member、score 或 DETAIL 格式。
