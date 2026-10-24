# videomanager 事件流说明

本文档记录 `VideoModel` 创建、修改、删除时需要触发的逻辑，以及会互动的 app。当前代码仍处在解耦过程中，后续修改事件逻辑时应先更新本文档。

## 核心模型

- `VideoModel`：录像主表，保存玩家、文件、审核状态、级别、模式、成绩、`pluck`、比赛标记等信息。
- `ExpandVideoModel`：录像扩展信息，目前主要保存录像内标识 `identifier` 和比赛标识列表 `tournament_identifier`。

`VideoModel` 是多个 app 的事实事件源。任何保存 `VideoModel` 的代码都应尽量使用 `save(update_fields=[...])`，让信号接收器能判断本次修改的影响范围。

## 创建录像

主要入口：

- `common.services.new_video_by_file`（普通上传的解析、标识校验、查重和创建）
- `VideoModel.create_from_parser`
- `accountlink.services.saolei_video_import_one`
- `tournament.gsc.services.upload_gsc_history_video`（独立编排历史代传，直接调用 `create_from_parser` 并显式关联历史比赛，不依赖普通上传业务）
- 管理命令或测试中直接 `VideoModel.objects.create`

创建前通常需要完成：

- `utils.parser.MSVideoParser` 解析录像文件，得到基础字段、扩展字段、状态、标识、比赛 token、`pluck`。
- `identifier` 检查标识安全性和归属。如果录像本身合法但标识不属于用户，状态应降为 `IDENTIFIER`。
- 文件重复检查。

导入传给 `create_from_parser(..., upload_time=...)` 的时间在创建信号中参与 check-in 判断，避免历史文件按当前时间误入正在进行的比赛。由于 `auto_now_add`，创建后仍通过 `videomanager.services.set_import_upload_time` 显式保存来源时间；复用文件只在指定时间更早时保存，继续触发队列和排行信号。

创建时需要触发：

- `tournament`：`pre_save(VideoModel)` 根据 `ExpandVideoModel.identifier` / `ExpandVideoModel.tournament_identifier` 执行比赛 check-in，并可能设置 `ongoing_tournament=True`，同时暂存命中的比赛；`post_save(VideoModel)` 在录像获得主键后消费该临时结果，写入比赛的 `videos` 多对多关系。
- `videomanager`：创建后需要进入对应审核队列或最新队列；队列副作用应由 `videomanager.signals` 统一处理。
- `msuser`：创建时按普通录像计数，并按符合条件的高级成绩提升上传额度。旧竞速纪录信号已移除。
- `effranking`：提交后读取数据库生成的 Thrp，尝试刷新对应级别的个人最佳及 sum；录像须为 STD、OFFICIAL、非隐藏比赛录像。
- `customranking`：自定义 pluck 排行需要录像满足 `OFFICIAL`、非比赛、合法自定义配置、`pluck is not None`。当前通过 `VideoModel` 保存后的信号维护 `CustomPluckRecord`。
- `utils.parser.MSVideoParser`：标准三等级和当前支持的自定义 `pluck` 场景都会在解析时前台计算，保存 `VideoModel` 后触发 `customranking`。
- `videomanager.tasks`：`task_video_pluck` 入口保留，供未来重新需要后台计算时复用。

## 删除录像

实例 `delete()`、QuerySet 删除、Admin 和用户级联删除均经过删除信号，不依赖上传或管理接口显式补偿。

站长单个删除入口为 `POST /api/video/admin/delete`，复用 Ninja 的 `django_auth_superuser` 会话认证及 CSRF 校验，仅 `is_staff` 的账号不能调用。JSON 请求体为 `{"id": 123}`，每次只接受一个严格正整数 ID，不再接受 ID 数组。业务服务 `delete_video_by_id` 在共享排行准入和数据库事务内锁定、删除这一条录像，返回 `id`、`deleted` 和 `affected_tournament_ids`；录像不存在时返回 `deleted=false`，便于核对上次结果未知的请求。涉及比赛时记录警告日志，暂不发送私信。排行重建期间，HTTP 准入会在删除前返回既有 503 响应。

固定中文的站长页面位于 `/#/superuser/delete-videos`，没有菜单或管理员标签页入口。页面通过同路径的 `GET /api/video/admin/delete` 向后端验证 superuser 权限，并获取 CSRF cookie 和请求 token；该响应禁止缓存，不修改录像。页面支持粘贴 ID 列表或 JSON 数组，先校验全部输入并去重，再在警告确认后逐条发送独立删除请求。每次等待完整响应后才发下一条；失败、超时或权限失效时停止，保留已确认结果和剩余 ID，不自动重试。手动停止或离开页面不取消正在执行的请求，只阻止后续请求；刷新页面不会保存本次进度。

每个请求都有独立事务，后续请求失败不会恢复此前成功删除的录像。文件清理和排行提交回调仍在该单次请求内同步执行；拆成单个请求降低每次工作量，不保证生产环境每次都能在 Nginx 超时前完成。

- `videomanager.signals.delete_video_expansion` 在录像删除事务内清理对应 `ExpandVideoModel`；事务回滚会一起恢复。若删除源本来就是扩展记录实例或 QuerySet，则交给原有级联处理，避免重复删除。
- `customranking.signals.refresh_custom_pluck_rank_on_video_delete` 在事务提交后复用 `refresh_custom_pluck_rank`，按玩家和级别从剩余合格录像补选 pluck 最佳纪录，并更新数据库和 Redis。批量待删录像不会被重新选入；没有候选时保留无纪录状态。`CustomPluckRecord` 删除后的缓存同步也延后到提交时，并重读当前纪录，兼容同一事务内删除后重建；删除回滚不发布这两项更新。
- 文件继续由 `django-cleanup` 在事务提交后删除；计数、竞速与效率榜、外站导入引用沿用各自已有逻辑。
- **最新录像队列保持现状**：数据库删除不移除 `newest_queue` 快照，最新录像接口仍可能返回已删除的 ID。队列只按既有规则裁剪或由管理员单独移除，不增加删除信号清理或读取时查库过滤。
- **比赛普通删除不立即重算。** 删除录像会清除比赛的多对多关联，暂时保留已结算成绩、名次、积分和历史最好成绩。显式重算按赛种及成绩来源处理：打卡赛和 GSC 录像来源不再计入已删除录像，GSC 手工来源保留录入成绩但仍参与全场排名及积分更新。新赛种须提供自己的删除及重算规则。站长 API 已提供比赛 ID 和日志警告，隐藏页面已增加删除警告和确认；未来通知主办方的私信尚未实现，详见 [比赛录像删除与成绩一致性](../tournament/VIDEO_DELETION_PLAN.md)。

本次不修改模型字段、不需要数据库迁移，也不自动扫描清理历史孤立扩展行。旧的 pluck 缺失纪录可通过既有 `refresh_all_custom_pluck_ranks` 业务服务重建；仅重建 Redis 缓存不能补回缺失的数据库纪录。

删除源判定和提交后回调沿用 Django 的 [删除信号 `origin`](https://docs.djangoproject.com/en/6.0/ref/signals/#post-delete) 与 [`transaction.on_commit`](https://docs.djangoproject.com/en/6.0/topics/db/transactions/#performing-actions-after-commit)。

## 修改录像字段

### `state`

影响：

- `videomanager`：录像应从旧状态队列移除，并加入新状态队列。
- `msuser`：符合条件的高级标准录像转为官方状态时，可提升上传额度。
- `customranking`：如果自定义 pluck 录像变为 `OFFICIAL`，可尝试加入排行；如果变为不可排行状态，需要移除该录像影响。
- `identifier`：标识绑定/解绑会间接修改录像 `state`。
- `effranking`：官方资格改变时尝试加入，或为由该录像保持的 Thrp 纪录补位。

推荐写法：

```python
video.state = MS_TextChoices.State.OFFICIAL
video.save(update_fields=['state'])
```

不推荐在业务代码中直接维护多个 app 的副作用。

### `ongoing_tournament`

影响：

- `videomanager`：比赛录像不应进入缓存队列。
- `msuser`：比赛录像创建时不计入普通录像数量；公开时不追加计数。
- `customranking`：比赛录像不进入纪录。
- `effranking`：隐藏比赛录像不进入 Thrp 榜，公开后可尝试加入。
- `tournament`：该字段由比赛 check-in 逻辑设置，表示录像属于进行中的比赛。比赛结束后，应将 `ongoing_tournament` 设置为 `False`。

推荐写法：

```python
video.ongoing_tournament = True
video.save(update_fields=['ongoing_tournament'])
```

### `pluck`

影响：

- `customranking`：保存 `pluck` 后，如果录像满足 density 排行条件，应刷新对应玩家的 `CustomPluckRecord` 和 Redis 全榜缓存。
- `utils.parser.MSVideoParser`：普通三等级和当前支持的自定义录像都会在解析时直接计算 `pluck`。

推荐写法：

```python
video.pluck = pluck
video.save(update_fields=['pluck'])
```

### 排行字段

旧经典排行的字段比较、分类迁移和补位逻辑已移除，恢复要求见 `../msuser/refactor.md`。录像本身的 `timems`、`bvs`、`iqg`、`ioe`、`path` 和只读 `stnb` 仍保留。

`customranking` 的数据库个人最佳纪录仍按 `pluck`、`timems`、`upload_time` 比较；Redis 使用简化 score 保存全榜。

`effranking` 使用数据库生成的 `thrp = bv / (left_ce + right_ce + double_ce)`。`CAPTURE_FIELDS` 已包含 `bv` 和三个有效点击数字段；其中 `right_ce` 在效率榜中参与分母计算，不用于区分 NF。保存后先判断影响范围，提交后再读取持久化的 Thrp，避免使用实例上的旧派生值。原纪录变差或失效时只查询受影响玩家、级别的补位。

### 文件和解析字段

`refresh_video(video)` 会重新解析文件并刷新所有文件包含的数据。

`python manage.py refresh_videos` 按主键顺序遍历全部录像并逐条调用此函数，不筛选状态或模式，不使用批量更新。有变化时由实例保存触发信号；无变化时不会强制保存。解析阶段的已知异常包装为 `VideoParseError`，命令报告录像 ID 并跳过；数据库、文件读写及保存链路等其他错误仍停止执行。已完成的刷新保留，正常结束时汇总成功与跳过数量。

重新解析时需要同步刷新 `ExpandVideoModel.identifier` 和 `ExpandVideoModel.tournament_identifier`。其中 `tournament_identifier` 使用 `JSONField` 保存 parser 提供的比赛标识列表。

如果重新解析后 `IDENTIFIER` 录像的标识已经属于玩家，可将状态改为 `OFFICIAL`，并通过状态保存触发后续事件。

## 互动 app

### `identifier`

职责：

- 维护标识文本是否安全、是否绑定到某个 `UserMS`。
- 当标识绑定、解绑、转移、删除或变为不安全时，修改相关录像的 `state`。

互动方式：

- `identifier.services` 批量更新匹配录像状态，并显式更新已有队列项、上传额度和 pluck 纪录。批量更新不触发录像保存信号。
- 竞速纪录由 `speedranking` 的批量服务在事务提交后更新或补位，仅处理这些录像保持的单项。
- 效率纪录同样显式调用 `effranking.services` 的批量加入/移除服务，不能依赖被批量更新绕过的保存信号。

### `tournament`

职责：

- 创建录像前识别比赛 token 或 Arbiter 标识。
- 对进行中比赛设置 `video.ongoing_tournament=True`。
- 创建后把录像加入比赛的 `videos` 多对多关系。
- 比赛结束后为比赛录像设置 `video.ongoing_tournament=False`。

互动方式：

- `VideoModel.create_from_parser` 将 parser 的 `tournament_identifier` 列表写入 `ExpandVideoModel`。比赛 check-in 直接读取 `video.video.tournament_identifier`，不再在 `VideoModel` 实例上暂存比赛 token 临时状态；`tournament` 仍会在 `pre_save` 到 `post_save` 之间短暂保存已命中的比赛对象，用于创建后写入 M2M。
- `tournament.signals` 在 `pre_save` / `post_save` 中完成 check-in。
- `reveal_videos_for_tournament` 在批量公开后调用竞速、效率和 pluck 的批量服务，不逐条保存录像。

### `msuser`

- 保留用户标识列表、录像计数和上传额度。
- NF 独立于 mode，以 `right_ce == 0` 判断；NF 子计数会与模式子计数重叠，空值不视为 NF。
- `post_save(VideoModel)` 在创建普通录像时增加计数，并在满足条件时提升上传额度。
- `pre_delete(VideoModel)` 在删除普通录像时减少计数，删除录像不回退额度。
- 已移除经典纪录字段、纪录刷新信号、UserMS 新闻信号及旧 Redis 排行读写。
- 新竞速榜的保存/删除信号和跨 app 批处理由 `speedranking` 负责，见 `../speedranking/README.md`。

### `effranking`

- `post_save(VideoModel)` 和 `post_delete(VideoModel)` 在事务提交后更新 Thrp 纪录及四个排序索引；事务回滚不写缓存。
- 绑定/解绑标识及比赛公开分别由业务入口显式调用批量服务。
- 纪录和索引均在 Redis，读接口不回源；全量重建使用 `rebuild_eff_ranks`。规则、错误日志与并发限制见 `../effranking/README.md`。

### `customranking`

职责：

- 维护pluck自定义排行榜。
- 每个玩家、每个支持的自定义配置只保留一条最佳 `CustomPluckRecord`。
- Redis 缓存保存所有用户的纪录。

互动方式：

- `customranking.signals` 监听 `VideoModel` 的 `state`、`ongoing_tournament`、`pluck`、`timems`、`upload_time`；不监听 `right_ce`，pluck 排行不需要 NF 信息。
- `CustomPluckRecord` 保存或删除后，同步更新 Redis 排行缓存。

### `common`

职责：

- 提供上传入口，做文件、用户、标识和重复录像检查。
- 调用 `VideoModel.create_from_parser` 创建录像。
- 创建后触发必要的保存和队列更新。

当前上传链路中仍有显式调用 `video.update_redis()`，但它不应再直接维护队列；队列写入和移除由 `videomanager.signals` 处理。

### `accountlink`

职责：

- 从外部站点导入录像。
- 复用 parser 和 `VideoModel.create_from_parser`。
- 导入后可能修改 `upload_time`，并触发同样的录像事件链。

## TODO

- `VideoModel.update_redis()` 已经不再维护 Redis 队列，且 `pluck` 调度和录像数量统计职责也已移出；名称和剩余职责都已经过时。
  - 当前实际职责只剩按录像状态写上传日志。
  - 上传日志应迁移到 `videomanager.signals`，和队列事件同属录像状态/创建事件的本 app 副作用。
  - 完成日志迁移后，应删除 `update_redis()`，上传、导入等入口不再需要显式调用它。
- 录像数量统计已迁移到 `msuser.signals`。
  - 创建录像会增加总数统计；删除录像会减少总数统计。
  - 经典级别和模式会同步维护对应子计数；所有模式/级别的 `right_ce == 0` 录像同时计入 NF。
  - `video_num_limit` 只会在符合条件的高级标准官方录像保存后提升，删除录像不会回退上限。
  - 后续若要处理状态回退、模式/级别变化，应先明确统计口径，再扩展 `msuser.signals`。
- `videomanager.signals` 是 `_old_values` 的统一来源，新增依赖旧值的 app 时应先扩展 `CAPTURE_FIELDS`。
  - 当前用于队列、custom pluck、竞速和效率排行；效率榜额外依赖 `left_ce`、`double_ce`。
  - 如果未来新增依赖 `file_size`、`end_time`、`cell*`、`flag/op/isl` 等字段的副作用，需要同步补充。
- 批量修改仍不能依赖普通 `save()` 信号。
  - `identifier` 已批量更新状态并显式补偿队列、上传额度、pluck、竞速和效率排行；比赛公开也已接入对应批量服务。
  - 其他数据迁移批量修改 `state/level/mode/player/timems` 或有效点击数时，需要显式批处理逻辑，否则排行和队列不会自动保持一致。
- `update_fields` 仍是信号正确判断影响范围的关键。
  - 不带 `update_fields` 的保存会让接收器按更宽的字段集合工作。
  - 后续可以用 lint 或测试约束重要路径的 `save(update_fields=[...])` 写法。
- `pluck` 计算分工需要保持清晰。
  - 普通三等级录像在 parser 中即时计算。
  - 当前支持的自定义录像也在 parser 中前台即时计算，并通过保存 `pluck` 触发 `customranking`。
  - `task_video_pluck` 仍保留为后台入口；未来如果重新出现耗时过长的场景，可切回任务队列。
  - 如果未来增加新的自定义配置或更昂贵的指标，应先评估是否需要进入后台任务。
- 旧 `refresh_stnb` 的录像重解析入口由 `refresh_videos` 替代；经典纪录全量重建已移除。竞速和效率榜已有各自的重建命令和批量服务，刷新录像不能替代完整建榜。
- `iqg` 使用数据库 `GeneratedField` 和 `Power` 表达式。
  - 本地测试库已经覆盖基本创建和查询路径。
  - 生产部署前仍需要在同版本数据库环境做迁移预演，确认生成列表达式兼容。

## 修改限制
`customranking`是新增app，可任意修改，无需担心迁移。其他app的迁移需要让django makemigrations能自动完成。


# stnb 支持说明

## 背景

`stnb` 与 `iqg` 成正比，比例系数只由标准三等级决定：

- Beginner: `stnb = 36 * iqg`
- Intermediate: `stnb = 162 * iqg`
- Expert: `stnb = 435 * iqg`

自定义级别没有 `stnb` 定义，`VideoModel.stnb` 返回 `None`。

`iqg = bv / (timems / 1000) ^ 1.7` 已作为 `VideoModel` 的 `GeneratedField` 保存，`ExpandVideoModel.stnb` 已删除。`stnb` 属性由 `VideoModel.iqg` 派生；旧个人纪录功能已移除。 `stnb` 与 `bvs`、`ioe` 一样属于 `VideoModel` 基础字段变化后的派生指标，不再监听 `ExpandVideoModel` 的保存事件。
