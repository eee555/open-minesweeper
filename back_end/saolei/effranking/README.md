# 效率排行榜

独立的 Django app `effranking` 承载效率排行榜类别，当前提供 Thrp 榜、个人纪录查询、增量刷新、管理员修复和全量重建。

## 规则

### 录像准入

- 只接收 `level` 为 `b`、`i`、`e` 的录像。
- `mode = STD`，`state = OFFICIAL`，`ongoing_tournament = False`。
- 不设最低 3BV 门槛，不沿用竞速榜的 3BV 限制。
- 原有 `b/i/e/sum` 不区分普通/NF，另设独立的高级 NF 小榜 `e_nf`。

### 个人纪录

使用已有的持久化派生字段：

```text
ce = left_ce + right_ce + double_ce
thrp = bv / ce
```

普通三级别各取个人最高 Thrp；Thrp 相同时，取上传时间更早的录像。用时不参与选优。成绩和上传时间均完全相同的录像无需额外业务区分，数据库查询可以追加 `id`，使结果稳定。

不同用户在四个小榜上同分时，同样优先上传更早的成绩。单项使用所选录像的 `upload_time`；sum 使用三个现有单项纪录中最晚的 `upload_time`，表示该成绩组合的达成时间，缺项不参与时间计算。不能直接使用 Redis 默认 member 顺序作为这一层 tie-breaker。

小榜分别为：

| 标识 | 含义 | 排序方向 |
| --- | --- | --- |
| `b` | 初级个人最佳 Thrp | 越大越好 |
| `i` | 中级个人最佳 Thrp | 越大越好 |
| `e` | 高级个人最佳 Thrp | 越大越好 |
| `sum` | `b + i + e` | 越大越好 |
| `e_nf` | 高级 NF 最佳 Thrp；达到 1 后按达成局数 | 越大越好 |

缺失单项在 sum 中按 0 计算。用户至少有一项合格纪录才进入 sum；单项榜仅包含实际拥有该项纪录的用户，不要求四个小榜的成员完全一致。

### 高级 NF

`e_nf` 只接收上述准入条件下的高级 `right_ce = 0` 录像，与原有四项仅共用个人纪录 hash。Thrp 的数学上限为 1：未达到 1 时比较个人最佳原始 Thrp；达到 1 后比较所有合格满分录像的局数，相同 BV 的多条录像分别计数。同分直接按 Redis member 顺序，不再编码上传时间。

该项只保存 `value` 和 `video_ids`：达到 1 时缓存全部合格满分录像的 id，按 id 升序排列；未满分时只保存最佳一局的 id。局数直接取列表长度，不重复保存计数、代表录像或上传时间。`e_nf` 不参与 sum。

## 缓存结构

### 事实来源

- `VideoModel` 是唯一事实来源，直接使用 `thrp`，不新增重复的录像字段。
- 不维护个人纪录数据库模型，个人纪录和排行均保存在 Redis，可通过录像库重建。
- 缺失点击统计等情况可能使 `thrp` 为 `NULL`。只吸收可排序、可序列化的有限数值，不把缺失值或除零结果作为有效纪录。
- hash 保存数据库原始取值，不因排序编码而转换个人纪录。单项 Thrp 的数学上界为 3.4，sum 的数学上界为 10.2，统一按 10.2 预留编码容量；这不是人为设置的准入上限，不因此增加数值过滤或截断逻辑。

### 一个 hash、五个 zset

| Key | 类型 | 内容 |
| --- | --- | --- |
| `effranking:thrp:records` | hash | field 为用户 id，value 为该用户的完整纪录 JSON |
| `effranking:thrp:b` | zset | 初级排序索引 |
| `effranking:thrp:i` | zset | 中级排序索引 |
| `effranking:thrp:e` | zset | 高级排序索引 |
| `effranking:thrp:sum` | zset | 总和排序索引 |
| `effranking:thrp:e_nf` | zset | 独立的高级 NF 排序索引 |

hash 的 JSON 结构为：

```json
{
  "b": {"value": 1.25, "video_id": 123, "upload_time": "2026-10-19T12:00:00Z"},
  "i": null,
  "e": null,
  "e_nf": {"value": 1, "video_ids": [456, 457, 458]}
}
```

录像 id 均指 `VideoModel.id`，不是 `VideoModel.video_id`。普通单项上传时间保留原始精度，用于个人选优。sum 的数值和达成时间都由三个单项计算，不在 hash 中重复存储；缺项使用 `null`，不能仅根据数值判断有无纪录。

zset 的 member 仍直接使用用户 id。原有四个小榜共用同一个 score 编码函数，在 score 中编码分值和上传时间，统一升序读取：

```text
value = 单项原始 thrp，或三个单项原始值之和
upload_time = 单项录像上传时间，或 sum 的达成时间
units = floor(value * 1000000 + 0.5)
upload = floor(upload_time 的 Unix UTC 秒数 / 60)
T = 2**29
score = -units * T + upload
```

要求 `0 <= upload < T`，并验证四个小榜编码范围内的整数均能由 Redis double 精确表示。这样高分优先，同分时早上传或早达成优先，不需要查找或移除旧的复合 member。只有量化分值和编码时间都相同时，才使用 Redis 默认 member 顺序。

sum 先用 hash 中三个原始成绩求和、缺项按 0，再调用同一编码函数，不能先量化三个单项再求和。sum 的达成时间取现有单项的完整上传时间最大值后统一转换为分钟数，不额外保存组合时间或引入独立编码规则。

zset 仅提供排名和排名段的用户索引；展示、个人比较和求和均使用 hash 中的原始纪录，不从 score 还原数据。

高级 NF 独立使用 `score = -value`（`value < 1`）或 `score = -len(video_ids)`（`value = 1`），同样升序读取，不使用原有四项的分值/时间编码。

### 精度与容量

- 单项 Thrp 与 sum 的排序值均保留六位小数，上传或达成时间精确到分钟。只为简化排序索引而量化，不保证所有不同原始成绩均能区分；个人最佳录像始终按原始值和完整上传时间比较。
- 使用 `T = 2**29`，时间为 Unix epoch 起的 UTC 分钟数，可覆盖约 1021 年。按 sum 的数学上界 10.2，整数分值最大为 10200000，`10200000 * 2**29 = 5476083302400000 < 2**53`，四个小榜的整数编码均能精确表示。
- `2**29` 是统一精度和容量上界下可用的最大 2 的幂次时间因子；改用 `2**30` 会超出 double 的连续精确整数范围。仍须保证 `0 <= upload < T`。
- 单项 Thrp 不可能超过数学上界 3.4，sum 不可能超过 10.2，无需设计数值超限处理。

### 读写与一致性

- 复用项目的 `django_redis` 连接配置、pipeline 和 `transaction.on_commit`。
- 各大榜自行处理选优和补位，缓存层只负责基础读写，不引入通用的业务 `transform` 管线。
- 一次事件先批量读取所需纪录，再判断变化，最后用一个事务 pipeline 写入 hash 和变化的 zset。
- 原有单项纪录变化时只检查该单项及关联 sum，不重写其他不相关的小榜。比较完整的新旧 score，决定是否写 zset；仅上传时间变化也可能改变 sum 的达成时间，因此仍需检查关联 sum。高级 NF 独立比较其 score。仅录像 id 改变、score 未变时只更新 hash。
- 最后一项纪录失效时删除该用户的 hash 项和对应 zset 成员。
- 不使用 WATCH、重试或新的全局锁。数据库提交和 Redis 更新不是跨库事务，并发读改写仍可能产生覆盖；管理员修复和全量重建作为恢复手段。
- 所有更新入口记录异常堆栈及已有的用户、录像、操作上下文，不静默吞错，也不为日志额外查询数据库。

## 录像更新链路

### 单录像创建、修改与删除

在 `effranking.signals` 监听 `VideoModel` 的保存和删除，复用 `videomanager` 的旧值捕获，不在 `VideoModel` 中加入排行业务。

需要关注的字段：

```text
player_id, level, mode, state, ongoing_tournament,
bv, left_ce, right_ce, double_ce, upload_time
```

`right_ce` 既是 Thrp 分母的组成项，也是高级 NF 的筛选条件。`timems`、`left/right/double` 本身不影响 Thrp，不因这些字段单独改变而刷新效率榜。

`videomanager.signals.CAPTURE_FIELDS` 捕获 `bv`、`left_ce`、`right_ce`、`double_ce` 等字段的旧值。`thrp` 是 GeneratedField，不把模型实例上可能过期的派生值作为更新依据；数据库提交后读取持久化的当前录像。

处理策略：

1. 新增或改善的合格录像直接与缓存中的对应单项比较，必要时替换并重算 sum。
2. 已持有纪录的录像变差、失去资格或被删除时，只为受影响的用户和级别查询最佳剩余录像。
3. `player/level` 改变时，旧分类按需补位，新分类尝试加入；`mode/state/ongoing_tournament` 改变时重新判断资格。
4. 查询补位按 `thrp DESC, upload_time ASC, id ASC`，不逐条加载用户的全部录像到 Python 中筛选。
5. 所有缓存副作用在 `transaction.on_commit` 后执行，事务回滚时不发布变更。
6. 旧/新分类涉及高级 NF 时，独立重查受影响用户的满分列表或最佳一局。任意满分录像变动都能影响排名，不能仅判断其是否保持普通高级纪录。

### 批量录像

`QuerySet.update`、`bulk_update` 不触发模型保存信号，因此必须提供独立的批量加入和移除 service，不能仅增加 receiver。

- 批量加入：按用户 id 分段，对 `(player_id, level)` 在数据库中分桶选优，与缓存纪录比较，再批量提交变化。
- 批量移除：从受影响用户的缓存中找出被这批录像保持的纪录，仅查询这些 `(player_id, level)` 的补位，不全量重建用户。
- 高级 NF：对同批受影响用户，用一个数据库窗口查询取全部合格满分录像或未满分时的最佳一局，重新构建 id 列表，避免重复加入或漏删。
- 传入固定录像 id 的 queryset；不能在修改 `state/ongoing_tournament` 后继续用依赖旧状态的过滤条件定位这批录像。
- 不对批量录像逐条调用单录像 service，不为效率榜强行合并其他 app 的不同排行查询。

接入现有业务入口：

| 入口 | 效率榜动作 |
| --- | --- |
| `identifier.services.bind_identifier` | OFFICIAL 状态更新后，批量吸收相关录像 |
| `identifier.services.unbind_identifier` | 状态降为 IDENTIFIER 后，批量移除影响并补位 |
| `tournament.services.reveal_videos_for_tournament` | 批量公开后，吸收新获得资格的录像 |
| 单录像公开、审核、刷新、删除 | 通过模型信号处理 |
| 本地快照初始化 | 建库完成后调用效率榜重建命令 |

后续新增绕过信号的批量写入时，也必须明确调用对应 service。

## 查询与维护接口

app 内使用 Ninja router，在项目 API 中挂载 `/api/effranking/`。接口路径不带结尾斜杠。

- 参数、响应 Schema 和装饰器说明由 Ninja API 文档生成。
- 分页使用左闭右开的 `start/end`。
- 所有查询只读取 Redis，不在请求中自动回源或重建。
- 排行的每个用户均返回完整的 `b/i/e/e_nf` hash 纪录及 `player_id`，不按当前排序列裁剪；sum 由前端计算。
- 分页排名由前端使用 `start + index + 1` 显示，不为每行重复查询排名。
- 个人接口用 pipeline 一次读取 hash 和五个 ZRANK；无纪录时返回完整空项，排名为 `null`。
- 管理员重建 `b/i/e` 时查询数据库，重算关联 sum；重建 `sum` 时只根据缓存中的三个单项计算，不回源数据库。
- 管理员重建 `e_nf` 时独立查询最佳及满分局数，只修复该项，不改动普通高级纪录或 sum。
- 手动修复即使数值未变，也要修复目标排序索引。无录像可补位时清除对应单项。

## 维护

```bash
python manage.py rebuild_eff_ranks
```

首次部署和缓存丢失后显式执行。`VideoModel` 使用 `thrp_idx` 索引，先完成数据库迁移，再暂停相关写入并建榜。临时榜全部构建成功后原子替换六个正式 key，失败保留旧榜；不扫描 Redis keyspace。本地快照初始化已调用此命令。

参数及暂停写入范围统一见[管理命令文档](../../../vitepress_doc/zh/guide/development/management-commands.md#rebuild-eff-ranks)。不提供自动回源、在线双写或定时重建。

## 代码组织

- 根目录 `signals.py` 和 `services.py` 协调录像事件与批量操作，`cache.py` 提供连接，`utils.py` 记录更新异常，`api.py` 聚合大榜路由。
- `thrp/` 包含本榜的计算、基础缓存、选优与补位、修复、重建、API 和测试；`nf_services.py` 独立负责高级 NF 最佳及局数查询。
- 按玩家分段的公共工具为 `utils.querysets.player_batches`，不依赖其他大榜的业务模块。

## 前端接入

`EfficiencyRanking.vue` 提供工具栏，`ThrpRanking.vue` 与个人纪录共用 `ThrpRecordValue.vue` 展示成绩及满分列表；管理员“排行纪录重建”页支持五个小榜。URL 约定见[排行榜 README](../../../front_end/src/views/RankingView/README.md)，展示、配色与请求职责见[个人主页 README](../../../front_end/src/views/UserView/README.md#thrp-纪录)。
