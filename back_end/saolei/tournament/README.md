# tournament TODO

## 竞速打卡赛模式扩展

TODO：按[竞速赛制首次上线步骤](../../../vitepress_doc/zh/guide/development/management-commands.md#weekly-formats-deployment)完成生产迁移、用户汇总刷新及缓存重建，并由用户运行相关 Cypress 组件/E2E 测试。

## 效率打卡赛与排行榜拆分

TODO：部署前备份并审计竞速打卡赛 `(year, week)` 重复，沿用服务器自动生成迁移的方式执行 `makemigrations tournament` 与 `migrate`。

TODO：暂停相关写入和 worker，执行 `rebuild_tournament_cache`、`rebuild_tournament_user_cache`，核对总积分、分项积分、全部积分 zset 及效率 best 年/周。检查已排队的旧结算任务不早于原 `end_time + 1 小时`，再恢复 worker。

TODO：由用户运行相应 Cypress 组件/E2E 测试，验收效率计分、双报名、四榜切换、过期报名重置及异步取消资格。业务规则见[打卡赛指南](../../../vitepress_doc/zh/guide/weekly-tournament.md)，缓存与任务边界见[缓存开发文档](../../../vitepress_doc/zh/guide/development/cache.md)。

## 比赛录像删除与成绩一致性

TODO：补齐其他录像删除入口的比赛警告、主办方私信，以及 GSC/竞速 best 的提交后缓存发布。失效预览、赛种接入要求等后续方案见 [比赛录像删除与成绩一致性](./VIDEO_DELETION_PLAN.md)。

## GSC 实时榜缓存

TODO: 如果未来需要比赛期间展示实时榜，可以再单独设计每个比赛的成绩缓存，例如使用 hash 存三组成绩数组、zset 存总成绩：

- `tournament:normal:gsc:{tournament_id}:scores`
- `tournament:normal:gsc:{tournament_id}:rank`

## 比赛积分系统

TODO: 奖金积分暂不实现，但需要预留设计：

- 奖金积分以后使用单独字段或单独发放记录，不进入 `rank_score`。
- 奖金金额与积分的换算规则、币种和管理员录入入口仍是争议核心，暂无结论。
- 在用户文档中继续标记“暂不支持”，直到后端和前端都完成。

TODO: 在用户资料页补充比赛积分展示，等资料摘要结构设计后再实现：

- 用户资料页需要展示当前比赛积分、历史总积分、GSC/竞速/效率拆分积分和最好成绩。
- `TournamentUser` 更新后如果影响用户资料摘要，需要同步考虑 `userprofile` 缓存/批量接口的失效策略。

## GSC 历史成绩补录

TODO：部署 [GSC 历史成绩补录](../../../vitepress_doc/zh/guide/development/gsc-history-import.md) 前人工审计旧的手工成绩及匿名记录，并设置 `manual_scores`，不按无录像自动推断来源；在实际服务器测量每批最多 10 条的完整请求耗时（含提交回调），本地性能不保证生产 2 秒时限。

TODO：由用户运行新增 GSC 历史补录 Cypress 组件/E2E 测试，核验标识多选、录像重试、CSV 分批、手工汇总，以及主办方异步取消资格后重新补录。

## 历史比赛列表同步计划

TODO: 这类列表展示问题优先参考 `userprofile` app 的缓存同步方式解决，而不是优先重构 Django 多表继承实现。前端应把比赛基础信息缓存在 IndexedDB 中，后端提供列表索引、批量详情和更新检查接口。

推荐接口形态：

- TODO: `GET /api/tournament/list`
  - 返回用于当前列表页的轻量索引，长期应支持分页、状态过滤、赛种过滤和排序。
  - 响应只包含 `id`、必要排序字段和可选的 `date_updated`，不负责返回完整 `TournamentInfo`。
- TODO: `GET /api/tournament/infobulk?ids=1,2,3`
  - 按 id 批量返回完整 `TournamentInfo`。
  - 后端可以在这个小批量范围内处理子类定向；短期即使仍使用单条定向，压力也远小于全量列表。
- TODO: `GET /api/tournament/infoupdated?since=123456789`
  - 返回自指定时间戳以来发生变化的比赛 id，用于前端删除 IndexedDB 中的过期缓存。

TODO: 为支持更新检查，`Tournament` 父表需要增加类似 `UserProfile.date_updated` 的 `DateTimeField(auto_now=True)`。如果 GSC 子表字段变化会影响 `TournamentInfo`，写路径必须同步触发父表更新时间更新。例如 `order`、`token`、`start_time`、`end_time`、`state`、`host` 等字段变化后，前端缓存应能通过 `infoupdated` 感知。

TODO: 前端实现可以复用 `userService.ts` 的设计：

- 新增 IndexedDB store，例如 `tournament-info`，主键为 `id`，row schema 与 `TournamentInfo` 保持一致。
- `fetchTournament(id)` 优先读取 IndexedDB，缓存缺失时进入批量请求队列。
- 同一 tick 或短延迟窗口内的多个缺失 id 合并为一次 `infobulk` 请求。
- 按配置周期请求 `infoupdated`，删除已更新比赛的本地缓存；首次 `lastUpdate=0` 时直接清空本地比赛缓存，避免请求全量更新 id。
- IndexedDB 不可用时降级为网络请求。

TODO: 迁移后，`get_tournament_list` 可以逐步退化为轻量索引接口，或由新的 `/list` 接口替代。完整比赛信息只在用户实际需要展示对应比赛时通过 `infobulk` 获取。模型层的子类定向问题因此被限制在小批量详情接口内部，不再成为全量列表的性能瓶颈。

## 暂不实现的接口

- TODO: `hide_videos_for_tournament(tournament)` 暂非必要。
  - 新上传录像仍由当前单条 `VideoModel` 创建信号路径处理。
  - 如果未来需要补录或批量隐藏比赛录像，再按同样原则设计批处理。
- TODO: `refresh_ongoing_tournament_for_range(start_id, end_id)` 暂非必要。
  - 数据修复需求出现后再实现分段重算。

## 待处理问题

- TODO: 明确比赛取消、状态回滚时应在哪些入口调用 `reveal_videos_for_tournament`。
