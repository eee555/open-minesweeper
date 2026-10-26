# 后端自定义管理命令

本文档记录自定义 Django 管理命令及本地数据初始化入口。均在 `back_end/saolei` 目录下执行，管理命令的完整参数可通过 `--help` 查看：

```bash
python manage.py <command> --help
```

## 勋章补发

### `enqueue_medal_backfill`

位置：`medal/management/commands/enqueue_medal_backfill.py`

给还没有 `MedalScan` 的玩家入队 `task_backfill_player_medals`。命令本身不扫描录像，也不写 Redis。任务优先级是 0，低于上传后的刷新。工人跑完现有 `evaluate_player` 后才写 `MedalScan` 和 `medal:state:{user_id}`；一枚都没有也写 `{"grants":[]}`。已经有 `MedalScan` 的玩家不会入队。同一玩家已经有一条 `READY` 的补发任务时不再插入第二条。

打开勋章详情时的补发仍然保留，用来盖住命令还没排到的人。

```bash
python manage.py enqueue_medal_backfill
```

## 小游戏排行榜

`minigame/management/commands/rebuild_minigame_ranks.py` 从数据库最佳成绩重建 ZSET、明细 Hash 和初始化标记；空榜也初始化。不修改数据库，允许与提交并发时产生偶发偏差。

```bash
python manage.py rebuild_minigame_ranks
python manage.py rebuild_minigame_ranks --ranking-key left-click-b-50-v1
```

首次部署先运行 `python manage.py migrate`。缓存也可在首次查询时按需初始化；Redis 故障期间查询降级至数据库。

## 录像缓存升级

### `compact_video_cache`

精简 `newest_queue` 与四种自定义 pluck 榜详情 Hash 的重复展示字段，并删除已停止维护的 `freeze_queue`、`review_queue`。不扫描 Redis keyspace，也不重建最新队列成员；并发修改或删除的成员不会被旧值覆盖或重新加入。

```bash
python manage.py compact_video_cache --dry-run
python manage.py compact_video_cache
```

先部署新的前后端并确保旧写进程已退出，再运行压缩。命令可重复运行，输出改写数量及内存估算；接口与存储字段对照见仓库中的 `front_end/src/services/videoService.md`。

## 本地公开数据快照

### `dangerzone.init_local_test`（独立脚本）

下载和初始化入口分别位于 `dangerzone/download_public_data.py`、`dangerzone/init_local_test.py`，使用 `python -m` 启动。

**初始化会清空本地数据库和 `saolei_website` 对应的 Redis 数据库。** 使用独立的本地测试数据库和 Redis，执行前停止 worker、定时任务及其他写入。要求不存在 `.production` 标记、`DEBUG=True`、`E2E_TEST=True`，数据库及 Redis 均为回环地址；导入前会校验快照完整性和引用关系。

```bash
# 下载公开元数据，支持断点续传。
python -m dangerzone.download_public_data
# detailbulk 不可用时，使用已有详情及公开录像列表完成快照：
python -m dangerzone.download_public_data --skip-details
python manage.py migrate
# 读取快照，清库、导入，并创建当天经典周赛。
python -m dangerzone.init_local_test
# 只导入，不创建周赛：
python -m dangerzone.init_local_test --no-weekly
```

默认快照目录为 `tmp/public-data`。下载使用 `--output-dir`，导入使用 `--snapshot-dir` 指定其他目录。下载仅请求公开 API，每次响应完成后至少等待 1.25 秒；`--interval` 可增加间隔。已完成的快照不会刷新已有数据，获取新数据需换目录；旧版快照可通过重新运行下载入口补齐用户标识。

导入保留用户/录像 ID、公开属性及用户标识归属，并自动重建录像计数、上传额度、竞速榜、效率 Thrp 榜、pluck 纪录缓存和录像状态队列。`--no-weekly` 仅跳过创建周赛，不影响重建。

- 管理员：ID `2`，密码 `admin123456`；普通账号：ID `48`，密码 `user123456`。用户名保留生产数据；可通过 `--admin-password` / `--user-password` 指定其他密码。
- 其他用户禁用密码登录；仅 ID `2` 获得本地管理员权限，邮箱统一为 `user-{id}@example.invalid`。
- 快照不包含原密码、邮箱、录像文件、头像文件和比赛关联。录像可用于列表和排行测试，不能在本地播放或重新解析；录像计数无法排除缺失关联的已公开比赛录像。
- `--skip-details` 优先使用已有详情，其余录像使用列表数据。缺失指标保持 NULL，录像内标识可能为空；保留列表提供的 `right_ce` 用于 NF 判断，不凭旧模式推测。

快照格式与兼容规则见仓库中的 `back_end/saolei/dangerzone/readme.md`。

## 缓存重建

### `rebuild_eff_ranks`

位置：`effranking/management/commands/rebuild_eff_ranks.py`

从录像数据库重建效率 Thrp 榜。`--ranking-name` 仅支持 `thrp`（默认值）；`--batch-size` 默认 1000，必须为正数。

```bash
python manage.py rebuild_eff_ranks
```

首次建榜或缓存丢失后执行，API 不回源数据库。执行前暂停录像上传、审核、修改、删除、标识绑定/解绑和比赛公开等写入。命令先构建临时榜，成功后原子替换，失败保留旧榜。规则见 `back_end/saolei/effranking/README.md`。

### `rebuild_speed_ranks`

位置：`speedranking/management/commands/rebuild_speed_ranks.py`

从 `VideoModel` 按玩家分段重建竞速排行榜。`--ranking-name` 可选 `saolei` 或 `saolei_nf`，省略则重建两者；`--batch-size` 默认 1000，必须为正数。

```bash
python manage.py rebuild_speed_ranks
python manage.py rebuild_speed_ranks --ranking-name saolei_nf --batch-size 1000
```

首次建榜或缓存丢失后执行，API 不自动回源。执行前暂停录像上传、修改、删除、标识绑定/解绑及比赛公开等写入。命令先构建临时榜，成功后依次原子替换各大榜，失败保留尚未发布的大榜原缓存。编码和升级要求见 `back_end/saolei/speedranking/README.md`。

### `rebuild_pb_ranks`

位置：`speedranking/management/commands/rebuild_pb_ranks.py`

从录像数据库重建 PB 普通/NF 榜、用户排名和小榜人数。`--batch-size` 默认 100，必须为正数。

```bash
python manage.py rebuild_pb_ranks
```

首次建榜或缓存丢失后执行，API 不回源。执行前暂停 PB 相关读写，包括上传、审核、绑定/解绑、删除及比赛公开。命令直接清空 PB 命名空间后重建，失败可能留下部分缓存，排除错误后重新运行。

### `rebuild_top_ranks`

位置：`speedranking/management/commands/rebuild_top_ranks.py`

从录像数据库重建 top 原始榜、锚点及软实力/LSF 派生榜。`--batch-size` 默认 100，必须为正数。

```bash
python manage.py rebuild_top_ranks
```

首次建榜或缓存丢失后执行，查询不自动回源。命令构建临时榜后原子发布，失败保留旧榜；强制终止可能遗留临时数据。重建期间等待在途写入完成，相关新 HTTP 写请求返回 503，后台写入等待，旧榜仍可读取。

所有进程必须共享可写的 `TOP_RANKING_LOCK_PATH`（默认 `BASE_DIR/runtime/top-lock.sqlite3`）；不要删除活动锁文件，自定义写入脚本也须遵守准入。缓存及锁的约定见 `back_end/saolei/speedranking/README.md`。

### `rebuild_top_soft_ranks`

位置：`speedranking/management/commands/rebuild_top_soft_ranks.py`

从现有 top 原始榜和实时锚点重建软实力/LSF 索引，不修复原始榜。使用与 `rebuild_top_ranks` 相同的独占准入和临时榜发布逻辑，失败保留旧版。首次建榜或原始榜损坏时使用 `rebuild_top_ranks`。

```bash
python manage.py rebuild_top_soft_ranks
```

### `rebuild_tournament_cache`

位置：`tournament/management/commands/rebuild_tournament_cache.py`

清空并重建 `tournament:normal` 和 `tournament:normal:participants`，只包含 `NORMAL` 状态的金羊杯、周赛及其参赛关系。

```bash
python manage.py rebuild_tournament_cache
```

### `rebuild_tournament_user_cache`

位置：`tournament/management/commands/rebuild_tournament_user_cache.py`

重建 `TournamentUser` 的全部 Redis 排行缓存。当前积分统一折算到当年 1 月 1 日 00:00 UTC，其余字段按数据库值写入，不修改数据库。执行期间暂停积分结算及其他排行缓存写入；只需修复当前积分排序时，使用 `rebuild_tournament_current_score_cache`。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--batch-size` | `1000` | 每批处理的缓存行数 |

```bash
python manage.py rebuild_tournament_user_cache
```

### `rebuild_tournament_current_score_cache`

位置：`tournament/management/commands/rebuild_tournament_current_score_cache.py`

从 `TournamentUser.score_current` / `last_updated` 重算当前积分排行，统一使用当年 1 月 1 日 00:00 UTC 锚点。不修改数据库或其他排行，也不重复发放积分。

重建期间暂停积分结算和历史积分修正任务。命令在同一 Redis 事务内原子替换排行与锚点，重复执行不会累计衰减。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--batch-size` | `1000` | 每批读取的用户数，必须为正整数 |

```bash
python manage.py rebuild_tournament_current_score_cache
```

### `rebuild_custom_pluck_cache`

位置：`customranking/management/commands/rebuild_custom_pluck_cache.py`

重建自定义 pLuck 排行的 Redis 缓存。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--level` | 无 | 只重建指定自定义级别；省略则重建全部配置 |
| `--batch-size` | `1000` | 每批写入 Redis 的纪录数量 |

`--level` 的合法值以 `config/customranking.py` 中的 `CUSTOM_PLUCK_CONFIGS` 为准，`--help` 也会列出。

```bash
python manage.py rebuild_custom_pluck_cache
python manage.py rebuild_custom_pluck_cache --level c16_30_150
```

## 数据刷新

### `refresh_videos`

位置：`videomanager/management/commands/refresh_videos.py`

按 ID 顺序逐条重新解析录像并通过实例保存触发信号，默认处理全部录像，不限制状态、模式、级别或比赛标记。每条录像独立加锁和提交，解析期间会阻塞同一录像的其他写入。

已知解析异常会报告 ID 并跳过；其他错误会停止命令，回滚当前条的数据库写入，此前完成的刷新和已写入 Redis 的内容不回滚。此命令不替代排行榜全量重建；需要重算录像计数时另行使用 `refresh_video_counts`。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--start` | `0` | 起始录像 ID，包含，必须非负 |
| `--end` | 不限制 | 结束录像 ID，不包含，不能小于 `start` |
| `--step` | `100` | 每处理多少条录像输出一次进度，必须为正整数 |

区间为 `[start, end)`，可仅指定一个边界；`step` 按实际处理条数计数。

```bash
python manage.py refresh_videos
python manage.py refresh_videos --start 10000 --end 20000 --step 50
```

### `refresh_video_counts`

位置：`msuser/management/commands/refresh_video_counts.py`

刷新全部 `UserMS` 的比赛、非比赛录像数量及文件空间：`video_num_total`、`video_num_tournament`、`video_size_total`、`video_size_tournament`。空间按 `VideoModel.file_size` 求和，单位为字节；合计字段 `video_num_all`、`video_size_all` 由数据库 `GeneratedField` 自动计算。不修改上传额度、个人纪录或 Redis。

进行中的比赛录像及关联到任何比赛的录像（包括已结束比赛）计入比赛口径，其余计入非比赛口径；不按审核状态筛选。通过 `EXISTS` 检查比赛关联，避免同一录像关联多个比赛时重复累计；无录像的用户四个基础统计均归零，包括未关联个人资料的 `UserMS`。

补录关联不立即调整统计，之后的删除、大小或归属修改按录像当前比赛归属增减，允许产生临时偏差，运行此命令统一修正。命令直接聚合当前录像，不维护历史分类标记，也不更新录像行；每批用户统计在同一事务内写入，失败回滚当前批，已完成批不回滚。迁移后先运行此命令回填新增统计。执行期间暂停录像、比赛关联及玩家归属等相关写入，避免统计覆盖。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--batch-size` | `1000` | 每批处理的用户数量，必须为正整数 |

```bash
python manage.py refresh_video_counts
```

### `refresh_tournament_scores`

位置：`tournament/management/commands/refresh_tournament_scores.py`

同步重算指定比赛的成绩、排名、积分和参赛用户的历史最佳成绩，无需后台 worker。只接受已颁奖且有结束时间的 GSC 或经典周赛。

命令按有效录像重算成绩，按新旧积分差额修正累计积分，并同步 Redis；不会重复累计积分或回退最后计分时间。执行期间避免修改该届录像、参赛者，并暂停相关用户的积分结算。数据库写入在一个事务内，失败会回滚；Redis 不随数据库回滚，排除故障后需重跑以恢复一致性。

重算规则按比赛类型及成绩来源区分。经典打卡赛及 GSC 的录像来源成绩只统计现存且符合计分条件的录像，已删除录像的成绩贡献作废，由剩余录像或赛制默认值补位。GSC 的 `manual_scores=true` 按参赛者设置，保留其 9 项手工成绩，不从部分/空录像重算，但仍参与全场排名及积分更新；录像来源只统计符合模式、级别与 3BV 条件的 OFFICIAL 录像。匿名选手共同排名但不获得积分。

普通删除录像不立即重算或撤分；显式执行本命令时才按上述规则更新成绩、名次和积分。删除参赛记录的信号则会撤回本人积分，本命令用于修正剩余名次和积分。历史补录后的操作顺序见 [GSC 历史录像补录](./gsc-history-import.md#重试与人工重算)。新增赛种或赛制时须提供自己的删除及重算实现，再接入命令，不能默认复用另一赛种的成绩来源规则。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `tournament_id` | 必填 | 比赛 ID，不是 GSC 届数或周数 |
| `--batch-size` | `1000` | 批量写入大小，必须为正整数 |

```bash
python manage.py refresh_tournament_scores 123
```

### `refresh_tournament_user_stats`

位置：`tournament/management/commands/refresh_tournament_user_stats.py`

补齐已颁奖比赛参赛者缺失的 `TournamentUser`，刷新比赛历史总分、金羊杯和经典周赛历史最好成绩，并同步 Redis；不修改实时 `score_current`。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--batch-size` | `1000` | 批量创建、批量更新和缓存写入的批大小 |

```bash
python manage.py refresh_tournament_user_stats
```

## 缓存清理

### `delete_legacy_speedranking_cache`

位置：`common/management/commands/delete_legacy_speedranking_cache.py`

清理 `saolei_website` Redis 中的旧竞速榜和 `news_queue`，不修改数据库或其他缓存。旧纪录 key 为 `player_{stat}_{mode}_{用户ID或ids}`，指标限于 `timems/bvs/stnb/ioe/path`，模式限于 `std/nf/ng/dg`。执行前确保旧写入逻辑已停用。

```bash
python manage.py delete_legacy_speedranking_cache --dry-run
python manage.py delete_legacy_speedranking_cache
```

`--dry-run` 仅列出匹配的 key 并统计数量。

### `delete_newest_queue`

位置：`videomanager/management/commands/delete_newest_queue.py`

裁剪 Redis 最新录像队列，读取 Hash 并在 Python 中按上传时间排序，保留最新 1000 条，上传时间相同时保留 ID 较大的录像。不再按 7 天期限删除；不足 1000 条时全部保留。写入时不裁剪，允许暂时超过上限，由后台任务每天 01:08 统一裁剪；也可运行本命令立即清理。

```bash
python manage.py delete_newest_queue
```

## 后台任务与定时任务

### `db_worker_robust`

位置：`common/management/commands/db_worker_robust.py`

启动 `django-tasks-db` worker，通过 pidfile 和进程检测避免重复启动。本进程以及启动它的父进程不算另一个 worker。仅在未检测到现有 worker 时，将遗留的 `RUNNING` 任务标记为 `FAILED`，然后启动 worker；不会在运行期间自动恢复任务或重启进程。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--queue-name` | 默认任务队列 | 要处理的队列；多个队列用逗号分隔，`*` 表示全部 |
| `--interval` | `2` | worker 轮询间隔，单位秒 |
| `--backend` | 默认任务后端 | 使用的 task backend |
| `--batch` | `False` | 传递给 `db_worker` 的批处理模式 |
| `--no-startup-delay` | 不启用 | 关闭 `db_worker` 的启动延迟 |
| `--max-tasks` | 无 | 最多处理的任务数 |
| `--worker-id` | 自动生成 | 覆盖自动生成的 worker id |
| `--pidfile` | `logs/db_worker_robust.pid` | 用于防止重复启动的 pidfile 路径 |

```bash
python manage.py db_worker_robust
python manage.py db_worker_robust --queue-name default --interval 2
```

### `refresh_monitor_snapshot` {#refresh-monitor-snapshot}

位置：`monitor/management/commands/refresh_monitor_snapshot.py`

立即采样录像、任务、磁盘和内存统计，原子发布 `BASE_DIR/runtime/monitor.json`，供 `GET /api/monitor/summary` 读取。首次部署或本地调试时可手动运行；日常更新由下方 APScheduler 任务执行。单项失败保留原样本及时间，其他项继续更新；具体结构见[服务器监控快照](./cache.md#服务器监控快照)。

```bash
python manage.py refresh_monitor_snapshot
```

生产环境需部署 `default.conf` 中的精确路径配置，并执行 `nginx -t` 和 reload。默认文件路径为 `/root/saolei/runtime/monitor.json`；更改部署目录时同步调整 Nginx alias。Nginx worker 需要读取文件及遍历父目录的权限。采样或写入失败时检查 `logs/apscheduler.log`；旧文件不会自动过期，应检查各项采样时间。

### `runapscheduler`

位置：`common/management/commands/runapscheduler.py`

在单一常驻进程中运行 `common/apscheduler.py` 注册的任务：

| 任务 | 频率 | 说明 |
| --- | --- | --- |
| `refresh_monitor_snapshot` | 启动时及每 5 分钟 | 生成统一监控 JSON；单实例执行，错过多次调度时合并执行 |
| `delete_old_job_executions` | 每天 00:03 | 清理超过 7 天的 APScheduler 执行记录 |
| `delete_newest_queue` | 每天 01:08 | 按上传时间保留最新 1000 条，允许两次清理之间暂时超过上限 |
| `delete_freezed_video` | 每天 01:28 | 删除 7 天以前冻结状态的录像 |
| `delete_overdue_emailverifyrecord` | 每周一 01:03 | 清理 1 小时以前的邮箱验证码 |
| `delete_overdue_captcha` | 每周一 01:05 | 清理过期图形验证码 |
| `delete_overdue_tasks` | 每周一 01:10（`settings.TIME_ZONE`，当前为 UTC） | 按 `config/common.py` 的保留期限分批清理成功的后台任务，删除总量不限 |
| `refresh_tournament_score_reference` | 每年 1 月 1 日 00:00 UTC | 将当前积分 zset 整体折算到新年年初，并原子更新锚点；数据库不变 |

年度锚点任务在调度器启动时也会执行一次幂等检查，补上跨年停机或错过的更新；同一年不会重复衰减。

后台任务清理与管理员接口 `POST /api/common/tasks/cleanup` 共用服务；接口每类任务每次最多删除 200 条，定时任务则以每批 200 条循环删除所有符合条件的记录。失败、待执行、执行中和未配置的任务均保留。

保留期限以 `config/common.py` 为准。其中 LSF 刷新任务 `speedranking.top.tasks.task_refresh_soft_ranks` 的成功记录（含合并后正常跳过的记录）保留 7 天，由下一次周清理删除。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--pidfile` | `logs/apscheduler.pid` | 用于防止重复启动 APScheduler 进程的 pidfile 路径 |

```bash
python manage.py runapscheduler
```

只运行一个 APScheduler 进程。修改任务注册或清理配置后，重启 `runapscheduler` 生效。

### 生产启动与日志

`start.sh` 在数据库迁移后通过 `nohup bash run_background.sh` 启动两个服务，退出后不会自动重启。环境变量如下：

| 服务 | 开关（设为 `0` 跳过） | 启动延迟（秒） | nice 值 | 轮询间隔（秒） | 日志 |
| --- | --- | --- | --- | --- | --- |
| APScheduler | `START_APSCHEDULER`，默认 `1` | `APSCHEDULER_START_DELAY`，默认 `10` | `APSCHEDULER_NICE`，默认 `10` | — | `logs/apscheduler.log` |
| worker | `START_DB_WORKER`，默认 `1` | `DB_WORKER_START_DELAY`，默认 `20` | `DB_WORKER_NICE`，默认 `10` | `DB_WORKER_INTERVAL`，默认 `2` | `logs/db_worker.log` |

### 后台进程退出排查

`run_background.sh` 记录启动时间、launcher/Python PID、退出状态和信号。`137/KILL` 不能单独证明 OOM，worker 收到 `SIGTERM` 也可能以 `0` 退出，需结合此前日志判断。若 launcher 也被杀死，退出记录可能缺失。

应用日志还可能写入 `logs/root.log` 和各 APP 日志；服务日志为空时也应检查这些文件及系统日志：

```bash
tail -n 100 logs/apscheduler.log
tail -n 100 logs/db_worker.log
sudo journalctl -k --since today --no-pager | grep -Ei 'oom|out of memory|killed process|segfault'
sudo journalctl -u systemd-logind --since today --no-pager
```
