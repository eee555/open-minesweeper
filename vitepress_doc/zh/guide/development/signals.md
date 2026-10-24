---
title: 信号触发关系 - 开源扫雷网
description: 开源扫雷网后端Django信号触发关系详解，包括录像、用户、比赛等模型的pre_save和post_save信号流程。
---

# 信号触发关系

旧竞速纪录和新闻信号已移除。`msuser` 目前只维护录像计数与上传额度；新竞速榜由 `speedranking` 接收 `VideoModel.post_save/post_delete`，在事务提交后增量更新 Redis 或补位失效纪录。

`speedranking` 复用 `videomanager` 捕获的旧值。关注 player、level、mode、state、ongoing_tournament、bv、timems、right_ce、upload_time；提高成绩直接比较，变差/失去资格/删除时只重建由该录像保持的单项。类别迁移同时处理原玩家和新玩家，bvs、iqg 使用数据库保存的 GeneratedField；bv 或 timems 变化会触发这些派生指标的判断。标识绑定/解绑与比赛批量公开不触发保存信号，须显式调用 `add_videos_to_speed_ranks` / `remove_videos_from_speed_ranks`。

竞速入口同时协调 `speedranking.saolei`、`speedranking.pb` 与 `speedranking.top`：共用用户纪录读取和主要变更写入 pipeline，各自判断选优与补位。PB 按等级、3BV、普通/NF 分桶，日常比较编码 score；旧 member 的录像 id 来自用户 hash，按变更前、后的 member 排名确定范围，写入后只批量刷新该区间的 rank，加入或移除延伸至榜尾。top 各项保留最佳五条；只对已入选五条的失效或变差录像查库补位，写入后对变动小榜去重刷新锚点。单录像和批量更新、管理员修复、管理命令重建的错误统一记录上下文与堆栈后继续抛出，不使用 WATCH 或重试。

个人纪录的增量选优、补位查询和批量重建保持原有逻辑；仅在生成 Redis zset score 时使用四位小数 Bvs 和分钟级上传时间，并检查单项或总值的编码范围。超限仅移除对应 zset 条目，不触发个人纪录补位，hash 仍保存原始最佳成绩；总榜按总值独立判断。

top 原始十八项统一参与用户集合，并以变换后的均值作为降序索引。共同写入后先按已发布锚点局部更新该用户的软实力；实时锚点数值变化时发送 `speedranking.top.events.soft_refresh_requested`，由 `top.signals` 创建 `task_refresh_soft_ranks`。任务执行时有其他同路径 READY 任务就正常跳过，否则取得单机独占准入，九次加权合并后统一发布。相关 HTTP 写入口在事务前取得共享准入并覆盖 on_commit 回调；刷新期间新 HTTP 写请求返回有业务原因的 503，后台业务等待而不拒绝。接口、锁路径和运维限制见 `back_end/saolei/speedranking/README.md`。

NF 是独立维度，由 `VideoModel.right_ce == 0` 判断，不再使用模式 `12`。创建和删除时，NF 子计数与录像原模式的子计数同时增减；`right_ce` 为空不计入 NF。`videomanager` 捕获 `right_ce` 变化并更新队列；`customranking` 不需要 NF 信息，不监听此字段。批量转换旧模式后需显式刷新计数及缓存，步骤见 `back_end/saolei/msuser/refactor.md`。

效率榜由独立 `effranking.signals` 监听录像保存和删除，复用 `_old_values` 及 `update_fields` 判断影响范围。除资格、玩家、级别及上传时间外，还监控 `bv/left_ce/right_ce/double_ce`，不按 NF 分榜。提交后重读数据库生成的 Thrp，改善直接比较缓存，原纪录失效或变差才查库补位；回滚不更新 Redis。绑定/解绑标识和比赛公开显式调用 `add_videos_to_eff_ranks` / `remove_videos_from_eff_ranks`。异常记录上下文和堆栈后继续抛出，见 `back_end/saolei/effranking/README.md`。

```automaton
flowchart LR
    video_pre_save[VideoModel pre_save]
    video_post_save[VideoModel post_save]
    video_pre_delete[VideoModel pre_delete]
    pluck_pre_save[CustomPluckRecord pre_save]
    pluck_post_save[CustomPluckRecord post_save]
    pluck_post_delete[CustomPluckRecord post_delete]
    tournament_post_save[Tournament post_save]
    tournament_post_delete[Tournament post_delete]
    gsc_post_save[GSCTournament post_save]
    weekly_post_save[WeeklyTournament post_save]
    participant_post_save[TournamentParticipant post_save]
    gsc_participant_post_save[GSCParticipant post_save]
    weekly_participant_post_save[WeeklyParticipant post_save]
    participant_post_delete[TournamentParticipant post_delete]
    gsc_participant_post_delete[GSCParticipant post_delete]
    weekly_participant_post_delete[WeeklyParticipant post_delete]

    video_pre_save --> capture_video_update[捕获字段旧值]
    capture_video_update --> video_post_save
    video_pre_save --> checkin_video_before_create[比赛录像检测]
    checkin_video_before_create --> video_post_save

    video_post_save --> refresh_state_queue_on_video_save[刷新状态队列]
    video_post_save --> update_video_count_on_video_save[更新用户录像计数]
    video_post_save --> update_video_count_limit_on_video_save[更新用户录像上限]
    video_post_save --> add_created_video_to_checked_tournaments[将比赛录像挂载到比赛]
    video_post_save --> refresh_custom_pluck_rank_on_video_save[刷新pluck纪录]
    video_post_save --> speedranking_save[提交后更新竞速纪录与必要补位]
    video_post_delete[VideoModel post_delete] --> speedranking_delete[提交后补位竞速纪录]
    video_post_save --> effranking_save[提交后更新效率纪录与必要补位]
    video_post_delete --> effranking_delete[提交后补位效率纪录]

    video_pre_delete --> update_video_count_on_video_delete[更新用户录像计数]



    refresh_custom_pluck_rank_on_video_save --> pluck_pre_save
    refresh_custom_pluck_rank_on_video_save --> pluck_post_delete
    pluck_pre_save --> pluck_post_save
    pluck_post_save --> update_custom_pluck_cache_on_record_save[更新pluck榜缓存]
    pluck_post_delete --> update_custom_pluck_cache_on_record_delete[删除pluck榜缓存]
    minigame_post_delete[MiniGameBestScore post_delete] --> delete_cached_score[删除小游戏排行成绩]

    add_created_video_to_checked_tournaments -. m2m_changed .-> no_video_signal[无]

    tournament_post_save --> update_cache_on_tournament_save[更新比赛缓存]
    gsc_post_save --> update_cache_on_tournament_save
    weekly_post_save --> update_cache_on_tournament_save
    tournament_post_delete --> update_cache_on_tournament_delete[删除比赛缓存]

    participant_post_save --> update_cache_on_participant_save[更新参赛缓存]
    gsc_participant_post_save --> update_cache_on_participant_save
    weekly_participant_post_save --> update_cache_on_participant_save
    gsc_participant_post_save --> update_best_score_on_gsc_participant_save[刷新GSC历史最好]
    weekly_participant_post_save --> update_best_score_on_weekly_participant_save[刷新周赛历史最好]
    gsc_participant_post_delete --> update_best_score_on_gsc_participant_delete[重算GSC历史最好]
    weekly_participant_post_delete --> update_best_score_on_weekly_participant_delete[重算周赛历史最好]
    participant_post_delete --> remove_participant_cache_on_delete[删除参赛缓存]
    participant_post_delete --> revoke_rank_score_on_participant_delete[撤回已发比赛积分]
    update_cache_on_participant_save -->|created 且非已颁奖GSC| add_existing_videos_to_participant_tournament[补录比赛录像]

    add_existing_videos_to_participant_tournament -. m2m_changed .-> no_participant_signal[无]

    click video_pre_save "#signal-function-map" "VideoModel 保存前触发"
    click video_post_save "#signal-function-map" "VideoModel 保存后触发"
    click pluck_pre_save "#signal-function-map" "CustomPluckRecord 保存前触发"
    click pluck_post_save "#signal-function-map" "CustomPluckRecord 保存后触发"
    click pluck_post_delete "#signal-function-map" "CustomPluckRecord 删除后触发"
    click delete_cached_score "#signal-function-map" "提交后删除小游戏 ZSET 和明细 Hash 中的玩家"
    click tournament_post_save "#signal-function-map" "Tournament 保存后触发"
    click tournament_post_delete "#signal-function-map" "Tournament 删除后触发"
    click gsc_post_save "#signal-function-map" "GSCTournament 保存后触发"
    click weekly_post_save "#signal-function-map" "WeeklyTournament 保存后触发"
    click participant_post_save "#signal-function-map" "TournamentParticipant 保存后触发"
    click gsc_participant_post_save "#signal-function-map" "GSCParticipant 保存后触发"
    click weekly_participant_post_save "#signal-function-map" "WeeklyParticipant 保存后触发"
    click participant_post_delete "#signal-function-map" "TournamentParticipant 删除后触发"
    click gsc_participant_post_delete "#signal-function-map" "GSCParticipant 删除后触发"
    click weekly_participant_post_delete "#signal-function-map" "WeeklyParticipant 删除后触发"

    click capture_video_update "#signal-function-map" "保存前记录录像旧状态，用于保存后判断副作用"
    click checkin_video_before_create "#signal-function-map" "录像创建前，根据用户参赛缓存判断是否属于比赛录像"
    click refresh_state_queue_on_video_save "#signal-function-map" "根据录像状态同步普通录像队列"
    click update_video_count_on_video_save "#signal-function-map" "录像创建后增加用户录像计数，跳过 ongoing_tournament=True 的录像"
    click update_video_count_limit_on_video_save "#signal-function-map" "录像保存后同步用户录像数量上限"
    click add_created_video_to_checked_tournaments "#signal-function-map" "录像创建后写入命中的比赛录像关系"
    click refresh_custom_pluck_rank_on_video_save "#signal-function-map" "录像保存后刷新自定义 pluck 排行"
    click update_video_count_on_video_delete "#signal-function-map" "录像删除前减少用户录像计数，跳过 ongoing_tournament=True 或仍关联比赛的录像"
    click update_custom_pluck_cache_on_record_save "#signal-function-map" "pluck 纪录保存后同步排行缓存"
    click update_custom_pluck_cache_on_record_delete "#signal-function-map" "pluck 纪录删除后同步排行缓存"
    click update_cache_on_tournament_save "#signal-function-map" "比赛保存后同步 NORMAL 比赛缓存"
    click update_cache_on_tournament_delete "#signal-function-map" "比赛删除后移除比赛缓存和相关参赛缓存"
    click update_cache_on_participant_save "#signal-function-map" "参赛关系保存后同步用户参赛缓存"
    click update_best_score_on_gsc_participant_save "#signal-function-map" "GSC 参赛成绩保存后刷新用户历史最好"
    click update_best_score_on_weekly_participant_save "#signal-function-map" "周赛参赛成绩保存后刷新用户历史最好"
    click update_best_score_on_gsc_participant_delete "#signal-function-map" "GSC 参赛成绩删除后重算用户历史最好"
    click update_best_score_on_weekly_participant_delete "#signal-function-map" "周赛参赛成绩删除后重算用户历史最好"
    click remove_participant_cache_on_delete "#signal-function-map" "参赛关系删除后移除用户参赛缓存，跳过非站内参赛者"
    click revoke_rank_score_on_participant_delete "#signal-function-map" "参赛关系删除后按比赛结束时间衰减撤回原积分，数据库随删除事务更新，提交后刷新积分排行"
    click add_existing_videos_to_participant_tournament "#signal-function-map" "创建参赛关系后扫描并补录既有比赛录像"
```

<a id="signal-function-map"></a>

`MiniGameBestScore.post_delete` 调用 `minigame.signals.delete_cached_score`，在事务提交后从该榜 ZSET 和明细 Hash 移除玩家，保留初始化标记；覆盖 Admin、QuerySet 和用户级联删除，回滚不改缓存。小游戏创建和改善由提交服务直接注册 `on_commit` 更新，不另设保存信号。

GSC 历史补录沿用默认 TournamentUser 创建和 best 保存信号，允许默认或手工成绩改善 best；匿名参赛者不调度参赛缓存更新。已颁奖 GSC 创建 participant 时不自动回填录像，由代传 service 显式关联，普通报名和周赛不变。补录接口的调用顺序和手工成绩规则见 [GSC 历史录像补录](./gsc-history-import.md)。

导入录像在 `create_from_parser` 中提前设置来源 `upload_time` 供 `pre_save` check-in 使用，创建后再次显式保存以覆盖 `auto_now_add`；既有文件仅当本次时间更早时保存。两种保存仍走状态队列和排行信号，不用 `QuerySet.update` 绕过副作用。

| 图中名称 | 函数 |
| --- | --- |
| 删除小游戏排行成绩 | `minigame.signals.delete_cached_score` |
| 捕获字段旧值 | `capture_video_update` |
| 比赛录像检测 | `checkin_video_before_create` |
| 刷新状态队列 | `refresh_state_queue_on_video_save` |
| 更新用户录像计数 | `update_video_count_on_video_save` / `update_video_count_on_video_delete` |
| 更新用户录像上限 | `update_video_count_limit_on_video_save` |
| 将比赛录像挂载到比赛 | `add_created_video_to_checked_tournaments` |
| 刷新pluck纪录 | `refresh_custom_pluck_rank_on_video_save` |
| 提交后更新效率纪录与必要补位 | `effranking.signals.refresh_ranks_on_video_save` |
| 提交后补位效率纪录 | `effranking.signals.refresh_ranks_on_video_delete` |
| 更新pluck榜缓存 | `update_custom_pluck_cache_on_record_save` |
| 删除pluck榜缓存 | `update_custom_pluck_cache_on_record_delete` |
| 更新比赛缓存 | `update_cache_on_tournament_save` |
| 删除比赛缓存 | `update_cache_on_tournament_delete` |
| 更新参赛缓存 | `update_cache_on_participant_save` |
| 刷新GSC历史最好 | `update_best_score_on_gsc_participant_save` |
| 刷新周赛历史最好 | `update_best_score_on_weekly_participant_save` |
| 重算GSC历史最好 | `update_best_score_on_gsc_participant_delete` |
| 重算周赛历史最好 | `update_best_score_on_weekly_participant_delete` |
| 删除参赛缓存 | `remove_participant_cache_on_delete` |
| 撤回已发比赛积分 | `revoke_rank_score_on_participant_delete` |
| 补录比赛录像 | `add_existing_videos_to_participant_tournament` |

录像计数排除比赛录像。创建时读取 `ongoing_tournament`；删除时在 `pre_delete` 中检查该标记及 `Tournament.videos` 关联，避免级联删除清除关联后误减计数。比赛公开不增加计数。已有数据可通过 `refresh_video_counts` 命令重算，包括补录到比赛的历史录像；上传数量上限仍由独立的 `update_video_count_limit_on_video_save` 维护。

`Tournament` / `GSCTournament` / `WeeklyTournament` 的保存信号分别绑定到同一个 `update_cache_on_tournament_save` 接收器。`TournamentParticipant` / `GSCParticipant` / `WeeklyParticipant` 的保存信号分别绑定到同一个 `update_cache_on_participant_save` 接收器。缓存删除信号只保留父类接收器；多表继承删除子类时会继续触发父表删除。历史最好成绩依赖子类 participant 的成绩字段，因此由 `GSCParticipant` / `WeeklyParticipant` 的保存和删除信号单独处理：保存时只比较当前 participant 与原 best，删除时才重算该用户历史 best。best 信号更新的是 `TournamentUser` 数据库汇总字段，需要和 participant 变更保持事务一致，因此不使用 `transaction.on_commit`。

`revoke_rank_score_on_participant_delete` 仅监听父类 `TournamentParticipant.post_delete`，实例、QuerySet 和比赛级联删除都会执行一次，不重复绑定子类。匿名参赛者和 `rank_score=0` 跳过。其他记录在删除事务内锁定既有 `TournamentUser`，调用 `add_score(-rank_score, tournament.end_time, category=...)` 撤回已发积分；当前积分按比赛结束时间衰减到该用户保留的 `last_updated`，历史总分与 GSC/经典周赛分类总分扣除未衰减原值。数据库扣分不使用 `on_commit`，回滚会连同删除一起撤销；仅 Redis 积分排行在提交后刷新，仍使用既有年度锚点。保留 TournamentUser，不自动重排剩余选手；需要重排并修正其积分时运行 `refresh_tournament_scores`。有已发积分却缺少 TournamentUser 属于数据完整性错误，不静默跳过或补建零分账户。

`medal.signals.invalidate_medal_catalog` 监听 `MedalDefinition` 的保存和删除，删掉图鉴缓存 `medal:catalog`。`medal.signals.enqueue_medal_refresh_on_video` 监听 `VideoModel` 的保存和删除，事务提交后为当前玩家入队 `task_refresh_player_medals`，并记下这次碰到的录像 id。退审、成绩变差、换玩家和删除会带上受影响难度。保存时如果录像上已经记下旧的 `player_id`，旧玩家也入队。`medal.signals.enqueue_medal_refresh_on_profile` 检查实际模型字段 `_realname`，资料保存且实名可能变化时入队全量刷新。`medal.signals.enqueue_medal_refresh_on_saolei_link` 在扫雷网平台绑定保存或删除时入队全量刷新；其他平台不入队。标识批量绑定、解绑同样入队全量刷新。接收器不直接评估勋章，也不在 `userprofile` 或 `accountlink` 里引用勋章。

`medal.signals.invalidate_summary_on_evidence_delete`监听`VideoModel`及`TournamentParticipant`的`pre_delete`。在授予证据外键被`SET_NULL`前查询受影响玩家，按主键顺序取得玩家锁，并在同一删除事务内删除对应`PlayerMedalSummary`。事务提交后再删 `medal:state:{user_id}`；删除回滚时摘要和状态键都还在。下次摘要读取补齐已置空的证据链接。自然进度和授予资格继续由既有后台评估处理；状态键被删掉后，下一次刷新按未扫描走全量 `evaluate_player`。

标识绑定、解绑和比赛录像公开保留 `QuerySet.update()`，它们不会触发 `post_save`。业务入口通过 `videomanager.events.videos_bulk_changed` 发送受影响的 `player_ids`，由勋章接收器去重，并为每名玩家注册独立的 `transaction.on_commit(..., robust=True)` 回调；事务回滚不入队，单名玩家入队失败会记录错误日志，不阻断其他玩家或缓存更新。比赛批量公开的最新队列及各排行也分别使用独立的 robust 提交回调，缓存与勋章入队互不依赖成功；这些回调暂不自动重试。入队函数在同一事务锁定玩家行，并在数据库按任务路径、`READY` 状态和玩家参数判断是否已有任务，不读取全队列 JSON。`on_commit()` 回调仍同步执行，不能据此认定请求没有入队开销。
