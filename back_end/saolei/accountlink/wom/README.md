# WOM 公开成绩与累计统计

玩家公开资料通过只读 HTTP 服务 `https://api.lockhart.ren/profile/{user_id}` 获取：服务端负责与 minesweeper.online 的连接、协议与重连，本站只发一次带令牌的 GET，再做字段转换。早期实现是进程内的 `wom-api` 客户端，2026-10 已移除。

站点保留原有成绩字段，并额外保存 22 个公开成绩与累计统计字段。不收录库存（`honour`、`minecoin`、`gem`、`coin`、`arena_ticket`、`equipment`、`part`）、用户名、国家、物品明细或完整原始响应。

## 读取和持久化

调用链：`accountlink/services.py::update_account` → `update_wom_account` → `wom/client.py::fetch_wom_profile` → `GET /profile/{user_id}`。

公开资料不能证明账号归属，账号关联仍走人工验证。同步是同步阻塞调用（`http.client`），不需要 `asgiref.sync.async_to_sync`。

配置在 `saolei/settings.py`：

| 设置 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `WOM_API_BASE_URL` | `WOM_API_BASE_URL` | `https://api.lockhart.ren` | 服务地址 |
| `WOM_API_TOKEN` | `WOM_API_TOKEN` | 空 | 36 位令牌，只放服务端环境变量，不下发前端 |
| `WOM_API_TIMEOUT` | `WOM_API_TIMEOUT` | `6` | 单次请求超时（秒） |

重试策略是 `wom/client.py` 里的常量：最多 `ATTEMPTS = 2` 次、退避上限 `MAX_RETRY_DELAY = 2` 秒；配合 6 秒超时，整体留在前端 20 秒请求超时之内。

只重试 `429`（入口限速，响应体是 nginx 的 HTML）、`502 connection|timeout|error`、`503 busy`、`504` 和网络异常；`400`、`401`、`502 protocol` 重试无意义，直接失败。令牌缺失时不发请求，直接失败并记日志。

## 超时预算

四层上限必须逐层递增，改动任何一层都要同步检查其余三层：

| 层 | 上限 | 位置 |
| --- | --- | --- |
| 客户端 | 总预算 10s（看门狗到点 shutdown 连接，建连/等响应头/读 body 都能被打断）；单次 6s × 最多 2 次，退避上限 2s | `wom/client.py` |
| nginx | 18s | `default.conf`：`/accountlink/update/`、`/api/accountlink/verify/` 两个精确匹配 |
| uWSGI | 90s（这两条路径跳过 `harakiri:10`） | `uwsgi.ini` 的 route 例外 |
| 前端 | 20s | `front_end/src/http.ts` 的 axios 超时 |

客户端用标准库 `http.client` 而非 `requests`：`requests` 的 `timeout` 只约束单次读的空闲时间，且调用一旦阻塞到等响应头就无法从外部取消。这里自己持有 socket，另起一个定时线程在总预算耗尽时 `shutdown()`，因此 10s 是硬上限，给 nginx 的 18s 留足余量。

nginx 默认的 `uwsgi_read_timeout 2` 不够：单次请求就可能 2–3 秒。网关必须是最后超时的那一层，这样应用才能返回 JSON 错误而不是网关 502/504。

## 错误映射

| 情况 | category |
| --- | --- |
| 请求超时、`504`、`502 timeout` | `timeout` |
| `4xx`、`429/502/503` 重试耗尽、网络异常 | `requestexception` |
| 响应不是 JSON、结构或身份与关联账号不符 | `indexerror` |

`wom/utils.py::normalize_wom_profile` 先校验玩家 ID、整数统计和成绩结构，全部转换成功后才生成更新字段；保存由调用方完成并更新 `update_time`。失败不写库，旧资料保留。日志只记玩家 ID、HTTP 状态码和错误类型，不记令牌。

## 字段转换

`stat` 指全历史 `response['userStat']`，不混入 `seasonUserStat`。

| 本站字段 | WOM 数据及转换 |
| --- | --- |
| `trophy` | `stat.score` |
| `experience` | `stat.exp` |
| `arena_point` / `max_difficulty` / `win` | `stat.arenaPoints` / `stat.diff` / `stat.winsAll` |
| `last_season` | 当前月赛季 ID 转编号：`id - 24192 + 1`；0 为无记录，低于 10000 的旧编号保留，未知编码报错 |
| `b_t_ms` / `i_t_ms` / `e_t_ms` | `timeResults['1'/'2'/'3'].duration`，已是毫秒 |
| `b_ioe` / `i_ioe` / `e_ioe` | `effResults['1'/'2'/'3'].eff100`，保留整数百分比精度：`((eff100 + 50) // 100) / 100` |
| `b_mastery` / `i_mastery` / `e_mastery` | `stat.mastery1` / `mastery2` / `mastery3` |
| `b_winstreak` / `i_winstreak` / `e_winstreak` | `stat.ws1` / `ws2` / `ws3` |
| `b_endurance_ms` / `i_endurance_ms` / `e_endurance_ms` | `86400000 - stat.end1/end2/end3`；原值 0 或 null 时存 86400000 |
| `b_ng_t_ms` / `i_ng_t_ms` / `e_ng_t_ms` | `timeResults['11'/'12'/'13'].duration`，无猜 PB |
| `b_win` / `i_win` / `e_win` | `stat.wins1` / `wins2` / `wins3`，标准胜场 |
| `b_ng_win` / `i_ng_win` / `e_ng_win` | `stat.wins11` / `wins12` / `wins13`，无猜胜场 |
| `experience_total` | `stat.expAll`，累计获得经验（区别于当前 `exp`） |
| `minecoin_total` | `stat.coinsAll`，累计雷币（区别于库存 `coins`） |
| `gem_total` / `arena_coin_total` | `stat.gemsAll` / `stat.arenaCoinsAll` |
| `game_count` | `stat.games` |
| `win_nf` | `stat.winsNf`；无旗（NF）与无猜（NG）不是同一种模式 |
| `play_time_ms` / `arena_play_time_ms` | `stat.timeAll` / `stat.arenaDuration` |
| `bbbv_total` | `stat.bbbvAll` |
| `season_count` | `stat.seasons` |

字段类型：累计用时用 `PositiveBigIntegerField`（32 位只够 49.7 天），计数用 `PositiveIntegerField`，赛季数用 `PositiveSmallIntegerField`。转换时按字段范围校验：普通计数 ≤ `2**32 - 1`，赛季数 ≤ `2**16 - 1`，累计用时 ≤ `2**63 - 1`，越界报解析错误。

## 空值与缺失

- 某难度无记录时对应键不存在 → 存 null；耐力存 `86400000`，前端显示 `24:00:00`。
- `userStat` 为 null：仅在 `noUserStatExp` 是有效非负整数时更新经验，其余字段保留；`-1` 表示不可读，报错。
- 顶层记录表被省略：保留旧 PB；明确返回空记录表：清除该表 PB。
- 有效计数 0 保留 0，不把 0 当缺失。

## 测试

`test/tests.py` 覆盖三块：字段映射（空值、单位、范围、64 位）、HTTP 客户端（令牌、重试、错误分类）、真实数据库保存与 API Schema。客户端测试分两层：决策逻辑用 `unittest.mock` 替换 `_request`；超时与取消行为用本地 `ThreadingHTTPServer` 起真实服务验证（滴流响应头、滴流响应体、发一半停住）。fixture `test/public_profile.json` 只保留字段与 ID；在线成绩会变，不要断言实时资料的固定值。

运行：`python manage.py test accountlink.wom.test --keepdb`。

## 依赖与迁移

`requirements.txt` 不含 `wom-api`；`requirements-wheels.txt` 只为 `msgames-api` 固定 wheel。HTTPS 证书用 `certifi` 校验（`requests` 的传递依赖，与仓库其他地方一致）。部署前需在后端进程环境配置 `WOM_API_TOKEN`，未配置时只有该同步功能失败。

`accountlink/migrations/0010`–`0012` 由 `makemigrations` 生成（删除库存列、添加统计列、收紧计数类型、耐力字段非空），项目忽略迁移文件，提交时需 `git add -f`。
