# 竞速排行榜

本 app 不新增数据库模型。录像仍以 `VideoModel` 为事实来源，排行和个人纪录查询只读 Redis，不自动回源或重建。

PB 使用每个小榜一个 zset、每个用户一个 hash，并额外维护各小榜人数 hash，是下述一般缓存结构的例外。PB 排行和个人 PB 页面均已实现；个人页面职责见 [UserView README](../../../front_end/src/views/UserView/README.md)。设计依据与后续优化见 [PB 榜开发计划](PB_PLAN.md)。

LSF 是竞速页面的首位和默认选项，由 top 纪录派生。规则、缓存、接口及页面入口见本文的 [top 榜](#top-榜)。讨论中 top 始终指该大榜，前端仅指前端网页。

## 代码组织

- `saolei/`：扫雷网规则的缓存、选优、补位、API 和测试，原有公开 API 路径不变。
- `pb/`：PB 专用的缓存、选优、补位、API 和测试，不套用扫雷网的成绩结构。
- `top/`：top 的前五明细、补位、锚点、软实力、后台任务、API 和测试，不依赖 PB 缓存。
- 根目录 `cache.py`：共享 Redis 连接与 pipeline；`utils.py`：错误日志和 UTC 时间换算。玩家分段工具为跨 app 共用的 `utils.querysets.player_batches`。
- 根目录 `services.py`：协调各大榜的共同读取、独立判断、共同写入；`signals.py`：录像事件入口；`api.py`：聚合各大榜的 router。
- 前端 `RankingView/routes.ts`：各大榜子路由。`SpeedRanking.vue` 提供大榜选择器、规则提示、“How to improve”上传建议，以及统一的颜色和刷新按钮。子榜通过 `defineExpose` 提供 `refresh`、`loading`，接收 `colored` prop；PB 刷新同时更新人数和榜单。切换大榜使用 push，支持浏览器返回；选项依次为 LSF、top、扫雷网、PB，`/ranking/speed` 默认跳转 `/ranking/speed/lsf`。项目使用 hash history，浏览器地址对应 `/#/ranking/speed/...`。

各大榜的排序、筛选、明细和分页选项写入 URL query，支持直接定位及浏览器历史恢复；参数说明见 [排行榜 URL](../../../front_end/src/views/RankingView/README.md)。上色统一使用 `store/local.ts` 的 `local.colored`，默认关闭，在 localStorage 持久化；竞速榜工具栏与设置页共享开关。top、PB、扫雷网单级别成绩复用 `store/color.ts` 的分段色阶，top 同时着色均值与真实明细，缺失成绩及扫雷网 sum 不着色。LSF 只给定阶着色，按等价 et 秒数使用 `colorTheme.grade`。色阶默认值来自 `utils/config.ts`，可在设置页编辑或还原当前项；彩色背景文字使用纯黑/白，透明背景继承文字色。原本没有开关的固定配色不受影响。

## Saolei.wang 规则

这是竞速排行中的一套规则，并非所有大榜的默认规则。`speedranking` 和 `SpeedRanking.vue` 保留为通用入口；前端该规则使用 `SaoleiRanking.vue`、`SaoleiCard.vue`、`saoleiRankingService.ts` 及 `Saolei*` 类型。未来其他大榜应使用自己的专名，不必沿用下面的指标和纪录结构。

- `saolei` 接收 STD、OFFICIAL、`ongoing_tournament=False` 的普通三等级录像。
- `saolei_nf` 是独立榜，额外要求 `right_ce == 0`；未知值不属于 NF。标准榜也接收 NF 录像。
- Time 门槛：初级 3BV >= 2，中级 >= 30，高级 >= 100。3BV/s 门槛：初级 >= 4，中级 >= 30，高级 >= 100。
- 单项先比较成绩，再比较 `upload_time`，上传更早优先；3BV/s 同分不再比较 timems。
- `sumt` 缺项按 999999 毫秒补齐，`sumb` 缺项按 0 补齐。至少有一项有效纪录才进入总榜。
- 总分同分时，使用组成该总分的现有纪录中最晚的上传时间，即当前成绩组合的达成时间。
- `is_lucky` 当前不参与准入判断。头像和签名资格读取标准榜 `et < 200000`，因此包含高级 3BV >= 100 的门槛。

## 缓存

当前两个 Saolei.wang 榜各使用一个 `speedranking:{ranking_name}:records` hash，field 为玩家 id；JSON 包含八项成绩、六个录像 id 和内部 `_uploads` 排序时间。

zset 舍弃部分精度并限制数值范围，是为了简化缓存逻辑：将成绩与上传时间合并进一个 score 后，member 只需使用玩家 id，更新成绩可直接覆盖，无需查找、删除旧的复合 member。zset 仅作为排名和排名区间查询的索引，允许近似排序，不从 score 恢复数据用于纪录比较；hash 仍保存原始纪录，个人选优、补位及求和逻辑不受影响。

每项使用 `speedranking:{ranking_name}:{stat}` zset，member 只保存玩家 id。令 `M = 3_000_000_000`、`upload` 为 Unix UTC 分钟数：Time 的 score 为 `timems * M + upload`，3BV/s 为 `-bvs_units * M + upload`，其中 `bvs_units` 是以 0.0001 为单位的整数。统一升序读取，相同玩家由 ZADD 直接覆盖。不同玩家同分同分钟时不再按更细时间区分。

`0 <= upload < M`，约可覆盖 5700 年。单项单位值最多 999999，总项最多 2999997，因此所有 score 都在 double 的精确整数范围内。hash 中的成绩保留原始精度，内部 `_uploads` 保存 UTC 微秒时间戳，API 不暴露 `_uploads`。只在生成 score 时将 Bvs 四舍五入至四位小数、时间截断到分钟，总分在求和后量化。允许 zset 对极接近的成绩给出近似排序；增量选优、补位查询和批量重建仍按原始成绩、上传时间比较。

范围限制仅作用于 zset：Time 单项最多 999999 毫秒，Bvs 单项最多 99.9999；`sumt` 最多 2999997 毫秒，`sumb` 最多 299.9997。编码前按原始值判断，超限不写入对应 zset，并移除已有条目；恢复范围后可重新入榜。超限纪录照常参与个人选优、保存至 hash 和求和，不以较差的录像替代。总榜按总值独立判断，单项超限不一定导致总榜超限。

`saolei.cache.SpeedRankingCache` 不执行排行规则，也不接收 `transform`。`read_records`、`write_record`、`write_score`、`read_rank` 只把基础读写加入调用方传入的 pipeline，不自行执行。清理和全量发布时，通过构造参数 `stats` 显式指定本榜的小榜列表；`get_record` 缓存未命中返回 `None`，缺省纪录由业务层提供。普通/NF 榜通过一个 pipeline 读取纪录，再独立判断，并通过一个 pipeline 提交变更。`plan_saolei_record_update` 按扫雷网规则重算总分和 score，只刷新变化的索引；管理员强制重建仍刷新目标大榜该用户的全部索引。

不使用 WATCH 或重试。并发更新同一用户时可能覆盖彼此的更新，后续破纪录也不保证恢复正确状态；可通过管理员单项重建或全量重建修复。分页读取允许人数、排名顺序和纪录在并发更新时短暂不一致，并跳过已缺失的纪录。不要在缓存类外直接修改这些 key。

## 更新机制

不同大榜可能采用不同的准入、选优、补位、总分和 score 编码规则，不能用一个通用的 `transform(record)` 更新管线承载所有业务。当前协调扫雷网普通/NF 榜、PB 榜和 top 榜；`_read_saolei_records`、`_write_saolei_records` 和 `plan_saolei_record_update` 属于扫雷网规则，新增其他大榜时不得直接套用其纪录结构或业务判断。

### 职责划分

- 根目录 `cache.py` 只提供共享连接和 pipeline；各大榜的缓存类提供必要的基础读写能力，不决定哪些录像可以入榜、怎样比较纪录、何时查数据库补位，也不统一规定各大榜的纪录结构、总分算法或 score 编码。
- 各大榜自行决定需要读取哪些缓存、怎样处理录像、需要写入哪些个人纪录和排序索引。Saolei.wang 的 `RULES`、缺项补齐、`sumt` / `sumb` 求和等规则属于该大榜，不应由共享缓存层执行。
- 调用入口负责协调一次事件涉及的各大榜，共享读取和写入 pipeline。PB 先从用户 hash 得到旧录像 id，再用额外一个 pipeline 读取相关旧 member 的 score；这是依赖前一次读取结果的第二阶段，不逐项往返 Redis。
- 扫雷网 hash 保存原始个人纪录，zset 只用于近似排序。PB 小榜没有成绩 hash，允许从整数 score 恢复原始毫秒用时，日常选优直接比较 score；这是 PB 的明确例外。

### 处理流程

每次更新按“共同读取、独立判断、共同写入”执行：

1. **共同读取**：各大榜根据本次操作声明所需的缓存读取，将命令加入同一个读取 pipeline。统一执行后，将结果交给对应大榜。
2. **独立判断**：各大榜使用读取结果和录像数据，自行完成准入、选优、补位、总分重算以及 score 编码，确定需要新增、修改或删除的缓存项。需要数据库查询时，由该大榜的业务逻辑决定，不强制所有大榜采用相同查询策略。
3. **共同写入**：各大榜将确定的 hash 和 zset 变更加入同一个写入 pipeline，最后统一执行一次。普通更新只写入需要刷新的项；强制修复时，由目标大榜决定需要重写的索引范围。

PB 写入前通过 `read_previous_ranks` 读取变化 member 的旧排名；共同写入完成后，由 `refresh_changed_ranks` 读取新排名、合并变动范围，再通过 `refresh_ranks` 批量更新区间内的用户 hash 和人数 hash。rank 刷新是单独的读写阶段，不与前面的个人纪录写入组成一个原子操作。

top 在共同读取时增加一次 HMGET。共同写入后，对本批次均值或成员资格变化的小榜去重，读取各榜前二十个 score 并批量更新锚点；明细录像替换但均值不变时不刷新 zset 或锚点。其补位查询独立于扫雷网和 PB，不强行合并不同规则。

读取 pipeline 和写入 pipeline 是两个独立执行阶段，中间的业务判断不在 Redis 事务内。写入阶段保留事务 pipeline，不使用 WATCH 或重试，也不保证读取到写入之间不会发生并发更新。数据库事务产生的事件仍在 `transaction.on_commit` 后处理，Redis 写入不参与数据库回滚。

### 更新错误日志

这是整个 `speedranking` app 的统一规则，适用于 Saolei.wang 榜、PB 榜及未来新增大榜：排行榜更新发生错误时，必须记录错误日志，不能静默忽略。更新入口使用 `utils.log_update_errors` 记录堆栈和业务上下文，当前通过项目根 logger 写入 `logs/root.log`。

- 覆盖单录像、批量录像更新，以及管理员修复、管理命令重建；PB 后续 rank 刷新出错也属于更新错误。
- 日志包含异常堆栈和定位所需的上下文，例如大榜、小榜、操作类型、用户 id、录像 id 或当前批次。只记录该操作实际拥有的信息，不为补充日志额外查询数据库或 Redis。
- 在能提供业务上下文的更新入口或执行阶段记录，避免同一异常沿调用链重复记日志。
- 记录日志不等于吞掉异常，也不改变调用方原有的失败传播、事务或中断规则。不因这条要求新增自动重试、锁或回滚机制。

### 按操作区分

单个录像与录像集合、增加与减少应分别考虑，不强制通过包装集合或统一增减接口复用同一个业务管线。各大榜可按以下场景采用不同实现：

| 操作 | 大榜自行负责的判断 |
| --- | --- |
| 单个录像加入或改善 | 判断该录像的资格，与受影响的缓存纪录比较，决定是否替换及更新关联总分。 |
| 单个录像失效、变差或删除 | 判断其是否保持现有纪录；只对需要补位的项查询剩余录像，并决定替换或清除。 |
| 录像集合加入 | 根据本榜规则在数据库或内存中分桶取最优，再与已有纪录合并；不要求逐条调用单录像逻辑。 |
| 录像集合失效或移除 | 确定受影响的用户和纪录，再按本榜规则批量补位或清除；不要求逐条调用单录像逻辑。 |

录像修改可能同时涉及旧分类移除和新分类加入，由各大榜处理。大批量操作可以分段，每段仍按上述三个阶段协调各榜的读写。Saolei.wang 的管理员 `sumt` / `sumb` 重建仍只使用缓存中的组成项，不回源数据库。

### 简单补位复用

单录像失效、变差或删除，以及录像集合移除时，先根据缓存中的录像 id 收集必须补位的 `(ranking_name, player_id, stat)`，不立即查询数据库。需求用集合去重，再交给 `resolve_saolei_backfills` 处理。

同一用户、同一指标的普通/NF 榜都需要补位时，先查询普通榜最佳录像：

- 如果它满足 `right_ce == 0`，两榜共用该候选，无需再次查询 NF。
- 如果普通榜没有候选，NF 也没有候选，无需再次查询。
- 如果普通榜最佳录像不属于 NF，再单独查询 NF。仅 NF 需要补位时，只查询 NF。

这些复用条件只适用于当前两榜相同的排序和包含关系，不能推断任意大榜之间的关系。本次未引入 Subquery / UNION 等复杂查询合并；批量加入仍在数据库按各榜规则独立分桶选优。各榜完成补位后，再统一准备并提交 Redis 写入。管理员单项重建直接按目标榜查询，不依赖普通/NF 复用。

新增其他大榜时，继续保留各自独立的单录像、录像集合、加入和移除实现；只共享基础缓存 pipeline，不为统一函数签名引入额外抽象。

## 写入与补位

- `post_save(VideoModel)` 复用 `videomanager` 的 `_old_values`，只对有关字段变化执行刷新；在事务提交后重新读取持久化的录像及派生 bvs。
- 成绩提高时直接比较缓存；变差或失去资格时，仅查询由该录像保持的单项并补位。
- 玩家或等级、模式、NF、审核状态、比赛隐藏状态改变时，旧分类补位，新分类尝试加入。
- `post_delete(VideoModel)` 仅补位被删除录像保持的单项；没有任何剩余纪录时删除玩家的 hash 和 zset 项。
- `add_videos_to_speed_ranks(queryset)` 支持标识绑定、比赛批量公开，在数据库按玩家和指标分桶取最佳。按玩家 id 分段以限制内存。
- `remove_videos_from_speed_ranks(queryset)` 用于批量失效后的补位，传入按录像 id 固定的 queryset，不要继续使用依赖旧状态的过滤条件。录像仍须存在；实际删除由删除信号处理。
- Redis 更新在 `transaction.on_commit` 执行，不参与数据库回滚。Redis 故障可能导致数据库已提交但榜单未同步，修复后应重建。全量重建期间暂停上传、审核、绑定、删除、比赛公开等写入。

## 重建与接口

### 扫雷网规则

```bash
python manage.py rebuild_speed_ranks
python manage.py rebuild_speed_ranks --ranking-name saolei_nf --batch-size 1000
```

命令构建独立临时榜，单个大榜构建成功后原子替换正式榜，最后清理临时 key。构建失败不会先清空正式榜；进程被强制终止时可能遗留 `speedranking:rebuild:*` 临时 key。两个大榜依次发布，并非同时切换。

从旧的“微秒时间戳 + 玩家 id” member 格式升级时，暂停相关读写，使用新代码执行 `python manage.py rebuild_speed_ranks`，完成两个大榜的重建后再恢复服务；不能混用新旧格式。无需修改录像数据库。

- `GET /api/speedranking/rank?ranking_name=saolei&stat=sumt&start=0&end=20`：左闭右开、最多 100 条，返回 `count` 和 `players`。
- `GET /api/speedranking/player/{player_id}`：一次返回 `saolei` 和 `saolei_nf`，每组包含原始纪录和八项 `ranks`。通过一次 Redis 事务 pipeline 读取 hash 和各 zset 的 ZRANK，排名从 1 开始，未入榜为 `null`（包括超限但仍保留原始成绩的情况）。无纪录也返回完整字段，单项为空、总项使用缺省值。
- `POST /api/speedranking/admin/rebuild_record`：仅管理员可用，表单参数为 `player_id`、`ranking_name`、`stat`，返回该用户的大榜纪录。普通/NF 两榜的八个小榜均可独立手动刷新：`bt`、`bb`、`it`、`ib`、`et`、`eb`、`sumt`、`sumb`。从数据库重建指定单项，并重算总成绩；选择 `sumt` 或 `sumb` 时仅使用缓存中的三个组成项求和，不回源数据库、不重建组成项。没有合格录像则清除对应单项。即使成绩未变也重新写入排序索引，其他单项不回源重建。管理员页面的“排行纪录重建” tab 提供此操作。该操作不锁定录像或缓存，仍可能受并发写入影响。
- 前端扫雷网规则榜使用 `BaseTable` 和 `ElPagination`，通过 `start/end` 请求后端分页，并提供 NF checkbox；个人纪录使用原生 HTML table 和 Element Plus 配色，按初级、中级、高级、总和四列及 Time、Bvs、Time (NF)、Bvs (NF) 四行显示 `score(rank)`。

测试：`python manage.py test speedranking common.tests.VideoUploadRankingIntegrationTest identifier tournament --keepdb --noinput`。

## PB 榜

### 规则与缓存

- 接收 `b/i/e`、STD、OFFICIAL、非隐藏比赛录像；按 `(level, bv)` 分桶取最小用时。普通榜包含 NF，NF 榜另要求 `right_ce == 0`。
- 小榜 zset：`speedranking:pb:std:{level}:{bv}`、`speedranking:pb:nf:{level}:{bv}`。member 是 `user_id:video_id`；替换时用用户 hash 中的旧录像 id 删除旧 member。
- 用户 hash：`speedranking:pb:player:{user_id}`。field 为 `std:{level}:{bv}` 或 `nf:{level}:{bv}`，JSON 保存 `timems`、`video_id`、`rank`。用户全部 PB 只需一次 HGETALL，不遍历约 500 个小榜。
- 人数 hash：`speedranking:pb:counts`。field 同用户 hash，value 为对应小榜的条目数量；空榜保存 0，未出现的 field 也视为 0。`get_counts()` 通过一次 HGETALL 读取各榜人数。rank 刷新时在现有读取 pipeline 中用 ZCARD 取人数，再与 rank 一起批量写入；单条、批量、管理员修复和全量重建共用此链路。已有缓存需运行 `rebuild_pb_ranks` 补齐所有人数。
- score 为 `timems * 2**26 + upload_minutes`，分钟从 Unix UTC epoch 起算；用时保留整数毫秒，上传时间截断到分钟。接受模型的完整用时范围，零用时可以入榜。分钟数必须在 `[0, 2**26)`，最后可编码的分钟是 UTC `2097-08-05 09:03`。
- 正常增量只在新 score 更小时替换，同分保留现有录像；数据库补位和重建按原始 `timems`、完整 `upload_time`、id 选优。
- `pb.services.prepare_add_videos` 用窗口函数分别查询普通/NF 的 `(player, level, bv)` 桶内最优录像，再与缓存比较；`prepare_remove_videos` 只补位由移除录像保持的纪录。目前 PB 不复用普通/NF 的选优查询，扫雷网的补位复用策略不能当作 PB 已实现的功能。
- 增量更新只刷新变化的排名范围：替换取旧、新排名之间的闭区间；加入或移除从变动位置刷新至榜尾。同批小榜变动合并范围，人数不变时只刷新旧、新位置覆盖的区间，人数改变时刷新至榜尾。用 pipeline 查询变动 member 的旧、新排名，再读取区间、批量写入从 1 开始的 rank，不逐一查询区间内其他用户的 ZRANK。全量重建仍逐小榜刷新整榜，不引入后台任务。
- 不使用 WATCH、锁或并发重试。个人纪录写入至 rank 刷新之间可能短暂不一致，失败会记录日志并抛出异常；管理员修复还会扫描目标小榜并删除该用户可能残留的多余 member。

个人纪录写入时 `rank` 暂为 `null`，随后区间刷新填入排名，因此刷新失败可能留下缺失或过期的 rank。人数 hash 用于整体选择界面，小榜分页的 `count` 则直接读取该 zset 的 ZCARD；并发写入期间两者允许短暂不一致。

### 重建与接口

```bash
python manage.py rebuild_pb_ranks --batch-size 100
```

首次部署或缓存丢失后执行此命令，API 不自动回源。命令只清理 PB 命名空间（包括旧人数 hash），按玩家 id 分段写入普通/NF 纪录，最后逐小榜生成 rank 并同步人数 hash；每批输出累计用户数和最后玩家 id，完成时提示 rank 和人数已刷新。重建后未出现的小榜按 0 人处理。

执行前暂停 PB 相关读取以及上传、审核、绑定、删除、比赛公开等写入。此命令直接清空后重建，不构建临时榜，也不原子切换；失败可能留下部分数据，应排除错误后重新运行。数据库不受影响，扫雷网缓存不会被清空。`rebuild_speed_ranks` 仍仅重建扫雷网规则，不能替代 PB 重建。

本地快照初始化 `python -m dangerzone.init_local_test` 在导入数据后依次调用 `rebuild_speed_ranks` 和 `rebuild_pb_ranks`，无需再手动建立 PB 缓存。

- `GET /api/speedranking/pb/rank?level=b&bv=4&nf=false&start=0&end=20`：左闭右开，最多 100 条，返回人数及用户、录像 id、原始毫秒用时和分钟级 `upload_time`；上传时间直接由 score 解码，不查数据库或用户 hash。区间排名由调用方按起点计算。
- `GET /api/speedranking/pb/counts`：一次读取人数 hash，返回普通/NF 各小榜人数的 field 到整数映射；未出现的 field 由调用方按 0 处理。
- `GET /api/speedranking/pb/player/{player_id}`：单次返回该用户全部普通/NF PB 的等级、3BV、毫秒用时、录像 id 和缓存 rank。缓存未命中返回空列表。
- `POST /api/speedranking/pb/admin/rebuild_record`：管理员表单请求，参数 `player_id`、`level`、`bv`、`nf`。数据库重建这一项、清理残留 member 并刷新该小榜 rank；无候选返回 `null`。

当前管理员“排行纪录重建”页面仅接入扫雷网规则；PB 已提供上述修复 API，但尚无对应前端入口。

### 前端

入口为 `/ranking/speed/pb`，组件职责如下：

| 文件（相对 `front_end/src`） | 职责 |
| --- | --- |
| `views/RankingView/PBRanking.vue` | 获取榜单和人数、选择 NF/等级/3BV、分页、加载状态、错误反馈和手动刷新 |
| `views/RankingView/PBBVButton.vue` | 按等级展示人数网格，接收选择与人数 props，发出 `select(bv)`；不请求数据 |
| `views/RankingView/PBRankingTable.vue` | 根据 `rows`、`level`、`bv`、`first`、`loading` 渲染 BaseTable；不请求数据 |
| `services/pbRankingService.ts` | API 请求、3BV 选择范围、Time/Bvs/Stnb 及分钟级上传时间格式化 |

页面使用 ElPagination，提供 20、50、100 条每页，将页码转换为 `start/end` 后请求后端分页。NF、等级、3BV 或每页条数变化时回到第一页；过期请求的响应不会覆盖新状态。人数在页面加载和手动刷新时获取，切换筛选复用人数缓存；人数与榜单请求的错误分别显示，刷新按钮可同时重试。

表格依次显示排名、PlayerName、Time、Bvs、Stnb、分钟级上传时间。排名为 `first + index + 1`；点击行或键盘触发预览对应录像，玩家名保留独立跳转。Bvs/Stnb 由当前等级、3BV 和原始用时计算，零用时显示 `Infinity`；上传时间从 API 的 UTC 时间转换为本地时区后显示到分钟。

NF checkbox 与三个等级按钮控制分榜。等级按钮的交互式 tooltip 用按钮显示人数，左侧为 `bv // 10`，固定在滚动区域外的顶部为 `bv % 10`（0 到 9）；空榜按钮禁用，整行为空则隐藏，范围外留空。前端选择范围为初级 1–54、中级 1–216、高级 1–381；后端只验证 `bv > 0`，没有用这些上限限制录像准入。NF、等级、3BV、页码和每页条数均写入子路由 query。

个人 PB 界面已实现，职责见 [UserView README](../../../front_end/src/views/UserView/README.md)。扫雷网规则依赖 PB 的优化仍留待后续。

### 测试

- `pb/tests.py`：编码、准入与 NF、选优与补位、分类迁移、变动排名区间、人数缓存、批量与全量重建、管理员修复和日志。
- `pbRankingService.test.ts`：请求参数及 Time/Bvs/Stnb、上传时间格式化。
- `PBRanking.cy.ts`：页面请求、人数传递、分页、NF/3BV 联动及失败重试，不重复子组件的渲染细节。
- `PBBVButton.cy.ts`：人数网格、范围、禁用与隐藏、选择事件和 props 更新。
- `PBRankingTable.cy.ts`：表格显示、props 更新、录像预览、空表和加载状态；三级别派生公式与零用时规则由 `pbRankingService.test.ts` 覆盖。
- `SpeedRanking.cy.ts`：直接访问 PB 子路由、大榜切换、浏览器返回、默认跳转，以及统一刷新、加载图标和颜色 prop 传递。

后端命令在 `back_end/saolei` 运行；前端命令在 `front_end` 运行。Cypress 由开发者运行，不能以静态检查通过代替组件运行验证。

```bash
python manage.py test speedranking.pb --keepdb --noinput
npx vitest run src/services/pbRankingService.test.ts
npx cypress run --component --spec "src/views/RankingView/PBRanking.cy.ts,src/views/RankingView/PBBVButton.cy.ts,src/views/RankingView/PBRankingTable.cy.ts,src/views/RankingView/SpeedRanking.cy.ts"
```

## top 榜

原始十八个小榜，以及普通/NF 的六个单级别、两个综合软实力和 LSF 共九个派生榜共享用户明细。面向玩家的动机、公式、等价 et 和定阶称号统一见 [top 榜与 LSF 榜指南](../../../vitepress_doc/zh/guide/top-lsf.md)；本文维护实现和运维约定。

### 规则与缓存

- 接收 `b/i/e`、STD、OFFICIAL、非隐藏比赛录像。三个指标统一要求 BV 至少为 10/30/100；普通榜包含 NF，NF 额外要求 `right_ce == 0`。
- 每用户每项独立取最佳五条，可以来自相同 BV，按成绩从好到差保存真实录像 id 与原始值。缺项按 Time 999999 毫秒、Bvs/iqg 0 补齐，始终除以五；不缓存虚假补位录像。
- 缺省值只用于缺项，不替代用时超过 999999 毫秒的真实合格录像。每项独立选优，不能从 Time 的五条录像或均值反推其他指标。
- `t/b/s` 分别表示 Time、Bvs、Stnb，但 `s` 的选优、均值、缓存及 API 全程使用 `iqg`，仅网页展示时按 b36/i162/e435 转为 Stnb。零用时沿用模型的 Bvs/iqg 0。
- 单条同分不挑选特定录像，用户均值同分不细分，也不以上传时间排序。不依赖 PB 缓存，以免丢失同 BV 的其他入选录像。
- 明细 hash 为 `speedranking:top:records`，field 是用户 id；JSON 中 `std:bt`、`nf:es` 等项只包含最多五条 `{value, video_id}` 的 `videos`。均值按需计算，不存 `mean`，不构造缺项录像。
- 十八个 zset 为 `speedranking:top:{std|nf}:{level}{stat}`，member 直接为用户 id。score 分别为 `1 / Time均值`、`Bvs均值`、`iqg均值 ** (1 / 1.7)`，统一降序，不打包上传时间或量化成绩。
- 有任意合格 top 录像的用户参与全部 27 项排行；缺项写默认 score，失去最后一条合格录像时全部移除。hash 仍仅保存真实成绩。
- 锚点 hash 为 `speedranking:top:anchors`，field 同十八项标识，JSON 为 `{value, sample_count}`。每项是该榜前二十名用户均值的平均值；测试不足二十人按实际人数平均，空榜计算为 0，未写入的字段由前端按 0 展示。

单录像新增或改善只与缓存的五条比较；已入选五条的录像变差、失效或删除时，仅对受影响用户和指标从数据库补位。批量加入用窗口函数按用户、等级、指标、NF 取最多五条，再合并缓存；批量移除只补位受影响项。明细改变但均值不变仅写 hash。各榜共用读取与写入 pipeline，zset 写完后有界重算变动小榜的锚点，每项最多二十个 score。

### 重建与接口

首次部署、旧 score 编码升级或缓存丢失后执行 `rebuild_top_ranks`，普通查询不自动重建。命令在临时命名空间构建明细、十八个原始索引、实时锚点、九个派生索引和发布元数据，再原子发布三十个正式 key；旧榜可继续读取。参数、部署注意事项和本地初始化入口统一见 [管理命令文档](../../../vitepress_doc/zh/guide/development/management-commands.md#rebuild-top-ranks)。

- `GET /api/speedranking/top/rank?level=e&stat=t&nf=false&start=0&end=20`：左闭右开，最多一百条，返回 `count` 和 `players`；每个用户为 `{player_id, records}`，`records` 是该用户的完整 hash JSON，小榜参数只决定排序，不筛选返回字段。
- `GET /api/speedranking/top/player/{player_id}`：一次 HGET 原样返回用户完整纪录，每项保留真实 `videos`；不附加逐项 rank，不构造 `record_count`，没有纪录返回 `{}`。缺项和均值展示由前端处理。
- `GET /api/speedranking/top/soft/rank?ranking=lsf&start=0&end=20`：按九个派生项之一分页，只返回 `count` 和完整用户 `players`。`ranking` 接受 `lsf`、`std:b/i/e/sum`、`nf:b/i/e/sum`；不附带锚点，不从 zset score 返回展示数值。
- `GET /api/common/loginauto`：网页启动时一次返回 `{user, top_anchors}`，访客的 user 为 null，完整实时锚点仍返回。前端保存到非持久化 Pinia 的 `store.topAnchors`，后续页面与刷新成绩操作不再请求锚点，重载网页才更新。允许展示计算与排序使用不同版本；后台发布快照仍用于内部局部更新。
- `GET /api/speedranking/top/anchors`：一次 HGETALL 原样返回锚点 hash 中所有字段，限流 20/s，不补造缺项。每次即时读取 Redis，不叠加 HTTP/进程结果缓存，不重新计算锚点。
- `POST /api/speedranking/top/admin/rebuild_record`：仅管理员，表单为 `player_id`、`level`、`stat`、`nf`。从数据库强制修复该用户的一个小榜、排序索引和对应锚点；未变化也重写，其他项不重建。目前仅提供 API，未新增管理员网页控件。

排行及用户纪录接口限流 5/s，全部查询只读 Redis，不回源数据库；`s` 的响应值均为 iqg。所有 API 不裁剪 hash 字段或五条明细；管理员修复也返回 `{player_id, records}`，其中 `records` 是完整用户纪录。更新沿用 on_commit、上下文错误日志及异常传播；不使用 WATCH 或自动重试。普通并发写仍允许短暂不同步，显式修复与重建是恢复路径。

### 软实力与刷新准入

- 软实力公式及权重见上述玩家指南；后端常量集中在 `top/utils.py` 的 `SOFT_WEIGHTS`、`LEVEL_WEIGHTS`，纯计算由 `soft_values` 提供，前端在 `topRankingService.ts` 实现对应计算。Stnb 比值中的等级系数抵消，后端使用 iqg 即可。
- 九个派生 zset 为 `speedranking:top:soft:{std|nf}:{b|i|e|sum}` 和 `speedranking:top:soft:lsf`。发布元数据 STRING 为 `speedranking:top:soft:published`，不另存用户派生分数 hash。锚点非正数时对应项贡献为 0；异常零 Time 均值按 999999 兜底，前后端一致。
- 锚点先对前二十个 score 逆变换，再求原始均值的算术平均；不能直接平均 Time 的倒数或 iqg 的幂。派生榜将十八个 score 按 `指标权重 / 变换后的锚点` 加权合并为六个级别榜，再生成两个综合榜和 LSF，共九次 `ZUNIONSTORE`。成员集合一致，不需额外补位集合；暂不按变动锚点裁剪重建范围。
- 普通变动先按已发布锚点局部更新受影响用户，再更新实时锚点；数值改变时通过 `soft_refresh_requested` 入队。后台任务发现其他同路径 READY 任务时跳过自身，否则按最新锚点用九次 ZUNIONSTORE 构建临时榜并统一发布，失败记录日志并保留旧版。只修复软实力可运行 `rebuild_top_soft_ranks`。
- `utils.ranking_lock` 用专用本地 SQLite 文件上的 `filelock.ReadWriteLock` 协调同机进程。默认文件为 `BASE_DIR/runtime/top-lock.sqlite3`，可用 `TOP_RANKING_LOCK_PATH` 指定稳定位置；所有 Web、worker、调度器与命令进程必须共享此文件且可写，运行中禁止删除或替换。
- HTTP 中间件在相关业务首次修改数据库之前获取非阻塞共享锁，范围覆盖视图事务及 on_commit 缓存回调；后台业务 service 和逐条录像刷新阻塞获取共享锁。全量 top/软实力重建持独占锁，等待在途写入，默认最多等待 30 秒（`TOP_RANKING_REFRESH_WAIT`），超时记录错误。查询不取锁。
- TODO（Unix 写优先限制）：SQLite 可能让同进程的新连接复用已有 SHARED 锁，绕过其他进程的 PENDING 写锁；因此排队期间不保证拒绝所有新请求，持续并发可能延长独占等待甚至触发超时，但独占期间的互斥不受影响。当前暂不修改业务锁；保留原同进程读锁场景，在 Linux 下标记为 `expectedFailure`，Windows 仍正常执行。将来修复后移除标记。见 [SQLite 对同进程锁复用的讨论](https://sqlite.org/forum/forumpost/fb0662276c?t=c)。
- 入口覆盖上传、修改、标识绑定/解绑、第三方录像导入、比赛公开、top 管理员修复、Django Admin 写入及测试管理入口；定时删除和受支持的管理命令也遵守准入。新增业务写入口及自定义 shell 脚本必须在最外层事务前使用 `ranking_access`，不能只依赖保存后信号。
- 锁实例按业务操作创建，同一操作的嵌套 service 复用已有准入，不在预加载/fork 前创建活动连接。禁止从共享操作内升级为独占重建；异常退出通过上下文释放锁，进程终止由底层机制清理持有状态，不能通过删除锁文件解锁。多机部署需重新设计协调方案。
- 被拒绝的 HTTP 请求返回 `503`、`Retry-After: 1` 和 `object=top/category=refreshing`，记录 WARNING；前端说明原因、提示等待重试并保留上传文件。后台操作等待、恢复有 INFO 日志，不套用 HTTP 拒绝策略。锁只隔离全量重建，不锁住整个 Redis/MySQL，也不提供跨库回滚或跨机器协调。

### 前端与验证

`LSFRanking.vue` 为竞速默认页面，使用 Pinia 的首次启动锚点和完整 top5 明细计算成绩。LSF 列只显示原始数值，八个普通/NF 软实力列显示定阶；英文表格将 Greater/Lesser 简写为 G./L.，原生 title 显示完整称号和三位小数的等价 et。普通项目参考普通 et 锚点，NF 项目参考 NF et 锚点，缺少对应的有效锚点时显示 `--`。点击表头仍切换原有后端排序，保留分页与刷新，不提供 NF 开关，不新增锚点请求。

定阶由 `topRankingService.ts` 的纯工具计算：设软实力为 `S`，基准 `C` 对单项/单级别/综合分别为 1/100/4000，对应 et 锚点 `A` 以秒计，令 `x = S / (C * A)`。固定节点为 `[0, 1/100, 1/60, 1/55, 1/50, 1/45, 1/40, 1/35, 1/30, 1/25]`，预计算区间宽度倒数，按软实力线性插值得到 `p`，阶数显示 `10*p`。边界归入更强区间，最后区间允许超过十阶；先选区间再格式化。节点固定，每项为 O(1)，不新增后端索引。原始 top 页面及个人表格从真实 top5 重建均值，雷达 Stnb 轴使用齐次化后的软实力。

`TopRanking.vue` 显示九列小榜均值，按三个等级分组，点击 Time/Bvs/Stnb 表头切换排序小榜，保留 NF 与后端分页。右侧固定增加五列录像明细，与均值区用双线分隔；九个指标表头各有一个 `pi-eye` 按钮，始终只有一个点亮，控制这五列的内容，切换明细不发请求。排序和明细默认均为 `et`，切换排序时明细同步为该小榜，单独切换明细不改变排序，分页及 NF 切换保留明细选择。真实成绩可预览录像，缺项显示缺省值且无链接。

个人主页默认 top 和独立 PB tab 的职责、双雷达及五条明细表、请求生命周期和组件测试统一见 [UserView README](../../../front_end/src/views/UserView/README.md)。

后端 `top/tests.py` 覆盖准入、前五选优、分类迁移与补位、批量及原子重建、锚点、局部/全量软实力和任务合并；`top/test_lock.py` 覆盖跨进程共享、独占等待、HTTP 拒绝、后台恢复及进程终止后的准入。`common/test_loginauto.py` 覆盖启动响应，前端工具测试覆盖均值、单位、归一化、等价 et 及定阶边界；组件测试覆盖展示、交互、请求生命周期及上传拒绝后的重试。

Cypress 与真实规模性能仍需开发者验收：除运行下列测试外，应记录用户规模、全量刷新耗时、写入拒绝窗口及 Redis 延迟，再决定是否需要更细粒度的重建。

```powershell
# back_end/saolei
.\.venv\Scripts\python.exe manage.py test speedranking common.test_loginauto --keepdb --noinput
# front_end
npx.cmd vitest run src/services/topRankingService.test.ts src/services/pbRankingService.test.ts
npx.cmd cypress run --component --browser chrome --headless --spec "src/views/RankingView/LSFRanking.cy.ts,src/views/RankingView/TopRanking.cy.ts,src/views/RankingView/SpeedRanking.cy.ts,src/views/UserView/TopSummary.cy.ts,src/components/VideoUpload/App.cy.ts"
```
