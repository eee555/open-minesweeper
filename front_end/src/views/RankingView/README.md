# 排行榜 URL

大榜通过路径选择，内部选项通过 query 保存。项目使用 hash history，以下路径放在浏览器 URL 的 `/#` 后。

| 路径 | 内部选项 | 默认值 |
| --- | --- | --- |
| `/ranking/speed/lsf` | `sort`：`lsf`、`std:b/i/e/sum`、`nf:b/i/e/sum` | `lsf` |
| `/ranking/speed/top` | `sort`、`detail`：等级 `b/i/e` + 指标 `t/b/s`；`nf` | 排序 `et`，明细随排序，普通榜 |
| `/ranking/speed/saolei` | `sort`：`bt/bb/it/ib/et/eb/sumt/sumb`；`nf` | `sumt`，普通榜 |
| `/ranking/speed/strict_ng` | `sort`：`bt/bb/it/ib/et/eb/sumt/sumb`；`nf` | `sumt`，普通榜 |
| `/ranking/speed/pb` | `level`：`b/i/e`；`bv`；`nf` | `b`、`1`，普通榜 |
| `/ranking/speed/collection` | `sort`：`collection:{b/i/e/sum}:{count/probability/asb}`；`nf` | `collection:sum:count`，普通榜 |
| `/ranking/speed/skill_tt` | `view`：`overview/skill_b/skill_i/skill_e/tt_b/tt_i/tt_e`；`sort`：`{skill/typical_time}:{b/i/e/sum}:{total/s1…s11}`；`nf` | `overview`、`skill:sum:total`，普通榜 |
| `/ranking/efficiency/thrp` | `sort`：`b/i/e/sum/e_nf` | `sum` |
| `/ranking/efficiency/nf-ioe` | `sort`：`b/i/e/sum` | `sum` |
| `/ranking/efficiency/tpe` | `sort`：`i/e/sum`，升序 | `sum` |
| `/ranking/minigame/left-click` | `sort`：本游戏 9 个榜单 key 之一 | `left-click-b-50-v1` |
| `/ranking/minigame/multi-touch` | `sort`：本游戏 9 个榜单 key 之一 | `multi-touch-b-50-v1` |
| `/ranking/minigame/flag-chord` | `sort`：本游戏 2 个榜单 key 之一 | `flag-chord-b-v1` |
| `/ranking/minigame/missing-cell` | `sort`：本游戏 3 个榜单 key 之一 | `missing-cell-b-v1` |
| `/ranking/minigame/reaction` | `sort`：本游戏 6 个榜单 key 之一 | `reaction-b-25-v1` |
| `/ranking/density` | `level`：四种密度配置的 code | `c8_8_40` |
| `/ranking/tournament/overall` | `sort`：`score_current/score_total/gsc_total/weekly_total/weekly_eff_total` | `score_current` |
| `/ranking/tournament/gsc` | `sort`：`gsc_total/gsc_best` | `gsc_total` |
| `/ranking/tournament/weekly` | `sort`：`weekly_total/weekly_classic_best` | `weekly_total` |
| `/ranking/tournament/weekly-eff` | `sort`：`weekly_eff_total/weekly_eff_best` | `weekly_eff_total` |

所有页面支持 `page`（从 1 开始，默认 1）和 `page_size`（20、50、100，默认 20）。`nf=1` 或 `nf=true` 选择 NF，控件写回使用 `1/0`。无效、重复或越界参数回退到相应默认值；PB 的 BV 范围沿用选择器限制。

示例：

```text
/#/ranking/speed/pb?level=e&bv=150&nf=1&page=2&page_size=50
/#/ranking/speed/collection?sort=collection:sum:probability&nf=1
/#/ranking/speed/skill_tt?view=tt_e&sort=typical_time:e:s3&nf=1
/#/ranking/speed/top?sort=eb&detail=es&nf=1
/#/ranking/speed/lsf?sort=nf:sum
/#/ranking/density?level=c24_30_200
/#/ranking/tournament/weekly?sort=weekly_classic_best
```

`useRankingQuery.ts` 统一解析和同步 query，不改变后端 API。控件操作使用 `router.push`，支持复制链接、重载和浏览器前进/后退。筛选、排序或每页条数变化时重置到第一页；恢复历史 URL 时保留其页码。top 单独切换 `detail` 不重置页码、不请求榜单，切换排序时同步明细。`collection` 与 `skill_tt` 的排序键在解析期用静态 field 列表校验；`skill_tt` 的排序键还必须属于当前子页，否则回退到该子页默认排序，不把非法字符串交给后端。

缓存但未激活的页面不响应其他大榜的 query。配色仍是全局 localStorage 设置，不放进 URL。

比赛排行榜通过 select 切换总榜、GSC、竞速打卡赛和效率打卡赛。旧 `/ranking/tournament` 入口跳转总榜并保留 query，再按该页可用列校验。各 total 降序、best 升序；best 与对应届号分列，不单独按届号排序。GSC 和竞速 best 沿用前端整数解码，效率 best 直接显示原始浮点成绩及独立年/周字段，三位小数只用于展示。当前积分仍按 `globalNow` 衰减，Redis 顺序使用年度统一锚点。默认值不入对应榜，切换排序可能改变总人数；`weekly_classic_total` 仍在后端维护，但不重复展示。

效率分类使用 select 切换 Thrp/NF IOE，默认 Thrp；两榜共用刷新、配色与随选择切换的帮助提示。NF IOE 显示三位小数，满分时括号显示比较用时（秒），sum 满分只显示高级用时；配色复用 IOE 色阶，sum 按值除以 3 上色。单项可预览录像，sum 不生成链接，不设置 NF 开关。

小游戏从 `/api/minigame/rankings` 获取固定列顺序；每页一次请求返回整组全部列。反应训练每级两列，`density` 为 `'25'`／`'50'` 并显示百分比；左键和多指每级三列并显示密度分数，Time／CES 切换仅适用于这两个游戏。无成绩显示 `--`，点击表头选择排序列。成绩链接前往 `/minigame/{game}?player={player_id}&key={mode_key}`，`key` 去掉游戏前缀，如 `b-50-v1`，播放对应玩家该榜当前最佳录像；日期 title 沿用项目格式。小游戏尚无配色，独立预留 `MinigameColorScheme(ranking, score)` 样式函数和禁用的配色按钮，不套用竞速榜色阶。
