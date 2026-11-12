# identifier 业务说明

## 公开查询

- 每种字符串匹配使用独立的 `GET /api/identifier/query/<mode>?identifier=...`。所有模式均无需登录，只返回已审核通过的标识。
- 前端通过“匹配模式”和“忽略大小写”复选框选择接口，例如 `exact` / `iexact`；“限流说明”浮层按分组列出配额、匹配条件及组内共享规则。正则仍只有 `regex` 接口，通过表达式中的 `(?i)` 控制大小写。
- 响应为 `{items: [{identifier, user_id}]}`，没有匹配时 `items` 为空。未绑定玩家时 `user_id` 为 `null`。不提供服务端分页或游标，符合条件的结果按主键递增一次性返回。
- 每条字符串查询最多允许匹配 1000 个已审核标识，正好 1000 条全部返回。超过时返回 HTTP 400，响应为 `{code: "too_many_matches", detail: "..."}`，不返回部分结果；未审核的标识不计入。
- 单次数据库查询最多读取 1001 条并预加载关联玩家，用额外一条判断是否超限，不执行全量 `COUNT(*)`。
- 前端使用 PrimeVue DataTable 完成本地分页、标识字符串排序和归属玩家多选筛选（包括未绑定玩家），这些操作不发送标识查询请求，也不消耗请求配额。标识展示转义不改变排序所用的原始字符串。
- 超额请求返回 HTTP 429，并且不查询标识表。限流按 IP 计算，同组接口共享配额，避免通过轮换类似模式绕过限流。
- 按玩家 ID 查询标识复用 `GET /api/userprofile/identifier?user_id=...`，无扫雷资料的玩家返回空列表。

| mode / API 后缀 | 匹配方式 | 限流策略 | 限流组 |
| --- | --- | --- | --- |
| `exact` | 完整匹配，区分大小写 | 2 次/秒 | `identifier-exact` |
| `iexact` | 完整匹配，忽略大小写 | 6 次/分钟 | `identifier-text` |
| `contains` | 包含，区分大小写 | 6 次/分钟 | `identifier-text` |
| `icontains` | 包含，忽略大小写 | 6 次/分钟 | `identifier-text` |
| `startswith` | 前缀，区分大小写 | 10 次/分钟 | `identifier-prefix` |
| `istartswith` | 前缀，忽略大小写 | 6 次/分钟 | `identifier-text` |
| `endswith` | 后缀，区分大小写 | 6 次/分钟 | `identifier-text` |
| `iendswith` | 后缀，忽略大小写 | 6 次/分钟 | `identifier-text` |
| `regex` | MySQL ICU 正则，用 `(?i)` 等内嵌标志控制大小写 | 2 次/分钟 | `identifier-regex` |

### 限流设计依据

- `exact` 可使用现有唯一索引定位。前缀匹配没有前置通配符，但 Django 的 MySQL 后端生成 `LIKE BINARY`，索引利用仍取决于实际执行计划；因此给予独立、较保守的分钟配额。
- 包含、后缀有前置通配符，不能据此构造普通 B-tree 的前缀范围扫描。忽略大小写的普通模式通过 Django `Collate` 显式使用 `utf8mb4_0900_as_ci`，与现有字段索引的 `utf8mb4_0900_as_cs` 不同，也可能扫描；这些模式共用更低的配额。
- 正则只使用 Django 的 `regex` 和一个 API，由 MySQL `REGEXP_LIKE` 原生执行，默认区分大小写，可在表达式中使用 `(?i)` 忽略大小写。开销随表达式而变，因此给予最小配额。非法表达式及 MySQL 正则资源限制错误返回 400，其他数据库错误不伪装为输入错误。
- 普通模式会由 Django 自动转义 `%`、`_`、反斜杠；正则保留原始表达式，不用 Python `re` 模拟或校验 ICU 语法。
- 这些配额是基于当前查询结构的保守策略，不是生产压测结论。前端仅展示限流策略，不展示性能估计；调整限流时需同步浮层中的分组和配额。无需更改字段排序规则或数据库索引。

参考：[Django 字段查询](https://docs.djangoproject.com/en/6.0/ref/models/querysets/#field-lookups)、[Django MySQL 排序规则](https://docs.djangoproject.com/en/6.0/ref/databases/#collation-settings)、[MySQL 范围优化](https://dev.mysql.com/doc/refman/8.4/en/range-optimization.html)、[MySQL 正则及资源限制](https://dev.mysql.com/doc/refman/8.4/en/regexp.html)。

本文档记录 `identifier` app 的业务约束和当前实现。标识绑定/解绑会影响录像状态和多个排行系统，修改相关逻辑前应先确认本文档仍符合目标业务。

## 业务约束

- `Identifier.identifier` 是只读业务字段。
  - 创建后不应修改。
  - 如果需要更名，应创建新 `Identifier`，并删除或解绑旧记录。
- `Identifier.userms` 只允许在空和非空之间转换。
  - `None -> UserMS`：绑定标识。
  - `UserMS -> None`：解绑标识。
  - `UserMS A -> UserMS B`：暂不支持，应拆成解绑 A 再绑定 B。
- `Identifier.safe=False` 时，`Identifier.userms` 必须为空。
  - 不安全标识不能绑定用户。
  - 如果安全标识需要重新判为不安全，管理员必须先解绑，再修改 `safe`。
- `UserMS.identifiers` 是面向用户的标识列表，应与 `Identifier.userms` 保持一致。

## 当前架构

标识绑定/解绑副作用由 `identifier.services` 入队、`identifier.tasks` 显式处理，不再依赖 `Identifier` 的 `pre_save` / `post_save` / `post_delete` receiver。

- `identifier.signals` 已移除，绑定/解绑不使用模型信号。
- 业务代码不应直接修改 `identifier.userms` 或手动维护 `userms.identifiers`。
  - 绑定统一调用 `bind_identifier(identifier, userms)`。
  - 解绑统一调用 `unbind_identifier(identifier, userms=None)`。
  - 修改审核状态统一调用 `set_safe(identifier, safe)`。

## 绑定流程

`bind_identifier(identifier, userms)` 负责 `None -> UserMS`。

前置检查：

- `identifier.safe` 必须为 `True`。
- 如果 `identifier.userms` 已绑定其他用户，直接抛错。

请求内（事务内）操作：

- 将 `identifier.identifier` 加入 `userms.identifiers`。
- 设置 `identifier.userms = userms`。
- 统计该用户、该标识、状态为 `IDENTIFIER` 的录像数，作为返回给调用方的待同步数量。
- 事务提交后入队 `identifier.tasks.task_sync_identifier_videos`，不修改录像状态、排行或缓存。

## 解绑流程

`unbind_identifier(identifier, userms=None)` 负责 `UserMS -> None`。

前置检查：

- 如果未传入 `userms`，使用 `identifier.userms`。
- 标识必须处于已绑定状态。
- 如果传入的 `userms` 与当前绑定用户不一致，直接抛错。

请求内（事务内）操作：

- 将 `identifier.identifier` 从 `userms.identifiers` 移除。
- 设置 `identifier.userms = None`。
- 统计该用户、该标识、状态为 `OFFICIAL` 的录像数，作为返回给调用方的待同步数量。
- 事务提交后入队同一后台任务。

## 后台同步任务

`identifier.tasks.task_sync_identifier_videos(identifier_text, player_id)` 在 worker 中执行录像的批量更新：

- 以执行时 `Identifier.userms` 是否仍指向该玩家为准，决定目标状态（绑定为 `OFFICIAL`，未绑定为 `IDENTIFIER`）。连续绑定、解绑留下的多条任务最终收敛到当前绑定状态，重复执行不会重复补偿。
- 使用 `queryset.update` 批量修改状态，并发送 `videos_bulk_changed`，让勋章刷新在任务事务提交后按玩家入队。
- 绑定方向显式补偿 `newest_cache.update_bulk`、`update_video_count_limit_from_videos`，以及竞速、自定义 pluck、效率榜的新增；解绑方向同步内存对象的状态后更新 `newest_queue`，并移除这些榜中受影响的纪录。
- `queryset.update` 不触发 `VideoModel` 的保存信号，因此补偿必须留在任务内。
- 任务失败可通过管理员任务接口重启；成功记录按 `config/common.py` 的 `TASK_CLEANUP_CONFIGS` 保留 7 天后清理。

接口返回时录像状态与排行尚未变化，需要立即看到结果的调用方必须等待任务完成。

## 当前入口

- 用户绑定：`identifier.views.add_identifier`
- 用户解绑：`identifier.views.del_identifier`
- 管理员绑定：`identifier.views.staff_add_identifier`
- 管理员解绑或删除：`identifier.views.staff_del_identifier`
- 管理员过审：`identifier.views.staff_approve_identifier`
- GSC 报名自动绑定：`tournament.gsc.api.register_GSCParticipant`

这些入口应调用 `bind_identifier` / `unbind_identifier` / `set_safe`，不应直接写 `identifier.userms` 或 `identifier.safe`。

## 审核状态

`set_safe(identifier, safe)` 负责修改标识审核状态。

- `safe=True`：只修改审核状态，不自动绑定用户。
- `safe=False`：要求 `identifier.userms is None`，否则直接拒绝。
- 管理员如果需要将已绑定标识改为不安全，必须先调用解绑流程。

## 注意事项

- `queryset.update` 不触发 `VideoModel` 的 `pre_save` / `post_save`。
  - identifier service 使用批量更新时，必须同步补偿队列缓存和排行刷新。
- `newest_queue` 同时包含 `IDENTIFIER` 和 `OFFICIAL` 录像。
  - 绑定/解绑只需要更新已在缓存中的项，因此使用 `newest_cache.update_bulk`，不无条件新增。
- 如果某条录像没有进入 `newest_queue`，`update_bulk` 不会创建新缓存项。
- 竞速榜解绑仅重建当前纪录指向被解绑录像的字段，不重建该用户的所有纪录。

## TODO

- 保护 `Identifier.identifier` 只读语义。
  - 当前模型层没有阻止修改 `identifier` 字段。
  - 可以在 service 层限制，也可以在模型保存时检测旧值并抛错。
- 补充接口级测试。
  - 当前已有 service/integration 覆盖绑定、解绑、录像额度和 pluck 纪录刷新。
  - 仍可补充 view 层对冲突、未过审、不存在标识的响应测试。
