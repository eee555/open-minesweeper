# tournament TODO

## 比赛录像删除与成绩一致性

普通删除已颁奖比赛录像时不立即重算，暂时保留结算成绩、名次、积分及历史最好成绩。显式重算按比赛类型及成绩来源处理：打卡赛和 GSC 录像来源不再计入已删除录像，GSC 手工来源保留录入成绩，但仍参与全场排名和积分更新。每个新赛种或赛制都须提供自己的删除及重算规则。删除前需要比赛相关警告；将来增加私信功能后，普通删除会私信通知受影响比赛的主办方。

现有计分服务已区分 GSC 手工来源与录像来源；站长单个删除 API 已返回受影响比赛 ID 并记录日志警告，隐藏中文页面已提供比赛警告、确认和逐条请求。其他入口的警告、私信以及重算事务和并发控制的完善仍待实现。业务边界、赛种接入要求及后续方案见 [比赛录像删除与成绩一致性](./VIDEO_DELETION_PLAN.md)。

## GSC 实时榜缓存

TODO: 如果未来需要比赛期间展示实时榜，可以再单独设计每个比赛的成绩缓存，例如使用 hash 存三组成绩数组、zset 存总成绩：

- `tournament:normal:gsc:{tournament_id}:scores`
- `tournament:normal:gsc:{tournament_id}:rank`

当前阶段不实现这部分。

## 比赛积分系统

TODO: 奖金积分暂不实现，但需要预留设计：

- 奖金积分以后使用单独字段或单独发放记录，不进入 `rank_score`。
- 奖金金额与积分的换算规则、币种和管理员录入入口仍是争议核心，暂无结论。
- 在用户文档中继续标记“暂不支持”，直到后端和前端都完成。

TODO: 补充积分展示 API 与前端：

先不急着做，等结构继续设计。

- 用户资料页需要展示当前比赛积分、历史总积分、GSC/周赛拆分积分和最好成绩。
- `TournamentUser` 更新后如果影响用户资料摘要，需要同步考虑 `userprofile` 缓存/批量接口的失效策略。

## GSC 历史成绩补录

TODO：部署 [GSC 历史成绩补录](../../../vitepress_doc/zh/guide/development/gsc-history-import.md) 前人工审计旧的手工成绩及匿名记录，并设置 `manual_scores`，不按无录像自动推断来源；在实际服务器测量每批最多 10 条的完整请求耗时（含提交回调），本地性能不保证生产 2 秒时限。

TODO：由用户运行新增 GSC 历史补录 Cypress 组件/E2E 测试，核验标识多选、录像重试、CSV 分批、手工汇总及无录像删除。

## 历史比赛列表同步计划

TODO: 这类列表展示问题优先参考 `userprofile` app 的缓存同步方式解决，而不是优先重构 Django 多表继承实现。前端应把比赛基础信息缓存在 IndexedDB 中，后端提供列表索引、批量详情和更新检查接口。

推荐接口形态：

- TODO: `GET /api/tournament/list`
  - 返回用于当前列表页的轻量索引，长期应支持分页、状态过滤、系列过滤和排序。
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
- TODO: 补充测试：
  - 比赛颁奖后，上万条录像不逐条触发 `VideoModel.save()`。
  - 录像从比赛恢复普通后，队列缓存恢复。
  - 录像从比赛恢复普通后，pluck 纪录刷新。
- 比赛批量公开调用 `speedranking.services.add_videos_to_speed_ranks`；用户主动公开走保存信号，两者均在提交后更新竞速纪录，且不移除比赛关联。
