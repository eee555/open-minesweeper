# 竞速排行榜重构计划
原竞速排行榜位于`back_end\saolei\msuser\models.py`以及相关缓存。

## 统一实现约束

以下约束适用于所有大榜，包括后续新增的大榜：

- 缓存层“大榜”的划分主要以前端展示页面/视图为依据，每个页面最好使用单个 `hset`。是否共享 `hset` 取决于展示组织，而不是 NF 等筛选条件本身。
- 每个大榜的缓存结构为一个 `hset` 加多个 `zset`；每个小榜对应一个 `zset`，同一大榜的小榜共用该大榜的 `hset`。
- `hset` 以用户 ID 为 field，保存该用户在大榜中的纪录数据。成绩等数据保持原始取值，不因 `zset` 的排序编码而转换；纪录比较和数据展示使用 `hset` 中的数据。
- `zset` 仅负责排序，用于查询用户排名以及指定排名段的用户。排序编码放在 score 中，不需要从 score 恢复纪录数据用于比较。
- `zset` 的 member 尽量直接使用用户 ID。如果确有必要拼接其他字段，必须先与我讨论并确认具体策略，不得自行决定拼接字段或编码方式。

## 第一步：彻底移除原功能

代码清理已完成；数据库迁移和 Redis 清理命令需要在部署时执行。`msuser` app 保留标识列表、录像计数、上传额度及管理员额度接口。
移除原排行榜后端相关的所有内容，包括
- App msuser和纪录相关的功能。如果移除的某个功能曾被其他app调用，则在本文件尾部添加一章描述该功能的作用，并在调用处添加注释说明。
- 删除`msuser.signals`中的排行逻辑时，也需要在本文件尾部记录已有的纪录补位逻辑，供新排行榜恢复。
- 前端的竞速排行榜`front_end\src\views\RankingView\SpeedRanking.vue`
- 前端首页的新闻部分`front_end\src\views\HomeView\NewsQueue.vue`（注意前面删后端的时候有没有漏掉这个功能相关的后端）
- 前端`front_end\src\components\PlayerName.vue`的弹窗相关功能
- 前端个人主页的纪录页相关功能`front_end\src\views\UserView\UserRecordView\ClassicalCard.vue`

停用旧排行榜及新闻的写入逻辑后，在`back_end/saolei`执行缓存清理命令：
```bash
python manage.py delete_legacy_speedranking_cache --dry-run
python manage.py delete_legacy_speedranking_cache
```
命令位于`common`，不依赖待移除的排行代码。只清理旧的`player_{stat}_{mode}_{用户ID}`、`player_{stat}_{mode}_ids`及`news_queue`，保留自定义pluck排行、比赛缓存和录像队列。使用`SCAN`遍历，分批`UNLINK`删除，可重复执行。

## 第二步：修改模式规则
移除专门的NF模式。NF模式现在是和其他模式独立的一个维度。如果一个VideoModel的`right_ce`为0，则属于NF模式。在VideoModel相关的api中增加`right_ce`返回字段。

为VideoModel添加一个布尔字段`is_lucky`，默认为False。（未来管理员可以设置，当前暂时不支持）

代码已完成：parser 保留原模式；删除前后端 NF 模式枚举；录像计数、比赛计分和 pluck 准入不再依赖模式 `12`。`VideoAbstract.isNF` 按 `right_ce === 0` 判断，未知值不视为 NF。`UserMS` 不再保存级别、模式及 NF 分类计数；数量与文件空间均提供非比赛（`*_total`）、比赛（`*_tournament`）及数据库生成的合计（`*_all`）三个口径，空间按 `file_size` 求和。补录逻辑及等待全量重算的统计行为保持不变，不保存历史统计分类；大小修改只查询该录像当前比赛归属并更新差额，允许偏差由全量重算修正。上传额度仍独立维护并使用非比赛数量。

录像列表、个人录像、比赛录像及录像队列返回 `right_ce`；pluck 缓存 detail 也保存此字段。录像查询迁至 `/api/video/query`，新增独立的 `nf` 筛选参数，返回普通 JSON 对象；个人录像导出迁至 `/api/video/query_by_id`。前端查询和导出已同步调用新入口。

迁移由 `makemigrations videomanager --name nf_dimension_and_is_lucky` 生成。这里只新增 `is_lucky=False`，不会根据 mode 或 pluck 自动设为 True，也不开放管理员修改入口。

部署时暂停上传及后台写入，先执行 `makemigrations` / `migrate`，再在 `manage.py shell` 中转换旧模式并更新已有录像队列（不添加已经移除的队列项）：

```python
from videomanager.models import VideoModel
from videomanager.cache import cache, freeze_cache, newest_cache, review_cache

VideoModel.objects.filter(mode='12').update(mode='00')
for queue in (newest_cache, freeze_cache, review_cache):
    videos = VideoModel.objects.filter(pk__in=cache.hkeys(queue.key)).select_related('player', 'video')
    queue.update_bulk(videos)
```

随后执行以下命令，再恢复写入：

```bash
python manage.py refresh_video_counts
python manage.py rebuild_custom_pluck_cache
```

这些数据转换和缓存重建未在本地业务库执行。旧 NF 转成 STD 后，NF 是否成立仍取决于已保存的 `right_ce`，不能把旧 NF 统一强制设为零。比赛的标准成绩仍接纳这些录像，不需要改变已有比赛成绩。

## 第三步：创建新的排行榜

已实现 `speedranking`，代码入口与缓存约定见 [speedranking/README.md](../speedranking/README.md)。录像保存、删除、标识绑定/解绑和比赛公开均已接入；前端已恢复竞速榜与个人纪录，新闻和姓名弹窗不恢复。

本轮确认：同成绩以 `upload_time` 升序作为 tie-breaker，不再比较 timems；总分同分以组成总分的纪录中最晚上传时间作为组合达成时间。头像和签名资格改用新标准榜 `et < 200000`，包含高级 3BV >= 100 的门槛。

部署时暂停录像相关写入，执行 `python manage.py rebuild_speed_ranks` 初始化两个大榜，然后恢复写入。前端读取只访问 Redis，不会自动从数据库恢复旧纪录。本步骤不新增数据库模型或迁移。

创建新的App：`speedranking`。新的排行榜完全由Redis管理。排行榜分为若干大榜（未来可能继续添加），每个大榜包括若干小榜；缓存结构及职责遵循前述统一实现约束。

对于每个排行榜，需要管理命令重建全榜。后续的更新，通过VideoModel的信号进行增量更新：对于满足条件的录像，数据和排行榜中的数据对比，如果变好了则更新。在第一步删除原排行榜时，删除了一些其他app需要的功能并留下了笔记，通过笔记恢复这些功能。

### 大榜：Saolei.wang规则
`Saolei.wang` 只是竞速排行中的一种规则，不占用通用的 `Speed*` 命名。前端 `SpeedRanking.vue` 仅负责大榜选择；该规则的表格、个人纪录和请求分别位于 `SaoleiRanking.vue`、`SaoleiCard.vue`、`saoleiRankingService.ts`，专属类型使用 `SaoleiRankingName`、`SaoleiStat`、`SaoleiRecord`。当前默认展示该榜不代表其他大榜必须沿用它的指标或结构。后续新增大榜使用独立规则名；现有 API 的 `saolei`、`saolei_nf` 标识和 Redis key 不变。

小榜：
- `bt`：初级time。越小越好。筛选条件：`mode == MS_TextChoices.Mode.STD`，`level == MS_TextChoices.Level.BEGINNER`，`bv >= 2`。
- `it`：中级time。越小越好。筛选条件：`mode == MS_TextChoices.Mode.STD`，`level == MS_TextChoices.Level.INTERMEDIATE`，`bv >= 30`。
- `et`：高级time。越小越好。筛选条件：`mode == MS_TextChoices.Mode.STD`，`level == MS_TextChoices.Level.EXPERT`，`bv >= 100`。
- `sumt = bt + it + et`：总Time。越小越好。缺少的单级成绩按999.999秒（999999毫秒）计入。
- `bb`：初级bvs，越大越好。筛选条件：`mode == MS_TextChoices.Mode.STD`，`level == MS_TextChoices.Level.BEGINNER`，`bv >= 4`。
- `ib`：中级bvs，越大越好。筛选条件同`it`
- `eb`：高级bvs，越大越好。筛选条件同`et`
- `sumb = bb + ib + eb`：总bvs。越大越好。缺少的单级成绩按0计入。

hset需要保存：八个小榜的成绩，以及每个`bt`，`it`，`et`，`bb`，`ib`，`eb`成绩对应的VideoModel id。

前端：带分页的表格，第一列是排名，第二列为`PlayerName`，后面的顺序是`bt`, `bb`, `it`, `ib`, `et`, `eb`, `sumt`, `sumb`

NF榜：以上所有内容，添加一个筛选条件`right_ce == 0`（`rce`为`right_ce`的简写）。NF榜和普通榜都属于“扫雷网规则”；当前对应两个独立展示页面/视图，因此缓存各自使用一个 `hset` 和对应小榜的多个 `zset`。这不是 NF 必须独立存储的通用约束；同一页面展示的普通与 NF 纪录可以共享一个 `hset`。

## 旧功能恢复笔记

以下保留第一步移除时的历史说明。第三步已恢复其中的纪录补位、标识批处理、比赛公开和排行读取，资格已确定使用新榜 `et`；旧新闻仍不恢复。

### 纪录补位

删除前的`msuser.signals`包含以下逻辑，新排行榜需要恢复：
- `refresh_personal_record_on_video_save`：同一排行分类内成绩变差时，仅重建由该录像保持且受影响的纪录。
- `rebuild_records_for_category`：录像的玩家、级别、模式或参赛资格变化，导致排行分类改变时，检查旧分类中由该录像保持的纪录并重建；录像符合新分类条件时，尝试加入新分类。
- `refresh_personal_record_on_video_delete`：删除录像后，仅重建由该录像保持的纪录，从剩余符合条件的录像中补位。

新榜补位后需要同步对应的成绩、录像id、总成绩和zset；无可用录像时，总成绩按前述缺省值计算。

### 标识绑定与解绑

- 原 `identifier.services.bind_identifier` 在批量改为 OFFICIAL 后，调用 `update_personal_records_from_videos(userms, queryset)`：对同一用户按等级、模式、指标取最佳录像，再与原纪录比较，更新纪录及 Redis。新榜需要支持 queryset 批量加入，不依赖逐条 save 信号。
- 原 `unbind_identifier` 在更新状态前按录像 id 找出受影响的纪录字段，更新后调用 `rebuild_personal_records` 补位。新榜也需只重建当前由这些录像保持的成绩。
- 两个 service 调用处均已留 TODO；录像状态、队列、上传额度、pluck 排行仍正常更新。

### 比赛录像公开

- 原 `tournament.services.reveal_videos_for_tournament` 在批量设置 `ongoing_tournament=False` 后调用 `update_personal_records_from_video_queryset`，按玩家分组吸收成绩，更新各自个人纪录及 Redis。调用处已留 TODO。
- `tournament.api.reveal_video` 的用户主动公开通过单条 save 触发旧纪录信号；新榜需覆盖此路径，且公开不能移除比赛关联或改变录像计数。
- 创建时带比赛标记的录像不得进入普通竞速榜；公开后需按新榜条件重新判断资格。

### 用户资料资格

- `userprofile.services.try_update_user_signature` 和头像上传接口原先要求 `UserMS.e_timems_std < 200000`。
- 删除旧字段后，暂由 `has_sub200_expert_video` 查询玩家是否有高级、STD（包括盲扫）、OFFICIAL、非隐藏比赛且低于 200 秒的录像，维持原资格规则。
- 第三步已确定并改用新标准榜 `et < 200000`，包含高级 3BV >= 100 的门槛，不再查询录像库。

### 全量重建与读取入口

- 已删除 `videomanager.view_utils.update_personal_record_stock` 和 `refresh_stnb` 管理命令。旧命令重解析官方录像、重建个人纪录/Redis并清空新闻；现由 `refresh_videos` 对所有录像实例逐条调用 `refresh_video`，通过差异保存触发信号，不使用批量更新。新榜仍需提供独立的全榜重建命令。
- 已删除 `/msuser/player_rank/`、`/api/msuser/records`、`/api/msuser/records_abstract` 和 `/video/news_queue/`。新榜需要新的排行和个人纪录读取 API。
- 已删除旧 `RankingField` / `RankingValue`、指标比较工具及 `UserMS` 的120个纪录值/id字段。迁移由 `makemigrations msuser --name remove_classical_records` 生成，原历史迁移保留。
- 前端移除竞速榜路由/标签、首页新闻和经典纪录卡片；排行榜默认进入密度榜。玩家名字直接链接个人主页，`interactive=false` 仍保留普通文本行为。
- 旧纪录/新闻专属测试已删除；标识状态、录像计数、上传额度、比赛公开和 pluck 联动测试继续保留。新榜实施时恢复对应的排行断言。

### 新闻与缓存

- 旧 UserMS 保存信号捕获纪录值/id，并向 `news_queue` 推送包含旧值的新闻，每次写入后保留最新200条；该功能和首页展示已移除。
- 仓库忽略迁移文件；部署时需先运行 `python manage.py makemigrations`，再运行 `python manage.py migrate`（`start.sh` 已包含两步）。停用旧写入后运行 `python manage.py delete_legacy_speedranking_cache` 清理旧 Redis key。
- 旧新闻是否以新形式恢复，需另行确定；新的竞速榜不应隐式依赖旧新闻机制。
