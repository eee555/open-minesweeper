# 小游戏成绩与排行榜

网站登录且未封禁的玩家成功通关后，可点击按钮提交用时与回放；离线版只保存本地历史。玩法见[使用指南](../../../vitepress_doc/zh/guide/minigames.md)，前端结构、回放和离线构建见[前端开发文档](../../../front_end/local-minigame/README.md)。

## 约定与取舍

这是娱乐训练排行，优先简单实现和查询性能。接受客户端成绩及回放，不检测作弊。

- 提交需要登录且未封禁，无需实名、扫雷档案或账号关联；排行和个人成绩公开查询。
- `MiniGameBestScore` 每人每榜保存一条最佳成绩及对应回放，以 `(player, ranking_key)` 为唯一约束；顺序提交只接受严格改善，同分或更差不更新成绩、达成时间及回放。
- 允许并发提交丢失成绩或覆盖较好成绩，也接受缓存偶发偏差；使用普通读取、比较和保存，不加玩家行锁。
- 名次直接使用 Redis 位置，同分按 Redis 默认成员顺序展示，不维护并列名次或 tiebreaker。
- 使用永久榜；规则变化影响可比性时新建榜单 key，保留旧榜数据。

## 游戏分组

[utils.py](./utils.py) 的 `GAME_RANKINGS` 定义分组和列顺序，`RANKINGS` 提供白名单。榜单称为 `ranking`，标识为 `ranking_key`，前端为 `rankingKey`；`board` 仅指实际棋盘。

| 游戏 key | 列数 | 榜单 key |
| --- | --- | --- |
| `left-click` | 9 | `left-click-{level}-{density}-v1`；`level=b/i/e`，`density=50/75/87.5` |
| `multi-touch` | 9 | `multi-touch-{level}-{density}-v1`；参数同左键训练，使用独立榜单 |
| `flag-chord` | 2 | `flag-chord-b-v1`、`flag-chord-i-v1`；分别为 4 题、15 题，数字均为 1 |
| `missing-cell` | 3 | `missing-cell-b-v1`、`missing-cell-i-v1`、`missing-cell-e-v1`；连续完成 10 局 |

当前成绩均为整数毫秒，越小越好，范围为 `1..MAX_SAFE_INTEGER`；上限在 [global_settings.py](../config/global_settings.py) 定义为 `2**53 - 1`，兼容 JavaScript Number 和 Redis ZSET 的安全整数范围。配置也支持降序比较与读取。

分类查询按组内任意一列排序，只包含该列有成绩的玩家，始终返回本组全部列：左键和多指各 9 列、标双 2 列、漏雷 3 列，缺项为 `null`。`count` 按排序列统计。

## API

路径均无末尾斜杠，Schema 和参数详情由 Ninja API 文档生成：

| 方法与完整路径 | 输入 | 输出 |
| --- | --- | --- |
| `GET /api/minigame/rankings` | 无 | 游戏分组、固定列顺序及榜单配置 |
| `POST /api/minigame/{ranking_key}/score` | 表单 `score` 和 `replay`（JSON 对象字符串），归属取自登录用户 | `{improved, record}`，不回传回放 |
| `GET /api/minigame/{game}/replay` | 查询参数 `player=玩家ID, key=模式key`（如 `b-50-v1`） | 对应最佳成绩的原始 7z，`X-Minigame-Score` 为匹配的整数毫秒成绩 |
| `GET /api/minigame/{game}/rank` | `sort=榜单key, start=0, end=20` | `{count, players}`，每行包含名次与完整成绩列 |
| `GET /api/minigame/{game}/player/{player_id}` | 路径参数 | 该玩家本组全部成绩及各列名次 |

分页为左闭右开区间，最多 100 人。`sort` 默认使用本组第一列；空榜或空区间返回空列表，现存用户没有成绩时各列为 `null`。

未知游戏、榜单或用户返回 `404`，跨游戏排序或非法输入返回 `422`，关闭提交的榜单返回 `409 ranking_closed`。业务错误为 `{code, detail}`；权限、限流和表单解析沿用项目格式。提交按用户限流 `60/m`，公开查询按 IP 限流 `5/s`。

回放公开读取，`game` 来自路径，查询参数 `key` 只包含模式部分，二者组合为完整的 `ranking_key`；数据库及 Redis 的榜单标识不变。缺失或空回放返回 `404 replay_not_found`。一次数据库查询读取成绩及 7z，不解包、不重新压缩、不访问 Redis。响应类型为 `application/x-7z-compressed`，设置 `Content-Encoding: identity` 跳过默认 GZipMiddleware，`Cache-Control: no-transform` 防止中间层再次转换，并公开 `X-Minigame-Score` 响应头供播放器读取。

## 持久化与缓存

[models.py](./models.py) 保存最佳成绩、服务端达成时间及 `replay_archive` BinaryField，`(ranking_key, score, id)` 索引用于回源排序。[services.py](./services.py) 负责提交与查询，[cache.py](./cache.py) 只负责缓存，不引用服务。缓存结构复用项目 [THRP](../effranking/thrp/cache.py) 与[自定义排行](../customranking/cache.py) 的 ZSET、Hash 和 pipeline 方案。

回放使用前端本地历史相同的 v1 数据：左键、标双为 `{version: 1, cellSize, initialBoard, events, specialEvents}`；漏雷为 `{version: 1, rounds: [{board, target, timeMs}, ...]}`。棋盘压缩保存，鼠标事件使用整数像素坐标、数组及差分编码。接口仍接收 JSON 对象字符串，新建或改善成绩时由 [archive.py](./archive.py) 使用 py7zr 压缩为只含 UTF-8 `replay.json` 的 7z，再与成绩一起写入 BinaryField；使用 LZMA2、级别 1、1 MiB 字典。不重演或校验游戏规则。回放仅存数据库，不进入 Redis；排行榜及个人成绩响应均不包含回放，缓存重建和数据库回源查询用 `defer('replay_archive')` 排除二进制字段。

载荷及前端历史迁移规则见回放数据格式 v1 的[中文标准](../../../vitepress_doc/zh/guide/development/minigame-replay-format.md)及[英文标准](../../../vitepress_doc/en/guide/development/minigame-replay-format.md)。后端历史回放已完成压缩迁移，旧 `replay` JSONField、一次性迁移命令及其转换代码已移除。

多指九榜开放提交，沿用相同的登录权限、最佳成绩更新和缓存逻辑。多指方向仅为本地显示设置，高级回放及事件坐标固定为 16×30，格式见上述标准；持久化沿用现有模型，无需结构迁移。

每榜三个固定键，均无 TTL：

| 键 | 类型 | 内容 |
| --- | --- | --- |
| `minigame:rank:v1:{ranking_key}` | ZSET | 玩家 ID → 原始整数成绩 |
| `minigame:detail:v1:{ranking_key}` | Hash | 玩家 ID → `{score, achieved_at}` JSON |
| `minigame:ready:v1:{ranking_key}` | String | `1` 表示整榜初始化完成 |

- 缺初始化标记时按榜从数据库加载全部成绩；空榜也设置标记，单条上传不设置。因此空榜及不足 100 人的榜也能完全命中缓存。
- 分类查询用两轮 pipeline 读取初始化标记、人数、页内玩家及本组全部成绩；已初始化后不查询成绩表。缺失明细直接返回 `null`，不逐项回源。
- 新建或改善成绩后通过 `on_commit` 更新 ZSET 与 Hash。同分或更差不写缓存；Redis 写入失败记录日志，保留已提交成绩及成功响应。
- [signals.py](./signals.py) 在删除事务提交后移除成员，覆盖 Admin 删除及用户级联删除；保留初始化标记，使删空的榜继续命中缓存。
- Redis 读取失败时整次请求降级：分类查询按排序列分页，再批量补全其他列；个人成绩批量读取，名次允许为 `null`。
- 普通读取、提交及重建之间不保证快照一致性。缓存偏差可用重建命令恢复；Admin 提供只读查询与删除。

运维索引：[缓存与内存统计](../../../vitepress_doc/zh/guide/development/cache.md)、[删除信号](../../../vitepress_doc/zh/guide/development/signals.md)、[管理命令](../../../vitepress_doc/zh/guide/development/management-commands.md)。23 榜共 69 个固定键，由 `MiniGameRankingCache.keys` 提供给监控，不扫描 keyspace。

## 检查与维护

在 `back_end/saolei` 运行：

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test minigame monitor.test_server_metrics
.\.venv\Scripts\python.exe -m flake8 minigame saolei/api.py monitor/cache.py monitor/test_server_metrics.py
```

迁移文件按项目约定由 Git 忽略，部署脚本 `start.sh` 自动执行 `makemigrations` 和 `migrate`。历史数据压缩迁移已完成，本次结构迁移仅删除旧 `replay` 列，保留 `replay_archive`、成绩及达成时间。缓存首次查询自动初始化，也可用 `manage.py rebuild_minigame_ranks [--ranking-key key]` 预热或恢复。

网站地址、URL 查询参数及配色扩展接口见[排行榜开发说明](../../../front_end/src/views/RankingView/README.md)；前端检查与由用户执行的 Cypress 命令见[前端开发文档](../../../front_end/local-minigame/README.md#验证)。
