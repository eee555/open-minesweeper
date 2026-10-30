---
title: 缓存结构 - 开源扫雷网
description: 开源扫雷网Redis/Django缓存结构详解，包括录像队列、玩家排行、比赛缓存等数据结构和读写流向。
---

# 缓存结构

本文记录项目当前使用的 Redis / Django cache 结构，以及缓存与数据库、API 之间的读写流向。数据库字段结构以各 app 的 `models.py` 为准，这里只记录缓存中实际保存的数据结构。

扫雷网首批迁移由 [sync_saolei_api](./management-commands.md#sync-saolei-api) 串行执行，没有专用 Redis 进度或任务缓存。目录与 `AccountSaolei.video_sync_cursor` 同数据库事务提交，`video_update_time` 标记完整目录扫描完成；游标不等待文件导入，未完成文件通过本地来源表补导。旧账号成绩、人气、三级录像数量及任务指针字段随迁移删除，不再维护对应历史值。创建本站录像和同主重复文件的更早上传时间仍经过既有保存信号及排行缓存更新，不清理本站录像缓存来重建来源目录。

`SaoleiApiVideo.file_url` 将详情返回的文件地址以客户端规范化后缀 `YYYY/MM/DD/filename` 保存到数据库，供文件导入使用，没有单独的 URL 缓存。目录列表不含此字段，目录刷新保留已存后缀；详情明确返回无文件时置空，下载失败仍保留后缀供重试时刷新。

录像解析字段现在由前端 IndexedDB 按 ID 缓存。普通查询返回 ID 和网站动态字段，再批量补全；字段定义变化时随前端更新递增 `CACHE_STORE_DEFINITIONS['video-info'].version`，加载新前端后清空整张录像表，接口无需携带版本。接口和 Redis 改动前后字段表见仓库 `front_end/src/services/videoService.md`。部署后运行 [compact_video_cache](./management-commands.md#compact-video-cache) 压缩存量载荷。

旧竞速排行榜及新闻的读写逻辑已移除，可运行`python manage.py delete_legacy_speedranking_cache`清理旧个人纪录hash、排行zset及`news_queue`。支持`--dry-run`预览，具体范围见[管理命令文档](./management-commands.md#delete-legacy-speedranking-cache)。

`UserMS` 的录像数量及文件空间保存在数据库，不按级别、模式或 NF 分类，也不涉及 Redis 清理。创建时按 `ongoing_tournament` 归类；全量重算时，`ongoing_tournament=True` 或关联到任意比赛的录像属于比赛口径，包括已公开、已结束比赛的录像。同一录像关联多个比赛只计算一次。空间按 `VideoModel.file_size` 求和，单位为字节。

| 口径 | 数量字段 | 文件空间字段 |
| --- | --- | --- |
| 非比赛录像 | `video_num_total` | `video_size_total` |
| 比赛录像 | `video_num_tournament` | `video_size_tournament` |
| 全部录像 | `video_num_all` | `video_size_all` |

两个 `*_all` 字段均为持久化 `GeneratedField`，由数据库计算比赛与非比赛口径之和，不直接写入。上传额度 `video_num_limit` 独立维护，额度检查继续使用非比赛数量 `video_num_total`。

删除 `UserProfile` 时，`userprofile.signals.delete_user_ms` 在同一删除事务内按真实 `userms_id` 删除关联 `UserMS`，其 `Identifier` 按外键级联删除。实例和 QuerySet 删除均生效；从 `UserMS` 发起的级联沿用原删除收集器，避免重复清理。历史上没有关联用户的 `UserMS` 可用 [cleanup_orphan_userms](./management-commands.md#cleanup-orphan-userms) 分批清理；该命令不写 Redis，已关联用户的记录保留。

纪念账号没有专用缓存，旧身份及 Redis 残留由站长在服务器上使用已有工具清理，尤其不能遗漏普通录像删除后保留的 `newest_queue` 快照。公开姓名与头像沿用现有更新周期，不在网站启动时强制失效；`is_memorial` 行缓存列缺省为 false，其他浏览器可在正常更新前暂时显示旧姓名。建档和补录像规则见 `back_end/saolei/userprofile/README.md`。

用户数据库页 `/database/users` 通过 `GET /api/userprofile/query` 直接读库，不使用用户资料 IndexedDB 缓存：录像统计变化不会更新 `UserProfile.date_updated`。查询集中在 `common.services`，每个非空页执行计数、用户及统计、当前页已验证关联 ID 三次查询。`AccountLinkQueue(platform, identifier)` 联合索引用于平台 ID 精确查询，用户外键索引用于分页后的批量读取。接口用法见仓库 `back_end/saolei/userprofile/README.md`。

补录逻辑及延迟重算行为保持不变：比赛关联变化不立即调整统计。删除、文件大小及玩家归属变更按该录像当前的比赛标记和关联归类，允许与原先计入的口径存在偏差，统一由 [refresh_video_counts](./management-commands.md#refresh-video-counts) 全量重算修复；不保存历史统计分类字段。迁移后需先运行重算命令补齐历史统计。

保存信号中数量、文件空间及需要提升的上传额度合并到一次 `UserMS UPDATE`；归属变化通过一条 `CASE WHEN UPDATE` 同时处理两位玩家。后台压缩修改 `file_size` 时，只查询该录像是否属于比赛，再按大小差额更新对应口径，不重算该用户的全部录像。所有统计字段使用固定字段名与 `if/else` 分支，不动态拼接。

旧 World 监控页面及其 CPU/网络 IO 采集已移除，不再读写历史采样；旧 `/monitor/io_cpus/` 和 `/monitor/capacity/` 不恢复。部署并停止旧采集进程后，可按固定名称清理 `saolei_website` Redis DB 中的五个遗留 key，无需遍历其他 key：

```bash
redis-cli -n 0 DEL io_s_old io_r_old io_s_spds io_r_spds cpus
```

扫雷网旧站爬取及旧来源列表、统计查询已关闭，账号关联保留。首批仅由管理命令使用新来源结构同步目录和导入文件；旧爬取任务不会访问外站或写入业务数据。具体入口见仓库 `back_end/saolei/accountlink/README.md`。

## 服务器监控快照

`GET /api/monitor/summary` 一次返回 `{videosummary, tasksummary, diskusage, memoryusage}`，前端服务器页面只请求一次，再分发给各张卡片。APScheduler 的 `refresh_monitor_snapshot` 启动时立即执行，此后每 5 分钟复用 `monitor/services.py` 的采集函数，发布监控 JSON。开发环境默认写入 `BASE_DIR/runtime/monitor.json`；生产环境写入与 `STATIC_ROOT` 同级的 `runtime/monitor.json`，与源码目录分离。生产 Nginx 直接提供该文件；本地 Ninja 接口也只读文件，不在请求中采集。文件不存在时返回 503。

前三项沿用原有统计字段，增加 UTC `sampled_at`；`memoryusage` 包含 `memory` 和 `redis`，各自保留采样时间。首次采集失败的统计项为 `null`；内存块仍使用下文的 `unavailable` 结构。后续某项采集失败时保留其上次成功结果及原时间，其他项正常更新。内存两块也独立保留旧样本。读取采样时间可以判断调度停止或持续失败导致的数据过期。

发布前按 `monitor/schema.py` 校验，在同目录完整写入临时文件，再用 `os.replace` 原子替换，失败不破坏正式文件。Nginx 对精确路径设置 JSON 类型、`Cache-Control: no-cache` 和 `open_file_cache off`，避免替换后继续使用旧文件描述符；请求限流由 Nginx 执行。目录需可遍历，文件以 0644 权限发布，确保 Nginx worker 可读。部署路径变化时同步修改 `default.conf`；可通过 `MONITOR_SNAPSHOT_PATH` 覆盖采样与本地读取路径。

采样与 Nginx 的 `alias` 必须指向同一文件。若只更新代码而未同步实际 Nginx 配置，或两者使用了不同路径，即使采样日志显示发布成功，请求仍可能返回 503。`start.sh` 会部署 `default.conf` 并重载 Nginx；手动部署时需同步配置，执行 `nginx -t` 检查通过后再重载。

旧的四个独立监控接口和 Redis 结果缓存已移除，旧结果 key 会按原 300 秒 TTL 自动过期。管理员任务页使用独立的 `GET /api/common/tasks/summary`，仅管理员可访问，每次直接查询数据库，不读取快照；任务删除、重启和清理不触发整份监控数据重算。首次部署或本地调试可执行 [refresh_monitor_snapshot](./management-commands.md#refresh-monitor-snapshot) 手动生成文件，再重启 APScheduler、检查并重载 Nginx。

### 内存采集口径

每块包含 `status`、UTC `sampled_at`、固定错误码 `reason`、非负整数 `total_bytes` 和固定分类 `groups`。进程按 uWSGI（含 master/workers）、本项目 APScheduler、Redis、MySQL、db_worker、其他进程聚合。Linux 统一采集 PSS，其他平台统一 RSS；RSS 可能重复计算共享页。合计仅覆盖进程驻留内存，主机总内存/可用内存单独放在 `memory.host`，不包含在图中合计内。本机 Redis 服务进程按进程名或可执行文件名汇总，Redis/MySQL 连接配置为远程或已知容器隔离时，进程块返回范围不足。

Redis 分类只读取业务代码直接确定的 DB 0 key，不执行 `SCAN`、`scan_iter`、`KEYS` 或排行榜成员枚举：

| 分类 | key 来源 |
| --- | --- |
| PB 榜 | `PBRankingCache.counts_key`；固定 hash 的 `HKEYS` 经校验后构造小榜 key；从 `UserProfile` 主键顺序每批最多 1,000 个 ID 构造用户 hash key。元数据缺失不发现 key、不触发重建。 |
| 其他排行榜 | `SpeedRankingCache(name, stats=RANK_STATS).keys`、`TopRankingCache().keys`、`ThrpRankingCache().keys`、`NFIOERankingCache().keys`、`MiniGameRankingCache().keys`、四种自定义 pluck 配置的 rank/detail key、比赛用户榜 key 和积分时间 key；当前共 144 个 key。 |
| 最新录像 | `newest_cache.key`（`newest_queue`）。 |
| 其他 | `INFO memory.used_memory` 减去前三类；包含其他业务、会话、同实例 DB 1 通用缓存、孤立/历史/临时 key 和 Redis 开销，不枚举 DB 1。 |

所有已知 key 去重后以 `pipeline(transaction=False)` 每批最多 100 个执行 `MEMORY USAGE ... SAMPLES 5`，不存在的 key 为 0。该结果为估算，`redis.estimated=true`、`redis.samples=5`；总量为实例 `used_memory`，不同于进程 RSS/PSS。分类合计大于实例总量时不发布分布。两块共享 5 秒协作式采集预算，另限制最多 5,000 个进程和 50,000 个 key；阻塞中的 socket/查询仍受各自超时控制，因此 5 秒不是硬中断时限。

进程采集中退出的 PID 跳过；存活进程权限不足时整块不可用，并通过 `memory.unreadable_processes` 记录数量，不能当作零。不可用块的时间、总量和分类为 `null`，另一块可独立成功；已有成功样本时发布器保留旧值和时间。采集器日志仅记录安全原因、耗时和数量，不记录 PID、命令行、key 名或业务值。上线需以实际 APScheduler 用户验证 Linux `/proc` 权限，并抽查采集耗时、Redis 计量结果及文件更新时间。HTTP 请求失败时前端继续显示当前页面的上次成功结果。

## 总览

### 小游戏 `minigame`

每个白名单榜单使用 `minigame:rank:v1:{ranking_key}` ZSET（玩家 ID → 原始整数毫秒）、`minigame:detail:v1:{ranking_key}` Hash（玩家 ID → `{score, achieved_at}` JSON）及 `minigame:ready:v1:{ranking_key}` String（`1` 表示整榜初始化完成）。23 榜共 69 个固定键，均无 TTL，计入服务器内存统计的其他排行榜。

分类请求一次返回左键或多指 9 列、标双 2 列或漏雷 3 列，以组内任一列排序。已初始化时用两轮 pipeline 读取标记、人数、页内玩家和全部列明细，不查询成绩表。空榜也保存初始化标记；单条上传不设置标记。未初始化时从数据库加载完整榜单；Redis 故障时整次请求批量回源数据库。

小游戏页排行榜抽屉仅读取所选配置的首页 20 人及登录用户位置，复用上述键，不初始化同组其他榜单或增加缓存键。含个人位置的响应禁止共享缓存，接口详情见后端 README。

成绩创建或严格改善后通过 `on_commit` 写 ZSET 和 Hash，删除后移除成员并保留初始化标记。接受并发和重建的偶发覆盖；运行 `manage.py rebuild_minigame_ranks [--ranking-key key]` 可恢复缓存，不改数据库成绩。完整接口与取舍见 `back_end/saolei/minigame/README.md`。

最佳成绩对应的 v1 JSON 回放压缩为 7z，仅保存在 `MiniGameBestScore.replay_archive` BinaryField，不进入 Redis。缓存重建和排行榜数据库回源用 `defer('replay_archive')` 排除二进制回放字段。

### 用户姓名与隐私

前端 `user-info` 的姓名列直接兼容隐藏标记 `hidden`，无需调整数据库版本或检查间隔。资料保存成功后，`invalidateUserInfo(id)` 删除该用户的本地缓存并通知已挂载的 `PlayerName` 重新读取公开姓名；失效前发出的响应不会写回旧值。缓存删除失败时不影响已保存的设置，跳过该用户的旧缓存并重置检查时间以便重试。资格及隐藏状态变更更新 `date_updated`，其他浏览器仍由现有 `infoupdated` 流程按正常周期更新。Redis 排行继续只引用用户 ID。缓存流程见仓库 `front_end/src/services/userService.md`；授权、展示与迁移约定见 `back_end/saolei/userprofile/README.md`。

独立的本地初始化脚本 `dangerzone/init_local_test.py` 会清空本地 `saolei_website` Redis 数据库（包含会话），然后根据导入的公开录像重建竞速榜（扫雷网普通/NF、PB 普通/NF、top 十八项及锚点）、效率 Thrp 榜、pluck 纪录缓存和录像状态队列。在 `back_end/saolei` 目录使用 `python -m dangerzone.init_local_test` 启动。只允许本地测试配置，并拒绝存在 `.production` 标记的环境；不注册 `import_public_data` 管理命令。详情及数据缺失限制见[本地公开数据快照](./management-commands.md#本地公开数据快照)。

### 标识管理

数据库标识页对普通用户仅查询 `safe=True` 的标识；管理员可查询全部标识并取得 `safe` 字段。管理员通过 `POST /api/identifier/safe` 设置安全状态，通过 `POST /api/identifier/bind` 设置归属用户，`id=0` 表示解绑并保留标识记录。已绑定的标识必须先解绑，才能设为不安全。

绑定和解绑复用 `identifier.services`，同步更新用户标识列表、相关录像审核状态、最新录像队列和排行榜。原管理员添加、删除/解绑、过审接口已由上述两个 Ninja API 替代；普通用户管理本人标识的入口保持不变。

### 新竞速榜 `speedranking`

扫雷网规则使用 `speedranking:{ranking_name}:records` hash 保存个人纪录，使用 `speedranking:{ranking_name}:{stat}` zset 保存以玩家 id 为 member 的排序索引，由 `speedranking.saolei.cache.SpeedRankingCache` 管理。PB 是一般约定的例外：每个 `(普通/NF, level, bv)` 一个 zset，每个用户一个包含用时、录像 id 和 rank 的 hash，由 `speedranking.pb.cache.PBRankingCache` 管理。

共享缓存层提供连接及 pipeline，扫雷网、PB 和 top 的业务分别位于对应子目录。一次更新或每个批处理段共同读取用户纪录，独立判断后共同写入；PB 查询旧 score、刷新变化小榜的 rank，以及 top 更新锚点是依赖前序结果的后续批量阶段。必须补位的单项按各榜规则查询。

top 由 `speedranking.top.cache.TopRankingCache` 管理，包含用户前五明细、十八个原始索引、九个软实力/LSF 索引及锚点。缓存结构、后台发布与单机准入、前端启动快照约定统一见 `back_end/saolei/speedranking/README.md`。部署升级需要执行 [top 重建命令](./management-commands.md#rebuild-top-ranks)，不能混用旧 score 编码。

排序编码、精度与数值范围、纪录更新及缓存升级约定统一维护在仓库的 `back_end/saolei/speedranking/README.md`，此处不再重复。重建命令用法见[管理命令](./management-commands.md#rebuild-speed-ranks)。

PB 只读接口不自动回源，初始化和修复用法见 [PB 重建命令](./management-commands.md#rebuild-pb-ranks)。前端 PB 排行页面已实现，分页上传时间直接由 zset score 解码，不增加查询或 hash 字段。

PB 另使用 `speedranking:pb:counts` hash 汇总各小榜人数，可通过 `GET /api/speedranking/pb/counts` 一次读取，随 rank 刷新同步更新；前端用于筛选网格的人数显示。已有缓存通过 PB 重建命令补齐。具体 field 及空榜约定见 app README。

管理员页面的“排行纪录重建” tab 可按大榜、小榜和用户 ID 修复单项缓存，对应接口为 `POST /api/speedranking/admin/rebuild_record`；具体更新范围和并发约定见上述 README。

### 效率榜 `effranking`

Thrp 使用一个个人纪录 hash 和五个排序 zset，NF IOE 独立使用一个 hash 和四个 zset，见下方数据结构表。编码、选优和事务边界统一见 `back_end/saolei/effranking/README.md`；首次部署及缓存丢失后执行指定大榜的 [rebuild_eff_ranks](./management-commands.md#rebuild-eff-ranks)，查询不自动回源。

```dot
digraph cache {
    graph [
        layout=neato,
        model=subset,
        overlap=prism,
        splines=true,
        outputorder=edgesfirst,
        bgcolor="transparent",
        start=7
    ];

    node [
        shape=box,
        style="rounded,filled",
        fillcolor="${#f8fafc|#1f2937}",
        color="${#94a3b8|#64748b}",
        fontcolor="${#0f172a|#e5e7eb}",
        fontsize=12
    ];

    edge [
        color="${#64748b|#94a3b8}",
        fontcolor="${#475569|#cbd5e1}",
        fontsize=9,
        arrowsize=0.7
    ];

    // Degree 较大的节点增大最小尺寸，减少 neato 布局中高密度连边贴边重叠。

    subgraph api_nodes {
        get_account_links [label="/api/accountlink/{user_id}"];
        create_account_link [label="/api/accountlink/create/"];
        delete_link [label="/accountlink/delete/"];
        update_link [label="/accountlink/update/"];
        view_saolei_get_import_list [label="/accountlink/saolei/videolist/get/"];
        view_saolei_get_import_summary [label="/accountlink/saolei/videoimport/stat/"];
        task_summary [label="/api/common/tasks/summary (staff)"];
        monitor_summary [label="/api/monitor/summary (Nginx)"];
        video_upload [label="/common/uploadvideo/"];
        pluck_rank [label="/api/customranking/pluck"];
        minigame_score [label="POST /api/minigame/{ranking_key}/score"];
        minigame_rank [label="/api/minigame/{game}/rank\n/api/minigame/{game}/player/{id}"];
        player_pluck_records [label="/api/customranking/pluck/player"]
        add_identifier [label="/identifier/add/"];
        del_identifier [label="/identifier/del/"];
        get_tournament_list [label="/api/tournament/get_list"];
        get_tournament [label="/api/tournament/get"];
        set_tournament [label="/api/tournament/set"];
        cancel_tournament [label="/api/tournament/cancel"];
        get_participant_list [label="/api/tournament/participants"];
        delete_participant [label="DELETE /api/tournament/participant/{participant_id}"];
        get_participant_videos [label="/api/tournament/get_videos/participant"];
        reveal_video [label="POST /api/tournament/video/{video_id}/reveal"];
        get_tournament_news [label="/api/tournament/get_news"];
        download_all_videos [label="/api/tournament/download"];
        download_videos_participant [label="/api/tournament/download/participant"];
        get_gsc_results [label="/api/tournament/gsc/results"];
        create_gsc_participant [label="/api/tournament/gsc/participant"];
        register_gsc_participant_identifier [label="/api/tournament/gsc/participant/identifier"];
        get_weekly_results [label="/api/tournament/weekly/results"];
        create_weekly_participant [label="/api/tournament/weekly/participant"];
        get_user_info [label="/api/userprofile/info/{user_id}"];
        get_user_info_bulk [label="/api/userprofile/infobulk"];
        get_user_info_updated [label="/api/userprofile/infoupdated"];
        get_user_identifier [label="/api/userprofile/identifier"];
        get_user_avatar [label="/api/userprofile/avatar/{user_id}"];
        get_user_videos [label="/api/userprofile/videolist"];
        update_user_profile [label="/api/userprofile/update_profile"];
        update_user_avatar [label="/api/userprofile/update_avatar"];
        user_login [label="/userprofile/login/"];
        user_retrieve [label="/userprofile/retrieve/"];
        user_register [label="/userprofile/register/"];
        check_collision [label="/userprofile/checkcollision/"];
        refresh_captcha [label="/userprofile/refresh_captcha/"];
        get_email_captcha [label="/userprofile/get_email_captcha/"];
        get_review_queue [label="/api/video/review_queue"];
        get_video_info_bulk [label="/api/video/infobulk"];
        get_video_detail_bulk [label="/api/video/detailbulk"];
        get_static_video_detail_batch [label="/api/video/staticdetailbatch"];
        get_video_abstract_bulk [label="/api/video/abstractbulk"];
        video_preview [label="/api/video/preview"];
        video_download [label="/api/video/download/{video_id}"];
        video_query [label="/api/video/query"];
        video_query_by_id [label="/api/video/query_by_id"];
        newest_queue [label="/api/video/newest_queue"];
    }

    subgraph db_nodes {
        node [shape=cylinder, fillcolor="${#e0f2fe|#0f172a}"];
        captcha_db [label="CaptchaStore"];
        task_db [label="DBTaskResult", width=2.0, height=0.8];
        accountlinkqueue_db [label="AccountLinkQueue\nplatform accounts"];
        accountlinkplatform_db [label="AccountSaolei\nAccountMinesweeperGames\nAccountBilibili\nAccountWorldOfMinesweeper\nAccountQQ", width=3.0, height=1.4];
        videosaolei_db [label="VideoSaolei"];
        custom_pluck_db [label="CustomPluckRecord"];
        minigame_db [label="MiniGameBestScore"];
        identifier_db [label="Identifier"];
        userms_db [label="UserMS", width=3, height=3, fontsize=30];
        tournament_db [label="Tournament\nGSCTournament\nWeeklyTournament", width=2.5, height=1.1];
        participant_db [label="TournamentParticipant\nGSCParticipant\nWeeklyParticipant", width=2.8, height=1.1];
        tournament_user_db [label="TournamentUser", width=2.2, height=0.8];
        userprofile_db [label="UserProfile", width=4, height=4, fontsize=40];
        email_otp_db [label="EmailVerifyRecord"]
        video_db [label="VideoModel\nExpandVideoModel", width=4, height=4, fontsize=30];
    }

    subgraph cache_nodes {
        node [shape=box, fillcolor="${#dcfce7|#14532d}"];
        pluck_rank_cache [label="customranking:pluck:{level}:rank\nzset"];
        pluck_detail_cache [label="customranking:pluck:{level}:detail\nhash"];
        minigame_cache [label="minigame:{rank|detail|ready}:v1:{ranking_key}\nzset / hash / string"];
        newest_cache [label="newest_queue\nhash"];
        tournament_cache [label="tournament:normal\nhash\nsubclass + data", width=2.6, height=1.0];
        participant_cache [label="tournament:normal:participants\nhash", width=3.2, height=0.9];
        tournament_user_rank_cache [label="tournament:user:{field}\nzset\nmember = user_id", width=3.4, height=1.0];
        tournament_user_score_time_cache [label="tournament:user:score_current:last_updated\nstring\n年度锚点：1 月 1 日 UTC", width=4.2, height=1.0];
    }

    minigame_score -> minigame_db [label="保存最佳成绩及回放 JSON"];
    minigame_db -> minigame_cache [label="on_commit 更新 / 删除；重建"];
    minigame_cache -> minigame_rank [label="分组批量读"];
    minigame_db -> minigame_rank [label="Redis 故障降级"];

    subgraph file_nodes {
        node [shape=folder, fillcolor="${#e0f2fe|#0f172a}"];
        video_files [label="video files"];
        avatar_files [label="avatar files"];
        monitor_snapshot [label="runtime/monitor.json"];
    }

    monitor_sampler [label="APScheduler refresh_monitor_snapshot\nstartup + every 5 minutes"];

    subgraph signal_nodes {
        node [
            shape=box,
            fillcolor="${#fef3c7|#713f12}",
            color="${#f59e0b|#d97706}"
        ];
        capture_video_update [label="capture_video_update"];
        refresh_state_queue_on_video_save [label="refresh_state_queue_on_video_save"];
        delete_video_expansion [label="delete_video_expansion"];
        update_video_count_on_video_save [label="update_video_count_on_video_save"];
        update_video_count_on_video_delete [label="update_video_count_on_video_delete"];
        refresh_custom_pluck_rank_on_video_save [label="refresh_custom_pluck_rank_on_video_save"];
        refresh_custom_pluck_rank_on_video_delete [label="refresh_custom_pluck_rank_on_video_delete"];
        update_custom_pluck_cache_on_record_save [label="update_custom_pluck_cache_on_record_save"];
        update_custom_pluck_cache_on_record_delete [label="update_custom_pluck_cache_on_record_delete"];
        checkin_video_before_create [label="checkin_video_before_create"];
        add_created_video_to_checked_tournaments [label="add_created_video_to_checked_tournaments"];
        update_cache_on_tournament_delete [label="update_cache_on_tournament_delete"];
        update_cache_on_tournament_save [label="update_cache_on_tournament_save"];
        update_cache_on_participant_save [label="update_cache_on_participant_save"];
        update_best_score_on_gsc_participant_save [label="update_best_score_on_gsc_participant_save", width=3.4, height=0.8];
        update_best_score_on_weekly_participant_save [label="update_best_score_on_weekly_participant_save", width=3.7, height=0.8];
        update_best_score_on_gsc_participant_delete [label="update_best_score_on_gsc_participant_delete", width=3.5, height=0.8];
        update_best_score_on_weekly_participant_delete [label="update_best_score_on_weekly_participant_delete", width=3.8, height=0.8];
        remove_participant_cache_on_delete [label="remove_participant_cache_on_delete"];
        revoke_rank_score_on_participant_delete [label="revoke_rank_score_on_participant_delete", width=3.4, height=0.8];
    }

    subgraph task_nodes {
        node [
            shape=box,
            fillcolor="${#ede9fe|#4c1d95}",
            color="${#8b5cf6|#a78bfa}"
        ];
        task_gsc_finish [label="task_gsc_finish"];
        task_gsc_refresh_best [label="task_gsc_refresh_best"];
        task_award_tournament [label="task_award_tournament"];
        task_weekly_finish [label="task_weekly_finish"];
        task_weekly_refresh_best [label="task_weekly_refresh_best"];
        refresh_tournament_score_reference [label="APScheduler\nrefresh_tournament_score_reference"];
        rebuild_tournament_current_score_cache [label="manage.py\nrebuild_tournament_current_score_cache"];
    }

    // accountlink API
    accountlinkqueue_db -> get_account_links;
    accountlinkplatform_db -> get_account_links;
    create_account_link -> accountlinkqueue_db;
    accountlinkqueue_db -> delete_link;
    delete_link -> accountlinkqueue_db;
    delete_link -> accountlinkplatform_db;
    accountlinkplatform_db -> update_link;
    update_link -> accountlinkplatform_db;
    userprofile_db -> view_saolei_get_import_list;
    accountlinkplatform_db -> view_saolei_get_import_list;
    videosaolei_db -> view_saolei_get_import_list;
    task_db -> view_saolei_get_import_list;
    accountlinkplatform_db -> view_saolei_get_import_summary;
    videosaolei_db -> view_saolei_get_import_summary;
    task_db -> view_saolei_get_import_summary;

    // monitor API
    task_db -> task_summary;
    task_db -> monitor_sampler;
    video_db -> monitor_sampler;
    userprofile_db -> monitor_sampler [label="PB user IDs"];
    newest_cache -> monitor_sampler [label="MEMORY USAGE"];
    monitor_sampler -> monitor_snapshot -> monitor_summary;

    // common API
    video_upload -> video_db [label="create after is_completed check"];
    video_upload -> video_files [label="write after is_completed check"];

    // customranking API
    pluck_rank_cache -> pluck_rank
    pluck_detail_cache -> pluck_rank
    pluck_rank_cache -> player_pluck_records
    pluck_detail_cache -> player_pluck_records

    //identifier API
    userms_db -> add_identifier;
    video_db -> add_identifier;
    add_identifier -> identifier_db;
    add_identifier -> userms_db;
    add_identifier -> custom_pluck_db;
    userms_db -> del_identifier;
    video_db -> del_identifier;
    del_identifier -> identifier_db;
    del_identifier -> userms_db;
    del_identifier -> custom_pluck_db;


    // tournament API
    tournament_db -> get_tournament_list;
    tournament_cache -> get_tournament_list;
    tournament_db -> get_tournament;
    userprofile_db -> set_tournament;
    tournament_db -> set_tournament;
    set_tournament -> tournament_db;
    userprofile_db -> cancel_tournament;
    tournament_db -> cancel_tournament;
    cancel_tournament -> tournament_db;
    tournament_db -> get_participant_list;
    participant_db -> get_participant_list;
    identifier_db -> get_participant_list;
    video_db -> get_participant_list [label="EXISTS has_videos"];
    participant_db -> delete_participant [label="read"];
    tournament_db -> delete_participant [label="host_id read (join)"];
    video_db -> delete_participant [label="any video EXISTS"];
    delete_participant -> participant_db [label="delete (parent/subclass)"];
    userprofile_db -> get_participant_videos;
    tournament_db -> get_participant_videos;
    participant_db -> get_participant_videos;
    video_db -> get_participant_videos;
    video_db -> reveal_video [label="read / lock / owner check"];
    reveal_video -> video_db [label="save ongoing_tournament=False"];
    tournament_cache -> get_tournament_news;
    tournament_db -> download_all_videos;
    video_db -> download_all_videos;
    video_files -> download_all_videos;
    tournament_db -> download_videos_participant;
    userprofile_db -> download_videos_participant;
    video_db -> download_videos_participant;
    video_files -> download_videos_participant;

    // tournament gsc API
    tournament_db -> get_gsc_results;
    participant_db -> get_gsc_results;
    identifier_db -> get_gsc_results [label="select_related"];
    video_db -> get_gsc_results [label="EXISTS has_videos"];
    tournament_db -> create_gsc_participant;
    userprofile_db -> create_gsc_participant;
    create_gsc_participant -> participant_db;
    userprofile_db -> register_gsc_participant_identifier;
    tournament_db -> register_gsc_participant_identifier;
    participant_db -> register_gsc_participant_identifier;
    identifier_db -> register_gsc_participant_identifier;
    register_gsc_participant_identifier -> identifier_db;
    register_gsc_participant_identifier -> participant_db;
    register_gsc_participant_identifier -> userms_db;
    register_gsc_participant_identifier -> video_db;

    // tournament weekly API
    tournament_db -> get_weekly_results;
    participant_db -> get_weekly_results;
    tournament_db -> create_weekly_participant;
    userprofile_db -> create_weekly_participant;
    create_weekly_participant -> participant_db;

    // userprofile API
    userprofile_db -> get_user_info;
    userprofile_db -> get_user_info_bulk;
    userprofile_db -> get_user_info_updated;
    userprofile_db -> get_user_identifier;
    userms_db -> get_user_identifier;
    userprofile_db -> get_user_avatar;
    avatar_files -> get_user_avatar;
    userprofile_db -> get_user_videos;
    video_db -> get_user_videos;
    userprofile_db -> update_user_profile;
    userms_db -> update_user_profile;
    update_user_profile -> userprofile_db;
    userprofile_db -> update_user_avatar;
    userms_db -> update_user_avatar;
    update_user_avatar -> userprofile_db;
    update_user_avatar -> avatar_files;
    captcha_db -> user_login;
    userprofile_db -> user_login;
    userms_db -> user_login;
    video_db -> user_login;
    email_otp_db -> user_retrieve;
    userms_db -> user_retrieve;
    video_db -> user_retrieve;
    userprofile_db -> user_retrieve;
    user_retrieve -> userprofile_db;
    user_retrieve -> email_otp_db;
    email_otp_db -> user_register;
    userms_db -> user_register;
    video_db -> user_register;
    userprofile_db -> user_register;
    user_register -> userprofile_db;
    user_register -> email_otp_db;
    userprofile_db -> check_collision;
    refresh_captcha -> captcha_db;
    captcha_db -> refresh_captcha;
    captcha_db -> get_email_captcha;
    get_email_captcha -> captcha_db;

    // tournament finish tasks
    task_db -> task_gsc_finish [label="status/read"];
    tournament_db -> task_gsc_finish [label="read/write"];
    participant_db -> task_gsc_finish [label="read/write/delete"];
    video_db -> task_gsc_finish [label="score: OFFICIAL only; reveal: read/write"];
    tournament_user_db -> task_gsc_finish [label="ensure_tournament_users: read"];
    task_gsc_finish -> participant_db [label="score/rank"];
    task_gsc_finish -> tournament_db [label="state write"];
    task_gsc_finish -> tournament_user_db [label="ensure_tournament_users: create missing"];
    task_gsc_finish -> newest_cache [label="restore queues"];
    task_gsc_finish -> freeze_cache [label="restore queues"];
    task_gsc_finish -> review_cache [label="restore queues"];
    task_gsc_finish -> pluck_rank_cache [label="restore pluck"];
    task_gsc_finish -> pluck_detail_cache [label="restore pluck"];
    task_gsc_finish -> task_award_tournament [label="enqueue"];
    task_gsc_finish -> task_gsc_refresh_best [label="enqueue"];

    task_db -> task_award_tournament [label="status/read"];
    tournament_db -> task_award_tournament [label="read"];
    participant_db -> task_award_tournament [label="read/write rank_score"];
    tournament_user_db -> task_award_tournament [label="read/write score"];
    task_award_tournament -> tournament_user_db [label="ensure_tournament_users / award_tournament_rank_scores"];
    task_award_tournament -> tournament_user_rank_cache [label="write score zsets"];
    tournament_user_score_time_cache -> task_award_tournament [label="read reference time"];
    tournament_user_rank_cache -> task_award_tournament [label="EXISTS only if reference missing"];
    task_award_tournament -> tournament_user_score_time_cache [label="init only when empty"];
    tournament_user_score_time_cache -> refresh_tournament_score_reference [label="read old anchor"];
    tournament_user_rank_cache -> refresh_tournament_score_reference [label="ZUNIONSTORE score_current"];
    refresh_tournament_score_reference -> tournament_user_rank_cache [label="annual rescale"];
    refresh_tournament_score_reference -> tournament_user_score_time_cache [label="set annual anchor"];
    tournament_user_db -> rebuild_tournament_current_score_cache [label="read score_current / last_updated"];
    rebuild_tournament_current_score_cache -> tournament_user_rank_cache [label="atomic rebuild score_current only"];
    rebuild_tournament_current_score_cache -> tournament_user_score_time_cache [label="set annual anchor"];

    task_db -> task_gsc_refresh_best [label="status/read"];
    tournament_db -> task_gsc_refresh_best [label="read"];
    participant_db -> task_gsc_refresh_best [label="read"];
    tournament_user_db -> task_gsc_refresh_best [label="read/write best"];
    task_gsc_refresh_best -> tournament_user_db [label="ensure_tournament_users / refresh_gsc_best_scores"];
    task_gsc_refresh_best -> tournament_user_rank_cache [label="write best zset"];

    task_db -> task_weekly_finish [label="status/read"];
    tournament_db -> task_weekly_finish [label="read/write"];
    participant_db -> task_weekly_finish [label="read/write/delete"];
    video_db -> task_weekly_finish [label="score: OFFICIAL only; reveal: read/write"];
    tournament_user_db -> task_weekly_finish [label="ensure_tournament_users: read"];
    task_weekly_finish -> participant_db [label="score/rank"];
    task_weekly_finish -> tournament_db [label="state write"];
    task_weekly_finish -> tournament_user_db [label="ensure_tournament_users: create missing"];
    task_weekly_finish -> newest_cache [label="restore queues"];
    task_weekly_finish -> freeze_cache [label="restore queues"];
    task_weekly_finish -> review_cache [label="restore queues"];
    task_weekly_finish -> pluck_rank_cache [label="restore pluck"];
    task_weekly_finish -> pluck_detail_cache [label="restore pluck"];
    task_weekly_finish -> task_award_tournament [label="enqueue"];
    task_weekly_finish -> task_weekly_refresh_best [label="enqueue"];

    task_db -> task_weekly_refresh_best [label="status/read"];
    tournament_db -> task_weekly_refresh_best [label="read"];
    participant_db -> task_weekly_refresh_best [label="read"];
    tournament_user_db -> task_weekly_refresh_best [label="read/write best"];
    task_weekly_refresh_best -> tournament_user_db [label="ensure_tournament_users / refresh_weekly_best_scores"];
    task_weekly_refresh_best -> tournament_user_rank_cache [label="write best zset"];

    // videomanager API
    video_db -> get_review_queue;
    video_db -> get_video_info_bulk;
    video_db -> get_video_detail_bulk;
    video_db -> get_static_video_detail_batch;
    video_db -> get_video_abstract_bulk;
    video_db -> video_preview;
    userprofile_db -> video_preview;
    video_files -> video_preview;
    video_db -> video_download;
    userprofile_db -> video_download;
    video_files -> video_download;
    userprofile_db -> video_query;
    video_db -> video_query;
    userprofile_db -> video_query_by_id;
    video_db -> video_query_by_id;
    newest_cache -> newest_queue;

    // videomanager signals
    video_db -> capture_video_update [label="pre_save"];
    video_db -> capture_video_update [label="read"];
    video_db -> refresh_state_queue_on_video_save [label="post_save"];
    video_db -> refresh_state_queue_on_video_save [label="O2O read"];
    userprofile_db -> refresh_state_queue_on_video_save [label="FK read"];
    refresh_state_queue_on_video_save -> newest_cache [label="write/delete"];
    video_db -> delete_video_expansion [label="post_delete"];
    delete_video_expansion -> video_db [label="delete expansion in transaction"];

    // msuser signals
    video_db -> update_video_count_on_video_save [label="post_save"];
    tournament_db -> update_video_count_on_video_save [label="membership read on size/owner change"];
    userprofile_db -> update_video_count_on_video_save [label="FK read"];
    userms_db -> update_video_count_on_video_save [label="O2O read"];
    update_video_count_on_video_save -> userms_db [label="one UPDATE: statistics + limit"];

    video_db -> update_video_count_on_video_delete [label="pre_delete"];
    tournament_db -> update_video_count_on_video_delete [label="m2m exists"];
    userprofile_db -> update_video_count_on_video_delete [label="FK read"];
    userms_db -> update_video_count_on_video_delete [label="O2O read"];
    update_video_count_on_video_delete -> userms_db [label="write"];





    // customranking signals
    video_db -> refresh_custom_pluck_rank_on_video_save [label="post_save"];
    video_db -> refresh_custom_pluck_rank_on_video_save [label="read best"];
    userprofile_db -> refresh_custom_pluck_rank_on_video_save [label="FK read"];
    custom_pluck_db -> refresh_custom_pluck_rank_on_video_save [label="read"];
    refresh_custom_pluck_rank_on_video_save -> custom_pluck_db [label="write/delete"];
    video_db -> refresh_custom_pluck_rank_on_video_delete [label="post_delete / on_commit read remaining"];
    refresh_custom_pluck_rank_on_video_delete -> custom_pluck_db [label="on_commit backfill/write/delete"];
    refresh_custom_pluck_rank_on_video_delete -> pluck_rank_cache [label="on_commit write/delete"];
    refresh_custom_pluck_rank_on_video_delete -> pluck_detail_cache [label="on_commit write/delete"];

    custom_pluck_db -> update_custom_pluck_cache_on_record_save [label="post_save"];
    video_db -> update_custom_pluck_cache_on_record_save [label="FK read"];
    update_custom_pluck_cache_on_record_save -> pluck_rank_cache [label="write"];
    update_custom_pluck_cache_on_record_save -> pluck_detail_cache [label="write"];

    custom_pluck_db -> update_custom_pluck_cache_on_record_delete [label="post_delete"];
    custom_pluck_db -> update_custom_pluck_cache_on_record_delete [label="on_commit read current"];
    update_custom_pluck_cache_on_record_delete -> pluck_rank_cache [label="on_commit write/delete"];
    update_custom_pluck_cache_on_record_delete -> pluck_detail_cache [label="on_commit write/delete"];

    // tournament signals
    video_db -> checkin_video_before_create [label="pre_save"];
    video_db -> checkin_video_before_create [label="O2O read"];
    participant_cache -> checkin_video_before_create [label="read"];
    tournament_db -> checkin_video_before_create [label="query read"];
    checkin_video_before_create -> video_db [label="write field"];

    video_db -> add_created_video_to_checked_tournaments [label="post_save"];
    add_created_video_to_checked_tournaments -> tournament_db [label="m2m write"];

    tournament_db -> update_cache_on_tournament_delete [label="post_delete"];
    update_cache_on_tournament_delete -> tournament_cache [label="delete"];
    participant_cache -> update_cache_on_tournament_delete [label="scan/read"];
    update_cache_on_tournament_delete -> participant_cache [label="write/delete"];

    tournament_db -> update_cache_on_tournament_save [label="post_save"];
    tournament_db -> update_cache_on_tournament_save [label="subclass read"];
    update_cache_on_tournament_save -> tournament_cache [label="write/delete"];
    participant_cache -> update_cache_on_tournament_save [label="scan/read"];
    update_cache_on_tournament_save -> participant_cache [label="write/delete"];

    participant_db -> update_cache_on_participant_save [label="post_save"];
    participant_cache -> update_cache_on_participant_save [label="read"];
    tournament_db -> update_cache_on_participant_save [label="FK/m2m read"];
    identifier_db -> update_cache_on_participant_save [label="FK read"];
    video_db -> update_cache_on_participant_save [label="query read"];
    update_cache_on_participant_save -> participant_cache [label="write/delete"];
    update_cache_on_participant_save -> tournament_db [label="m2m write"];

    participant_db -> update_best_score_on_gsc_participant_save [label="post_save"];
    tournament_db -> update_best_score_on_gsc_participant_save [label="FK/subclass read"];
    tournament_user_db -> update_best_score_on_gsc_participant_save [label="read/create"];
    update_best_score_on_gsc_participant_save -> tournament_user_db [label="write best"];

    participant_db -> update_best_score_on_weekly_participant_save [label="post_save"];
    tournament_db -> update_best_score_on_weekly_participant_save [label="FK/subclass read"];
    tournament_user_db -> update_best_score_on_weekly_participant_save [label="read/create"];
    update_best_score_on_weekly_participant_save -> tournament_user_db [label="write best"];

    participant_db -> update_best_score_on_gsc_participant_delete [label="post_delete"];
    participant_db -> update_best_score_on_gsc_participant_delete [label="query best"];
    tournament_db -> update_best_score_on_gsc_participant_delete [label="FK/subclass read"];
    tournament_user_db -> update_best_score_on_gsc_participant_delete [label="read"];
    update_best_score_on_gsc_participant_delete -> tournament_user_db [label="write best"];

    participant_db -> update_best_score_on_weekly_participant_delete [label="post_delete"];
    participant_db -> update_best_score_on_weekly_participant_delete [label="query best"];
    tournament_db -> update_best_score_on_weekly_participant_delete [label="FK/subclass read"];
    tournament_user_db -> update_best_score_on_weekly_participant_delete [label="read"];
    update_best_score_on_weekly_participant_delete -> tournament_user_db [label="write best"];

    participant_db -> remove_participant_cache_on_delete [label="post_delete"];
    participant_cache -> remove_participant_cache_on_delete [label="read"];
    remove_participant_cache_on_delete -> participant_cache [label="write/delete"];

    participant_db -> revoke_rank_score_on_participant_delete [label="post_delete"];
    tournament_db -> revoke_rank_score_on_participant_delete [label="FK read end_time/subclass"];
    tournament_user_db -> revoke_rank_score_on_participant_delete [label="SELECT FOR UPDATE"];
    revoke_rank_score_on_participant_delete -> tournament_user_db [label="write decayed refund/totals"];
    tournament_user_score_time_cache -> revoke_rank_score_on_participant_delete [label="on_commit read anchor"];
    tournament_user_rank_cache -> revoke_rank_score_on_participant_delete [label="on_commit EXISTS if anchor missing"];
    revoke_rank_score_on_participant_delete -> tournament_user_rank_cache [label="on_commit write/remove score zsets"];
    revoke_rank_score_on_participant_delete -> tournament_user_score_time_cache [label="on_commit init only when empty"];
}
```

<a id="cache-data-structure"></a>

## 缓存数据结构

最新录像队列明确保持独立快照语义：删除 `VideoModel` 不移除 `newest_queue` 项，读取接口也不查询数据库过滤，因此可能返回已删除录像 ID。条目只按既有上限裁剪或由管理员单独移除。

自定义 pluck 录像删除后，在事务提交时从剩余合格录像补位 `CustomPluckRecord` 和对应 Redis 项；纪录删除后的缓存同步也提交后重读当前数据库状态，回滚不发布这两项更新。

比赛录像普通删除不立即重算，暂时保留已结算成绩、名次、积分和历史最好成绩，不刷新对应比赛积分与 best 排行。显式重算按赛种及成绩来源处理：打卡赛和 GSC 录像来源排除已删除录像，GSC 手工来源保留输入成绩，但两种来源均参与全场排名及积分更新。各新赛种须定义自己的删除、重算及 best 维护规则。站长 API 已返回受影响比赛 ID 并记录日志警告，隐藏中文页面已提供删除警告和确认；未来通知主办方的私信尚未实现，方案见仓库 `back_end/saolei/tournament/VIDEO_DELETION_PLAN.md`。

`POST /api/video/admin/delete` 仅允许 superuser，会话请求校验 CSRF；JSON 请求体为 `{"id": 123}`，每次删除一个录像。`videomanager.services.delete_video_by_id` 在数据库事务内调用实例 `delete()`，触发现有扩展清理、录像计数及排行更新信号，不直接删除 Redis 队列项。排行重建期间，HTTP 准入在任何删除发生前返回 503；服务自身的共享准入覆盖数据库提交及删除回调。同路径 GET 仅检查 superuser 并初始化 CSRF cookie/token，响应禁止缓存。

隐藏页面 `/#/superuser/delete-videos` 固定使用中文，不加入菜单或管理员标签页。页面在后端权限确认后接受 ID 列表，校验去重并逐个等待删除响应，显示删除、已不存在和受影响比赛。每次请求独立提交；错误、超时或手动停止会阻止后续请求，不自动重试，不恢复此前已成功项。单条请求仍会同步执行提交回调，不把 `on_commit` 当作后台任务。

| 所属 app | key | Redis 类型 | 数据结构 |
| --- | --- | --- | --- |
| `minigame` | `minigame:rank:v1:{ranking_key}` | zset | `member = player_id`，score 为原始整数毫秒。 |
| `minigame` | `minigame:detail:v1:{ranking_key}` | hash | `field = player_id`，value 为 `{score, achieved_at}` JSON。 |
| `minigame` | `minigame:ready:v1:{ranking_key}` | string | `1` 表示整榜已初始化；空榜也保留，无 TTL。 |
| `videomanager` | `newest_queue` | hash | `field = video_id`；JSON 仅包含 `state`、`time`、`player_id`。最新录像接口直接读取 Hash 快照并转换成元信息数组，不查询数据库；队列只写入公开录像，因此响应的 `ongoing_tournament` 为 `false`。解析字段由浏览器录像缓存补全；后台任务每天 01:08 按 `time` 保留最新 1000 条，时间相同时保留 ID 较大的录像，不再按天数过期。写入时不裁剪，允许暂时超过上限；裁剪使用 Python 排序和普通 Redis 删除操作，管理命令复用同一逻辑。`freeze_queue`、`review_queue` 已停止维护，遗留 key 由升级命令删除。 |
| `effranking` | `effranking:thrp:records` | hash | `field = player_id`；完整个人纪录 JSON。普通 `b/i/e` 为 `null` 或 `{value, video_id, upload_time}`；`e_nf` 为 `null` 或 `{value, video_ids}`，满分时含全部达成录像，否则只含最佳一局。sum 不重复存储。 |
| `effranking` | `effranking:thrp:{stat}` | zset | `stat = b/i/e/sum/e_nf`；`member = player_id`。原有四项编码六位小数成绩和分钟级达成时间；高级 NF 使用负 Thrp，满分后使用负达成局数。统一升序读取，不用于恢复成绩。 |
| `effranking` | `effranking:nf_ioe:records` | hash | `field = player_id`；完整 `b/i/e` 纪录，每项为 `null` 或 `{value, video_id, timems}`；sum 从原始成绩计算，不重复存储。 |
| `effranking` | `effranking:nf_ioe:{stat}` | zset | `stat = b/i/e/sum`；`member = player_id`；score 取业务分值的负数，满分单项比较用时，满分总和只比较高级用时。 |
| `customranking` | `customranking:pluck:{level}:rank` | zset | `member = player_id`；`score = pluck`，当 `pluck == 0` 时使用 `timems - MAX_TIMEMS` 降低 0 碰撞风险。 |
| `customranking` | `customranking:pluck:{level}:detail` | hash | `field = player_id`；JSON 包含 `video_id`、`timems`、`upload_time`。展示用的模式和 3BV 通过录像缓存补全；排序 zset 保持原编码。 |
| `tournament` | `tournament:normal` | hash | `field = tournament_id`；`value = CachedTournament JSON`，包含 `id`、`state`、`subclass`、`host_id`、`start_time`、`end_time`、`data`。`data` 保存子类独占字段：GSC 为 `order`、`token`；周赛为 `year`、`week`、`tournament_format`。 |
| `tournament` | `tournament:normal:participants` | hash | `field = user_id`；`value = list[CachedNormalParticipant] JSON`，每项包含 `id`、`token`、`arbiter_identifier`、`tournament`、`start_time`、`end_time`。 |
| `tournament` | `tournament:user:score_current` | zset | `member = user_id`；`score = score_current × tournament_score_decay_factor(last_updated, 缓存时间基准)`；所有成员使用同一时间基准。数据库 `score_current = 0` 时不写入。 |
| `tournament` | `tournament:user:score_current:last_updated` | string | 带时区的 ISO datetime；当前积分 zset 的年度统一锚点，正常为当年 1 月 1 日 00:00 UTC。由年度 APScheduler 任务更新；普通积分发放不推进。调度任务延迟时继续统一使用旧锚点。 |
| `tournament` | `tournament:user:score_total` / `gsc_total` / `gsc_best` / `weekly_total` / `weekly_classic_total` / `weekly_classic_best` | zset | `member = user_id`；`score = TournamentUser` 对应字段值。各 total 字段为 `0` 时不写入；`gsc_best`、`weekly_classic_best` 为 `MAX_TOURNAMENT_BEST` 时不写入。 |
| `article` | `articles` | list | 文章目录项字符串，来自 `assets/article` 或静态目录下的文章文件。 |

`TournamentUser` 是比赛积分的持久化汇总表；Redis 中另用 7 个 sorted set 保存排行榜入口。站内用户创建 `TournamentParticipant` / `GSCParticipant` / `WeeklyParticipant` 时，保存信号会在当前数据库事务内立即创建缺失的 `TournamentUser`；删除 participant 不会跟随删除 `TournamentUser`。无站内用户的 participant 在数据库中保留 `user_id = NULL`，但 API 序列化时统一输出 `user_id = 0`，前端只按 `0` 识别非站内用户。GSC / 周赛 finish 任务先调用 `ensure_tournament_users`，为本场所有站内参赛用户补建缺失的默认 `TournamentUser`，然后才调用 `delete_participants_without_videos` 删除无录像站内 participant。排名积分发放和 best 刷新是独立的非关键后台任务，入口同样先执行 `ensure_tournament_users`，支持独立执行或重跑；随后各自从本场剩余站内 participant 出发，通过 `participant.user.tournamentuser` 取得对应的 `TournamentUser`，并使用 `select_related('user__tournamentuser')` 避免 N+1。积分发放任务读取并衰减既有 `TournamentUser.score_current`，再根据本场 participant 的 `rank_score` 增量写回 `TournamentUser` 和 `TournamentParticipant.rank_score`，随后同步刷新 `score_current`、`score_total` 和对应分类 total 的 zset。历史最好成绩在 participant 保存后只读取当前 participant 和对应比赛子表，并与 `TournamentUser.gsc_best` / `weekly_classic_best` 直接比较；只有当前成绩更好时才改变内存值。结算流程使用 `bulk_update` 写入 `rank_score`，不会触发保存信号，因此 best 刷新通过 `refresh_gsc_best_scores` / `refresh_weekly_best_scores` 作为独立后台任务执行，并在写库后刷新对应 best zset；best 与排名积分发放没有顺序依赖。为了简化结算代码，积分发放和 best 刷新都不筛选字段是否发生变化，会统一 `bulk_update` 候选 participant 和对应 `TournamentUser`。结算链路通过 `tournament` logger 写入 `logs/tournament.log`，记录后台任务、删除无录像 participant、读取 `TournamentUser`、成绩/排名刷新、积分发放、best 刷新、状态切换和录像公开等阶段的处理数量。没有有效历史成绩时，best 字段使用 `MAX_TOURNAMENT_BEST` 作为哨兵值，并且不写入 Redis。participant 删除时，GSC / 周赛各自的信号会在当前事务内按需调用 `calculate_gsc_best_score` / `calculate_weekly_classic_best` 重算该类型历史最好成绩，并同步更新对应 best zset。由于 `TournamentUser` 是数据库汇总数据，participant 信号触发的创建和 best 更新必须在当前事务内立即执行，不使用 `transaction.on_commit`。如果需要修复历史汇总数据，尤其是把旧的 `0` best 值迁移到新的最大值哨兵，可以运行 `manage.py refresh_tournament_user_stats`。该命令会先调用 `tournament.services.refresh_tournament_user_total_fields` 重建 `score_total`、`gsc_total`、`weekly_total` 和 `weekly_classic_total`，再执行命令内的 best 重建步骤写回 `gsc_best` 和 `weekly_classic_best`；`score_current` 依赖实时衰减，不由该命令刷新。如果 Redis 排行缓存丢失或需要按当前数据库状态重建，可以运行 `manage.py rebuild_tournament_user_cache`。

GSC 历史补录不新增缓存，管理接口不画入公共 API 图。创建参赛者仍执行默认 TournamentUser 创建及 best 更新；匿名选手不写用户积分 zset。标识绑定、录像创建或提前上传时间仍通过原信号维护队列和排行，HTTP 准入锁覆盖准备、单标识绑定与上传请求的事务及提交回调。列表的 `has_videos` 使用相关 EXISTS 子查询，GSC 结果标识使用 `select_related('arbiter_identifier')`，不逐人读取用户表。完整流程见 [GSC 历史录像补录](./gsc-history-import.md)。

participant 删除时，`revoke_rank_score_on_participant_delete` 在删除事务内锁定并更新 TournamentUser，提交后仅刷新受影响的积分 zset；扣至 0 的成员移除，年度锚点不变。数据库回滚时不发布撤分缓存。衰减及分类扣分规则见[信号触发关系](./signals.md#signal-function-map)。

比赛批量公开 `reveal_videos_for_tournament` 先在事务内更新录像公开标记，提交后才按本批固定录像 ID 更新最新队列、竞速榜、custom pluck 纪录及其 Redis 缓存、效率榜。每项更新使用独立的 `transaction.on_commit(..., robust=True)` 回调；事务回滚不发布缓存，提交后的单项失败由 Django 记录错误日志，不撤销公开状态，也不阻断其他缓存或勋章入队回调。勋章批量入队回调同样隔离异常，缓存更新不依赖入队成功。目前不自动重试失败的回调，相关缓存或勋章任务需通过现有重建、重算入口恢复。

当前积分 zset 使用固定年度锚点。`update_tournament_users` 读取缓存锚点，仅换算本批用户，不再根据用户 `last_updated` 推进基准或整体衰减其他成员。空缓存首次写入时初始化为当年 1 月 1 日 00:00 UTC。折算使用 `tournament_score_decay_factor(last_updated, 锚点)`，负时间差通过负指数自动兼容；因此年内新积分折算到年初时会放大，但所有成员共用锚点，排序等价于实时积分。锚点读取和本批写入使用 redis-py `transaction`（`WATCH` / `MULTI` / `EXEC`），年度更新并发发生时重试。数据库仍保留用户各自的 `score_current` / `last_updated`，API 回表输出这些原始值，前端按 `globalNow` 衰减显示；统一锚点只影响 Redis 排序。更新其他 total / best 字段不会改变当前积分基准。

`common.apscheduler.refresh_tournament_score_reference` 在每年 1 月 1 日 00:00 UTC 调用 `TournamentCache.refresh_tournament_score_reference`，使用 `ZUNIONSTORE` 权重将当前积分 zset 整体折算到新锚点，并在同一 Redis 事务中设置锚点；其他排行和数据库不变。同一年重复执行无副作用。调度器启动时也执行一次，补齐跨年停机；尚未补齐时，结算仍沿用旧锚点，不会混用年份。读取旧锚点、整体折算及设置新锚点采用 `WATCH` / `MULTI` / `EXEC`，与结算写入并发时保持一致。

`rebuild_tournament_current_score_cache` 从数据库分批读取当前积分，按当年年初锚点重算并原子替换当前积分 zset 和锚点，不改其他 6 个排行或数据库；并发缓存写入会触发重试，读请求在提交前仍能读取旧排行。为避免数据库尚未提交但缓存已写入的跨系统窗口，重算期间仍应暂停积分结算和历史积分修正任务。部署年度锚点方案后应先运行此命令，再重启 APScheduler。`rebuild_tournament_user_cache` 则清理并分批重建全部 7 个 zset 和年初锚点，重建期间仍需暂停其他排行写入。清理全部排行时也删除锚点 key；非空当前积分 zset 缺少锚点时会报错，要求显式重建，不进行数据库 fallback。

每批排行缓存更新按字段汇总：每个 zset 最多执行一次多成员 `ZADD` 和一次多成员 `ZREM`，分别写入非默认分数与移除默认分数成员，不再为每个用户单独排入命令。缓存重建按 `batch_size` 分批读取。

`ensure_tournament_users` 按本场 participant 的非空 `user_id` 去重并执行 `get_or_create`，不覆盖已有记录；默认积分为 0，best 为 `MAX_TOURNAMENT_BEST`，因此补建本身不写入排行 zset。此步骤兼容早期只有 participant、尚无 `TournamentUser` 且未发放积分的历史数据，不负责恢复已丢失的历史积分。新 participant 仍由创建信号保证关联完整；删除信号不容忍缺失关联，也不补建记录。每次任务会记录补建数量，无需额外管理命令。

`GSCParticipant.t37` 是数据库持久化 generated field，并建立 `gsc_t37_idx` 索引，服务于 GSC 排名和历史最好成绩查询。保存信号使用当前 participant 实例上的临时 `t37` 值进行 best 增量比较，因此不会为了读取 generated field 再查询一次 participant。

## 勋章图鉴

`medal/cache.py` 把已启用的成就定义放在 Django `default` 缓存，逻辑 key 为 `medal:catalog:v3`，TTL 300 秒。内容是定义字典，不含玩家是否解锁。先检查缓存，命中时不再查询默认定义是否缺失；未命中才补齐并装回图鉴。定义保存或删除时删掉这个 key。

玩家摘要持久化到MySQL的`medal_playermedalsummary`，每名玩家一行，以玩家ID为主键。JSON只含有效授予的公开事实、进度数值、佩戴顺序和首次扫描状态；定义、隐藏条件和计分读取当前共享图鉴。图鉴缓存命中、摘要已建立时，`player_summary()`通过连接玩家表和摘要表的1次查询返回结果。此计数不包含认证、会话、Redis访问和中间件。

后台评估、单项授予、人工决定和佩戴服务在同一玩家锁、同一数据库事务中更新业务记录和摘要；内容相同时不改写摘要。首次读取旧玩家时从现有勋章表补齐，不扫描录像。录像或比赛参加记录删除前，在同一玩家锁和删除事务内移除关联摘要。事务提交后再删掉该玩家的 `medal:display:v4:{user_id}`；删除回滚时摘要和键都还在。下次读取从完成外键置空的记录补齐摘要。维护原始勋章表的脚本必须使用服务入口，或在相同玩家锁和事务中删除受影响摘要；现有管理员重算入口也会同步重建摘要。

录像补传或上传时间修改触发的刷新，在发布摘要前校正授予日期、证据和阶段日志；摘要仍在同一事务更新，状态键在提交后按数据库中的新日期重建。已有勋章也会处理时间变化，不要求成绩改善或档位变化。新手集合及三阶勋章记录完整分项证据，任一分项改时都可以重算完成时间。

前端侧栏与勋章页通过共享服务复用按玩家保存的摘要和进行中的请求。首次扫描未完成时有限轮询；切换玩家或停用页面时取消该组件订阅，旧请求不得覆盖新玩家。保存佩戴后使相关摘要失效并通知活跃订阅者刷新。名字悬停另读 `medal:display:v4:{user_id}`；浏览器里的悬停缓存只活在当前页面会话。

普通录像上传成功后，同一浏览器启动一条共享的有限状态检查。每次等待间隔依次为 1、2、3、5、8、13、20、30 秒，最多 8 次；连续上传合并，不重置次数，慢请求不并发。`GET /api/medal/refresh-status` 只允许登录用户查询本人，使用一次 EXISTS 检查刷新和补发任务是否 READY/RUNNING，不返回任务参数、不入队、不查询录像。每次状态请求超时 5 秒；请求失败或次数耗尽后停止，下一次成功上传可以重新启动。后台队列停止或延迟超过等待上限时，不保证本轮自动同步。

任务不再待执行时，前端使对应玩家的摘要失效，活跃勋章页和佩戴栏共享一次新摘要请求；同时清除名字悬停缓存。已经打开过提示的名字会重新读取，其余名字留到下次显示。上传前仍在进行的旧请求不得写回缓存。没有活跃摘要订阅者时只使摘要失效，下次进入再读取。Redis 展示键仍由后台任务提交后更新，前端不重复计算或强制重建 Redis。该通知只影响发起上传的浏览器页面，其他浏览器没有推送。

管理员人工决定保存在 `medal_medaloverride`，操作记录追加到 `medal_medaloverridelog`。撤销规则只保存在数据库；展示缓存移除被撤销的授予，不保存锁定标记或理由。管理页提交后使同一浏览器内目标玩家的摘要失效，其他玩家缓存不变。恢复自动需要后台任务完成后重新加载；其他浏览器已打开的页面不会收到推送。详细优先规则见 [管理员勋章决定](./medal-overrides.md)。

## 勋章状态

勋章系列、类型、方向、玩法使用 `config.text_choices.Medal_TextChoices` 的短码，前端对应 `utils/medal_const.ts`；名称、说明和寄语以枚举值直接查找前端翻译字典，图片目录和勋章 code 不变。系列值最长 2 字符，其他上述枚举值为单字符。枚举成员直接引用，不在 `medal/utils.py` 另设同值别名。

逻辑 key 为 `medal:display:v4:{user_id}`，TTL 300 秒，只服务 `GET /api/medal/players/state` 展示。Redis 不保存计算状态；原始股东的最小录像 ID、未完成的新手难度和模式集合、能力自然档位、人工覆盖均从本次已读取的数据库状态取得。是否完成初始化只看 `MedalScan`，缺键或 Redis 故障不会触发全量评估。

值只含玩家佩戴的已授予短记录，顺序与佩戴列表一致，时间为 Unix 秒。没佩戴时为 `{"grants":[]}`：

```json
{"grants":[{"code":"ability.time.b","stage":20000,"timestamp":1761123456,"scope":"","tournament":null,"rank":null}]}
```

- `code` 为定义，`stage` 为当前档，`timestamp` 为 `granted_at`。
- `scope` 为 `scope_key`，普通勋章为空；`tournament`、`rank` 来自赛事授予。
- 不保存 `value`、`levels`、`modes`、`locked`、录像 ID、阈值、分数或人工理由。未入档和已撤销的条目不写入。
- 扫描后一枚都没有时可以缓存 `{"grants":[]}`；未扫描的玩家不建展示键。

后台计算一次加载有效定义、玩家进度、全部授予和人工覆盖。普通录像按主键批量读取，与数据库自然档位及新手集合比较。同档从 48 秒提升到 46 秒不改授予证据；补传更早录像或修改时间仍按需校正发放日期、证据和阶段日志。证据失效只重算受影响难度；首次扫描、显式完整刷新和既有批量变更入口仍完整评估该玩家。旧数据库进度缺少集合时查询一次历史补齐。

摘要在业务事务内更新。佩戴列表、其中的公开短记录或扫描状态变化才注册提交后发布；内部集合变化或结果完全不变均不发布。发布时重新取得同一玩家锁，连接读取最新摘要，在持锁期间批量写 Redis；旧提交回调和缓存回填也遵守此锁，防止旧快照覆盖新结果。业务回滚不发布。证据删除提交后删键，下次刷新仍根据 `MedalScan` 走增量。

状态接口先批量读 Redis。缺失的 ID 一起在玩家锁内读取摘要：摘要齐全时 1 次 SELECT，部分摘要缺失时再用 1 次批量授予查询补齐展示；不查询历史录像。未扫描或不存在的玩家返回空列表，不在此接口启动扫描，首次补发仍由详情接口和 [enqueue_medal_backfill](./management-commands.md#enqueue-medal-backfill) 入队。命中缓存时没有业务 SQL。

Redis 连接和读写异常记录日志，计算及数据库摘要不回滚，状态接口返回数据库结果。发布失败时尝试删除旧值，下次请求重新回填；如果 Redis 连删除也不可用，旧值最多保留到剩余 TTL 到期。这里的重试依赖下一次缓存未命中的读取，没有新增独立发布队列。

当前浏览器标签页内，管理员授予、撤销或恢复自动的请求成功后，以及保存佩戴或上传同步完成后，共用 `refreshPlayerMedals` 使目标玩家的摘要和名字悬停缓存一起失效。已打开的悬停提示通过版本通知重新批量读取，未打开的留到下次悬停；失败的管理请求不清缓存，也不新增定时轮询。

## 写入与重建入口

| 缓存 | 主要写入入口 | 重建 / 清理入口 |
| --- | --- | --- |
| 录像状态队列 | `videomanager.signals.refresh_state_queue_on_video_save` | `videomanager.cache.add_videos_to_state_queues_bulk` 可按状态批量恢复普通队列。 |
| 效率 Thrp / NF IOE 排行 | `effranking.signals` 与批量 services，提交后更新 | `rebuild_eff_ranks --ranking-name thrp/nf_ioe` 指定大榜重建；管理员对应大榜的 `admin/rebuild_record` 修复单项，sum 仅从个人 hash 重算。 |
| 自定义 pluck 排行 | 保存时 `update_custom_pluck_top_cache`；录像删除提交后 `refresh_custom_pluck_rank` 补位，纪录删除提交后 `sync_custom_pluck_top_cache` 同步当前状态 | `manage.py rebuild_custom_pluck_cache` 从 `CustomPluckRecord` 全量重建，不补建缺失的数据库纪录。 |
| NORMAL 比赛 | `TournamentCache.update_tournament` | `manage.py rebuild_tournament_cache` 显式查询 `NORMAL` GSC 与周赛并重建。 |
| NORMAL 参赛关系 | `TournamentCache.update_participant` / `remove_participant` | `manage.py rebuild_tournament_cache` 按 `user_id` 分组重建。 |
| 比赛积分排行 | `TournamentCache.update_tournament_user` / `update_tournament_users`；APScheduler 年度锚点更新 | `manage.py rebuild_tournament_user_cache` 重建全部 7 个 zset；`manage.py rebuild_tournament_current_score_cache` 原子重算当前积分 zset 和年度锚点。 |
| common 摘要 | 对应 API 内部 `cache.set` | TTL 到期自动失效。 |
| 勋章图鉴 | `medal.signals.invalidate_medal_catalog` | 定义保存或删除后删除 `medal:catalog:v3`。没有单独的重建命令，下次读取从 `MedalDefinition` 装回。 |
| 勋章状态 | 佩戴列表、佩戴中的公开授予或扫描状态改变后，提交时读取最新摘要写 `medal:display:v4:{user_id}` | 缺键按需批量回填展示，不扫描录像；摘要删除提交后删键。`manage.py enqueue_medal_backfill` 只给未扫描玩家入队首次评估。 |
| 文章目录 | `article.views.update_list` | 管理员手动调用 `update_list` 全量刷新。 |

## 读取约定

- NORMAL 比赛列表只读 `tournament:normal`，不在缓存未命中时回落数据库；缓存与数据库不同步视为写路径 bug。
- 录像队列缓存不保存比赛录像，`VideoQueueCache.add` / `add_bulk` 会跳过 `ongoing_tournament=True` 的录像。
- 参赛 checkin 先读 `tournament:normal:participants`，命中后再按 tournament id 查询数据库对象，用于写入录像的多对多关系。
- `customranking:pluck:{level}:rank` 只保存排序所需数据，展示字段来自同级 `detail` hash。
