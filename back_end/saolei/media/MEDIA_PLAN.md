# 作品页（media）开发计划

状态：**第 4 阶段（前端）已完成**；第 0-3 阶段（app 外壳、数据层、服务与缓存、API 层）均已落地并通过局部检查，设计已按「外站超时降级投稿」「外站作者 id 不入库」「软删除状态机」口径修订。作品页已改为单页表格（表头切换三种排序）、移除《审核中》公开入口，见第 11.2 节。阶段 4 已接入 `/works` 表格页、排行榜 / 数据库 / 个人主页 / 后台四个 tab、投稿与投喂组件、`mediaService.ts` 的 25s 投稿超时、全局与 SFC 双语 i18n，并完成 lintfix / typecheck / vitest / `build:openms` 与 9 个 Cypress 组件测试；阶段 5（生产迁移、确认 `T_r` 与四个 zset 初始化、超时链实测与一次性全量开放，不做灰度）已完成本地可交付部分（E2E spec、部署手册、本地前置检查），生产部署动作待执行。删除路径改为 `status` 状态机（第 16 节），降级投稿与平台扩展约定见第 7.2、17 节；外站作者 id 的一次性核验口径见第 16.1 节第 15 条；每日投喂上限口径见第 17 条；第一轮代码审查修复（按行热度基准、anchor 发布时序、真实外站异常降级、数字外链归一化与前端权限/展示）见第 18 条；第二轮 P2 并发修复（缓存写入改为 DB 绝对值覆盖 + 全局缓存锁、投稿基准复核、重建持锁）见第 19 条；第三轮 P2 超时修复（请求路径零锁等待、缓存同步改为业务事务内入队的持久化任务、worker 非阻塞取锁与退避重排）见第 20 条；竞态取舍与失败可检测口径（最终一致即可、失败必须可见，月度刷新阻塞取锁失败抛错、新增只读巡检命令）见第 21 条；作品页标题列的平台图标与「投稿时已确认身份则审核免填外站作者 id」见第 22 条；「管理员不能改 URL，信息补录仅限降级投稿」见第 23 条。**缓存与双基准简化重构（第 24 条）已在本工作区的未提交改动中落地**：四个 zset 全部保留、`T_db` / `T_r` 各自独立、请求路径一个显式 `MULTI/EXEC` 直写绝对分数且不做后台任务重试、低频管理命令 `refresh_media_rankings` 负责基准推进 / 纠偏 / 巡检；第 5.2-5.4、6、10、12、18 节已按该实现改写，附录 A 是缓存部分的唯一当前口径，16.1 第 18-21 条保留为历史决策记录。「保留四个 zset」推翻了讨论中曾出现的「去掉 zset 改查 DB」方向；media 单测与两份 vitepress 开发文档已同步改写、本地检查已全部通过（A.7），本地仅剩生产部署动作待部署侧执行。

本文档是实现的唯一设计基线；实现时若改变第 5 节的衰减不变量、附录 A 的双基准 / 缓存写入口径或第 9 节的权限口径，应先更新本文档。

## 1. 目标与范围

- 本站支持与其他平台账号关联（`accountlink` app）。用户把自己在对应平台发表的文字/视频作品投稿到本站，作品页展示标题、语言、发表时间、作者、平台，并外链到原作品；支持在本站页面嵌入可嵌入的作品（当前只有 B 站视频）。
- 本站**不托管**作品正文、图片或视频，也**不做自动化内容审查**。作品是否合规由来源平台负责；本站管理员只人工判断「是否与扫雷相关」，审核不通过置为 `rejected`（驳回），**不删除记录**；面向用户不提供任何删除功能，作品行原则上永久保留，被驳回的外链无法重新投稿。唯一例外是站长对已通过作品的硬删除（P2 / 第 5.6 节），该路径退还红宝石并释放外链唯一性。
- 本站提供红宝石投喂（点赞/热度）、作品页表格（标题 / 作者 / 发表时间 / 实时热度 / 累计投喂 + 投喂按钮，点击后三个表头切换热门 / 精品 / 最新三种排序）、排行榜页《作品》tab（用户 `hot_value` 与 `likes` 排行，走 Redis）、数据库页与用户主页作品 tab、投稿封禁。
- 投稿时后端自动调用来源平台 API 拉取 `title` / `created_at` / 外站作者 id 并自动核对归属；**外站作者 id 只用于本次请求的一次性归属核验，绝不写入 `Media`**（16.1 第 15 条）。**外站超时或上游不可用时仍保持投稿**，落为「待补全」作品（无标题），由管理员审核时补录标题、并凭一次性输入的外站作者 id 核验身份；结构性错误仍拒绝。语言由投稿者自由填写，只限制长度，站点不解释取值。
- MVP 支持三类作品：`B_v`（B 站视频）、`B_a`（B 站专栏/文章）、`c_p`（扫雷网帖子）。B 站动态（`B_o`）因上游详情没有稳定标题字段而移除支持（降级路径不改变该决定），详见第 7.1 节。

不做：外站内容抓取入库、评论区、作品编辑历史、通知推送、作品推荐算法、外站账号自动同步。

## 2. 现状与可复用实现

| 现有实现 | 位置 | 本计划如何复用 |
| --- | --- | --- |
| 平台枚举 `Platform`、`AccountLinkQueue(platform, identifier, userprofile, verified)`、各平台账号模型 `AccountBilibili.id` / `AccountSaolei.id`、`PLATFORM_CONFIG` | `accountlink/models.py:11-20, 29-36, 40-49, 105-119, 260-270` | 投稿资格与归属校验；只认 `verified=True` 的绑定 |
| 绑定归属校验模板 | `accountlink/saolei/services.py:29-41`、`accountlink/msgames/api.py:40-52`、`accountlink/services.py:32-55` | API 层校验请求者归属 + service 层事务化防重复认领 |
| 外链 host 白名单与规范化 | `accountlink/msgames/utils.py:37-44` | `urlsplit` + scheme/host 白名单 + 规范化后缀 |
| 比赛积分的指数衰减 | `tournament/utils.py:8-9, 36-49`、`tournament/models.py:296-327`、`tournament/cache.py:243-274` | 衰减因子与统一时间基准的设计范式；本计划不用 `ZUNIONSTORE` / `WATCH` 缩放，改由 `refresh_media_rankings` 从 DB 全量重算（附录 A.4） |
| APScheduler 周期作业 | `common/apscheduler.py:58-102`、`common/management/commands/runapscheduler.py` | 本计划不新增周期作业；曾用于月度刷新的 `refresh_media_hot_reference` 已删除，注册时清理同名持久化 job，`common/tests.py` 作业集合断言同步 |
| Django 6 Tasks / `django-tasks-db` | `saolei/settings.py:167-172`、`medal/tasks.py:11-31`、`accountlink/saolei/tasks.py:33-38` | 其它 app 仍按此入队；**media 不再使用后台任务**，缓存写入在请求路径完成（附录 A.3）；`config/common.py` 无 media 清理项、`common/api.py` 无 media 重启服务 |
| Redis 排行 | `tournament/cache.py:15, 302-315`、`customranking/cache.py:112-148` | `get_redis_connection('saolei_website')`、zset 只存 id、回表 `in_bulk` 取展示字段 |
| 限流 | `identifier/api.py:87-105`、`minigame/api.py:85-92` | `@decorate_view(ratelimit(...))`、显式 `group`、查询接口 `block=False` + `request.limited` |
| 权限与 CSRF | `userprofile/decorators.py:7-48`、`ADMIN_API_CSRF.md` | `staff_required`（管理员写）、`login_required_error` + `banned_blocked`（普通写）、普通 API 不加 CSRF |
| 匹配查找 | `identifier/api.py:21-84`、`front_end/src/views/DatabaseView/IdentifierView.vue:192-283` | 数据库页作品 tab 的模式、1000 条上限、`too_many_matches` 400 |
| 前端页面与请求 | `front_end/src/router/index.ts:9-119`、`DatabaseView/App.vue`、`UserView/App.vue`、`src/services/*`、`src/http.ts` | tab 页壳、后端排序分页、`$axios` 服务封装 |
| 排行榜页 | `front_end/src/views/RankingView/routes.ts:5-51`、`RankingView/App.vue:29-53`、`RankingView/TournamentRanking.vue:1-70`、`RankingView/useRankingQuery.ts` | 新增《作品》tab：路由名 `ranking_media`、tab 文案、`BaseTable` + `ElPagination` + 查询参数 |
| 外站 HTTP 客户端 | `accountlink/utils.py:41-50`（bilibili `User` + `sync`）、`accountlink/saolei/client.py:10-34`（`saolei_client()` 密钥 + Redis 节流）、`accountlink/wom/client.py:18-31`、`accountlink/msgames/client.py:14-25`、`accountlink/github/client.py:40-49` | 复用 `sync()` / `saolei_client()` / 超时与错误分类范式；两个固定版本依赖**已提供**作品详情接口，`media/clients.py` 只做适配（第 7.1 节） |
| 超时与日志 | `default.conf:152, 180-244`、`uwsgi.ini:22, 29`、`saolei/settings.py:340-466`、`videomanager/services.py:39, 53` | 放宽投稿端点的 nginx/uWSGI 超时；驳回只写 `media` logger 文件日志，不再需要审计表 |

关键现状校正：

- 用户模型里**没有** `joind_at` / `register_time`。`register_time` 已在 `userprofile/migrations/0002_remove_userprofile_register_time.py` 删除，当前只有继承 `AbstractUser` 的 `date_joined`（`userprofile/models.py:21`）。红宝石一律以 `UserProfile.date_joined` 推算。
- 全站封禁字段是 `UserProfile.is_banned`（`userprofile/models.py:68`），与本次新增的 `UserMedia.banned`（仅禁止投稿）是两个独立概念。
- `settings.py:196` 已有 `MEDIA_URL = '/media/'` 静态资源前缀，与 Python app 名 `media` 不冲突，但**前端页面路由使用 `/works`**，避免读者把作品页和静态资源目录混淆；后端 API 前缀仍为 `/api/media/`。
- 旧 BBS 链接 `http://www.saolei.wang/BBS/Title.asp?Id=9786`（见 `vitepress_doc/zh/guide/minesweeper/stat.md:173-177`）只是历史参考；站长确认当前作品外链为 `https://saolei.wang/bbs/{id}`（Q6），这也正是 `saolei-api` 文档中的官方帖子页。后端只需新建 URL 解析工具，帖子元数据接口由依赖提供。
- `bilibili-api-python==17.4.2` 在仓库里虽只用于用户资料（`accountlink/utils.py:1-2`），但已内置本期需要的 `Video` / `Article` 详情方法；`saolei-api==0.4.1` 提供 `post_info` 与 `Post(title, post_time, user_id)`。`Opus` 详情虽存在，但实测无稳定标题字段，本期不接入（第 7.1 节）。**两个依赖的接口契约已通过源码与实测核对（Q14）**，字段映射见第 7.1 节。
- 项目没有可复用的外部 iframe 播放器封装，需新建组件。

## 3. 命名、枚举与 URL 规范

### 3.1 app 与分层

- Django app：`media`，`MediaConfig`（`media/apps.py`），注册到 `INSTALLED_APPS` 与 `setup.cfg` 的 `application-import-names`。
- 根路由：`api.add_router('/media/', media_router)` → `/api/media/...`。不新增 `urls.py` / `views.py`。
- app 内引用链条：`utils.py`（常量、纯函数，**不引入同 app 其他模块**）→ `models.py` → `services.py` → `api.py`；`schema.py` 放输出/输入 Schema；`cache.py` 放 Redis 逻辑；`clients.py` 放外站 HTTP 客户端（只依赖 `utils.py` 常量与第三方库，不引入 `models` / `services`）；`decorators.py` 放 app 专用权限装饰器；`management/commands/refresh_media_rankings.py` 放低频基准推进 / 重建 / 巡检命令。**没有 `tasks.py`**（附录 A 删除同步任务），不新增 `signals.py`：四个 zset 由 `services.sync_media_scores()` 在 DB 事务提交后的请求路径直写，不用模型信号、不用 `on_commit`、不用后台任务。
- 无模型信号，故 `apps.py` 的 `ready()` 不需要注册信号。

### 3.2 枚举与语言字段

`MediaFormat`（`media/utils.py`，`TextChoices`，`max_length=3`）：`B_v` / `B_a` / `c_p`。值首字母与 `accountlink.Platform` 的平台值（`B` / `c`）一致，便于映射。

`language` **不是枚举**（Q4）：`CharField(max_length=32, blank=True, default='')`。后端只校验长度（`strip` 后不超过 32 字符），不做白名单、格式或大小写归一化，允许任意字符串（含空值）。前端维护已知 locale 代码到语言名的展示映射，未命中（含空字符串）统一显示 i18n 的「未知语言 / Unknown language」；该映射只影响展示，不参与后端筛选、排序或校验。新增 locale 时只改前端映射，不改模型或迁移。

### 3.3 URL 前缀与后缀

| format | 规范化外链 | suffix 规则 | 站内嵌入 |
| --- | --- | --- | --- |
| `B_v` | `https://www.bilibili.com/video/{bvid}/` | `BV` + 10 位字母数字，大小写敏感 | `https://player.bilibili.com/player.html?bvid={bvid}&page=1&autoplay=0&danmaku=0` |
| `B_a` | `https://www.bilibili.com/read/cv{id}` | 纯数字 `cv` id（suffix 只存数字） | 不支持，仅外链 |
| `c_p` | `https://saolei.wang/bbs/{id}` | 纯数字帖子 Id | 不支持，仅外链 |

规则：

- 后端保存**规范化后的 suffix**，不保存完整 URL；`MediaOut` 由 `format` 推导 `url` 与 `embed_url` 两个只读字段（用 `create_schema` 的 `custom_fields` 或 resolver）。
- 投稿表单用 select 选 `format`、input 填 `suffix`，提交 `format` / `suffix` / `language`；API 层先用 `MediaFormat(data.format)` 枚举校验，再调用 `utils.parse_media_url(suffix, format)` 按该 format 的正则校验并归一化 suffix，format 与外链不符返回 400。**管理员不能改 URL**：`EditIn` 不含 `url` / `format` / `suffix` 且设 `extra='forbid'`，旧客户端传这些字段会校验失败而不是被静默忽略后返回 200（第 23 条）；`utils.parse_media_url()` 的完整 URL 分支（`urlsplit` 校验 scheme/host 白名单：`www.bilibili.com`、`bilibili.com`、`m.bilibili.com` 且仅 `/video/`、`/read/` 路径；`saolei.wang` 仅允许 `https` + `/bbs/` 路径，剥离 query/trailing slash，识别 `format`，正则校验 suffix，越界返回 400）当前无生产调用方，只保留作平台扩展的解析基础。**B 站 `/opus/`（动态）链接一律拒绝**；旧 `www.saolei.wang/BBS/Title.asp?Id=` 与 `saolei.wang` 其它路径也一律不接受（Q6）。禁止用户自定义域名、协议或路径，避免开放重定向与 XSS。
- **数字 suffix 去前导零**：`B_a` / `c_p` 的纯数字 id 由 `_validate_suffix()` 统一为无前导零的规范形式（全零归一为 `0`），例如 `cv01646742` 与 `cv1646742`、`/bbs/09786` 与 `/bbs/9786` 解析后是同一条 `suffix`。否则 `(format, suffix)` 唯一约束不生效，同一作品可被重复投稿；`build_external_url()` 也只输出规范外链。
- **不支持任何短链**（Q7）：`b23.tv` 等跳转域名直接拒绝，客户端也不跟随重定向（参照 `accountlink/github/client.py:40-41`），避免短链绕过 host 校验。后续扩展平台时增加 `FORMAT_PREFIX` 表项即可。
- 外链前缀只用于展示跳转与 iframe；作品元数据由 `media/clients.py` 按 `format` 调用两个依赖已提供的详情接口获取（第 7.1 节），不从 HTML 页面爬取，不恢复旧 BBS 爬虫（`accountlink/SAOLEI_API_IMPORT_PLAN.md:13`）。
- 前端 iframe 必须设置 `sandbox="allow-scripts allow-same-origin allow-presentation"`、`referrerpolicy="no-referrer"`、`loading="lazy"`、固定宽高比与 `allowfullscreen`；只根据后端返回的 `embed_url` 渲染，不接受用户拼接的 src。

## 4. 数据库设计

三张表（`Media` / `MediaLikes` / `UserMedia`）都在 `media/models.py`，驳回审计字段并入 `Media`；迁移用 `python manage.py makemigrations media` 自动生成，禁止手写迁移（`AGENTS.md`）。本地每次模型改动重新生成干净的 `0001_initial`，生产端在阶段 5 生成并执行一次迁移（第 16 节）。

### 4.1 Media

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `BigAutoField` (隐式) | 主键，zset member |
| `user` | `FK(UserProfile, CASCADE, related_name='media_works')` | 投稿者（本站账号） |
| `title` | `CharField(max_length=200, blank=True, default='')` | 作品标题，正常情况下由来源平台 API 返回；**外站超时降级投稿时为空**，管理员审核通过前必须补录 |
| `metadata_pending` | `BooleanField(default=False)` | 是否为降级投稿（元数据待补全）；审核通过时置 `False` |
| `language` | `CharField(max_length=32, blank=True, default='')` | 投稿者自由填写，只限制长度，不做枚举校验（Q4、第 3.2 节） |
| `created_at` | `DateTimeField()` | **对方平台的发表时间**，由来源平台 API 返回；统一转 UTC，不得晚于投稿时刻。**降级投稿用本站投稿时刻兜底**，管理员仅对这类作品可修正（第 7.2、23 条） |
| `submitted_at` | `DateTimeField(auto_now_add=True)` | **新增字段**：本站投稿时间，用于审核队列与审核中 tab 排序；用户原计划未列出，但不加会缺少稳定的审核排序键 |
| `format` | `CharField(max_length=3, choices=MediaFormat.choices)` | 作品媒介 |
| `suffix` | `CharField(max_length=128)` | 规范化后的 URL 后缀；数字 id 去前导零（第 3.3 节） |
| `status` | `CharField(max_length=8, choices=MediaStatus.choices, default=pending)` | `pending` 未审核 / `verified` 审核通过（**严格终态**，仅站长可硬删除）/ `rejected` 已驳回；**没有删除状态** |
| `rejected_at` | `DateTimeField(null=True, blank=True)` | 驳回时间；改回 `pending` 时清空 |
| `rejected_by` | `FK(UserProfile, SET_NULL, null=True, related_name='media_rejections')` | 执行驳回的管理员；账号注销后仍留作品行；**对普通访客可见**（P3） |
| `reject_reason` | `CharField(max_length=200, blank=True)` | 驳回原因；**对普通访客可见**（P3） |
| `refunded_likes` | `PositiveBigIntegerField(default=0)` | 本次驳回实际退还的红宝石总数，用于幂等与审计；站长硬删除时该值随作品行消失，改记入 `media.log` |
| `likes` | `PositiveBigIntegerField(default=0)` | 累计投喂红宝石数；**驳回时随退还立刻清零**（P1） |
| `hot_value` | `FloatField(default=0)` | 以 `hot_value_updated_at` 为时间基准的热度；**驳回时随退还立刻清零**（P1），`hot_value_updated_at` 不动以保持该行时间基准 |
| `hot_value_updated_at` | `DateTimeField(default=timezone.now)` | **全表统一的 DB 基准 `T_db`**（附录 A.1）：新建作品写当前 `T_db`，低频管理命令推进时全表一起更新；字段保留，但不再作为按行独立基准参与换算 |

**没有 `external_author_id` 字段**（16.1 第 15 条）：外站作者 id 只在投稿时与已验证绑定比对、降级投稿审核时由管理员一次性填入并在 API 层用 `AccountLinkQueue` 核验，两种路径都不写入 `Media`、不写日志、不出现在 `MediaOut`。归属由 `AccountLinkQueue` 的绑定关系保证，无需在作品表冗余保存。

`Meta`：

- `UniqueConstraint(fields=['format', 'suffix'], name='media_format_suffix_unique')`：同一外链只能投稿一次；重复返回 409，不覆盖归属。**全表唯一、不带状态条件**，`rejected` 行继续占用唯一性，因此被驳回的 URL 无法重新投稿；恢复只能由管理员把同一行改回 `pending`（第 16 节）。
- `Index(fields=['status', '-submitted_at'], name='media_pending_idx')`：审核中列表（`status='pending'`）、管理审核队列。
- `Index(fields=['user', '-hot_value'], name='media_user_hot_idx')`、`Index(fields=['user', '-likes'], name='media_user_likes_idx')`、`Index(fields=['user', '-created_at'], name='media_user_created_idx')`：个人主页三种「直接查库」排序。
- `Index(fields=['title'], name='media_title_idx')`：数据库页 exact/startswith 匹配；`icontains`/`iendswith` 无法用该索引，靠 1000 条上限与限流兜底。
- `Index(fields=['status', '-created_at', '-id'], name='media_latest_idx')`：作品页《最新》tab 只取 `status='verified'` 直接查库排序；`id` 作为同发表时间时的稳定 tie-breaker。
- 不建全站 `-hot_value` / `-likes` 索引：全站排序由 Redis 负责；`created_at` 排序不用 Redis（评估见第 6.1 节）。

### 4.2 MediaLikes —— 关于 M2M 与联合主键

用户提问：「`ManyToManyField` 对额外的 `likes` 字段支持如何？」

- Django 支持通过 `through` 模型给 M2M 增加额外字段，例如 `ManyToManyField(UserProfile, through='MediaLikes', related_name='liked_media')`，`MediaLikes` 里可以自由加 `likes`、时间等字段。代价是必须使用 `through_defaults` / 显式创建中间表行，`add()` / `set()` 的语义受限，且中间表仍需要一个主键。
- Django 6.1 也支持 `models.CompositePrimaryKey('user', 'media')` 声明真正的联合主键，但项目所有模型都用隐式单列主键（连 `AccountLinkQueue` 也是），复合主键在外键引用、`bulk_update`、`in_bulk`、admin 上限制更多，MySQL 下收益很小。

**结论**：不声明 `ManyToManyField`，直接把 `MediaLikes` 作为独立模型，用隐式单列主键 + 联合唯一约束，语义等价于联合主键且兼容项目现有写法：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `BigAutoField` (隐式) | 主键 |
| `user` | `FK(UserProfile, CASCADE, related_name='media_likes')` | 投喂者 |
| `media` | `FK(Media, CASCADE, related_name='like_records')` | 作品 |
| `likes` | `PositiveBigIntegerField(default=0)` | 该用户对该作品累计投喂数 |

`UniqueConstraint(fields=['user', 'media'], name='media_likes_user_media_unique')`，同时是 `(user, media)` 查询索引。驳回时按 `like_records` 逐条退还投喂者的 `UserMedia.likes_sent`，并随退还删除该作品的全部投喂记录（P1，第 5.5 节）；站长硬删除时由 `CASCADE` 级联删除（第 5.6 节）。

### 4.3 UserMedia

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `user` | `OneToOneField(UserProfile, primary_key=True, CASCADE, related_name='media_profile')` | 主键 |
| `likes_sent` | `PositiveBigIntegerField(default=0)` | 累计投喂出去的红宝石数 |
| `daily_likes` | `PositiveSmallIntegerField(default=0)` | 所属 UTC 自然日内已成功投喂次数 |
| `daily_date` | `DateField(null=True, blank=True)` | 计数所属 UTC 日期；与当日不同则把 `daily_likes` 视为 0 |
| `banned` | `BooleanField(default=False)` | 仅禁止投稿；不影响浏览、投喂等其它权限 |

行采用惰性创建（`get_or_create`）：不存在视为 `likes_sent=0, daily_likes=0, daily_date=None, banned=False`。`model.save()` 必须显式传 `update_fields`（flake8 插件 `DJM100`）；`get_or_create` 内部创建不受该规则约束。

### 4.4 驳回审计（并入 Media，Q12）

不设独立审计表。除站长硬删除外作品行永久保留；驳回只是把 `status` 置为 `rejected` 并填写第 4.1 节的 `rejected_at` / `rejected_by` / `reject_reason` / `refunded_likes`，原行本身就是完整快照，因此无需 `MediaDeletionLog` 与 `MediaDeletionAction` 枚举（16.1 第 4 条已确认删除）。

Q12 的「写入日志」只指应用日志：`transaction.atomic()` 内用 `logging.getLogger('media').info(...)` 记录操作者、作品 id、原因与退还数量（参照 `videomanager/services.py:39, 53`），不含外站凭据或原始响应；失败与 DB 一起回滚。需在 `saolei/settings.py:397-432` 仿 `videomanager` 增加 `media` logger 与 `logs/media.log` handler（`propagate=False`），管理员可通过 `common/api.py:336, 365` 的日志接口查看文件日志。

管理员可把 `rejected` 改回 `pending`（16.1 第 3 条），复用同一行而不是新建投稿；该行仍不进入热门/精品/《最新》与排行榜。驳回时已按 P1 退还红宝石并把 `likes` / `hot_value` 与投喂记录清零，恢复后从零重新累计，**无需再处理红宝石**。`status='verified'` 严格终态：不允许驳回或退回重审；如确需变动，只能由站长走第 5.6 节的硬删除路径（P2）。

`reject_reason` / `rejected_by` 对普通访客可见（P3），`MediaOut` 需输出这两个字段；硬删除后作品行不复存在，其快照只写入 `media.log`（第 5.6 节），不新建审计表。

## 5. 红宝石与热度机制

### 5.1 余额

```text
earned  = floor((now - user.date_joined).total_seconds() / 86400)
balance = earned - UserMedia.likes_sent（行不存在时按 0）
```

- 从注册时刻起每满 24 小时得到 1 个，按完整周期累计，**不封顶、不需要定时任务、不与登录挂钩**；`date_joined` 使用 UTC（`settings.TIME_ZONE = 'UTC'`）。
- 用 `django.utils.timezone.now()`，测试中通过 `patch('media.services.timezone.now')` 固定时间，不修改用户字段。
- 每次只投 1 个红宝石、可以给自己投喂。余额不足返回 400，不产生部分扣减。
- **每 UTC 自然日最多 10 次成功投喂**（16.1 第 17 条）：`timezone.now()` 返回 UTC aware datetime，`.date()` 即 UTC 自然日；`daily_date` 与当日不同时从 0 重新计数，`daily_likes >= MEDIA_DAILY_LIKE_LIMIT` 返回 429。计数与 `likes_sent` 在同一 `transaction.atomic()` 内更新，事务回滚即不计数，`select_for_update()` 保证并发不超额。驳回与硬删除只退还 `likes_sent`，**不回退**当日已用次数。

### 5.2 衰减公式与双时间基准

参照 `tournament/utils.py:36-40` 的 `tournament_score_decay_factor`，在 `media/utils.py` 定义：

```text
MEDIA_HOT_DAILY_RETENTION = 0.99      # 每天衰减 1%
decay(t0, t1) = 0.99 ** ((t1 - t0).total_seconds() / 86400)
real_hot(m, t) = m.hot_value * decay(m.hot_value_updated_at, t)
```

- 允许 `t1 < t0`（因子 > 1），便于把当前时刻的增量折算回更早的基准。
- 连续指数，不按自然日跳变；30 天约 `0.7397`，365 天约 `0.0255`。
- **双基准（附录 A.1）**：`T_db` 存 DB（全表统一的 `Media.hot_value_updated_at`），`T_r` 存 Redis `media:hot:anchor`。两者各自内部自洽，**不要求相等、不要求原子同步**：DB 的 `hot_value` 全部以 `T_db` 为基准，四个 zset 的 hot 分数以 `T_r` 为基准，相差一个共同常数因子 `reference_factor() = decay(T_db, T_r)`，排序一致。`real_hot()` 按行的 `hot_value_updated_at`（稳态即 `T_db`）折算，投喂按 `1 / decay(T_db, now)` 折算，衰减严格连续。
- `cache.read_db_hot_reference()` 返回首行的 `hot_value_updated_at`（空表兜底为当月 1 日 00:00 UTC）；`cache.get_hot_reference()` 读 `T_r`，缺失时以 `T_db` 用 `SET NX` 初始化。`T_db` 与 `T_r` 不需要同步：作品页字段与实时热度以 DB 为准（`MediaPageOut.anchor = T_db`），作者榜是派生数据、以缓存为准（`UserRankingPageOut.anchor = T_r`，返回 zset 原值由前端折算）。
- Redis 不是增量账本，而是 DB 的排序索引：请求路径按**写入时刻的 DB 绝对值**覆盖四个 zset，hot 分数为 `hot_value * decay(T_db, T_r)`；不引入按行独立基准、`WATCH`、`ZUNIONSTORE` 或全局锁（第 5.3、6 节、附录 A）。
- 用户主页「不走 Redis，按 `hot_value` 排序」依赖全表统一的 `T_db`：投喂绝不把单行基准改成 `now`；低频管理命令推进 `T_db` 时用 `F()` 全表一起 `UPDATE`，不会留下混用基准的行。

### 5.3 投喂 1 个红宝石（时刻 now）

在 `services.like_media()` 的单个 `transaction.atomic()` 内：

1. `select_for_update()` **先锁 `Media` 行、再锁 `UserMedia` 行**（与 `reject_media()` / `hard_delete_media()` 顺序一致，避免死锁）；校验登录、全站封禁、余额 >= 1。**已审核与审核中的作品都可投喂**（Q2），只拒绝不存在的作品与 `rejected` 作品。
2. 每日计数：`today = timezone.now().date()`（UTC 自然日）；`daily_date != today` 时把 `daily_likes` 视为 0，`daily_likes >= MEDIA_DAILY_LIKE_LIMIT(10)` 返回 429。
3. `base = media.hot_value_updated_at`（稳态即 `T_db`）；`delta_hot = 1 / decay(base, now)`：把「now 时刻的 +1」折算成以 DB 基准表示的等效热度，不读 Redis `T_r`。
4. `Media.hot_value += delta_hot`，`Media.likes += 1`，`hot_value_updated_at` 保持不变。
5. `MediaLikes` 用 `get_or_create` + `likes += 1`；同一条 `UserMedia.update()` 写 `likes_sent += 1`、`daily_likes += 1`、`daily_date = today`，保证「成功才计数」且并发不超额。
6. DB 事务提交后，**仅当 `media.status='verified'`** 在请求路径调用 `services.sync_media_scores(media_id, author_id)`：重查 DB 中该作者所有 `verified` 作品的 `hot_value` / `likes`，乘 `cache.reference_factor() = decay(T_db, T_r)` 得绝对分数，由 `cache.set_media_scores()` 的一个显式 `pipeline(transaction=True)` 覆盖四个 zset（作品行不存在则 `ZREM`）。`verify_media()` 过审补齐、`hard_delete_media()` 回退与 `create_media()` 也走同一入口；审核中作品只落 DB，等审核通过时按累计值一次性补齐四个 zset（第 6 节）。**没有后台任务、没有 `on_commit`、没有锁**：Redis 异常只被 `sync_media_scores()` 吞掉并记 error 日志，DB 事务照常提交，请求不因缓存失败而失败，残留漂移由 `refresh_media_rankings` 纠偏（附录 A.3 / A.5）。

驳回与硬删除只按第 5.5 / 5.6 节退还 `likes_sent`，不回退 `daily_likes`；管理员操作不应重置当日额度。

说明：早期设计用 `ZINCRBY` 累加增量，随后依次改为「锁内按 DB 绝对值覆盖」与「业务事务内入队持久化任务」（16.1 第 19-21 条），均已被第 24 条 / 附录 A 整体覆盖。当前口径是**请求路径一个 MULTI/EXEC 直写绝对分数 + 不做重试补偿**：绝对 `ZADD` 不会因迟到、乱序或响应丢失而重复累加；DB 是事实来源，Redis 偶发错误只影响派生榜单的顺序与数值。请求路径使用 1s 短超时 Redis 客户端（`cache.MEDIA_SOCKET_TIMEOUT`），不吃掉普通 API 的 2s 网关预算；代价是每次同步多一次按 `user_id` 的索引查询（通常几十行）。

### 5.4 低频基准推进与全量重建（不再有月度作业）

- `T` 仍需推进，理由是防止 `1 / decay(T, now)` 长期指数增长到浮点上溢；double 下至少以年为单位即可，因此**不需要月度刷新**：`common/apscheduler.py` 的 `refresh_media_hot_reference` 作业、`media/tasks.py` 的月度任务、`config/common.py` 的任务清理项与 `common/api.py` 的 media 重启服务全部删除，注册作业时清理持久化的旧 job id；`db_worker` / `stop.sh` 因其它后台任务保留（附录 A.4）。
- 单一低频管理命令 `media/management/commands/refresh_media_rankings.py`（人工执行，不进部署流程、不进 `start.sh` / `stop.sh`）：
  1. `--reference <ISO UTC>` 指定新基准（默认 `timezone.now()`，不得早于当前 `T_db`）：DB 事务内 `UPDATE ... SET hot_value = hot_value * decay(T_db_old, T_new), hot_value_updated_at = T_new` 用 `F()` 在 SQL 端乘算并提交；不按行分组换算，也不用 Python 快照覆盖已提交的投喂。
  2. `cache.rebuild_rankings(batch_size, reference)` 只取 `status='verified'` 的行，把 `hot_value * decay(T_db, T_r)` 与 `likes` 写进 `media:rebuild:*` 临时 key，再在**一个 `MULTI/EXEC`** 里 `rename` 四个正式 zset 并**最后** `SET media:hot:anchor = T_r`；likes 榜只重建不缩放。缩放融进从 DB 重算，不需要 `ZUNIONSTORE`。
  3. 命令**不持锁、不阻塞请求写**：执行期间正式 key 上的增量可能被 `rename` 覆盖而短暂漂移，已确认接受；DB 始终正确，重跑或下一次写入即可收敛。Redis 发布失败时命令抛 `CommandError`，提示 `T_db` 已是权威值、重跑命令即可，不阻断服务。
  4. `--rebuild-only` 不推进 `T`，只按当前 `T_r` 纠偏；`--check` 只读巡检，按 `decay(T_db, T_r)` 从 DB 算四个 zset 的期望分数，漂移或 `T_r` 缺失以 `CommandError` 非零退出码告警；`--max-examples`、`--batch-size` 控制输出与批量。
- 边界：Redis double 与 MySQL `FloatField` 精度；`hot_value < 1e-9` 可在重建时按 0 清理，但命令不做删除，避免排行人数抖动。相同 `--reference` 重跑时 `T_db` 已等于目标值，不会重复缩放 DB，重复发布也不会改变分数。

### 5.5 驳回作品（Q12 / P1；无用户删除路径）

按 16.1 已确认口径：**没有面向用户的 `POST /delete`，作者不能删除自己的投稿；需要撤下的作品必须在过审前联系管理员驳回；`status='verified'` 严格终态**。Q1（自删不扣减 `likes_sent`）与 Q9（删除接口限流）随之作废。已通过作品如需变动，只能由站长走第 5.6 节硬删除（P2）。

`services.reject_media(media_id, actor_id, reason='')` 在单个 `transaction.atomic()` 内（权限判定仍在 API 层）：

1. 锁 `Media` 行；校验 `status == 'pending'`，否则拒绝（重复驳回幂等返回 409）；取 `like_records` 的 `(user_id, likes)` 列表与当前 `likes` / `hot_value`。
2. 置 `status='rejected'`，写 `rejected_at` / `rejected_by` / `reject_reason` / `refunded_likes`；`save()` 显式传 `update_fields`（`DJM100`）。**不删 `Media` 行**。
3. 红宝石退还：按 `like_records` 逐条把投喂者 `UserMedia.likes_sent -= likes`（下限 0，用 `Greatest` 或先校验），包括作者给自己投喂的部分（Q12）；投喂者多时分批更新，避免长事务。`refunded_likes` 记录实际退还总数。
4. **立刻清零（P1）**：同一事务内把 `Media.likes = 0`、`Media.hot_value = 0`，并删除该作品全部 `MediaLikes` 行，使退还后的数据库状态与「未投喂过」一致；`hot_value_updated_at` 不动，保持该行时间基准。**退还与清零必须同事务**，否则中途失败会出现「已退还但仍计数」；删除投喂记录是清零的必要配套，否则恢复后再次投喂会基于旧行累加、与 `Media.likes=0` 不一致。
5. 应用日志：事务内 `logging.getLogger('media').info(...)`（第 4.4 节）。
6. **Redis 无需操作**：审核中作品按第 6 节只写 DB、从未进入四个 zset，驳回发生在 `pending` 状态，因此不需要 `ZREM` 或 user zset 回退；`rejected` 也不参与 `refresh_media_rankings` 的全量重建。
7. `format+suffix` 全表唯一持续生效，该 URL 无法重新投稿；`/submit` 命中时返回 409 与统一提示「该作品已投稿过，不可重复投稿」，不明说曾被驳回（P4）。改回 `pending` 由 `POST /admin/reopen` 完成（P5），复用同一行，因已清零而无需处理红宝石。

### 5.6 站长硬删除（P2）

`status='verified'` 严格终态，普通管理员不能驳回、改回 `pending`、编辑或删除。**唯一例外**：站长（`is_superuser`）可硬删除已通过作品，用于纠错或合规下架。

- 权限：`auth=django_auth_superuser`（Ninja 会话认证自带 CSRF，现成范式 `videomanager/api.py:192-206`），不走 `staff_required`；管理员 API 按规范不限流，docstring 开头必须列出该 auth。普通 staff 与普通用户一律 403。
- `services.hard_delete_media(media_id, actor_id)` 在单个 `transaction.atomic()` 内：锁行 → 校验 `status == 'verified'` → 取 `like_records` 的 `(user_id, likes)` 与当前 `likes` / `hot_value`、作品快照 → 逐条退还投喂者 `UserMedia.likes_sent`（与第 5.5 节同规则）→ 写 `media.log` 快照（`media_id` / `format` / `suffix` / `title` / `user_id`（本站作者）/ `actor_id` / `likes` / `hot_value` / `refunded_likes`，参照 `videomanager/services.py:51-53`）→ `media.delete()` 级联删除 `MediaLikes`。**不新建审计表**，行删除后唯一可查痕迹是文件日志。
- DB 事务提交后调用 `services.sync_media_scores(media_id, author_id)`（与投喂共用）：按删除后的 DB 绝对值在一个 `MULTI/EXEC` 内覆盖四个 zset——作品行已不存在则 `ZREM media:rank:hot/likes {media_id}`，作者两个 user zset 由剩余 `verified` 作品重算，无剩余作品则 `ZREM` 成员。Redis 异常只记日志，不影响已提交的删除。与驳回不同，`verified` 作品确实在榜，必须回退；与早期设计不同，不再有 `on_commit` 回调、锁或后台任务，也就没有「迟到回调把已删除作品重新入榜」的窗口。
- 唯一约束释放：`format+suffix` 行被物理删除，该外链**可以重新投稿**；这与被驳回（行仍在）不可重投形成明确区别。
- 前端不给普通用户或普通管理员暴露该入口；站长操作在 `StaffMediaReview.vue` 提供二次确认。

### 5.7 数值示例

设 `T = 2026-11-01 00:00 UTC`，`now = 2026-11-07 00:00 UTC`，`decay(T, now) = 0.99^6 ≈ 0.9415`。

- 投喂 1 个红宝石：`delta_hot = 1 / 0.9415 ≈ 1.0621`，`hot_value` 增加 1.0621，实时热度（now）= `1.0621 * 0.9415 = 1`。
- 11 月 7 日再投喂 1 个：`delta_hot ≈ 1.0621`，累计 `hot_value ≈ 2.1242`，实时热度 = `2.1242 * 0.9415 ≈ 2`（两颗都在 now 生效）。
- 12 月 1 日低频推进基准：`factor = 0.99^30 ≈ 0.7397`，`refresh_media_rankings --reference 2026-12-01T00:00:00+00:00` 在 DB 端把 `hot_value` 乘以 0.7397、全表 `hot_value_updated_at = 2026-12-01`，再从 DB 重建四个 zset 并把 `T_r` 发布为同一时刻；排序不变，不需要 `ZUNIONSTORE` 或锁。

## 6. Redis 排行

统一使用 `django_redis.get_redis_connection('saolei_website')`（db0）封装在 `media/cache.py`；请求路径的读写走 1s 短超时的同库客户端（`MEDIA_SOCKET_TIMEOUT`，`LOCATION` 为字符串时用 `Redis.from_url`），key 前缀 `media:`，五个固定 key 全部参与 `monitor` 的内存统计（附录 A）。

| key | 类型 | score | member | 说明 |
| --- | --- | --- | --- | --- |
| `media:rank:hot` | zset | `hot_value * decay(T_db, T_r)` | `media_id` | 热门排序，只含已审核作品；**只作排序索引**，展示字段回 DB 取 |
| `media:rank:likes` | zset | `likes` | `media_id` | 精品排序，只含已审核作品 |
| `media:rank:user:hot` | zset | 用户所有已审核作品 hot 分数之和（`T_r` 基准） | `user_id` | 排行榜页《作品》tab 的热度指标，派生数据以缓存为准 |
| `media:rank:user:likes` | zset | 用户所有已审核作品 `likes` 之和 | `user_id` | 排行榜页《作品》tab 的精品指标 |
| `media:hot:anchor` | string | ISO datetime（`T_r`） | — | Redis 侧统一基准；`get_hot_reference()` 缺失时以 `T_db` 用 `SET NX` 初始化 |

**没有 `media:cache:lock`**：不引入全局锁、`WATCH`、Lua 或后台任务；并发写入的绝对值可能交错、命令执行期间可能被 `rename` 覆盖，均已确认接受（附录 A.5）。

- 读取：`ZCARD` 取总数，`ZREVRANGE key start end-1` 取 id 索引，再 `Media.objects.in_bulk(ids)` / `UserProfile.objects.in_bulk(ids)` 回表组装展示字段（参照 `tournament/cache.py:302-315`）。单次返回条数上限 50，响应体远小于 300KB。score 相同按 Redis member 字典序，作为稳定但不承诺业务优先级的次序；API 保持 zset 返回顺序，不二次排序。作品页 `MediaPageOut.anchor` 返回 `T_db`，`hot_now` / `likes` 等字段一律以 DB 为准；`UserRankingPageOut.anchor` 返回 `T_r`，`items.hot` 是 zset 原值，前端按 `0.99 ** ((now - T_r) / 1 天)` 折算后展示。
- **审核中作品可以被投喂（Q2 已确认）**，但审核期间**只写 DB**（`Media.likes/hot_value` 与 `MediaLikes`），不写四个 zset：热门/精品/《最新》与排行榜页《作品》tab 只展示 `verified` 作品，不做「写入后再过滤」，否则分页会出现空洞。审核通过时 `verify_media()` 由 `services.sync_media_scores()` 按 DB 当前值一次性 `ZADD` 补入四个 zset；驳回只改状态并退还红宝石，因从未入榜而无需 `ZREM`（第 5.5 节）；**站长硬删除 `verified` 作品是唯一例外**，必须回退四个 zset（第 5.6 节）。
- 管理员审核队列直接查库 `status='pending' ORDER BY -submitted_at`（走 `media_pending_idx`）；普通用户作品页不展示 `pending`，待审核作品只在个人主页 `GET /user/{user_id}` 查看。作品页按发表时间排序同样直接查库，不额外建 zset（评估见第 6.1 节）。`rejected` 作品不在作品页表格中，但在作者主页与数据库页对所有人可见（16.1 第 5 条）。
- 重建与纠偏：`refresh_media_rankings` 调用 `cache.rebuild_rankings()`，**只取 `status='verified'` 的行**（`pending` / `rejected` 一律排除），按 `decay(T_db, T_r)` 折算到 `media:rebuild:*` 临时 key，再在**一次 `MULTI/EXEC`** 内 `rename` 四个正式 zset 并发布 `T_r`；likes 榜不缩放。命令不持锁、不阻塞请求写，失败时保留旧榜并抛 `CommandError`；`cache.clear_rankings()` 只清五个固定 key，供测试与人工维护使用。不做请求时懒重建；`--check` 按同一因子比较四个 zset 与 DB 期望值，漂移时非零退出码告警。
- 一致性：DB 是事实来源，Redis 是排序索引。**四个 zset 的写入都在请求路径、DB 事务提交后完成**：`services.sync_media_scores()` 重查 DB 求绝对分数，`cache.set_media_scores()` 用一个显式 `pipeline(transaction=True)` 写入绝对 `ZADD` / `ZREM`，不用 `ZINCRBY`、不用事件序号或墓碑。`MULTI/EXEC` 没有回滚，因此绝不把抛异常当作「未写入」；异常只记 error 日志、不回滚 DB、不入队任务、不重试补偿，允许偶发 Redis 错误与排序轻微不正确（16.1 第 24 条、附录 A.5）。`db_worker` / `stop.sh` 保留给其它后台任务，但 media 没有同步任务、任务清理期与重启服务；`monitor/cache.py` 仍统计五个固定 key。
- **失败检测（当前口径）**：不再有 FAILED 同步任务或阻塞取锁失败。检测手段是只读巡检 `python manage.py refresh_media_rankings --check`：以 `decay(T_db, T_r)` 从 DB 派生四个 zset 的期望分数，发现漂移（含 `T_r` 缺失）以 `CommandError` + 非零退出码告警，一致时输出 `matches the database`；建议接入外部定时巡检按退出码告警。修复手段是 `refresh_media_rankings --rebuild-only`（只纠偏不推进 `T`）或带 `--reference` 的低频基准推进。Redis 异常只在 `media.log` 留 error 日志，DB 始终正确；巡检不再输出 FAILED / 积压同步任务数。
- 文档：按 `AGENTS.md`，五个固定 key、双基准与绝对分数策略应写入 `vitepress_doc/zh/guide/development/cache.md`，低频命令的执行前提与 `--check` / `--rebuild-only` / `--reference` 语义应写入 `vitepress_doc/zh/guide/development/management-commands.md`；两份文档已按本轮实现同步改写（附录 A.7）。本设计不使用信号接收器，`signals.md` 无需改动。

### 6.1 按发表时间排序是否需要 Redis

**结论：不需要 Redis，直接查库**。作品页按发表时间排序时按 `created_at` 倒序展示已审核作品，读 `GET /api/media/latest`，SQL 为 `WHERE status = 'verified' ORDER BY -created_at, -id LIMIT count OFFSET start`，走第 4.1 节 `media_latest_idx`，返回结构与 `/ranking` 一致（复用 `RankingPageOut`）。理由：

1. `created_at` 由上游 API 返回后写入，是静态值（管理员纠错除外），没有衰减、没有高频增量；zset 的核心收益「O(logN) 增量维护 + 统一时间基准」在这里用不上。
2. 规模：投稿限流 `10/h` 且需人工审核，已审核作品数量增长慢；MySQL 的索引范围扫描 + `LIMIT 50` 成本不高于 `ZREVRANGE` + `in_bulk` 回表（后者还多一次 Redis 往返与对象组装），单页响应远小于 300KB。
3. 维护成本：若新增 `media:rank:latest` zset，就必须在审核通过、管理员修改 `created_at` 时同步 `ZADD/ZREM`，并纳入 `refresh_media_rankings` 与 `cache.md`；任何遗漏都会让 DB 与缓存不一致，而 Redis 在本项目只是排序索引、不是事实来源。
4. 分页与并列：直接查库用 `(created_at, id)` 作为稳定排序键，同时间按 `id` 倒序，必要时可把 offset 分页换成 keyset 游标分页避免深分页退化。Redis zset 的 double score 无法精确表示微秒时间戳，同分只能按 member 字符串排序，仍需在 API 层补 tie-breaker。
5. 一致性：数据库页检索、审核中 tab、用户主页排序都直接查库，《最新》沿用同一模式，避免一个页面两套同步机制。

**何时改为 Redis**（满足任一条件再评估）：已审核作品量级超过约 10 万且首页 QPS 高、需要 O(logN) 查询「某作品当前排第几」、或《最新》要与其它 zset 做集合运算（按语言/format 分榜）。届时新增 `media:rank:latest`，score 由 `created_at` 秒级时间戳加 `id` 编码的 tie-breaker 组成，member 为 `media_id`；score 静态，可直接由 DB 一次性重建，改造成本低。

口径：**已确认（Q13）按外站发表时间 `created_at`**，由上游 API 返回后写入，不随投稿时间变化；审核中作品不进入作品页表格，只在个人主页与管理端可见。

## 7. 后端分层与关键流程

| 模块 | 职责 |
| --- | --- |
| `media/utils.py` | `MediaFormat`、`FORMAT_PREFIX`、`MEDIA_HOT_DAILY_RETENTION`、`MEDIA_AUTHOR_ID_MAX_LENGTH`、`decay()`、`real_hot()`、`parse_media_url()`、`format_to_platform()`、`normalize_language()`、`normalize_external_author_id()`（一次性核验输入的字符串归一化，不落库）；纯函数与常量，不引入同 app 其它模块 |
| `media/models.py` | `Media` / `MediaLikes` / `UserMedia` 三张表、`MediaStatus` 状态机、驳回审计字段与 Meta 约束、索引 |
| `media/clients.py` | 外站元数据拉取：`fetch_media_metadata() -> MediaMetadata(title, created_at, author_id: str)` 与 `fetch_media_metadata_optional()` 降级入口；`author_id` 是请求内的临时归属比对值，**不落库**；超时、重试、错误分类；不引入 models/services |
| `media/services.py` | 投稿、投喂、驳回（含退还与幂等）、改回 `pending`、审核通过、封禁/解封、余额计算、`sync_media_scores()` 请求路径缓存同步、应用日志；**不检查操作者角色权限**（`AGENTS.md`）；无月度刷新、无任务入队 |
| `media/cache.py` | 五个 Redis key、`T_db` / `T_r` 读写与 `reference_factor()`、读榜、`set_media_scores()` 绝对分数写入、`rebuild_rankings()` 无锁全量重建、`clear_rankings()`；1s 短超时客户端 |
| `media/schema.py` | `MediaOut`（`create_schema` + `url`/`embed_url`/`hot_now` 等 custom fields，**不含外站作者 id**）、`MediaPageOut`（`anchor = T_db`）、`UserRankingPageOut`（`anchor = T_r`）、`QueryOut`、`MeOut`、`SubmitIn`（`url`/`language`）、`LikeIn`、`IdIn`、`VerifyIn`（降级投稿审核的 `title` / `external_author_id` / 可选 `created_at`；`external_author_id` 为一次性核验输入）等 |
| `media/api.py` | Ninja `Router`，所有权限/限流/CSRF 在此层，docstring 开头逐行列装饰器；作品分页返回 `T_db`、作者榜返回 `T_r` |
| `media/decorators.py` | `media_banned_blocked`：读 `UserMedia.banned` 拒绝投稿（仅此一处使用） |
| `media/management/commands/refresh_media_rankings.py` | 低频基准推进、四个 zset 全量重建与 `--check` 只读巡检；**没有 `tasks.py`** |

投稿校验链（顺序固定）：

1. API 层：`login_required_error` + `banned_blocked` + `media_banned_blocked` + `ratelimit(10/h)`；GET 只读、无 CSRF。
2. API 层：`MediaFormat(data.format)` 校验投稿表单选中的 format，`parse_media_url(data.suffix, format)` 得到归一化的 `suffix`；查 `AccountLinkQueue(platform=format_to_platform(format), userprofile=request.user, verified=True)` 是否存在（参照 `accountlink/msgames/api.py:40-52`）。此处只确认「投稿人已绑定该平台账号」，`identifier` 不写入 `Media`。降级投稿仍需该绑定，只是不在此步核对具体作品作者。
3. service 层：`clients.fetch_media_metadata_optional(format, suffix)`。成功返回 `MediaMetadata(title, created_at, author_id: str)`；`timeout` / `upstream_error` 返回 `None` 表示降级；`parse_error` / `invalid_metadata` 抛错并拒绝投稿、不落库（第 7.2 节）。`language` 由用户自由填写，只做长度与 `strip` 归一化。
4. API 层：成功路径把临时 `author_id` 与第 2 步已验证绑定的 `identifier` 比对，不一致返回 403，防止冒领；比对结果不落库。**降级路径没有上游作者 id，自动核对跳过**，改由管理员审核时凭一次性输入核验（第 7.2 节）。
5. service 层：`transaction.atomic()` + 唯一约束防重复外链；`format+suffix` 已存在返回 409；成功路径写入拉取到的 `title` / `created_at`；降级路径写入 `title=''`、`created_at=now`（本站投稿时刻兜底）、`metadata_pending=True`；**两条路径都不接收、不保存外站作者 id**（16.1 第 15 条）；两者都写 `status='pending'`、`likes=0`、`hot_value=0`、`hot_value_updated_at=T_db`（`cache.read_db_hot_reference()`）、`submitted_at=auto_now_add`；`create_media()` 事务提交后按第 5.3 节同步一次绝对分数（该行未过审，实际效果是 `ZREM` 作品并覆盖作者榜），审核中作品本身不入榜。
6. 输出：`MediaOut`（不含外站作者 id）；成功路径用通知提示等待审核，待审核作品在个人主页查看，降级路径额外提示「标题由管理员审核时补全，并核验投稿人在外站的账号」。

所有 `save()` 显式 `update_fields`；能用 `F()` / `bulk_update` 的批量更新优先，减少锁竞争。

### 7.1 外站元数据拉取与超时链（Q5）

**结论**：`bilibili-api-python==17.4.2` 与 `saolei-api==0.4.1` 都提供了所需详情接口，**不需要新写 HTTP 客户端**；`media/clients.py` 只做调用适配、字段映射与错误分类。依据为本地 `.venv` 中这两个固定版本依赖的源码（版本与 `requirements.txt` 一致）以及真实/离线实测，见下表与「实测记录」。

**接口契约与字段映射**（`created_at` 一律由 Unix 秒转 UTC datetime，外站作者 id 统一归一化为字符串、仅作一次性归属核验输入）：

| format | 调用 | 上游 endpoint | title | created_at | author_id (str) |
| --- | --- | --- | --- | --- | --- |
| `B_v` | `sync(Video(bvid=suffix).get_info())` | `https://api.bilibili.com/x/web-interface/view` | `title` (str) | `pubdate` (int 秒) | `str(owner.mid)` |
| `B_a` | `sync(Article(cvid=int(suffix)).get_detail())` | `https://api.bilibili.com/x/article/view` | `title` (str) | `publish_time` (int 秒)，缺失回退 `ctime` | `str(author.mid)` |
| `c_p` | `saolei_api.Client(...).post_info(int(suffix)).items[0]`（复用 `saolei_client()` 的密钥与 Redis 节流，见下文超时说明） | `https://saolei.wang/api/public/v1/post_info?id={id}` | `Post.title` (str) | `Post.post_time` (int 秒) | `str(Post.user_id)` |

- 依赖源码：`bilibili_api/video.py:145-174, 237-251, 326-334`、`article.py:144-166, 562-588, 590-612`；`saolei_api/client.py:130-131, 285-286`、`saolei_api/models.py:157-177`、`saolei_api/_core.py:15, 35-42`。
- 顶层不导出 `Video` / `Article` 类，必须从子模块导入；`sync()` 接收协程对象，写法是 `sync(v.get_info())`（项目已有用法 `accountlink/utils.py:41-50`）。两类 B 站详情都是 GET 且 `verify=false`，**不需要登录 Credential**。`bilibili_api.parse_link()` 返回 `(对象, ResourceType)`，可作为 URL→ID 的辅助，但 Q7 的 host 白名单与禁重定向仍由 `parse_media_url()` 负责。
- `B_a`：`Article.get_info()`（`/x/article/viewinfo`）只有 `title` / `mid`，**没有发表时间**；必须用 `get_detail()`（`/x/article/view`）。实测 `pub_time` 字段不存在，`publish_time` 才是发表时间，`ctime` 是创建时间。
- **移除 `B_o`（B 站动态）**：`Opus.get_info()` 实测 `module_title=None`（普通图文动态没有标题），`pub_ts` 还是字符串时间戳，只能从 `module_content.paragraphs` 猜标题；标题不可靠且作者 id 也不稳定，因此本期不接入，`/opus/` 链接直接拒绝（第 3.3 节）。若上游将来提供稳定标题字段，再按新增 `MediaFormat` + 字段映射扩展。
- `c_p`：`Post` 只含元数据（无正文/回复），不覆盖已删除/待审帖；上游 JSON 为 camelCase（`postTime` / `userId`），模型以 snake_case 暴露。`post_info` 一次最多 50 个 id，投稿只查 1 个；官方帖子页即 `https://saolei.wang/bbs/{id}`（Q6）。
- 鉴权与节流：`saolei_api.Client(api_key, timeout=30, min_interval=2.0)` 使用 `X-Api-Key` 请求头；项目 `accountlink/saolei/client.py:10-34` 的 `saolei_client()` 已封装 `read_secret('saolei_api_key')`、`timeout=30`、`min_interval=2.1` 与基于 Redis 的跨进程 `ThrottledTransport`（数据接口间隔 2.1s、最多等 6s）。**投稿链路需要更短超时**：在 `media/clients.py` 复用 `ThrottledTransport` 与 `saolei_api.Client` 自行构造（`timeout=8`），或给 `saolei_client()` 增加可选 `timeout` 参数且不改变其它调用方，保证总预算 ≤15s；不改 `accountlink` 现有行为。`saolei_api_key` **已由站长配置**；助手当前工作区没有 `secrets.json`，所以 `post_info` 的真实返回用包自带 `MockTransport` + 无密钥 401 验证代替，部署环境联调时再跑一次真实 `post_info`（第 15 节）。
- 不跟随重定向（Q7）；不记录含凭据的 URL；跨 app 只引用 `accountlink.saolei.client` 的客户端/Transport，不引入其模型，`accountlink` 不反向引用 `media`。**不从 HTML 页面爬取**，旧 BBS 爬虫不恢复（`SAOLEI_API_IMPORT_PLAN.md:13`）。

**实测记录**（2026-11-07，只读请求；本地 `.venv` 版本 `bilibili-api-python 17.4.2` / `saolei-api 0.4.1`）：

| 项 | 结果 |
| --- | --- |
| `Video('BV1xx411c7mD').get_info()` | `title='字幕君交流场所'`、`pubdate=1252458549` (int)、`owner.mid=2` |
| `Article(1646742).get_detail()` | `title='黑白棋、纸牌、扫雷…'`、`publish_time=1543758597` (int)、`ctime=1543756404`、`author.mid=106345360`；`pub_time` 不存在 |
| `Opus(1266049845845557253).get_info()`（移除依据） | `module_title=None`、`pub_ts='1793613600'` (str)、`pub_time` 为展示文本，正文在 `module_content.paragraphs`；无稳定标题字段 → 本期移除 `B_o` |
| `Client(...).post_info(123)`（MockTransport 离线） | camelCase 响应正确解析为 `Post(id=123, title='test', post_time=1690000000, user_id=42)`；`saolei_api_key` 已配置，真实请求在部署环境联调 |
| `GET /api/public/v1/post_info?id=1`（无密钥） | 401 `{"error":"unauthorized"}`，确认端点与 `X-Api-Key` 鉴权 |
| B 站风控 | 连续请求触发 `ResponseCodeException: -509 请求过于频繁`（`ttl=1`）；裸排行榜请求返回 `-352`，需纳入错误分类 |

**返回与校验**：统一返回 `title`、`created_at`（UTC）、`author_id`（str，**只在本次请求内用于归属比对，不落库**）；`title` 超长或为空、`created_at` 缺失/晚于 `now`、字段类型不符、`post_info` 返回空 `items` 都归入 `parse_error` / `invalid_metadata`，仍拒绝投稿且不落库，不静默截断（参照 `SAOLEI_API_IMPORT_PLAN.md:41`）。`timeout` 与 `upstream_error` 走 7.2 节降级路径。三类 format 上游都有明确标题，无需标题兜底。

**超时与错误分类**：B 站 connect 3s / read 8s，扫雷网 `timeout=8s`（含 2.1s 节流排队最多 6s），总预算 ≤ 15s；只对 429 / 5xx / B 站 `-509` 风控（按 `ttl` 等待 ≤1s）重试一次，`-352` 与其它 `ResponseCodeException` 不重试。异常统一转 `ExceptionToResponse` 分类：`timeout`（504）、`upstream_error`（502，含 -509/-352、401 鉴权失败、429）、`parse_error` / `invalid_metadata`（502）、`author_mismatch`（403）；响应只给分类码与提示，不含外站原始错误或凭据。结构性错误不写 DB；降级路径按 7.2 节落库。
- **真实 B 站异常族**：`bilibili_api` 默认 `CurlCFFIClient` 直接透传 `curl_cffi` 原生异常，不会包成 `NetworkException`。`curl_cffi.requests.exceptions.Timeout`（含 `ConnectTimeout` / `ReadTimeout`）归 `timeout`；`curl_cffi.CurlError`（含 `ConnectionError` / `RequestException`）归 `upstream_error`；两者都在 `DEGRADED_FETCH_CATEGORIES` 内，可触发降级投稿。仅捕获内置 `TimeoutError` / `httpx.TimeoutException` 会让真实超时落到 500 而不是降级。

**超时链配置**（用户提示需要放宽；以下为必须同步修改的层）：

| 层 | 当前值 | 改动 |
| --- | --- | --- |
| 应用客户端 | 依赖默认 timeout 30s（扫雷网） | 总预算 ≤ 15s：B 站 connect 3s / read 8s，扫雷网 `timeout=8` + 2.1s 节流排队 ≤6s（见上） |
| uWSGI | `uwsgi.ini:29` 普通请求 `harakiri:10`，全局 `harakiri=90`（`:22`） | 在 `:29` 白名单正则末尾追加一个匹配 `/api/media/submit$` 的分支（`route` 按 `PATH_INFO` 匹配），使其保留 90s；否则 10s 即被杀 |
| nginx | `default.conf:152` `^~ /api/` 的 `uwsgi_read_timeout 2` | 新增更精确的 `location = /api/media/submit`：`uwsgi_read_timeout 25s`、`uwsgi_connect_timeout 5s`；location 路径的尾斜杠必须与 Ninja 实际路由一致（**阶段 3 已确认实际为 `/api/media/submit` 无尾斜杠并据此修正**），否则配置不生效 |
| 前端 | `src/http.ts:7` `$axios` 全局 `timeout: 20000` | 仅投稿请求单独传 `timeout: 25000`，其它请求不变 |
| 生效 | `start.sh:31-33` 每次启动复制 `default.conf` | 改仓库内配置；`nginx -s reload`，`uwsgi.ini` 改动必须重启 uWSGI |

**并发与限流**：投稿 `10/h`/用户，uWSGI `processes=5`；同步外站调用会占用 worker，需配合监控。若上线后观察到排队，可另评审「先落待抓取状态 + Django Task + 前端轮询」的异步方案，但那会改变「失败即拒绝」的即时反馈语义，不在本阶段实现。

### 7.2 降级投稿与审核补录（平台无关）

外站超时或上游不可用**不再拒绝投稿**：`fetch_media_metadata_optional()` 返回 `None`，`services.create_media()` 落一条 `metadata_pending=True` 的作品，`title=''`、`created_at` 用本站投稿时刻兜底；**`Media` 不保存外站作者 id**。仅 `timeout` / `upstream_error`（含 B 站 -509 / -352、扫雷网 401 / 429）降级；`parse_error` / `invalid_metadata` 说明 URL 或响应本身有问题，仍拒绝且不落库。

**只有这类降级作品**需要管理员补做身份核验：投稿时上游元数据拉取成功、且 `metadata.author_id` 已命中用户已验证 `AccountLinkQueue` 的正常投稿，归属在投稿链路里已经确认，审核时 `POST /admin/verify` 只需 `id`（传入的 `external_author_id` 直接忽略），后台表单也不再显示该输入框。

管理员审核降级作品时，先人工打开外链确认作品作者，再在 `POST /admin/verify` 提交两项：

| 字段 | 用途 | 是否入库 |
| --- | --- | --- |
| `external_author_id` | 投稿人在外站的账号 id，**一次性核验输入**：API 层用它查 `AccountLinkQueue` 确认该账号属于投稿人，从而确认作品归属 | **否**，不写 `Media`、不写日志、不进 `MediaOut` |
| `title` | 对应投稿的标题 | 是，写入 `Media.title` |

可选 `created_at` 用于把兜底的本站投稿时刻修正为真实发表时间（`POST /admin/edit` 也可修正，第 23 条确认保留该能力）；但两种入口都只对 `metadata_pending=True` 的降级投稿生效，正常投稿的信息一律不可改。`services.verify_media()` 在 `metadata_pending=True` 时缺 `title` 即返回 400 且状态不变；补齐后才置 `verified` 并写四个 zset。**身份核验在 API 层**：`AccountLinkQueue(platform=format_to_platform(format), identifier=external_author_id, userprofile=media.user, verified=True)` 不存在返回 403；该 id 不传进 `verify_media()`，service 层不处理权限（AGENTS.md、16.1 第 15 条）。这条链路只证明「管理员填报的外站账号是投稿人已验证绑定的账号」，作品与该账号的对应关系由管理员人工核对，本站不抓取上游内容复核。

降级作品在审核中 tab 与卡片上以「待补全」标记展示，仍可被投喂（Q2），但标题为空时不进热门/精品/《最新》与排行榜（这些 tab 只取 `verified`）。`metadata_pending` 的作品若被驳回，按第 5.5 节同样退还并清零。

`created_at` 兜底是 Q13 的已知例外：这类作品在《最新》tab 按本站投稿时刻排序，直到管理员修正。不额外引入 Redis key。

## 8. API 清单

路径前缀 `/api/media/`，Ninja 实际路由**无尾斜杠**（如 `/api/media/submit`），nginx 精确 location 与 uWSGI harakiri 白名单按此对齐（第 7.1 节）。所有接口都要限流（`AGENTS.md`），管理员专用接口例外；所有装饰器用 `decorate_view` 包装并在 docstring 开头注明；权限只在 API 层。

| 方法 / 路径 | 用途 | 权限与限流 | 备注 |
| --- | --- | --- | --- |
| `GET /ranking?sort=hot\|likes&start&count` | 作品页表格实时热度 / 累计投喂排序 | `ratelimit(key='ip', rate='5/s', group='media-ranking')` | zset → `in_bulk`；`count<=50`；只返回已审核 |
| `GET /user-ranking?sort=hot\|likes&start&count` | 排行榜页《作品》tab | `ratelimit(key='ip', rate='5/s', group='media-user-ranking')` | 两个 `user:` zset；只统计已审核作品；响应 `anchor` 是 `T_r`、`items.hot` 为 zset 原值，由前端折算；落点已确认（Q11） |
| `GET /latest?start&count` | 作品页表格发表时间排序 | `ratelimit(key='ip', rate='5/s', group='media-latest')` | **不走 Redis**，直接查库 `status='verified' ORDER BY -created_at, -id`（走 `media_latest_idx`）；`count<=50`；复用 `RankingPageOut`；评估见第 6.1 节 |
| `GET /pending?start&count` | 管理员审核队列（作品页无入口） | `ratelimit(key='ip', rate='5/s', group='media-pending')` | 直接查库 `status='pending'`，按 `submitted_at` 倒序 |
| `GET /detailbatch?ids=1,2,3` | 批量详情（卡片、嵌入） | `ratelimit(key='ip', rate='5/s', group='media-detail')` | 返回 `url` / `embed_url` / `hot_now`；`ids` 上限 50 |
| `GET /query/{mode}?value=&limit=` | 数据库页作品匹配查找 | `ratelimit(key='ip', rate='6/m', group='media-query', block=False)` + 视图内检查 `request.limited` 抛 429 | `mode` 参照 `identifier/api.py:21`，`field=title|suffix`、`limit<=1000`；最多 1000 条，超出 400 `too_many_matches`；regex 用 MySQL ICU，捕获 `DatabaseError` 3684-3700 转 400；`rejected` 作品也可见（16.1 第 5 条） |
| `GET /user/{user_id}?sort=hot\|likes\|created_at&order=&page=&pageSize` | 个人主页作品 tab | `ratelimit(key='ip', rate='30/m', group='media-user')` | **不走 Redis**，直接查库并用第 4.1 节索引排序；`pageSize<=50`；**展示所有状态且对所有人可见**（16.1 第 5 条） |
| `GET /me` | 本人红宝石余额、`likes_sent`、`banned` | `login_required_error` + `ratelimit(key='user', rate='30/m')` | 未创建 `UserMedia` 行时返回零值，不写库 |
| `POST /submit` | 投稿 | `login_required_error` + `banned_blocked` + `media_banned_blocked` + `ratelimit(key='user', rate='10/h', group='media-submit', block=True)` | 表单只有 `format` / `suffix` / `language`（select 选格式、input 填标识）；自动拉取 `title`/`created_at`/外站作者 id 并核对归属（外站作者 id 不入库）；**超时/上游不可用降级为待补全投稿**（第 7.2 节），结构性错误仍拒绝且不落库；409 重复外链（含已被驳回的外链）统一提示「该作品已投稿过，不可重复投稿」，不明说曾被驳回（P4）；403 归属不符 |
| `POST /like` | 投喂 1 个红宝石 | `login_required_error` + `banned_blocked` + `ratelimit(key='user', rate='1/s', group='media-like', block=True)` | 参数只有 `media_id`，每次固定投 1 个；每 UTC 自然日最多 10 次成功投喂，由 service 层在同一事务内计数并返回 429；**审核中作品也可投喂**，但只写 DB 不写 zset；`rejected` 作品不可投喂；返回最新 `likes` / `hot_now` / `balance` / `status` |
| `POST /admin/verify` | 管理员审核通过 | `staff_required`（含 CSRF），不限流 | 仅 `pending → verified`，按当前 `likes/hot_value` 补齐四个 zset；**投稿时已确认身份的正常投稿只接受 `id`，带 `title` / `created_at` / `external_author_id` 任一字段返回 400**（第 22、23 条）；**降级投稿必填 `title` 与 `external_author_id`**（可选 `created_at`）；`external_author_id` 是 API 层一次性核验输入，用 `AccountLinkQueue` 确认该外站账号属于投稿人，**不写入 `Media`**（第 7.2 节、16.1 第 15 条） |
| `POST /admin/reject` | 管理员驳回 | `staff_required`，不限流 | 仅 `pending → rejected`；**不删行**、填驳回审计字段、写 `media.log`、**退还红宝石**并同步清零 `likes` / `hot_value` 与投喂记录（P1 / Q12，第 5.5 节） |
| `POST /admin/reopen` | 改回待审核 | `staff_required`（含 CSRF），不限流 | 仅 `rejected → pending`，复用同一行（P5）；驳回时已退还并清零，恢复后从零重新累计，无需再处理红宝石 |
| `POST /admin/ban` / `POST /admin/unban` | 投稿封禁 / 解封 | `staff_required`，不限流 | 只改 `UserMedia.banned`；`get_or_create` 惰性建行 |
| `POST /admin/edit` | 降级投稿补录元数据 | `staff_required`，不限流 | **仅 `metadata_pending=True` 且处于 `pending` / `rejected` 的作品可编辑**，可改 `title` / `language` / `created_at`（第 23 条保留发表时间修正）；`verified` 严格终态不接受编辑（P2），正常投稿返回 400；**不接受 `url` / `format` / `suffix`**，`EditIn` 设 `extra='forbid'`，旧客户端传这些字段校验失败；改 `created_at` 会影响《最新》排序 |
| `POST /admin/delete` | 站长硬删除已通过作品 | `auth=django_auth_superuser`（会话认证自带 CSRF），不限流 | 仅 `status='verified'`；硬删除 + 退还红宝石 + 写 `media.log` 快照 + 回退四个 zset（P2，第 5.6 节）；删除后该外链可重新投稿 |
| `GET /admin/rejected?start&count` | 查看已驳回作品 | `staff_required`（只读，无需 CSRF token），不限流 | 可选；直接查 `status='rejected'` 的 `Media` 行，替代原 `GET /admin/deletion-log`；文件日志仍走 `common/api.py` 的日志接口 |

约定：

- 管理写操作一律 `POST`，`staff_required` 自带 `csrf_protect`；前端复用 `src/services/adminCsrf.ts` 安装的统一拦截器，token 入口复用 `GET /api/userprofile/admin/csrf`；第三方管理员客户端自行维护 Cookie 会话。
- 普通用户 API 不新增 CSRF，不启用全局中间件，不修改 `login_required_error` / `banned_blocked`（`ADMIN_API_CSRF.md`）。
- 错误统一用 `ninja.errors.HttpError`（400/403/404/409/429）或项目 `ExceptionToResponse`；不返回外站原始错误。Q5 的拉取失败按第 7.1 节映射为 504（超时）/ 502（上游、解析、元数据非法）/ 403（作者不匹配）；其中超时与上游错误按第 7.2 节**降级为待补全投稿**，不再返回错误，响应改为 `MediaOut(metadata_pending=true)`；结构性错误仍不落库、不写 Redis。
- `POST /submit` 的响应包含后端拉取到的 `title` / `created_at`，前端只读展示；正常投稿已在投稿链路自动核对作者归属，管理员只判断「是否与扫雷相关」，**不得改动这类作品的任何信息**（`/admin/verify` 只收 `id`、`/admin/edit` 返回 400，第 23 条）；**降级投稿**因上游不可用，须由管理员按第 7.2 节凭一次性输入的外站作者 id 补做归属核验并补录标题，也只有这类作品允许修正 `title` / `language` / `created_at`。所有响应都不含外站作者 id。
- `MediaOut` 的 `hot_now` 由后端按 `real_hot()` 计算并返回，避免前端重复实现衰减公式；作品分页 `MediaPageOut.anchor` 返回 DB 基准 `T_db`（作品字段以 DB 为准），作者榜 `UserRankingPageOut.anchor` 返回 Redis 基准 `T_r`（`items.hot` 为 zset 原值，前端按此折算实时热度），两者都只在分页响应中返回一次、不重复在每条作品里输出，也不可互相混用。
- 输出 Schema 涉及模型时优先 `create_schema`（`AGENTS.md`），实际实现为 `create_schema(Media, fields=MEDIA_OUT_FIELDS, custom_fields=..., base_class=MediaResolvers)`（不含 `suffix`），用 resolver 提供 `url`、`embed_url`、`hot_now`、`user_id`、`rejected_by`。`MediaOut` 需输出 `reject_reason` 与 `rejected_by`（P3 已确认对普通访客可见），后者按用户 id 交给前端 `PlayerName` 展示；还需输出 `metadata_pending`，供审核队列标记待补全作品；**不输出外站作者 id**（16.1 第 15 条）；`rejected` 作品也要能返回，不能只在管理接口里可见。
- `GET /latest` 是唯一按 `created_at` 做全站排序的读接口；它与 `/ranking`、`/user-ranking` 共用分页约定，但不读 Redis，也不参与四个 zset 的写入与重建（第 6.1 节）。

## 9. 权限、限流与 CSRF 的两处口径澄清

1. **面向用户不提供删除接口**：作者不能自删，需撤下的作品只能在过审前联系管理员驳回；`verified` 严格终态。原 Q9 的「删除不限流」与 `group='media-delete'` 限流作废，也不再有与投喂 `1/s` 配额串用的问题。管理员驳回 / 改回 `pending` 走 `staff_required`；**站长硬删除是唯一例外**，走 `auth=django_auth_superuser`（Ninja 会话认证自带 CSRF，参照 `videomanager/api.py:192-206`），两者按管理员 API 规范均不限流。
2. **两级封禁**：`banned_blocked` 读 `UserProfile.is_banned`（全站封禁，禁止所有写操作）；`media_banned_blocked` 读 `UserMedia.banned`（只禁止 `POST /submit`）。封禁不撤销已有作品、不禁止浏览/投喂。

另外，`decorate_view` 的参数中最后一个最先执行；docstring 的装饰器清单按实际执行顺序列出（参照 `minigame/api.py:85-92`），并显式写 `group`，避免 Ninja 共享 `Operation.run` 导致多个端点共用配额（`videomanager/api.py:66`）。

## 10. 后台任务清理、低频命令与文档

| 改动 | 位置 | 说明 |
| --- | --- | --- |
| 月度作业删除 | `common/apscheduler.py`、`common/tests.py` | 删除 `refresh_media_hot_reference` 作业与作业 id 断言；`register_jobs()` 仍清理同名持久化 job，避免旧 job 恢复 |
| 后台任务删除 | `media/tasks.py`（已删）、`config/common.py`、`common/api.py` | 无 `task_sync_media_scores` / `task_refresh_media_hot_reference`；任务清理配置与 `restart_media_sync_task` 一并移除；`db_worker` / `stop.sh` 保留给其它任务 |
| 缓存同步 | `media/services.py::sync_media_scores`、`media/cache.py::set_media_scores` | DB 事务提交后在请求路径直写四个 zset 的绝对分数，异常只记日志；无锁、无 `on_commit`、无重试 |
| 低频管理命令 | `media/management/commands/refresh_media_rankings.py` | `--reference` 推进 `T_db`、全量重建四个 zset 与 `T_r`；`--rebuild-only` 只纠偏；`--check` 只读巡检（漂移 / `T_r` 缺失非零退出码）；`--batch-size` / `--max-examples` |
| 双基准与展示 | `media/cache.py`、`media/api.py`、`media/schema.py` | `T_db`（DB）/ `T_r`（Redis）独立；作品页返回 `T_db`，作者榜返回 `T_r` |
| 前端折算 | `front_end/src/views/RankingView/MediaRanking.vue`、`src/services/mediaService.ts` | 作者榜 `redisAnchor` 按 `T_r` 折算实时热度；作品页字段以 DB 为准；两处 `anchor` 注释标明语义 |
| 文档 | `vitepress_doc/zh/guide/development/cache.md` | 五个固定 key、无锁、双基准与绝对分数策略（已同步改写） |
| 文档 | `vitepress_doc/zh/guide/development/management-commands.md` | 低频命令的 `--check` / `--rebuild-only` / `--reference` 与执行前提（已同步改写） |
| 文档 | `vitepress_doc/zh/guide/development/signals.md` | 本设计无信号，不改动 |
| 驳回日志 | `saolei/settings.py:397-432`、`media/services.py` | `media` logger 与 `logs/media.log` handler；驳回与硬删除写应用日志，不新增审计表（第 4.4 节） |
| 超时链 | `default.conf`、`uwsgi.ini:29`、`src/http.ts:7` | 投稿端点 nginx 25s / harakiri 白名单 / 前端 25s / 应用 ≤15s；详见第 7.1 节 |

生产已有 `runapscheduler` 与 `db_worker_robust` 常驻进程（`start.sh`），不新增进程、不引入系统 crontab，media 不占用它们。发布顺序：先 `migrate`，确认 `logs/media.log` 可写与外站密钥可用，再 `nginx -s reload`、用 `stop.sh` 完整终止 uWSGI / launcher / worker 后重启并实测投稿超时链，最后开放投稿入口。`T_r` 在首次调用 `get_hot_reference()`（`/user-ranking` 读取或请求路径的缓存同步）时以 `T_db` 惰性初始化，空库时四个 zset 为空即正确，因此**不需要在部署流程里跑 `refresh_media_rankings`**；如需部署自检可跑 `--check`（`T_r` 未初始化时先 `--rebuild-only`）。低频基准推进按附录 A.4 人工执行，不进部署流程。

## 11. 前端

### 11.1 路由与文件

| 文件 | 说明 |
| --- | --- |
| `src/router/index.ts` | 新增 `/works` 顶层单路由（无子路由）、`/database/works`、`/player/:id/works`、`/staff/media`；`Menu.vue:118-122` 的 `mainItems` 加入口 |
| `src/views/WorksView/App.vue` | 页面级工具栏：右端 `投稿` 与刷新按钮、`SubmitMediaDialog`、投稿通知；无 `ElTabs` / `router-view` / `keep-alive` |
| `src/components/media/MediaListPanel.vue`、`MediaListPanel.cy.ts` | `BaseTable` + `ElPagination` 单页表格：五列，点击发表时间 / 实时热度 / 累计投喂表头分别请求 `/latest`、`/ranking?sort=hot`、`/ranking?sort=likes`；`aria-sort` / `aria-pressed` 标记当前排序；标题左侧按 `format` 显示平台图标（图标地址复用 `views/UserView/AccountLinks/platforms.ts`）；`defineExpose({ refresh })` 供页面刷新按钮调用 |
| `src/views/RankingView/routes.ts`、`App.vue`、`MediaRanking.vue`、`MediaRanking.cy.ts` | 排行榜页《作品》tab：`ranking_media` 路由与 tab 文案、`BaseTable` + `ElPagination` + `useRankingQuery`、组件测试 |
| `src/components/media/MediaCard.vue`、`MediaEmbed.vue`、`MediaFeedButton.vue`、`SubmitMediaDialog.vue` | 单次投喂 / 投稿表单（select 选 `format`、input 填 `suffix`、自由文本 `language`）；卡片与嵌入组件按渐进迁移约定暂留、作品页不再引用；通用组件放 `src/components/media/` |
| `src/views/DatabaseView/MediaQueryView.vue` | 数据库页作品 tab，交互参照 `IdentifierView.vue` 的模式下拉、1000 条上限、本地分页 |
| `src/views/UserView/UserMediaView.vue` | 个人主页作品 tab，后端排序分页，参数 `hot_value/likes/created_at` |
| `src/views/StaffView/StaffMediaReview.vue` | 管理员审核队列：外链、通过、驳回、改回待审核、封禁/解封；**待补全作品通过前必须填标题与外站作者 id 供归属核验**（该 id 不入库，第 7.2 节）；**投稿时已确认身份的作品隐藏标题 / id 输入与提示，审核请求只带 `id`**（第 22、23 条）；表单不提供任何改 URL 或其它信息修改入口，正常投稿的 `title` / `language` / `created_at` 只能由投稿链路写入；另有仅站长可见的硬删除入口（二次确认，P2）；管理员页面不追求 UI 质量与复用性 |
| `src/services/mediaService.ts` | 所有请求用 `$axios`，`.catch(httpErrorNotification)`；`src/http.ts` 是唯一 Axios 实例；投稿请求单独传 `timeout: 25000`（第 7.1 节） |
| `src/views/WorksView/*.cy.ts` 等 | 组件测试；临时组件用 `render` 语法 |

### 11.2 作品页表格与数据源

表格列固定为：标题、作者（`PlayerName`）、发表时间、实时热度、累计投喂 + 投喂按钮。标题左侧是 16px 平台图标：`Media.format` 按 `B_v` / `B_a` → B 站、`c_p` → 扫雷网映射到 `AccountLinkPlatform`，图标地址复用账号关联页的 `platforms.ts`；`alt` / `title` 用全局 `platform.*` 文案。标题对有 `embed_url` 的作品渲染为按钮，点击按需打开 `ElDialog` 预览 iframe（dialog 内另给「打开原作品」外链，不跳转出去）；其余作品仍在新窗口打开外链。前两列不可排序，后三列表头是 `BaseTextButton`，点击切换原来的三种排序，`aria-sort` / `aria-pressed` 标记当前列，切换后页码回到 1；表格上方右端是 `投稿` 与刷新按钮。

| 表头 | 数据源 | 排序 | 可见性 |
| --- | --- | --- | --- |
| 实时热度（默认） | `GET /ranking?sort=hot` | 实时热度（Redis 索引 + 回表） | 仅 `status='verified'` |
| 累计投喂 | `GET /ranking?sort=likes` | 累计投喂数 | 仅 `status='verified'` |
| 发表时间 | `GET /latest` | `created_at` 倒序，同时间按 `id` 倒序；**不走 Redis** | 仅 `status='verified'` |

作品页**没有《审核中》入口**：`GET /pending` 只服务于管理员审核队列，普通用户的待审核作品只在个人主页 `GET /user/{user_id}` 查看；审核期间仍可投喂（Q2，只写 DB），投喂不改变排行榜。

数据库页作品 tab 与用户主页作品 tab 均展示所有状态（含 `pending` 与 `rejected`）、对所有人可见，并显示 `status` 状态（16.1 第 5 条）；`rejected` 作品同时展示 `reject_reason` 与 `rejected_by`（P3 已确认可见），后者用 `PlayerName` 渲染。

投稿表单与语言展示（Q4/Q5）：`SubmitMediaDialog.vue` 用 select 提交 `format`、input 提交 `suffix` 与自由文本 `language`（`maxlength=32`）；标题与发表时间由后端拉取后返回，前端只读展示；超时/上游不可用不再报错，改为提示「投稿已保留，标题由管理员审核时补全并核验外站账号」，并提示可在个人主页查看；结构性错误仍用 `httpErrorNotification` 显示分类错误（元数据非法 / 归属不符）。语言展示用前端已知 locale 映射，未命中（含空字符串）显示 i18n「未知语言 / Unknown language」；用户输入只作为文本渲染，不作为 i18n key 或 HTML。作品页表格的投喂按钮以红宝石余额为 `title`，点击走第 11.3 节的单次投喂逻辑。

排行榜页《作品》tab（`ranking_media`）：表头用 `BaseTextButton` 切换 `hot` / `likes` 两个指标，数据来自 `GET /user-ranking`，用 `BaseTable` + `ElPagination` 展示，`useRankingQuery` 管理 `sort/page/page_size` 查询参数（参照 `TournamentRanking.vue`）。榜内只统计已审核作品，行内 `PlayerName` 的组件测试需注入 `$axios` 并 `cy.mockPlayerNameFallback()`。落点已确认（Q11），Redis 数据在阶段 2 已就绪，本 tab 不需要新的后端计算。**`hot` 是 `T_r` 基准的 zset 原值，不是实时热度**：`UserRankingPageOut.anchor` 是 Redis 侧基准 `T_r`，前端 `redisAnchor` 用本地当前时间按 `0.99 ** ((now - T_r) / 1 天)` 衰减后再展示；作品页的 `MediaPageOut.anchor` 是 DB 的 `T_db`，两处基准互不混用。

### 11.3 单次投喂

按 16.1 第 17 条：`POST /like` 不再接受数量参数，每次请求固定投 1 个；服务端另有每 UTC 自然日 10 次成功投喂上限（第 5.3 节），目的是防止短时间爆发式刷数据。

`MediaFeedButton.vue` 的实现要点：

```text
sending: boolean; cooldownTimer; sentAt
onClick: 若 disabled 或 sending 则忽略；否则立即 POST /like { media_id }
send: sending = true，sentAt = Date.now()
      成功：emit('feed', result)，由列表更新 likes / hot_now / balance
      失败：httpErrorNotification(error)，不重试
      finally：按钮保持禁用至 1050ms 冷却结束（对齐服务端 1/s 窗口）
```

`onBeforeUnmount` 清理冷却定时器；不再有 `pending` 累计、`+N` 角标、`flush()` 与 `onDeactivated`。

- 服务端 `1/s` 是硬限制（`block=True`），冷却期间的多余点击被忽略，避免连点撞 429；失败请求（含每日上限 429）不消耗 DB 额度，也不重试。
- 前端不做余额预判的硬限制（只做禁用态展示）；每日剩余次数暂不展示。

### 11.4 其它前端约定

- i18n：新增可复用 messages 放 `src/i18n/locales/{zh-cn,en}.ts`，组件专有 messages 放 SFC 的 `script` 末尾（`AGENTS.md` 的 `i18nMessages` 风格）；至少完整覆盖 zh-cn 与 en，其它 locales 靠 fallback。
- UI：按 `front_end/UI_REFACTOR_PLAN.md`，直角紧凑、原生 HTML + CSS/`BaseTable` 优先、Element Plus 只用于弹窗/表单/Tabs、深浅主题、`src/styles/text.css`、PrimeIcons、vue-tippy 保持不变。
- 表格文本断言用 `cy.getTable` / `cy.extractTableData`；关闭通知用 `cy.closeElNotifications()`；渲染 `PlayerName` 的组件测试需注入 `$axios` 并用 `cy.mockPlayerNameFallback()`。
- `UserMedia.banned` 只禁止投稿：`MediaListPanel.vue` 的 `feedDisabled` 只看 `/me` 是否成功（登录态），**不得**用 `me.banned` 禁用投喂；页面内登录 / 切账号由 `store.sessionRevision` 触发重新拉取 `/me`，并用独立 request id 防止旧会话响应覆盖新会话。
- 后台审核页提供「待审核 / 已驳回 / 已通过」三个入口；硬删除接口只接受 `verified`，所以「已通过」列表复用 `GET /latest`；审核通过后自动切到「已通过」并保留选中项，站长可直接硬删除刚通过的作品。
- 本页不涉及公共 VideoAnalyzer 或离线包，正常不触发 `front_end/local-analyzer/version.json` 递增；若实现时改动会实际影响它们的共享 CSS/i18n/工具/依赖，必须先按 `front_end/local-analyzer/VERSIONING.md` 处理。

## 12. 测试与检查

后端（`back_end/saolei/`，需要 MySQL + Redis）：

- `python -m flake8`：新 app 加入 `application-import-names`、google import 顺序、`save(update_fields=...)`、`print` 等。
- `python manage.py makemigrations --check --dry-run`、`python manage.py migrate`：确认只有 `media.0001_initial`，不产生其它 app 的迁移。
- `python manage.py test media common.tests`：
  - URL 解析：三种 format 的合法/非法 URL、host 白名单、大小写、query 剥离、suffix 正则、`https://saolei.wang/bbs/{id}`、B 站 `/opus/` 动态链接、短链与重定向一律拒绝（Q6/Q7）。
  - 归属与去重：必须有 verified 绑定、重复外链 409、解绑后拒绝投稿。
  - 降级补录：`metadata_pending` 作品不填 `title` 时 `POST /admin/verify` 返回 400 且状态不变；service 层只填 `title` 即可过审、`metadata_pending=False`、`created_at` 可修正（第 23 条保留该修正），API 层仍须一次性 `external_author_id`，`POST /admin/edit` 也只对这类作品开放 `title` / `language` / `created_at` 补录；`Media` 无 `external_author_id` 字段，`create_media()` / `verify_media()` 也不接收该参数；字符串外站 id（含 `UC...` 形式）归一化后能在 API 层用于 `AccountLinkQueue` 核验，**任何路径都不落库、不进 `MediaOut`**。
  - 外站拉取（Q5/Q14）：三类 format 的字段映射单测用 `httpx.MockTransport` / `unittest.mock` 固定上游响应（覆盖 `pubdate`、`publish_time`、`post_time` 与 camelCase alias）；解析失败 / 缺字段 / 空 `items` / 标题超长 / 未来时间仍拒绝且不落库；**超时 / 非 2xx / -509 / -352 降级为待补全投稿**（`metadata_pending=true`、空 title）；作者 id 不匹配 403；语言自由文本只校验长度。外站作者 id 字符串化（含非数字 id、`bool` 拒绝）单测通过，该值只作为请求内临时返回值。部署环境用已配置的 `saolei_api_key` 跑一次真实 `post_info` 联调。
  - 审核中投喂（Q2）：审核期间 DB 累加 likes/hot 但不写 zset；审核通过后四个 zset 按累计值一次补齐；驳回后退还红宝石、立刻清零 `likes` / `hot_value` 并删除投喂记录、写 `media.log`；重复驳回幂等。
  - 驳回口径（Q12 / P1）：`pending → rejected` 不删 `Media` 行、逐条退还 `likes_sent`、同事务把 `likes` / `hot_value` 清零并删除 `MediaLikes`、`hot_value_updated_at` 不变；退还与清零必须同事务，失败一起回滚；`verified` 作品拒绝驳回；`rejected` 的同一外链再次投稿返回 409 且提示统一（P4）；无面向用户的 `POST /delete`。
  - 红宝石：`date_joined` 边界（0/23:59/24:00/48:01）、余额不足、给自己投喂、并发投喂不超支（`select_for_update`）；每日 10 次成功投喂上限（第 11 次 429）、UTC 跨日重置、失败请求不计数、退还不回退当日计数。
  - 站长硬删除（P2）：仅 `verified` 可删、`pending` / `rejected` 拒绝；逐条退还全部投喂者 `likes_sent`（含作者自投）；级联删除 `MediaLikes`；`media.log` 快照字段齐全；四个 zset 回退正确且幂等；删除后同一 `format+suffix` 可重新投稿（与被驳回不可重投形成对比）。
  - 衰减与双基准：`decay` 单位测试（1 天 = 0.99、6 天幂次、逆向 > 1）、`real_hot()` 按 `T_db` 折算、投喂增量示例（第 5.7 节）、`T_db`（DB 首行基准 / 空表兜底）与 `T_r`（Redis `SET NX` 初始化）互不要求相等、`reference_factor() = decay(T_db, T_r)`、用户总热度与逐作品求和一致；低频命令对同一 `--reference` 重跑不重复缩放 DB。
  - 请求路径直写（第 24 条 / 附录 A.3）：`create_media()` / `verify_media()` / `like_media()`（仅 `verified`）/ `hard_delete_media()` 在 DB 事务提交后调 `sync_media_scores()`；`pending` 投喂、`reject_media()` / `reopen_media()` 不写 zset；`set_media_scores()` 只用一个显式 `pipeline(transaction=True)` 写绝对 `ZADD` / `ZREM`，无 `ZINCRBY`、无 `on_commit`、无 `media.tasks`、无 `enqueue_media_score_sync`、无 `media:cache:lock`；`config/common.py` 的 media 清理项与 `common/api.py` 的 `restart_media_sync_task` 均不存在。
  - Redis 异常口径（附录 A.5）：`sync_media_scores()` 遇到 `ConnectionError` / `TimeoutError` / `ResponseError` 只记 error 日志，DB 事务照常提交、请求仍返回成功；不重试、不补偿、不入队任务、不引入 Lua / `WATCH` / 锁；`MULTI/EXEC` 部分生效或响应丢失时由下一次绝对分数写入或 `--rebuild-only` 收敛，绝不把抛异常当作「未写入」。请求路径使用 1s 短超时 Redis 客户端，不占满 2s 网关预算。
  - 并发与漂移：同一作者两个作品并发投喂时绝对值覆盖可能交错、低频命令执行期间正式 key 的写入可能被 `rename` 覆盖，均只影响派生榜单、不影响 DB；无锁、无重试，重跑 `--rebuild-only` 后与 DB 一致；硬删除后 `ZREM` 作品、作者两个 user zset 由剩余 `verified` 作品重算，无剩余作品则 `ZREM` 作者，重复执行幂等。
  - 低频管理命令：`refresh_media_rankings --reference` 用 `F()` 在 SQL 端按 `decay(T_db_old, T_new)` 缩放全表并写新 `T_db`，随后从 DB 重建四个 zset 并发布 `T_r`；`--reference` 早于 `T_db` 抛 `CommandError`；发布失败时提示 `T_db` 权威、重跑命令；`--rebuild-only` 不推进 `T`；`--check` 按 `decay(T_db, T_r)` 对比四个 zset，漂移 / `T_r` 缺失抛 `CommandError` 非零退出码，一致时输出 `matches the database`。巡检不再输出 FAILED / 积压同步任务数（media 无后台任务）。
  - 前端折算：`MediaRanking.vue` 用 `UserRankingPageOut.anchor`（`T_r`）折算 zset 原值 `hot`；作品页 `MediaPageOut.anchor` 是 `T_db`，两处不可混用；`mediaService.ts` 两个 `anchor` 注释与类型说明与之一致。
  - 投稿表单（P2）：select 选 `format`、input 填 `suffix`，提交 `format`/`suffix`/`language`；未知 format 与格式不符外链返回 400；数字 suffix 去前导零后仍按 `format` 判重。
  - 榜单可见性（P2）：审核通过但 0 分的作品同时出现在 `/ranking?sort=hot` 与 `sort=likes`，避免只在发表时间排序可见；点击表头切换排序会重新拉列表，表格上方的刷新按钮可手动重拉当前排序。
  - 审核身份（第 22 条）：`POST /admin/verify` 对 `metadata_pending=False` 的投稿只传 `id` 即通过，传入的 `external_author_id` 被忽略且响应 / `Media` 都不含该值；`metadata_pending=True` 的降级投稿仍分别因缺标题、缺 id、绑定不符返回 400/403。前端组件测试断言正常投稿隐藏 id 输入与提示、审核请求体只有 `id`，降级投稿仍显示并发送标题与 id。
  - 平台图标（第 22 条）：`MediaListPanel.cy.ts` 断言 `B_v` 标题左侧是 B 站 favicon、`c_p` 是扫雷网 icon，且图标带平台名称的 `alt`。
  - 管理员信息修改（第 23 条）：`POST /admin/verify` 对正常投稿带 `title` / `created_at` / `external_author_id` 任一字段返回 400 且作品不变；`POST /admin/edit` 对 `verified` 返回 409、对正常投稿返回 400，只对降级投稿允许改 `title` / `language` / `created_at`（含发表时间修正）；带 `url` / `format` / `suffix` 的请求校验失败且 `format` / `suffix` 保持不变。组件测试断言正常投稿审核表单无标题与 id 输入，降级投稿仍须填写并发送两者。
  - URL 去重：数字 suffix 去前导零后 `cv01646742` 与 `cv1646742`、`/bbs/09786` 与 `/bbs/9786` 命中同一唯一约束，第二次投稿返回 409。
  - 真实外站异常族：`curl_cffi` 的 `Timeout` / `ConnectTimeout` 归 504 `timeout`，`ConnectionError` / `RequestException` 归 502 `upstream_error`，四类都能经 `fetch_media_metadata_optional()` 降级为 `None`。
  - Redis 排行：投喂 / 审核通过后的四个 zset 数值与顺序（hot 分数按 `decay(T_db, T_r)` 折算）、`--rebuild-only` 全量重建只取 `status='verified'` 且与 DB 一致；驳回无需 `ZREM`；站长硬删除必须 `ZREM` 两个作品榜并按剩余作品绝对值覆盖作者两个 user zset，无剩余作品改 `ZREM` 作者，重复执行幂等。
  - 排行榜《作品》tab：`/user-ranking` 两个指标与 `media:rank:user:*` 一致、只统计已审核作品、分页边界、空榜。
  - 《最新》tab：`created_at` 倒序、`id` tie-breaker、`pending` / `rejected` 不入列、分页稳定、管理员改 `created_at` 后顺序更新；该接口不读 Redis。
  - 权限与限流：投稿 `10/h`、投喂请求 `1/s`（`django_ratelimit` 装饰器）+ 每 UTC 自然日 10 次成功投喂（DB 计数）、封禁只禁投稿、管理员接口 GET 只读；无面向用户的删除接口，故无 `media-delete` 限流；`POST /admin/delete` 只允许 `is_superuser`，普通 staff / 普通用户一律 403。
  - CSRF 回归：`Client(enforce_csrf_checks=True)` 覆盖管理员缺 token / 错 token / 不可信 Origin / 合法 token / 普通用户无 CSRF 要求；额外覆盖 `auth=django_auth_superuser` 的 `POST /admin/delete`（缺 token 拒绝、合法 token 放行，参照 `videomanager/test_video_delete.py:212-231`），并把新管理写接口加入现有回归清单（`userprofile/test_admin_csrf.py:39-45` 的做法）。
  - `common/tests.py` 的 APScheduler 作业集合不含 `refresh_media_hot_reference`；`register_jobs()` 清理同名持久化旧 job 后仍通过。
  - API 层（阶段 3，`media/test_api.py`）：18 个接口路径可由 OpenAPI 生成；读接口的 `MediaOut` 派生字段、anchor、分页与 `rejected` 可见性；投稿的绑定校验、作者不匹配 403、重复 409、结构性错误 502 不落库、超时降级 `metadata_pending=true`；降级审核 `/admin/verify` 的 `external_author_id` 一次性 `AccountLinkQueue` 核验（缺绑定 / id 不符 / 缺 title / 缺 id 分别 403/400）且响应与 `Media` 都不含该值；`staff_required` 权限矩阵、`auth=django_auth_superuser` 仅站长；`Client(enforce_csrf_checks=True)` 覆盖缺 token / 错 token / 不可信 Origin / 合法 token，并把新管理写接口加入 `userprofile/test_admin_csrf.py` 的回归清单。
- 测试统一 `@override_settings(RATELIMIT_ENABLE=False)`（需要验证限流的用例单独覆盖），Redis key 在 `setUp` 清理并 `addCleanup`。
- **已改写**：`media/test_services.py`、`media/test_cache.py`、`media/test_api.py` 已删除 `media.tasks` / `enqueue_media_score_sync` / `media_cache_lock()` / `check_media_rankings` 等旧引用，改按双基准、请求路径绝对分数写入、Redis 异常只记日志、`refresh_media_rankings --check` / `--rebuild-only` / `--reference` 与两个 `anchor` 语义编写；本轮 `manage.py test media common.tests` 共 142 个用例通过（附录 A.7）。

前端（`front_end/`）：`npm run lintfix`、`npm run typecheck`、`npm run vitest -- run`、`npm run build:openms`；组件测试用 `npx cypress run --component --browser chrome --headless --spec "src/components/media/*.cy.ts,src/views/RankingView/MediaRanking.cy.ts,src/views/StaffView/StaffMediaReview.cy.ts"`（CodeBuddy 环境可直接运行）。新增回归：作者榜按 `T_r` 折算显示实时热度（作品页 `anchor` 为 `T_db`，不可混用）、投稿封禁不禁用投喂、页面内登录后 `/me` 重新拉取、后台「已通过」入口与审核后保留选中项。E2E 与预览/开发服务器由用户按需运行。

CI 参考：`.github/workflows/backend.yml` 会跑 `makemigrations` + `migrate` + `manage.py test`，因此迁移必须与模型同步提交；`.github/workflows/flake8.yml`、`BackendSafety.yml` 同样适用。

## 13. 分阶段实施

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| 0（已完成） | `media` app 外壳、三处项目注册、本文档 | `python manage.py check` 通过；OpenAPI 可加载；`flake8` 通过；无新增迁移 |
| 1 数据层（已按状态机口径重做完成） | `utils.py` 常量/URL 解析/衰减函数/`MediaStatus`、`models.py` 三张表（`status` 状态机 + 驳回审计字段 + `metadata_pending`，**无 `external_author_id`**、无 `MediaDeletionLog`）、`0001_initial` 迁移、纯函数与模型单测 | `makemigrations --check` 干净；迁移可 `migrate`；约束/索引符合第 4 节；语言字段无枚举；`rejected` 行仍占全表唯一、禁止重投 |
| 2 服务与缓存（已完成） | `clients.py` 依赖适配与字段映射（三种 format、不新写 HTTP 客户端）、`services.py` 事务流程（驳回退还并清零、改回 `pending`、审核通过补齐 zset、站长硬删除退还与 zset 回退、应用日志）、`cache.py` 五个 key、月度任务与调度、重建命令（只取 `verified`）、LOGGING 与 nginx/uWSGI 超时链、开发文档 | 三类 format 字段映射与超时/错误分类单测通过；衰减/幂等/回退/重建单测通过；驳回清零与硬删除回退单测通过；`common.tests.APSchedulerRegistrationTests` 通过；《最新》不新增 Redis key。**前端投稿 25s 超时已由阶段 4 的 `mediaService.ts` 落地** |
| 3 API 层（已完成） | `schema.py`、`api.py`、`decorators.py`、全部读写接口（含 `/submit` 自动拉取与归属校验、`/admin/reject`、`/admin/reopen`、`/admin/delete` 的 `django_auth_superuser`）、限流与 CSRF 回归 | 所有装饰器写入 docstring；管理写接口通过 CSRF 回归；`reject_reason` / `rejected_by` 对普通访客可见；无 GET 写操作；结构性错误不落库、超时降级落库；降级投稿 `/admin/verify` 的一次性 `external_author_id` 经 `AccountLinkQueue` 核验且不落库；无面向用户的 `POST /delete`；18 个接口可由 OpenAPI 生成，nginx 精确 location 已按实际无尾斜杠路由修正 |
| 4 前端（已完成） | `router/index.ts` 的 `/works` 与 `/database/works`、`Menu.vue` 主导航、`WorksView` 单页表格（`BaseTable` + 表头排序，初版为四 tab 后改版）、`RankingView/MediaRanking.vue`、`DatabaseView/MediaQueryView.vue`、`UserView/UserMediaView.vue`、`StaffView/StaffMediaReview.vue`、`services/mediaService.ts`（投稿 timeout 25s）、`components/media/` 卡片 / 嵌入 / 投喂 / 投稿 / 列表组件与共享 `media.css`、全局与 SFC 双语 i18n | `lintfix` 0 errors（4 个既有 warning）、`typecheck` 通过、Cypress 组件测试 4 spec / 9 用例通过、`vitest -- run` 退出码 0、`build:openms` 成功；zh-cn + en 文案齐全；降级作品审核时 `title` 与一次性 `external_author_id` 必填且后者不落库 |
| 5 联调与发布 | 部署一次 `makemigrations` + `migrate` → 确认 `T_r` 惰性初始化与四个 zset 为空 / 一致（必要时 `refresh_media_rankings --check`） → reload nginx / 重启 uWSGI 与调度器/worker → 实测投稿超时链与 E2E → **一次性全量开放投稿（不做灰度）** | 作品页三种排序正确（热门 / 精品走 Redis，发表时间查库）、排行榜《作品》tab 与两个 user zset 一致且按 `T_r` 折算；拉取超时降级投稿、结构性错误拒绝；驳回退还清零且日志可查、被驳回外链无法重投；站长硬删除后四个 zset 回退正确且外链可重投；单次响应 < 300KB；`cypress/e2e/media.cy.ts` 通过；回滚方案明确（第 18 节） |

阶段 1-4 可以先合入代码；在阶段 5 完成生产迁移、确认 `T_r` 与四个 zset 初始化、超时链实测前不对外开放投稿入口，完成后一次性全量开放（不做灰度），保证未开放时不影响线上。阶段 1-5 的验收记录是各自当时的快照，其中 `rebuild_media_rankings` / `check_media_rankings`、月度刷新作业、缓存锁与后台任务均已被附录 A 的实施取代，判断当前代码以第 5、6、10、12、18 节与附录 A 为准；附录 A 的实施记录与本轮检查结果见 A.7。

阶段 1 验收记录（状态机口径重做后）：`python -m flake8`、`manage.py check`、`makemigrations --check --dry-run`、`migrate media`、`manage.py test media`（18 个测试）均通过；`check` 只剩既有的 `staticfiles.W004`（`dist/` 目录不存在）。全量 `manage.py test` 另有 2 个与本功能无关的既有失败：`accountlink/wom/test/tests.py:198` 的 `test_update_wom`（`update_time` 未变化）与 `videomanager/test_video_hashes.py:11` 的 `test_hashes_entire_memory_or_temporary_upload_and_rewinds_for_parser`（`_safe_remove()` 参数不匹配）。功能尚不完整时不追求全量测试通过，留待后续阶段统一处理。

阶段 2 验收记录（含降级口径修订与「外站作者 id 不入库」修订后）：本地 `migrate media zero` 后重新生成不含 `external_author_id` 的 `0001_initial`；全量 `python -m flake8`、`manage.py check`、`makemigrations --check --dry-run`、`migrate media`、`manage.py test media common.tests.APSchedulerRegistrationTests`（54 个测试：media 48 个、调度作业 6 个）与 `read_lints` 均通过；`check` 只剩既有的 `staticfiles.W004`。`monitor/cache.py` 已把五个 key 纳入固定内存统计清单；`cache.md`、`management-commands.md` 已同步。B 站依赖只有全局 `request_settings`，`clients.py` 在单次调用内临时把 timeout 设为 8s 并在 `finally` 恢复原值，不长期改变 `accountlink` 的 B 站调用行为；该折中在同进程并发请求下仍有短暂影响，部署前应确认 web 进程为单线程。

阶段 3 验收记录：`python -m flake8`、`manage.py check`、`manage.py makemigrations --check --dry-run`、`api.get_openapi_schema()`（178 条路径，其中 `/api/media/` 18 条）、`manage.py test media common.tests.APSchedulerRegistrationTests userprofile.test_admin_csrf.AdminCsrfTests`（84 个测试：media 67、调度作业 6、既有 CSRF 回归 11）与 `read_lints` 均通过；`check` 只剩既有的 `staticfiles.W004`。`default.conf` 的精确 location 由 `/api/media/submit/` 修正为 `/api/media/submit`（Ninja 实际路由无尾斜杠），`uwsgi.ini` 白名单注释同步；前端投稿 25s 超时与页面仍属阶段 4。

阶段 4 验收记录：`front_end` 下 `npm.cmd run lintfix` 最终 0 errors、4 个既有 `vue/one-component-per-file` warning；`npm.cmd run typecheck`（vue-tsc）通过；`npm.cmd run vitest -- run` 与 `npx.cmd vitest run --reporter=verbose` 均退出码 0（输出未给出完整用例汇总，故不记录通过数）；Cypress 组件测试以 `--component --browser chrome --headless` 指定 `src/components/media/MediaCard.cy.ts`、`MediaFeedButton.cy.ts`、`SubmitMediaDialog.cy.ts` 与 `src/views/RankingView/MediaRanking.cy.ts`，共 9 个用例通过（4 + 2 + 1 + 2）；`npm.cmd run build:openms` 成功，生成 `OpenMinesweeperVideoAnalyzer-0.2.2.zip`，仅有既有的 Vite 无扩展名 import、mediabunny BigInt 目标环境与 `module` externalized 警告。首次构建在清空 `dist/assets` 时被 IDE 批量删除守卫拦截（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`，1120 项 > 500 阈值），按 CodeBuddy 约定用 `Move-Item front_end/dist .tmp/dist_stage4_backup` 改名保留后重跑成功；旧 `dist` 备份保留在 `.tmp/dist_stage4_backup`，阶段 5 前可由用户自行清理。按 `front_end/local-analyzer/VERSIONING.md`，本阶段改动不实际影响公共 VideoAnalyzer 或离线包，`version.json` 未递增（仍为 `0.2.2`）。E2E、预览与开发服务器按约定未运行。本阶段新增 `views/WorksView/`（App.vue、routes.ts、HotView / LikesView / LatestView / PendingView）、`views/RankingView/MediaRanking.vue` 与 `.cy.ts`、`views/DatabaseView/MediaQueryView.vue`、`views/UserView/UserMediaView.vue`、`views/StaffView/StaffMediaReview.vue`、`components/media/`（`MediaCard.vue`、`MediaEmbed.vue`、`MediaFeedButton.vue`、`MediaListPanel.vue`、`SubmitMediaDialog.vue`、`media.css` 与 3 个 `.cy.ts`）、`services/mediaService.ts`，并同步 `router/index.ts`、`Menu.vue`、四个 `App.vue` 的 tab / route 与 `i18n/locales/{zh-cn,en}.ts`；`mediaService.ts` 的 `SUBMIT_CONFIG` 已把投稿 timeout 设为 25s，与 `default.conf` 精确 location 的 25s 对齐。

阶段 5 验收记录（本地部分）：新增 `front_end/cypress/e2e/media.cy.ts`，含 5 个用例（`Before All` 造数据，以及无已验证绑定 403、用真实 B 站视频 `BV1eB4y1F7Ao` 投稿成功并出现在《审核中》列表、重复投稿 409、作者主页作品 tab 可见）。绑定用 `cy.request` 建 `AccountLinkQueue` 后由 `cy.adminRequest` 调 `POST /api/accountlink/verify/` 置 `verified=True`，identifier 为该视频真实作者 mid `349467963`（本地 `.venv` 的 `bilibili_api.video.Video.get_info()` 实测：标题「【扫雷比赛】巨佬群殴！史上最燃的扫雷大赛！第八届金羊杯总结视频」、`pubdate=1621436166`）；外站拉取失败时投稿降级，spec 按 `metadata_pending` 分支分别断言空标题与真实标题，两条链路都覆盖。静态检查：`npm.cmd run typecheck` 通过、`npm.cmd run lintfix` 0 errors / 4 个既有 `vue/one-component-per-file` warning、`npx.cmd eslint cypress/e2e/media.cy.ts` 通过。后端部署前置检查：`python -m flake8`=0、`manage.py check`=0（只剩既有 `staticfiles.W004`）、`makemigrations --check --dry-run`（No changes detected）、`manage.py migrate media`（No migrations to apply）、`manage.py rebuild_media_rankings`（当时的命令，现已由 `refresh_media_rankings` 取代；0 verified rows，`anchor_changed=False`）均通过。**E2E 本身未运行**（按 CodeBuddy 约定由用户执行，命令见 18.3）；预览与开发服务器未启动；本轮只新增 spec 与文档，未重跑 `build:openms`、Vitest 与组件测试。生产端的迁移、确认 `T_r` 初始化、reload nginx / 重启 uWSGI 与 worker、超时链实测、一次性全量开放均未执行，按 18.2 顺序由部署侧完成，回滚见 18.4；「不做灰度」口径见 16.1 第 16 条。

`media/migrations/0001_initial.py` 由 `makemigrations` 自动生成，受 `.gitignore` 的 `**/migrations/*` 规则忽略（仅 `migrations/__init__.py` 例外），提交阶段 1 时须 `git add -f back_end/saolei/media/migrations/0001_initial.py`。本地每次模型改动重新生成干净的 `0001`，生产端在阶段 5 生成并执行一次迁移（16.1 第 7 条）。

## 14. 口径确认与核对结论

| # | 问题 | 默认实现 / 结论 |
| --- | --- | --- |
| Q1（已作废） | 「被删除的投稿…从 UserMedia 扣减」是否指退还所有投喂者的红宝石？ | **废除**：16.1 第 2 条去掉了自删功能，不存在作者自删路径；仅管理员驳回退还（Q12） |
| Q2（已确认） | 审核中的作品能否被投喂？ | **能**：审核期间照常写 DB 与 `MediaLikes` 但不写 zset；审核通过补齐四个 zset，驳回按 Q12 退还 |
| Q3（已确认） | 审核中作品是否进入数据库页检索、个人主页？ | 默认实现：进入，带状态标记；作品页热门/精品/最新与排行榜页《作品》tab 排除。16.1 第 5 条进一步确认 `rejected` 作品在作者主页与数据库页对所有人可见 |
| Q4（已确认） | `language` 的取值集合？ | 只限制字符串长度（`max_length=32`），不限制内容；模型无枚举；前端无法识别显示「未知语言」（第 3.2 节） |
| Q5（已按 16.1 第 13、15 条修订） | 投稿时是否自动拉取标题、发表时间、外站作者 id？ | **是**：自动拉取并核对归属，外站作者 id **不入库**；**外站超时 / 上游不可用时仍保持投稿**、落为待补全作品（无标题），管理员审核时必须补录标题、并填入投稿人在外站的 id 供 `AccountLinkQueue` 一次性核验；结构性错误仍拒绝。详见第 7.1、7.2 节 |
| Q6（已确认） | `c_p` 的 URL 前缀？ | `https://saolei.wang/bbs/{id}`，suffix 为纯数字；旧 `www.saolei.wang/BBS/Title.asp?Id=` 不接受 |
| Q7（已确认） | B 站短链？ | 不支持任何短链，客户端不跟随重定向；`B_v` = BV 号、`B_a` = `cv` 后数字；B 站 `/opus/`（动态）链接一律拒绝 |
| Q8（已确认） | 「每天 1%」的定义？ | 连续指数 `0.99 ** (Δt / 1 天)`，不是每日阶梯、不按半衰期换算 |
| Q9（已作废） | 删除接口「不限流」如何落地？ | **废除**：16.1 第 2 条去掉了删除接口，不再有 `POST /delete` 与 `group='media-delete'` |
| Q10（已确认） | 红宝石是否封顶 / 是否按自然日发放？ | 不封顶、按注册起完整 24h 周期累计、无定时任务 |
| Q11（已确认） | 作者 `hot_value` / `likes` 求和榜的前端落点？ | 排行榜页新增《作品》tab（`ranking_media`），复用已有的 `media:rank:user:hot` / `media:rank:user:likes` 与 `GET /user-ranking`，不新增 Redis 计算 |
| Q12（已按 16.1 更新） | 管理员驳回？ | **不删行**：`pending → rejected` + 填驳回审计字段 + 写 `media.log` 应用日志 + **退还红宝石并立刻清零** `likes` / `hot_value` 与投喂记录（P1）；`verified` 严格终态，仅站长可硬删除（P2）；被驳回外链无法重投，只能由管理员 `POST /admin/reopen` 改回 `pending`。无独立审计表（第 4.4、5.5、5.6 节） |
| Q13（已确认） | 《最新》按外站发表时间 `created_at` 还是本站投稿时间 `submitted_at`？ | `created_at`（外站发表时间，由上游 API 返回） |
| Q14（已核对） | 来源平台元数据接口契约？ | 已通过本地 `.venv` 中两个固定版本依赖的源码与真实/离线实测核对：B 站 `Video` / `Article` 详情、扫雷网 `Client.post_info` 均提供 `title` / 发表时间 / 外站作者 id（后者仅用于一次性归属比对），Q5 不阻塞；`Opus` 因无稳定标题字段不接入。`media/clients.py` 只做适配，无需新写 HTTP 客户端。字段映射、鉴权、节流与风控见第 7.1 节；`saolei_api_key` 已由站长配置 |

## 15. 交付检查清单

- [ ] 阶段 0：`media` app 外壳、`INSTALLED_APPS`、`setup.cfg`、`saolei/api.py` 已接入，本文档已评审。
- [ ] 第 14 节 Q1-Q14 已确认/核对；Q1、Q9 按 16.1 作废，Q12 按状态机口径更新；P1-P5 已确认并落实（16.1 第 8-12 条）；附录 A.5 的 Redis 写入原子性口径已确认（不做重试、接受偶发漂移）；当前无待定口径，附录 A 已在未提交改动中落地（A.7）。
- [ ] `saolei_api_key` 已由站长配置；部署环境验证 `read_secret('saolei_api_key')` 可读取并跑一次真实 `post_info` 联调；`post_info` 401 归入 `upstream_error`（按第 7.2 节走降级路径），部署联调应确认密钥正确；单测用 MockTransport，不依赖真实密钥。
- [ ] 模型迁移由 `makemigrations` 生成并随代码提交；`migrate` 与 CI 的 `makemigrations` 不产生额外迁移；三张表（`Media` / `MediaLikes` / `UserMedia`）、`status` 状态机、`metadata_pending`、**无 `external_author_id` 字段**（16.1 第 15 条）、无 `MediaDeletionLog`；本地重复生成 `0001` 不影响生产（16.1 第 7 条）。
- [ ] 《最新》tab 不新增 Redis key、不参与四个 zset 的写入与重建，但必须有 `media_latest_idx`；排行榜页《作品》tab 复用两个 user zset 并纳入 `refresh_media_rankings` 的重建与 `--check` 验收；重建只取 `status='verified'`。
- [ ] 投稿链路超时链落地：应用客户端 ≤15s、`default.conf` 精确 location 25s（阶段 3 已修正为无尾斜杠 `/api/media/submit`）、`uwsgi.ini:29` harakiri 白名单已配置；前端投稿 timeout 25s 已由阶段 4 的 `mediaService.ts` `SUBMIT_CONFIG` 落地；部署后 reload nginx / 重启 uWSGI 并实测。
- [ ] 驳回日志：`settings.py` 的 `media` logger 与 `logs/media.log` 可写、驳回与站长硬删除时应用日志可查（硬删除含作品快照）；不新增审计表。`rejected` 行仍占全表唯一、禁止重投；站长硬删除释放唯一性后可重投。
- [ ] `flake8`、`manage.py test`、前端 `lint` / `typecheck` / `vitest` / `build:openms` 与指定组件测试全部实际运行并记录结果（后端见阶段 1-3、前端见阶段 4 验收记录）；附录 A 实施后本轮已复跑：`python -m flake8`=0、`manage.py check`=0（仅既有 `staticfiles.W004`）、`manage.py test media common.tests` 142 个用例通过、`npm run lint` 0 errors / 4 个既有 warning、`npm run typecheck`=0、`vitest run` 101 文件 873 用例通过、`MediaRanking.cy.ts` 3 用例通过（A.7）。
- [ ] 按附录 A 改写 `cache.md`、`management-commands.md`（已完成）；新增管理写接口加入 CSRF 回归清单；`common/tests.py` 作业集合已删除 media 月度作业 id。
- [ ] 部署：确认 `T_r` 惰性初始化与四个 zset 为空 / 一致（必要时 `refresh_media_rankings --check` / `--rebuild-only`），确认 media 月度作业与同步任务已删除、其它后台任务 worker 正常，再一次性全量开放投稿入口（不做灰度，16.1 第 16 条）；步骤与回滚见第 18 节。

## 16. 状态机口径变更与确认台账

第 1 阶段实现后，站长就「改成软删除」给出 7 条答复，随后确认 P1-P5，据此把删除路径整体改为状态机并收紧红宝石与权限口径。本节是这批口径的唯一来源，覆盖第 1、4、5.5、5.6、6、8、9、11、12、13、14、15 节中的相关表述。

### 16.1 已确认口径

| # | 站长答复 | 落地结论 |
| --- | --- | --- |
| 1 | 方案 B | `Media.status`（`pending` / `verified` / `rejected`）替换 `verified` bool；`media_pending_idx` / `media_latest_idx` 前缀由 `verified` 改为 `status` |
| 2 | 去掉自删；需要删除的在过审前联系管理员驳回；已通过审核发出的不允许删除 | 删除面向用户的 `POST /delete` 与 `group='media-delete'` 限流；`verified` 严格终态，不能驳回或退回重审；Q1、Q9 作废。**经 P2 补充**：唯一例外是站长硬删除（第 5.6 节） |
| 3 | 管理员可以把状态改回 `pending` | 提供 `rejected → pending` 恢复，复用同一行而不新建投稿，解决误驳回 |
| 4 | 按照建议 | 删除 `MediaDeletionLog` 表与 `MediaDeletionAction` 枚举，驳回审计字段并入 `Media`；Q12 的「写入日志」只保留 `media.log` 文件日志 |
| 5 | 作者主页对所有人都可见 | `rejected` 作品在作者主页与数据库页对所有人可见并显示状态，不隐藏；作品页热门/精品/最新与排行榜页《作品》tab 仍只展示 `verified` |
| 6 | 现在不设置删除功能，只有驳回 | 不提供面向用户的删除功能，不存在软删除记录的清理/归档问题；除站长硬删除外作品行永久保留，`format+suffix` 全表唯一持续生效，被驳回 URL 无法重新投稿。**经 P2 补充**：站长硬删除会释放唯一性，该 URL 可重新投稿 |
| 7 | 本地迁移无所谓，生产端在整个计划执行完毕后进行一次自动迁移 | 本地每次模型改动都重新生成干净的 `0001_initial`；生产端在阶段 5 生成并执行一次迁移，不叠加中间历史迁移 |
| 8 | P1：`rejected` 时 `likes` / `hot_value` 随退还立刻清零 | 同一事务内清零两个字段并删除该作品 `MediaLikes` 行，`hot_value_updated_at` 不动；`rejected → pending` 恢复后从零累计，无需再处理红宝石（第 5.5 节） |
| 9 | P2：`verified` 严格终态，如需变动由站长硬删除并退还红宝石 | 只允许 `pending → verified`、`pending → rejected`、`rejected → pending`，`/admin/edit` 也仅限 `pending` / `rejected`；新增 `POST /admin/delete`，`auth=django_auth_superuser` + CSRF，退还红宝石、写 `media.log` 快照、回退四个 zset，删除后外链可重投（第 5.6 节） |
| 10 | P3：`reject_reason` / `rejected_by` 可见 | `MediaOut` 输出这两个字段，作者主页与数据库页对普通访客展示，`rejected_by` 用 `PlayerName` 渲染（第 8、11 节） |
| 11 | P4：按建议 | `/submit` 命中已被驳回的同一 URL 返回 409，统一提示「该作品已投稿过，不可重复投稿」，不明说曾被驳回（第 8 节） |
| 12 | P5：按建议 | 独立 `POST /admin/reopen`，`staff_required` + CSRF，仅 `rejected → pending`，复用同一行（第 8 节） |
| 13 | 外站超时：保持投稿，但没有 title；管理员审核时必须填入投稿人在外站的 id（验证身份）和对应投稿的标题 | 修订 Q5：`metadata_pending=True` 的降级投稿，`title` 为空、`created_at` 用本站投稿时刻兜底；`POST /admin/verify` 必填 `title` 与 `external_author_id`，后者是 API 层一次性核验输入，用 `AccountLinkQueue` 核验归属、**不入库**（另见第 15 条）；仅 `timeout` / `upstream_error` 降级，`parse_error` / `invalid_metadata` 仍拒绝（第 7.2 节） |
| 14 | 该机制接入 YouTube 等平台时还要复用 | 降级与补录做成平台无关流程：一次性输入的外站作者 id 统一由 `normalize_external_author_id()` 归一化为字符串（≤128，兼容 `UC...` 频道 ID / `@handle`）；新增平台只改 `utils.py` 映射、`clients.py` 分派分支与 `accountlink` 平台枚举，不动 service / cache / API 业务流程（第 17 节） |
| 15 | 不需要存外站作者ID；管理员填入该ID是用于在accountlink里验证该作品确实属于该user | 删除 `Media.external_author_id` 字段与迁移列；`clients.MediaMetadata.author_id` 与 `POST /admin/verify` 的 `external_author_id` 都只是请求内的一次性归属核验输入，API 层用 `AccountLinkQueue(platform=format_to_platform(format), identifier=..., userprofile=media.user, verified=True)` 核验；`create_media()` / `verify_media()` 不接收该参数，`Media`、`media.log` 与 `MediaOut` 都不含该值；平台无关流程不变（第 4.1、7.2、8、17 节） |
| 16 | 不做灰度 | 阶段 5 完成生产迁移、确认 `T_r` 与四个 zset 初始化、超时链实测与 E2E 后**一次性全量开放投稿入口**，不设灰度名单、白名单或按比例放量；前端入口随代码上线，没有运行期开关；发布前用第 18 节的联调清单与 E2E 兜底，出问题按第 18 节回滚方案整体回退（第 13、15、18 节） |
| 17 | 放弃「单次离线红宝石上限 15 + `likes_left` 代替 `likes_sent` + 登录时按上次登录时间发放」；改为限制每天投喂数量：去掉 `/like` 的 `count` 参数（每次只投 1 个）、每 UTC 自然日最多 10 次成功投喂，DB 计数按 UTC 重置 | 放弃原方案（需改登录链路、模型语义与迁移）；`UserMedia` 新增 `daily_likes` / `daily_date`，`services.like_media()` 在 `select_for_update()` 事务内做跨日重置、上限 429 与「成功才计数」，`select_for_update()` 保证并发不超额；`1/s` 请求级限流保留做瞬时防护，二者互补防爆发刷数据；不用 `django_ratelimit` 的 `10/d`（固定窗口 + crc32 偏移、只计请求不计成功）也不引新依赖；前端取消批量累计，改为单次点击单请求 + 冷却禁用；驳回 / 硬删除只退还 `likes_sent`，不回退当日计数（第 4.3、5.1、5.3、8、11.3、12 节） |
| 18 | 代码审查 P1/P2 修复（不改产品口径） | 月度刷新改 SQL 端 `F()` 乘算且不覆盖已提交投喂；新 anchor 在 DB 换算提交后发布、随后幂等补齐窗口内新行；投喂按 DB 行自身基准折算（当时由 Redis 增量 `WATCH anchor` 换算，后由第 19 条改为绝对值覆盖）；投喂与退款统一「先 `Media` 后 `UserMedia`」锁顺序；数字 suffix 去前导零；后台增加「已通过」入口并保留审核后选中项；`me.banned` 不禁用投喂、页面内登录刷新 `/me`；作者榜按当时的单基准 `anchor` 衰减展示实时热度（现为 `T_r`）；`curl_cffi` 原生超时/连接异常纳入降级分类（第 3.3、5.2、5.3、5.4、6、7.1、11、12、18.3 节） |
| 19 | 第二轮 P2 并发审查修复（不改产品口径） | 放弃 `ZINCRBY` 增量回调，四个 zset 改由 `sync_media_scores()` 在 `media:cache:lock` 内按**回调执行时刻的 DB 绝对值**一次 `MULTI/EXEC` 覆盖：解决硬删除后的迟到投喂重建作品、作者分数归零后事务外 `ZREM` 清掉新投喂、重建快照覆盖期间增量三个问题；`create_media()` 从读 anchor 到插入并复核基准全程持锁，月度刷新三步各自持锁，解决旧基准新行；`rebuild_rankings()` 持锁覆盖快照与发布，锁过期报错保留旧榜；管理命令要求低峰期暂停相关写操作（该持锁投稿后由第 20 条改为请求侧零锁等待 + 后台基准收敛）（第 5.2、5.3、5.4、5.6、6、10、12、18.3 节） |
| 20 | 请求锁等待超出超时预算（P2，不改产品口径） | 普通 API 的 Nginx 2s / uWSGI 10s 容不下 `media:cache:lock` 的 60s 等待，且 `on_commit` 回调可能在进程被杀前未执行。改为**请求路径零 Redis 写入、零锁等待**：缓存同步变成业务 DB 事务内入队的持久化 `task_sync_media_scores`，任务行与红宝石扣除 / 审核状态同事务提交；worker 非阻塞取锁 + 退避延迟重排（累计约 315s > 300s 锁 TTL，最多 8 次），锁只在后台任务 / 管理命令里阻塞；`create_media()` 去掉请求侧锁，旧基准行由后台任务用 `F()` 收敛；`config/common.py` 增加同步任务 1 天清理（第 5.3、5.4、6、10、12、18.3 节） |
| 21 | 竞态取舍与失败可检测（P2，产品口径已确认） | 确认「偶发竞态导致缓存滞后可接受，只要 DB 正确，但失败必须能检测到」，最终一致即可，**不做请求内 best-effort 同步**。重试耗尽改抛 `MediaCacheSyncError` 使任务变 FAILED（管理页 / monitor 快照可见），`restart_media_sync_task()` 重跑时归零 `attempt`；新增只读 `check_media_rankings` 巡检命令对比四个 zset 与 DB，漂移或 anchor 缺失以非零退出码告警，并输出 FAILED / 积压任务数；修复手段是 `rebuild_media_rankings` 或重启失败任务；月度刷新 / 重建的 `media_cache_lock(blocking=True)` 取锁失败改为抛 `MediaCacheLockError` 并记 error 日志，任务变 FAILED 而不是在未持锁状态下跑完并被记为成功，`blocking=False` 仍返回 `None` 供同步任务延迟重排（第 6、10、12、18.3 节）。该口径已由第 24 条与附录 A 整体覆盖并已实施：后台同步链路、缓存锁与 FAILED 任务检测全部删除，本条保留为历史决策记录 |
| 22 | 作品页标题左边放对应平台图标；投稿时后端已确认身份的作品，管理员审核时不再需要输入 id 核实 | 标题列按 `Media.format` 映射到 `AccountLinkPlatform`，复用账号关联页平台图标；`metadata_pending=False` 表示投稿时已用上游 `author_id` 核对过绑定，`POST /admin/verify` 只需 `id`，后台表单隐藏 id 输入与提示；`metadata_pending=True` 的降级投稿仍按第 13/15 条要求管理员填标题与一次性 id（第 7.2、8、11、12、18.3 节）。第 23 条进一步把正常投稿带信息字段改为显式 400 |
| 23 | 不允许管理员改 url；管理员的信息修改权限只有在数据获取失败时，设置标题 | 三项确认：① `POST /admin/edit` 只删 `url` 字段，保留 `title` / `language` / `created_at` 的补录能力，且 `EditIn` 设 `extra='forbid'`，旧客户端传 `url` / `format` / `suffix` 直接校验失败而非静默忽略；② 降级投稿的发表时间修正视为元数据补录，**保留**，`Q13` 的「管理员可修正」口径不变；③ 正常投稿的任何信息修改尝试显式 400。为使「只有在数据获取失败时」与③自洽，`/admin/edit` 限定为仅 `metadata_pending=True` 且未过审的作品（`verified` 仍 409），`POST /admin/verify` 对 `metadata_pending=False` 的作品带 `title` / `created_at` / `external_author_id` 任一字段返回 400；前端移除 `MediaEditPayload.url`，审核表单标题输入也只在降级投稿显示（第 3.3、7.2、8、11、12、18.3 节） |
| 24 | 缓存与基准简化重构（**口径已确认并已实施**，实施记录见附录 A.7；推翻讨论中「去掉四个 zset」的中间方向） | ① 四个 zset 全部保留，不新增 DB 索引，`/ranking` 仍读 zset；作品 zset 只提供排序索引、字段回 DB 取并以 DB 为准，作者榜为派生数据、以缓存为准并返回原值 + `T_r` 由前端折算。② `T_db`（DB）与 `T_r`（Redis）各自独立、不要求相等或原子同步，投喂仍按 `1/decay(T, now)` 折算，衰减保持严格连续。③ 请求路径一个显式 `transaction=True` 的 pipeline 写四个 zset 的绝对值（`MULTI/EXEC`），**不做后台任务重试**、不补偿；Redis 异常只记日志，DB 事务照常提交，允许偶发错误与排序轻微不正确，漂移由 A.4 管理命令纠偏；不引入 Lua / `WATCH` / 额外锁。④ T 推进改为低频管理命令（防浮点上溢，double 下以年为单位），不进部署流程、不做月度作业、`start.sh` / `stop.sh` 不动；命令从 DB 全量重算 + `rename` 发布，不用 `ZUNIONSTORE`，执行期间不阻塞写、接受漂移。⑤ 不迁移、不删 `hot_value_updated_at`，部署前只读核对基准是否已统一。⑥ 接受管理命令期间竞态与同作者并发覆盖交错，不影响 DB 正确性。实现差异：1s 短超时 Redis 客户端、`read_db_hot_reference()` 取首行基准、`get_hot_reference()` 用 `SET NX` 初始化 `T_r`、命令 `--check` / `--rebuild-only` / `--reference` 与 `register_jobs()` 清理旧持久化 job（附录 A.1-A.7） |

当前无待定口径；附录 A 已在本工作区的未提交改动中落地（含 A.5 的「不做重试、接受偶发漂移」），第 5、6、10、12、18 节已同步改写，A.7 记录本轮实施与检查结果，仅剩生产部署动作待部署侧执行。本节台账第 18-21 条记录的是已被附录 A 覆盖的历史方案，其中「anchor」「月度刷新」「锁」「后台任务」等表述不代表当前代码。P1-P5（第 8-12 条）、降级投稿、平台扩展、外站作者 id 不入库（第 13-15 条）、不做灰度（第 16 条）、每日投喂上限（第 17 条）、作品页平台图标 / 审核免填 id（第 22 条）、管理员信息修改权限收紧（第 23 条）与缓存与双基准重构（第 24 条）均已落到第 3.3、4.1、4.3、5.1、5.2、5.3、5.4、6、7.1、7.2、8、9、10、11、12、13、14、15、17、18 节与附录 A；后续产生新口径时另开条目记录。


## 17. 平台扩展约定（接入 YouTube 时复用）

「外站不可用 → 保持投稿 → 管理员补录」是**平台无关的一等流程**，不是 B 站/扫雷网的临时兜底。以下部分接入 YouTube 等新平台时无需改动：

- 外站作者 id **不在 `Media` 中持久化**：`AccountLinkQueue.identifier` 是 `CharField(max_length=128)`，`clients.MediaMetadata.author_id` 与 `POST /admin/verify` 的一次性输入都经 `normalize_external_author_id()` 归一化为同类型字符串；B 站 `owner.mid`、扫雷网 `Post.user_id`、YouTube 的 `UC...` 频道 ID 或 `@handle` 都能直接核验，不需要整数 UID，也不需要为 `Media` 加字段或迁移。
- `metadata_pending` 标记、`fetch_media_metadata_optional()` 的降级分类、`create_media()` 的降级落库（只补 `title`）、`verify_media()` 的必填补录标题，以及 API 层 `AccountLinkQueue` 身份核验，全部不引用具体 format。
- 投稿、投喂、审核队列、Redis 排行、驳回、恢复、站长硬删除、文件日志同理。

接入新平台只需按清单改动（以 YouTube 为例）：

| 位置 | 改动 |
| --- | --- |
| `media/utils.py` | 新增 `MediaFormat.Y_V = 'Y_v'`（**保持 3 字符短码**，`format` 字段 `max_length=3`）；`FORMAT_PREFIX` 加视频页 URL，`FORMAT_PLATFORM` 加对应 `Platform` 单字符，`SUFFIX_PATTERNS` 加视频 id 正则，host 白名单加 `www.youtube.com` / `youtu.be`（Q7 的禁短链策略需单独确认） |
| `media/utils.py` | `parse_media_url()` / `build_external_url()` / `build_embed_url()` 加分支，短链与 `/embed/` 等路径按白名单口径处理 |
| `media/clients.py` | `fetch_media_metadata()` 加一个分派分支与 `_fetch_youtube_video()`，返回 `(title, 发表时间 Unix 秒, author_id: str)`（`author_id` 只用于一次性归属比对，不落库）；失败沿用同样的四类错误与降级分类 |
| `accountlink` | `Platform` 增加 `YOUTUBE`（单字符），补齐账号绑定流程；`identifier` 已是字符串，无需改类型 |
| 迁移 | `Media.format` 的 choices 变化会生成迁移；生产端按 16.1 第 7 条在整个计划完成后一次自动迁移 |
| 前端 / 文档 | 嵌入组件、平台图标、第 3 节 URL 规则、第 7.1 节字段映射表、本节清单 |

注意事项：

- `Media.format` 是 `CharField(max_length=3)`，新增编码必须 ≤3 字符，否则要改字段长度并迁移。
- 若上游发表时间不是 Unix 秒而是 ISO 字符串，由 `clients` 的平台分支在 `_validate_metadata()` 之前统一转成数值秒，或扩展 `_validate_metadata()` 接受 datetime；降级路径不依赖发表时间，但《最新》要求 `created_at` 非空。
- 若某平台（如 YouTube Data API）因配额或密钥经常不可用，降级会成为常态：应优先保证 `/admin/verify` 的补录表单与身份核验可用，而不是继续放宽超时链。
- 新增平台不改变 Q7 短链、Q6 URL 前缀、`format+suffix` 全表唯一、P2 严格终态等既有口径；每项在对应章节单独确认。

## 18. 阶段 5 部署与联调手册（不做灰度）

阶段 5 由生产环境执行，本地只负责代码、文档与 E2E spec。按 16.1 第 16 条**一次性全量开放**，不设灰度名单、白名单或比例放量；前端入口随代码上线，没有运行期开关，因此发布前必须用 18.3 的清单与 E2E 兜底。

### 18.1 前置条件

- `media/migrations/0001_initial.py` 已随代码提交（被 `.gitignore` 忽略，须 `git add -f`）；`makemigrations --check --dry-run` 不产生额外迁移。
- `secrets.json` 的 `saolei_api_key` 可读；`logs/` 与 `assets/` 目录可写，`media` logger 能写 `logs/media.log`。
- MySQL `saolei` 与 Redis `127.0.0.1:6379` 可用；`default.conf` 的精确 location `= /api/media/submit` 25s 与 `uwsgi.ini` 的 harakiri 白名单已同步（阶段 3 已修正为无尾斜杠）。
- 前端静态资源已由 `npm run build:openms` 生成；按 `front_end/local-analyzer/VERSIONING.md`，本阶段不实际影响公共 VideoAnalyzer 或离线包，`version.json` 不递增。

### 18.2 部署顺序（一次完成，不做灰度）

| # | 操作 | 确认点 |
| --- | --- | --- |
| 1 | `python manage.py makemigrations media` → `python manage.py migrate` | 生产端只生成并执行一次 `0001_initial`（16.1 第 7 条）；三张表建立，`Media` 无 `external_author_id` |
| 2 | 首次调用 `get_hot_reference()`（读 `/user-ranking` 或请求路径缓存同步）时以 `T_db` 用 `SET NX` 初始化 `T_r`；如需部署自检，`python manage.py refresh_media_rankings --check`（`T_r` 缺失时先跑 `--rebuild-only`） | 空库时四个 zset 为空即正确，**不需要在部署流程里全量重建**；巡检按 `decay(T_db, T_r)` 对比四个 zset 与 DB |
| 3 | 确认 media 月度作业与同步任务已删除、旧持久化 job 被 `register_jobs()` 清理；其它后台任务的 worker 正常 | `common/tests.py` 作业集合无 `refresh_media_hot_reference`；`config/common.py` / `common/api.py` 无 media 任务项 |
| 4 | `nginx -t && nginx -s reload`；重启 uWSGI 与调度器/worker | `/api/media/submit` 命中 25s 精确 location，不落到 `^~ /api/` 的 2s 超时 |
| 5 | 完成 18.3 联调实测 | 全部通过后才可开放 |
| 6 | 一次性全量开放投稿入口 | 前端路由与菜单随部署生效；不做灰度，不设开关 |

### 18.3 联调实测清单

- 作品页三种排序：《实时热度》/《累计投喂》读 Redis 两个作品 zset，《发表时间》按 `created_at` 查库；排行榜页《作品》tab 与 `media:rank:user:hot` / `media:rank:user:likes` 一致，作者榜按响应的 `T_r` 折算实时热度（作品页返回 `T_db`）。
- 投稿超时链：用真实 B 站视频 `BV1eB4y1F7Ao` 实测 `POST /api/media/submit`；应用客户端 ≤15s、nginx 25s、前端 axios 25s；上游超时/不可用时降级为 `metadata_pending=true`、空 `title`，结构性错误仍 502 且不落库。
- E2E：`npx cypress run --e2e --browser chrome --headless --spec "cypress/e2e/media.cy.ts"`，覆盖无已验证绑定 403、成功投稿、重复 409、作者主页可见；spec 对「拉取成功」与「降级」两种分支都做断言。运行前需同时启动 `E2E_TEST=True python manage.py runserver 127.0.0.1:8000` 与 `npx vite --host 127.0.0.1 --port 8080 --strictPort`（见 `front_end/docs/testing.md`）。E2E 由用户运行，助手不主动执行。
- 投喂上限：连续 10 次成功投喂后第 11 次返回 429，跨 UTC 0 点后恢复；失败请求（余额不足 / 作品不存在 / 429）不消耗当日额度；并发 10 个请求同时投喂不超额（`select_for_update`）。
- 状态机：驳回退还红宝石并清零、写 `logs/media.log`、被驳回外链重投返回 409；`POST /admin/reopen` 恢复 `pending`；站长 `POST /admin/delete` 硬删除后四个 zset 回退且外链可重投。
- 降级审核与信息修改：`POST /admin/verify` 对降级投稿必填 `title` 与一次性 `external_author_id`，后者经 `AccountLinkQueue` 核验后不落库；投稿时已确认身份的正常投稿只传 `id`（后台表单不显示标题与 id 输入，带这些信息字段返回 400）；`POST /admin/edit` 只对降级投稿开放 `title` / `language` / `created_at` 补录，传 `url` / `format` / `suffix` 校验失败，`verified` 仍 409；接入 YouTube 时复用（第 17、22、23 条）。
- 性能：单次响应 < 300KB；《最新》不读 Redis、不新增 key。
- 审查修复回归：真实 B 站超时 / 连接失败应降级为 `metadata_pending=true` 而不是 500；`cv01646742` 与 `cv1646742` 视为同一作品；「禁止投稿」用户仍能投喂、页面内登录后投喂按钮可用；后台「已通过」列表可选中作品硬删除；排行榜《作品》tab 的热度随时间按 `T_r` 衰减。
- 双基准与漂移：`MediaPageOut.anchor` 是 `T_db`、`UserRankingPageOut.anchor` 是 `T_r`，两者不要求相等；人为改动一个 zset 分数后 `refresh_media_rankings --check` 应报漂移，`--rebuild-only` 后与 DB 一致；同一作者并发投喂或命令执行期间写入造成的短暂漂移只影响派生榜单，DB 始终正确（附录 A.5）。
- 请求预算：请求路径使用 1s 短超时 Redis 客户端，DB 事务提交后同步执行 `sync_media_scores()`，异常只记日志、不影响响应；没有锁、任务行、任务重启与 worker 依赖（`db_worker_robust` 仍为其它任务保留）；普通 API 在 Nginx 2s（投稿 25s）内返回。
- 失败检测：部署后运行 `python manage.py refresh_media_rankings --check`，应输出 `matches the database` 且退出码为 0；人为改动一个 zset 分数后重跑应报 `drift detected` 并以非零退出码退出；`T_r` 缺失同样非零退出。建议把巡检命令接入外部定时巡检与告警（按退出码）；不再有 FAILED 同步任务、`/tasks/restart` 与月度刷新窗口。出现漂移时人工执行 `--rebuild-only`，低频基准推进按附录 A.4 执行。

### 18.4 回滚方案

- 前端入口没有运行期开关，回退即回滚前端部署版本（撤掉 `/works`、`/database/works` 路由与菜单、排行榜/个人主页/后台 tab）；后端三张表与 18 个接口保留对既有功能无副作用，不必同步回滚。
- 迁移仅在紧急情况下用 `python manage.py migrate media zero` 撤销（会删除全部作品数据）；一般保留空表不动。
- Redis 数据异常用 `python manage.py refresh_media_rankings --rebuild-only` 从 DB 纠偏；`--check` 只读巡检，低频基准推进对同一 `--reference` 重跑不会重复缩放 DB。
- nginx / uWSGI 配置回滚后 `nginx -s reload` 并重启服务；`logs/media.log` 保留，用于事后核对驳回与硬删除记录。

## 附录 A. 缓存与基准简化重构（口径已确认，已实施）

本节是**当前缓存实现的唯一口径**：代码已在本工作区的未提交改动中落地，第 5.2-5.4、6、10、12、18 节已同步改写，16.1 第 18-21 条的锁 / 后台任务 / 失败检测方案仅作历史决策记录，不再描述当前实现。讨论过程中曾决定「去掉四个 zset、改查 DB 并加索引」，本轮**明确推翻**：四个 zset 全部保留，不新增 `(status, -hot_value)` / `(status, -likes)` 索引，`/ranking` 仍读 zset。第 24 条记录确认链，A.7 记录实施范围、本轮检查结果与剩余部署动作。

### A.1 双基准各自独立（核心）

- `T_db` 存 DB，`T_r` 存 Redis，**不要求相等、不要求原子同步**。DB 侧所有行以 `T_db` 为基准，Redis 侧所有分数以 `T_r` 为基准，各自内部自洽；两者相差一个共同常数因子，排序一致，折算到同一观察时刻后真实值也一致。这样跨存储窗口不再是正确性问题。
- 投喂仍按 `delta_hot = 1 / decay(T, now)` 折算（DB 用 `T_db`、Redis 用 `T_r`），**不固定加 1**。衰减因此仍是严格连续指数，不是阶梯；缩放只压缩数值量级，不改变语义。
- `hot_value_updated_at` 字段保留但不再作为按行独立基准参与计算；不删字段、不做数据迁移。部署前用 `SELECT COUNT(DISTINCT hot_value_updated_at) FROM media_media` 只读确认：为 0（空库）或 1 时现有 `hot_value` 直接可用；若不一致，须先人工把各行折算到同一 `T_db` 再启用——低频命令只按首行 `T_db` 做全表缩放，不做按行分组换算。`T_db` 与 `T_r` 的乘性偏差不会自动消失，靠 `reference_factor()` 在每次写入与巡检中折算，不依赖时间稀释。
- 实现：`cache.read_db_hot_reference()` 取首行 `hot_value_updated_at`（空表为当月 1 日 00:00 UTC），`cache.get_hot_reference()` 读 / 用 `SET NX` 初始化 `T_r`，`cache.reference_factor()` 返回 `decay(T_db, T_r)`；`create_media()` 新建行写当前 `T_db`，`like_media()` 按 `1 / decay(T_db, now)` 折算，`real_hot()` 仍按行的 `hot_value_updated_at` 计算；低频命令推进时全表 `UPDATE`，不按行分组换算。

### A.2 数据源与前端

- **作品 zset 仅提供排序索引**：拿到 member id 与总数后回 DB `in_bulk` 取实际字段，**以 DB 为准**（现有 `_media_page` 已如此，几乎不改）。作品页展示的实时热度从 DB `hot_value` 按 `T_db` 折算，不把 zset 原值交给前端。
- **作者榜是派生数据，以作者榜缓存为准**：API 返回 zset 原值 + `T_r`，由前端折算。前端从 DB 拿 `T_db` 用于作品页，不把 `T_r` 用于作品榜。
- 实现：`media/api.py::_media_page()` 返回 `cache.read_db_hot_reference()`（`T_db`），`get_user_ranking()` 返回 `cache.get_hot_reference()`（`T_r`）；`MediaPageOut.anchor` / `UserRankingPageOut.anchor` 的 `Field(description=...)` 分别标明语义；`MediaRanking.vue` 用 `redisAnchor` 折算，`mediaService.ts` 两个 `anchor` 注释同步。

### A.3 请求路径写入

- 四个 zset 的写入在请求路径用**一个显式 `transaction=True` 的 pipeline（MULTI/EXEC）**完成，不再创建后台任务；请求路径零锁等待、零任务行。`cache.MEDIA_SOCKET_TIMEOUT = 1`（`LOCATION` 为字符串时用 `Redis.from_url` 构造同库短超时客户端，否则回退 `get_redis_connection`），不吃掉普通 API 的 2s 请求预算（现网 `SOCKET_TIMEOUT=5`）。
- **不做后台任务重试**：pipeline 抛异常（含 `ConnectionError` / `TimeoutError` / `ResponseError`）时只记 error 日志，DB 事务照常提交，不因缓存失败回滚投喂，也不入队任何任务。允许 Redis 偶发错误与排序轻微不正确，残留漂移由 A.4 的低频管理命令全量重建纠正（产品口径见 A.5）。
- 四个 zset 一律写**绝对值**（`ZADD` 绝对分数 / `ZREM`），不用 `ZINCRBY` 增量：`EXEC` 已执行但响应丢失、或四条命令只生效一部分，都不会重复累加，下一次写入或管理命令重建即可覆盖收敛。
- 该策略覆盖所有改动 zset 的路径：`verify_media()` 过审补齐、`hard_delete_media()`、`create_media()`（新行按当前 `T_db` 落库后同步，未过审故实际为 `ZREM` 作品 + 覆盖作者榜）与 `like_media()`（仅 `verified`），不只是投喂。硬删除按 DB 重算该作者剩余作品的绝对值覆盖，**不做增量回减**；`reject_media()` / `reopen_media()` 与 `pending` 投喂不触发同步。
- 不再有 media 同步任务，但 `db_worker` 与 `stop.sh` 完整停服因其它后台任务仍然保留。`config/common.py` 的 `task_sync_media_scores` 清理项、`common/api.py` 的 `restart_media_sync_task`、原 `check_media_rankings` 的 FAILED 输出一并清理；`monitor/cache.py` 仍统计五个固定 key，无 media 任务专项统计。
- 已知并接受：同一作者两个不同作品并发投喂时两次绝对值覆盖可能交错、作者榜短暂少算；管理命令执行期间正式 key 上的写入会被 `rename` 覆盖。都不引入全局锁。
- 实现：`services.sync_media_scores()` 在上述四个入口的 DB 事务提交后调用，重查该作者所有 `verified` 作品求绝对分数并用 `logger.exception` 吞掉任何异常；`cache.set_media_scores()` 显式 `cache.pipeline(transaction=True)` 写四条 `ZADD` / `ZREM` 组合；`cache.clear_rankings()` 清五个固定 key（测试与人工维护用，无 `--clear` 命令参数）。

### A.4 低频管理命令（T 推进 + 全量重建）

- **T 仍需推进**，理由是防止 `1/decay(T, now)` 长期指数增长到浮点上溢；double 下至少需要以年为单位，因此**不需要月度刷新**，改为人工低频管理命令。不加入部署流程，`start.sh` / `stop.sh` 及其静态测试都不动，APScheduler 的 `refresh_media_hot_reference` 作业删除（含 `common/tests.py` 作业 id 断言）。
- 命令步骤：DB 事务内 `UPDATE ... F('hot_value') * decay(T_db_old, T_new)` 并写 `T_db` → 从 DB 全量重算四个 zset 写入临时 key → `rename` 原子发布 → **最后** `SET T_r = T_new`。likes 榜只重建不缩放。**不需要 `ZUNIONSTORE`**：缩放融进从 DB 重算里，而重算本来就要读 DB。
- 原 `check_media_rankings` 的巡检能力合并为该命令的 `--check`；`T_db != T_r` 时，从 DB 算期望的 zset 分数要乘 `decay(T_db, T_r)`，否则误报漂移。`check_media_rankings.py` 与 `rebuild_media_rankings.py` 均已删除。
- 命令执行期间**不阻塞请求写**，正式 key 上可能仍在增量写、会被 `rename` 覆盖而漂移；已确认接受：不影响 DB 正确性，也就不影响下一次重建 / 刷新。命令失败时显式抛错提示，不阻断服务（它本来也不在启动流程里）。
- 实现：`refresh_media_rankings` 支持 `--check`、`--rebuild-only`、`--reference`、`--batch-size`、`--max-examples`；推进 `T_db` 用 `F()` 全表更新且 `--reference` 不得早于当前 `T_db`，发布失败抛 `CommandError` 并提示 `T_db` 权威、重跑命令；`cache.rebuild_rankings()` 用 `media:rebuild:*` 临时 key + 一次 `MULTI/EXEC` 的 `rename` / `SET`，无锁；`common/apscheduler.py` 删除月度作业并清理同名持久化 job，`common/tests.py` 集合同步，`config/common.py` / `common/api.py` 的 media 任务项已清理。

### A.5 Redis 写入的原子性（已确认，不做补偿）

- **产品口径**：允许 Redis 偶发错误、排序轻微不正确；不做后台任务重试，不追求请求内的确定性补偿，漂移等发生了或定期用 A.4 管理命令刷新即可。DB 始终正确，缓存只是派生索引。
- 事实：`cache` 是同库连接的原生 redis-py 客户端（字符串 `LOCATION` 时用 `Redis.from_url` 构造 1s 短超时实例，否则用 `get_redis_connection('saolei_website')`）；`pipeline()` 默认 `transaction=True` 即自动包 `MULTI/EXEC`，现有 `set_media_scores()` 显式写出 `transaction=True`，不依赖默认值。
- `MULTI/EXEC` 只保证 Redis 单线程连续执行、其他读者看不到中间态，**不提供回滚**：`EXEC` 阶段运行时错误不会撤销已执行命令；`EXEC` 已执行但响应丢失时客户端看到的是「失败」。Redis 没有 rollback，`WATCH` 只是乐观锁，Lua 脚本同样不回滚，跨网络的「确定全部成功或全部失败」做不到。
- 因此**绝不把「抛异常」当作「未写入」**：全绝对值 `ZADD` / `ZREM`（不增量），不重放、不补偿、不引入 Lua / `WATCH` / 额外锁。四种结果（全部成功 / 部分生效 / 全部未生效 / 结果未知）都只记日志，最终由 A.4 管理命令全量重算收敛。
- Redis 失败只影响派生榜单的顺序与数值，不写回 DB、不影响红宝石与审核状态；这是本轮明确接受的代价。

### A.6 实施范围与落地状态

| 范围 | 状态 |
| --- | --- |
| `media/cache.py`：去锁、去 `ZUNIONSTORE`、双基准读写、`set_media_scores()` 显式 `transaction=True`、无锁 `rebuild_rankings()`、1s 短超时客户端 | 已落地 |
| `media/services.py`：请求路径 `sync_media_scores()` 直写四个 zset、去掉所有任务入队与 `refresh_hot_reference()`、Redis 异常只记日志 | 已落地 |
| 删除 `media/tasks.py` 及 `task_sync_media_scores` / `enqueue_media_score_sync` / `restart_media_sync_task` / `task_refresh_media_hot_reference` | 已落地 |
| `media/api.py` / `media/schema.py`：作品页返回 `T_db`、作者榜返回 `T_r` | 已落地 |
| `media/management/commands/`：删除 `check_media_rankings.py` / `rebuild_media_rankings.py`，新增 `refresh_media_rankings.py` | 已落地 |
| `common/apscheduler.py` / `common/tests.py` / `common/api.py` / `config/common.py`：清理月度作业、作业 id 断言、重启服务与任务清理期 | 已落地 |
| `front_end/src/views/RankingView/MediaRanking.vue` / `src/services/mediaService.ts`：按 `T_r` 折算、双 `anchor` 注释 | 已落地 |
| `monitor/cache.py` / `monitor/services.py`：五个固定 key 统计保留、无 media 同步任务专项统计 | 已落地（无需改动） |
| 本文档第 5、6、10、12、18 节与 16.1 台账同步改写 | 已落地 |
| `vitepress_doc/zh/guide/development/cache.md`、`management-commands.md` 同步改写 | 已落地 |
| `media/test_services.py` / `test_cache.py` / `test_api.py` 按新口径改写 | 已落地 |
| `db_worker`、`stop.sh` 及其静态测试 | 保留（其它后台任务仍需要） |

### A.7 实施记录、检查结果与剩余部署动作

**未提交改动**（以 `git status` 为准）：修改 `media/api.py`、`cache.py`、`schema.py`、`services.py`、`test_cache.py`、`test_services.py`、`test_api.py`，`common/api.py`、`common/apscheduler.py`、`common/tests.py`，`config/common.py`，`front_end/src/services/mediaService.ts`、`front_end/src/views/RankingView/MediaRanking.vue`，`vitepress_doc/zh/guide/development/cache.md` 与 `management-commands.md`，以及本文件；删除 `media/tasks.py`、`media/management/commands/check_media_rankings.py`、`media/management/commands/rebuild_media_rankings.py`；新增 `media/management/commands/refresh_media_rankings.py`。与本计划无关的未提交改动（`accountlink/mineracer/README.md`、`GAMES_API.md`、临时录像文件等）不在本附录范围内。

**本轮已完成**：

1. `media/test_services.py`、`media/test_cache.py`、`media/test_api.py` 按第 12 节清单改写：删除 `media.tasks` / `enqueue_media_score_sync` / `media_cache_lock()` / `check_media_rankings` 等旧引用，覆盖 `T_db` / `T_r` 独立与 `SET NX` 初始化、`reference_factor()` 折算、请求路径绝对分数写入与 Redis 异常只记日志、无任务行 / 无锁、迟到同步不复活、`--check` / `--rebuild-only` / `--reference` 及两个 `anchor` 语义。
2. 按 `AGENTS.md` 同步 `vitepress_doc/zh/guide/development/cache.md` 与 `management-commands.md`：删除 `media:cache:lock`、月度 `refresh_media_hot_reference`、`ZUNIONSTORE` / `WATCH`、`task_sync_media_scores`、FAILED 任务重启等旧段落，改为五个固定 key、`T_db` / `T_r`、请求路径短超时直写、低频命令 `--check` / `--rebuild-only` / `--reference` 与执行前提；`management-commands.md` 的 `stop.sh` 举例也去掉旧 media 任务名。
3. 修复 `front_end/src/services/mediaService.ts` 两处 `anchor` 注释前缺少的空行（`npm run lint` 报的 2 个 `@stylistic/lines-around-comment` error）；`npm run lintfix` 复跑未改动其它文件。

**本轮检查结果（均已实际运行）**：

| 检查 | 结果 |
| --- | --- |
| 后端 `python -m flake8`（`back_end/saolei/.venv`） | 退出码 0 |
| 后端 `manage.py check` | 退出码 0；仅既有 `staticfiles.W004` 警告 |
| 后端 `manage.py test media common.tests --noinput` | 142 个用例全部通过 |
| 前端 `npm run lint`（CI 的 `eslint .`，覆盖 `.ts`） | 0 errors；4 个既有 `vue/one-component-per-file` warning |
| 前端 `npm run lintfix` | 退出码 0；未改动其它文件 |
| 前端 `npm run typecheck` | 退出码 0 |
| 前端 `npx vitest run --reporter=dot` | 101 个文件 / 873 个用例通过 |
| 前端 Cypress 组件测试 `MediaRanking.cy.ts` | 3 个用例通过，退出码 0 |

`refresh_media_rankings --check` 的一致 / 漂移 / `T_r` 缺失、`--rebuild-only` 纠偏、`--reference` 推进与幂等、发布失败时 `T_db` 权威均由改写后的 `media/test_services.py` 覆盖并通过；`common/tests.py` 的 APScheduler 作业集合断言随 `manage.py test common.tests` 通过。后端测试需要 MySQL 与 Redis，本轮使用 `back_end/saolei/.venv`；阶段 1-5 的验收记录仍是各自当时的快照。

**剩余动作（部署侧，本地无法执行）**：按第 18.2 节顺序执行迁移、确认 `T_r` 惰性初始化、reload nginx / 重启服务、实测投稿超时链与 E2E（E2E 由用户运行），最后一次性全量开放；低频基准推进为上线后的人工低频操作，不进部署流程。步骤与回滚见第 18.3、18.4 节。
