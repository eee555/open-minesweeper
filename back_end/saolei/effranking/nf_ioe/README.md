# NF IOE 榜

## 规则

- 大榜名为 `nf_ioe`，小榜为 `b/i/e/sum`，均越大越好。
- 准入：初、中、高级，STD、OFFICIAL、非隐藏比赛录像，`right_ce = 0`，不设最低 BV。
- 使用 `VideoModel.ioe` 原始值，即 `bv / (left + right + double)`，不以有效点击数代替实际点击数。缺失 IOE 的录像不入榜。
- NF IOE 为正数，数学上限为 1，可达到；这不是人为设置的数值截断。
- 每级别取个人最高 IOE。未满分时不比较用时；满分时用时越小越好。仍相同则不设置进一步 tie-breaker，同分候选可保留现有录像。
- 每级别仅保存一条录像，不沿用高级 NF Thrp 的满分局数或录像列表。
- `sum` 为三项个人最佳原始 IOE 之和，缺项按 0，至少有一项才入榜。
- `sum < 3` 不设置 tie-breaker；`sum = 3` 只比较所选高级录像的用时，越小越好。
- 不设置进一步 tie-breaker 的用户按 Redis member 顺序排列；重建时同分录像任选一条，不影响排行成绩。

## Score 编码

统一使用整数毫秒，`T` 复用录像用时上限 `MAX_TIMEMS = 99_999_999`。

业务 score 越大越好：

```text
单级别：
IOE < 1：score = IOE
IOE = 1：score = 1 + T - timems

S = b.IOE + i.IOE + e.IOE
总和：
S < 3：score = S
S = 3：score = 3 + T - e.timems
```

- 沿用当前效率榜的升序读取约定，Redis 写入业务 score 的负值。
- 满分单项的业务 score 至少为 1，满分总和的业务 score 至少为 3，分别始终优于未满分纪录。
- 用时为 0 或达到模型上限时公式仍有效；满分分支最大为 `100_000_002`，整数可由 Redis double 精确表示。
- 未满分分支直接使用原始浮点值，不量化 IOE，也不编码上传时间。
- sum 必须先加原始 IOE，不能相加三个单项的编码 score。
- score 仅用于排序，查询成绩始终读取 hash，不从 zset 反解原始值。

## 缓存

一个 hash、四个 zset，与 Thrp 分开存储：

| Key | 内容 |
| --- | --- |
| `effranking:nf_ioe:records` | 用户 id 对应完整 `b/i/e` 个人纪录 JSON |
| `effranking:nf_ioe:{stat}` | `stat = b/i/e/sum`；member 直接使用用户 id |

hash 示例：

```json
{
  "b": {"value": 0.95, "video_id": 123, "timems": 8000},
  "i": null,
  "e": {"value": 1, "video_id": 456, "timems": 45000}
}
```

`video_id` 为 `VideoModel.id`。不重复保存 sum、上传时间或达成局数；满分 sum 的高级用时直接取 `e.timems`。查询返回完整个人纪录，不按当前排序项裁剪。

## 刷新与维护

监听实际点击 `left/right/double`、BV、用时及资格字段。满分单项比较用时，满分 sum 只比较高级用时；修改初、中级用时不会改变 sum 排序。单项修复回源，sum 修复仅根据缓存三项重算。

共用更新链路、事务边界和重建用法见[效率排行榜 README](../README.md)，前端展示与路由见[排行榜 README](../../../../front_end/src/views/RankingView/README.md)。
