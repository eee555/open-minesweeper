# 排行榜 URL

大榜通过路径选择，内部选项通过 query 保存。项目使用 hash history，以下路径放在浏览器 URL 的 `/#` 后。

| 路径 | 内部选项 | 默认值 |
| --- | --- | --- |
| `/ranking/speed/lsf` | `sort`：`lsf`、`std:b/i/e/sum`、`nf:b/i/e/sum` | `lsf` |
| `/ranking/speed/top` | `sort`、`detail`：等级 `b/i/e` + 指标 `t/b/s`；`nf` | 排序 `et`，明细随排序，普通榜 |
| `/ranking/speed/saolei` | `sort`：`bt/bb/it/ib/et/eb/sumt/sumb`；`nf` | `sumt`，普通榜 |
| `/ranking/speed/pb` | `level`：`b/i/e`；`bv`；`nf` | `b`、`1`，普通榜 |
| `/ranking/efficiency/thrp` | `sort`：`b/i/e/sum` | `sum` |
| `/ranking/minigame/left-click` | `sort`：本游戏 9 个榜单 key 之一 | `left-click-b-50-v1` |
| `/ranking/minigame/multi-touch` | `sort`：本游戏 9 个榜单 key 之一 | `multi-touch-b-50-v1` |
| `/ranking/minigame/flag-chord` | `sort`：本游戏 2 个榜单 key 之一 | `flag-chord-b-v1` |
| `/ranking/minigame/missing-cell` | `sort`：本游戏 3 个榜单 key 之一 | `missing-cell-b-v1` |
| `/ranking/density` | `level`：四种密度配置的 code | `c8_8_40` |
| `/ranking/tournament` | `sort`：七种比赛积分字段名 | `score_current` |

所有页面支持 `page`（从 1 开始，默认 1）和 `page_size`（20、50、100，默认 20）。`nf=1` 或 `nf=true` 选择 NF，控件写回使用 `1/0`。无效、重复或越界参数回退到相应默认值；PB 的 BV 范围沿用选择器限制。

示例：

```text
/#/ranking/speed/pb?level=e&bv=150&nf=1&page=2&page_size=50
/#/ranking/speed/top?sort=eb&detail=es&nf=1
/#/ranking/speed/lsf?sort=nf:sum
/#/ranking/density?level=c24_30_200
/#/ranking/tournament?sort=weekly_classic_total
```

`useRankingQuery.ts` 统一解析和同步 query，不改变后端 API。控件操作使用 `router.push`，支持复制链接、重载和浏览器前进/后退。筛选、排序或每页条数变化时重置到第一页；恢复历史 URL 时保留其页码。top 单独切换 `detail` 不重置页码、不请求榜单，切换排序时同步明细。

缓存但未激活的页面不响应其他大榜的 query。配色仍是全局 localStorage 设置，不放进 URL。

小游戏从 `/api/minigame/rankings` 获取固定列顺序；每页一次请求返回整组全部列。无成绩显示 `--`，点击表头选择排序列。成绩链接前往 `/minigame/{game}?player={player_id}&key={mode_key}`，`key` 去掉游戏前缀，如 `b-50-v1`，播放对应玩家该榜当前最佳录像；日期 title 沿用项目格式。小游戏尚无配色，独立预留 `MinigameColorScheme(ranking, score)` 样式函数和禁用的配色按钮，不套用竞速榜色阶。
