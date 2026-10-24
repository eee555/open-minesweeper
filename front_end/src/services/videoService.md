# 录像信息缓存与字段结构对照

录像的稳定文件数据由 `videoInfoService.ts` 按 ID 获取，使用现有 `idb` 数据库持久化。查询接口负责当前结果集合、权限、排序、分页和网站动态字段；前端批量补全解析字段，再构造页面使用的 `VideoAbstract`。录像二进制不缓存。

`VideoPreviewLink` 默认在文字前显示软件图标，只从调用方或录像解析缓存取得 `software`；缓存未命中时通过 `fetchVideoInfo` 复用批量解析接口，不请求 `abstractbulk`。悬停或聚焦时才创建 Tippy 中的 `VideoAbstractDisplay`，由摘要组件按 ID 从解析缓存补全其余统计字段。上传时间、状态等动态字段仅在调用方已提供时显示。已有完整摘要的调用方传入 `video`，无需额外请求；`showSoftware`、`showTooltip` 可关闭重复的图标或提示框。摘要兼容部分字段、空数据和无效日期，未知统计显示 `—`。

## 字段组

下表使用以下字段组，避免重复列出相同的长字段列表：

| 名称 | 完整字段 |
| --- | --- |
| `M`：网站元信息 | `id, player, upload_time, state, ongoing_tournament` |
| `P`：持久化的稳定字段 | `id, software, level, mode, end_time, file_size, timems, bv, left, right, double, left_ce, right_ce, double_ce, path, pluck, flag, op, isl, cell0, cell1, cell2, cell3, cell4, cell5, cell6, cell7, cell8, identifier, tournament_identifier` |
| `B`：原通用摘要 | `id, player, software, level, mode, state, cl, ce, right_ce, timems, bv, upload_time, end_time` |
| `U`：原个人页摘要 | `id, upload_time, level, mode, timems, bv, state, software, cl, ce, right_ce, file_size, end_time, ongoing_tournament, path, pluck` |
| `Q`：原数据库列表 | `id, upload_time, player__id, player__realname, timems, bv, bvs, state, level, mode, software, flag, op, isl, path, pluck, left, right, double, left_ce, right_ce, double_ce, cell0, cell1, cell2, cell3, cell4, cell5, cell6, cell7, cell8, left_s, right_s, double_s, left_ces, right_ces, double_ces, flag_s, ioe, thrp, cl_s, ce_s, video__id, video__identifier, video__tournament_identifier, stnb` |

`identifier` 和 `tournament_identifier` 来自 `ExpandVideoModel`，批量接口中使用扁平字段名。`tournament_identifier` 是文件中的比赛标识，不是网站比赛 ID。

`cl, ce, bvs, iqg, left_s, right_s, double_s, cl_s, left_ces, right_ces, double_ces, ce_s, flag_s, ioe, thrp, corr, stnb` 由 `videoDisplayFields` 从基础字段恢复，不在 IndexedDB 中重复保存。`bv` 或点击字段为 `null` 时保留未知语义；自定义难度不套用标准难度 STNB 常数。

## 接口结构对照

以下均为 JSON 响应，实际路由没有结尾斜杠。仅包含录像列表的响应直接返回数组；有总数、排名等额外信息的响应保留对象。接口不携带缓存版本；录像缓存版本随前端代码维护。

| 接口 | 修改前 | 修改后 |
| --- | --- | --- |
| `GET /api/video/staticdetailbatch?ids=1,2` | 不存在 | `[(P + ongoing_tournament)]`；最多 100 个 ID，不保证响应顺序，缺失或无权访问的 ID 不返回 |
| `GET /api/video/abstractbulk?first=1&count=10000` | 不存在 | `[{id, player, upload_time, state}]`；按连续 ID 范围查询公开录像的当前网站元信息，`count` 上限为 10000，不返回 `ongoing_tournament` |
| `GET /video/get_software/?id=...` | `{msg: software}` | 已移除；软件字段通过 `fetchVideoInfo` 和录像缓存获取 |
| `GET /api/userprofile/videolist?user_id=...` | `[U]` | `[M]` |
| `GET /api/video/query` | `{count, videos: [Q]}` | `{count, videos: [{id, upload_time, state, ongoing_tournament, player__id, player__realname}]}`；后端排序、筛选与分页能力保持 |
| 最新队列 | `GET /video/newest_queue/` → `{[id]: JSON字符串}`，字符串字段见 Redis 对照表 | `GET /api/video/newest_queue` → `[M]`；直接读取 Redis Hash 快照，将 field 映射为 `id`，`player_id`、`time` 映射为 `player`、`upload_time`，`ongoing_tournament` 为 `false`（队列只写入公开录像），不查询数据库 |
| 从最新队列移除 | `POST /video/newest_queue/remove/`，表单 `{id}` | `POST /api/video/newest_queue/remove`，同样表单 `{id}`，成功返回 204；仍仅管理员可用 |
| `GET /api/video/review_queue` | `[B]` | `[M]`；继续从数据库查询待审录像 |
| `GET /api/common/video/{id}/analyzer-info` | `{video: VideoModel全部字段, expanded_video: ExpandVideoModel全部字段, tournament_ids, filename, rankings}` | `{video: M, tournament_ids, filename, rankings}`；前端补全稳定字段，比赛关联和名次仍每次获取 |
| `GET /api/customranking/pluck` | `{count, players: [{player_id, video_id, mode, pluck, timems, bv, upload_time}]}` | `{count, players: [{player_id, video_id, pluck, upload_time}]}`；`mode, timems, bv` 通过录像缓存补全 |
| `GET /api/video/infobulk`、`GET /api/video/detailbulk` | 连续 ID 区间的自包含数组，`count` 上限分别为 5000、1000 | 响应字段保持原结构；`count` 上限分别调整为 2000、500，继续用于公开数据导出 |
| `GET /api/video/query_by_id` | 用户录像的自包含导出数组 | 保持原结构，现有 JSON/CSV 导出无需改变 |
| 比赛录像列表、管理员原始模型详情、历史补录响应 | 既有 Schema | 保持原结构及独立查看规则；本轮不放宽比赛数据的访问权限 |

批量解析接口 `staticdetailbatch` 允许读取公开录像；`ongoing_tournament=True` 的录像仅向录像本人返回，staff 身份不提供额外读取权限。原分析器和录像文件接口仍保留各自既有的访问规则。公共 CORS 路径补入 `staticdetailbatch` 与 `abstractbulk`，以便站外客户端补全录像数据。

`abstractbulk`、`infobulk`、`detailbulk` 均使用 `first`、`count` 参数，查询范围为 `[first, first + count)`，只返回公开录像，登录本人或管理员时也不包含未公开录像。`first` 至少为 1，`count` 限制在 1 至各接口上限之间，超出上限时截断；不存在或未公开的 ID 不返回，也不会向后补足条数。`staticdetailbatch` 使用 `ids` 参数，上限为 100 个 ID。

数据库查询和待审队列按约定保留原有 staff 可见范围。它们返回他人未公开录像时，新缓存接口不会补全这些条目，当前页面会报加载失败；这两处列表的兼容处理暂未调整。

在线快照工具 `dangerzone/download_public_data.py` 接收录像数组；列表缺少 `timems` 等解析字段时，分批补全解析字段并保存为原有自包含快照；旧的完整列表直接保存。断点续传和 `--skip-details` 仍可使用。

## 浏览器存储与配置对照

| 项目 | 修改前 | 修改后 |
| --- | --- | --- |
| 数据库 `saolei-cache` | 版本 1；`meta, user-info` | 版本 2；增加 `video-info`，保留用户表 |
| `video-info` 行 | 不存在 | `{scope, id, data: P}`，主键 `[scope, id]`，`scope` 索引用于清理当前用户的未公开缓存 |
| 缓存作用域 | 不存在 | 公开录像：`public`；未公开录像：`user:{登录用户ID}`，仅用户开启后持久化 |
| 版本元信息 | `meta['storeVersions']` 记录用户表版本 | 同一记录增加 `video-info` 表版本；前端定义变化时清空整个录像表，再记录新版本，不逐行迁移 |
| `service-config` | 仅用户缓存配置 | 增加 `videoInfoBatchSize=100`、`videoInfoBatchDelay=250`、`videoInfoCacheUnpublished=false`；原配置保留 |

用户可调批量大小为 1～100，延迟为 250～60000ms；服务层会再次限制非法配置。每次只读取需要的 ID，缓存检查按小块处理，避免扫描全部录像表。批量请求在途去重，并依次发送；网络和存储错误不会留下永久失败的 Promise。

未公开录像默认实时获取。开启缓存后按当前登录用户保存；关闭后删除当前用户作用域的记录，旧在途响应不能重新落库。登录会话切换后旧任务不返回给新用户。动态元信息不持久化到录像表。

网络补全在后台异步进行，当前页面顶部显示非模态的条目进度，不遮挡内容、不锁定滚动或焦点，用户可以继续操作和切换页面。依赖完整录像字段的列表仍等待补全后展示，不会提前返回不完整数据。多个调用方复用同一录像请求，进度按作用域和 ID 去重；全部命中时不显示提示。页面切换后不显示旧页面任务，后台下载继续并写入缓存；网络失败经调用方原有错误提示反馈。

## Redis 字段对照

| key / 数据结构 | 修改前 | 修改后 |
| --- | --- | --- |
| `newest_queue` Hash，field 为录像 ID | JSON `{state, tournament, software, time, player_id, identifier, level, mode, timems, bv, cl, ce, right_ce}` | JSON `{state, time, player_id}`；接口直接读取缓存元信息；每天 01:08 按上传时间保留最新 1000 条，时间相同时保留 ID 较大的录像；允许暂时超过上限，不再按 7 天期限清理 |
| `freeze_queue` Hash | 与最新队列相同的完整 JSON，持续写入 | 停止维护；原读取函数没有有效路由，部署命令删除旧 key |
| `review_queue` Hash | 与最新队列相同的完整 JSON，持续写入 | 停止维护；有效待审接口一直直接查询数据库，删除已无路由的旧审核函数及其读取依赖 |
| `customranking:pluck:{level}:detail` Hash | JSON `{video_id, mode, timems, bv, upload_time}` | JSON `{video_id, timems, upload_time}` |
| pluck 排序 zset、扫雷榜、PB、Thrp、top 等计算缓存 | 各模块现有分值、精确成绩、录像 ID、上传时间和名次 | 保持原结构与计算精度，避免为增量更新引入数据库回源 |

## 更新与部署

前后端接口需要一起部署。修改稳定字段名称、类型或解析计算含义时，递增前端 `database.ts` 中 `CACHE_STORE_DEFINITIONS['video-info'].version`；需要重算历史数据时先准备数据。用户加载新前端后，`getDatabase()` 会比较本地保存的表版本并整体删除旧录像缓存，再按需下载。普通前端更新无需递增缓存版本；IndexedDB 结构变化才递增 `CACHE_DB_VERSION`。

Redis 存量压缩的执行步骤统一见[管理命令文档](../../../vitepress_doc/zh/guide/development/management-commands.md)。
