# 作品页（media）开发计划

状态：**第 2 阶段（服务与缓存）已完成，并按「外站超时降级投稿」与「外站作者 id 不入库」口径修订**。阶段 0 的 app 外壳、阶段 1 的三张表与 `0001_initial` 迁移、阶段 2 的 `clients.py` / `services.py` / `cache.py` / 月度任务 / 重建命令 / LOGGING / nginx 与 uWSGI 超时链均已落地并通过局部检查（47 个 `media` 单测 + 调度作业断言）；API、前端页面与前端投稿 25s 超时尚未实现，按第 13 节分阶段落地。删除路径改为 `status` 状态机（第 16 节），降级投稿与平台扩展约定见第 7.2、17 节；外站作者 id 的一次性核验口径见第 16.1 节第 15 条。

本文档是实现的唯一设计基线；实现时若改变第 5 节的衰减不变量或第 9 节的权限口径，应先更新本文档。

## 1. 目标与范围

- 本站支持与其他平台账号关联（`accountlink` app）。用户把自己在对应平台发表的文字/视频作品投稿到本站，作品页展示标题、语言、发表时间、作者、平台，并外链到原作品；支持在本站页面嵌入可嵌入的作品（当前只有 B 站视频）。
- 本站**不托管**作品正文、图片或视频，也**不做自动化内容审查**。作品是否合规由来源平台负责；本站管理员只人工判断「是否与扫雷相关」，审核不通过置为 `rejected`（驳回），**不删除记录**；面向用户不提供任何删除功能，作品行原则上永久保留，被驳回的外链无法重新投稿。唯一例外是站长对已通过作品的硬删除（P2 / 第 5.6 节），该路径退还红宝石并释放外链唯一性。
- 本站提供红宝石投喂（点赞/热度）、作品页热门/精品/最新/审核中四个 tab、排行榜页《作品》tab（用户 `hot_value` 与 `likes` 排行，走 Redis）、数据库页与用户主页作品 tab、投稿封禁。
- 投稿时后端自动调用来源平台 API 拉取 `title` / `created_at` / 外站作者 id 并自动核对归属；**外站作者 id 只用于本次请求的一次性归属核验，绝不写入 `Media`**（16.1 第 15 条）。**外站超时或上游不可用时仍保持投稿**，落为「待补全」作品（无标题），由管理员审核时补录标题、并凭一次性输入的外站作者 id 核验身份；结构性错误仍拒绝。语言由投稿者自由填写，只限制长度，站点不解释取值。
- MVP 支持三类作品：`B_v`（B 站视频）、`B_a`（B 站专栏/文章）、`c_p`（扫雷网帖子）。B 站动态（`B_o`）因上游详情没有稳定标题字段而移除支持（降级路径不改变该决定），详见第 7.1 节。

不做：外站内容抓取入库、评论区、作品编辑历史、通知推送、作品推荐算法、外站账号自动同步。

## 2. 现状与可复用实现

| 现有实现 | 位置 | 本计划如何复用 |
| --- | --- | --- |
| 平台枚举 `Platform`、`AccountLinkQueue(platform, identifier, userprofile, verified)`、各平台账号模型 `AccountBilibili.id` / `AccountSaolei.id`、`PLATFORM_CONFIG` | `accountlink/models.py:11-20, 29-36, 40-49, 105-119, 260-270` | 投稿资格与归属校验；只认 `verified=True` 的绑定 |
| 绑定归属校验模板 | `accountlink/saolei/services.py:29-41`、`accountlink/msgames/api.py:40-52`、`accountlink/services.py:32-55` | API 层校验请求者归属 + service 层事务化防重复认领 |
| 外链 host 白名单与规范化 | `accountlink/msgames/utils.py:37-44` | `urlsplit` + scheme/host 白名单 + 规范化后缀 |
| 比赛积分的指数衰减 | `tournament/utils.py:8-9, 36-49`、`tournament/models.py:296-327`、`tournament/cache.py:243-274` | 衰减因子、统一时间基准、`ZUNIONSTORE` 整体缩放、`WATCH` 式幂等刷新 |
| APScheduler 周期作业 | `common/apscheduler.py:58-102`、`common/management/commands/runapscheduler.py` | 月度刷新作业；作业 id 断言在 `common/tests.py:44-65` |
| Django 6 Tasks / `django-tasks-db` | `saolei/settings.py:167-172`、`medal/tasks.py:11-31`、`accountlink/saolei/tasks.py:33-38` | 月度刷新由 cron 入队、worker 执行；防堆积 |
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
- app 内引用链条：`utils.py`（常量、纯函数，**不引入同 app 其他模块**）→ `models.py` → `services.py` → `api.py`；`schema.py` 放输出/输入 Schema；`cache.py` 放 Redis 逻辑；`clients.py` 放外站 HTTP 客户端（只依赖 `utils.py` 常量与第三方库，不引入 `models` / `services`）；`tasks.py` 放 `@task`；`decorators.py` 放 app 专用权限装饰器；`management/commands/` 放重建命令。不新增 `signals.py`（缓存写入统一在 service 的 `transaction.on_commit` 中，不用模型信号）。
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
- 投稿可以粘贴完整 URL 或只填 suffix。`utils.parse_media_url()` 用 `urlsplit` 校验 scheme/host 白名单（`www.bilibili.com`、`bilibili.com`、`m.bilibili.com` 且仅 `/video/`、`/read/` 路径；`saolei.wang` 仅允许 `https` + `/bbs/` 路径），剥离 query/trailing slash，识别 `format`，正则校验 suffix，越界返回 400。**B 站 `/opus/`（动态）链接一律拒绝**；旧 `www.saolei.wang/BBS/Title.asp?Id=` 与 `saolei.wang` 其它路径也一律不接受（Q6）。禁止用户自定义域名、协议或路径，避免开放重定向与 XSS。
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
| `created_at` | `DateTimeField()` | **对方平台的发表时间**，由来源平台 API 返回；统一转 UTC，不得晚于投稿时刻。**降级投稿用本站投稿时刻兜底**，管理员可修正（第 7.2 节） |
| `submitted_at` | `DateTimeField(auto_now_add=True)` | **新增字段**：本站投稿时间，用于审核队列与审核中 tab 排序；用户原计划未列出，但不加会缺少稳定的审核排序键 |
| `format` | `CharField(max_length=3, choices=MediaFormat.choices)` | 作品媒介 |
| `suffix` | `CharField(max_length=128)` | 规范化后的 URL 后缀 |
| `status` | `CharField(max_length=8, choices=MediaStatus.choices, default=pending)` | `pending` 未审核 / `verified` 审核通过（**严格终态**，仅站长可硬删除）/ `rejected` 已驳回；**没有删除状态** |
| `rejected_at` | `DateTimeField(null=True, blank=True)` | 驳回时间；改回 `pending` 时清空 |
| `rejected_by` | `FK(UserProfile, SET_NULL, null=True, related_name='media_rejections')` | 执行驳回的管理员；账号注销后仍留作品行；**对普通访客可见**（P3） |
| `reject_reason` | `CharField(max_length=200, blank=True)` | 驳回原因；**对普通访客可见**（P3） |
| `refunded_likes` | `PositiveBigIntegerField(default=0)` | 本次驳回实际退还的红宝石总数，用于幂等与审计；站长硬删除时该值随作品行消失，改记入 `media.log` |
| `likes` | `PositiveBigIntegerField(default=0)` | 累计投喂红宝石数；**驳回时随退还立刻清零**（P1） |
| `hot_value` | `FloatField(default=0)` | 以 `hot_value_updated_at` 为时间基准的热度；**驳回时随退还立刻清零**（P1），`hot_value_updated_at` 不动以保持 anchor 不变量 |
| `hot_value_updated_at` | `DateTimeField(default=timezone.now)` | 热度时间基准；**全站所有作品恒等于同一个 anchor 值**（第 5.2 节不变量） |

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
| `banned` | `BooleanField(default=False)` | 仅禁止投稿；不影响浏览、投喂等其它权限 |

行采用惰性创建（`get_or_create`）：不存在视为 `likes_sent=0, banned=False`。`model.save()` 必须显式传 `update_fields`（flake8 插件 `DJM100`）；`get_or_create` 内部创建不受该规则约束。

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
- 投喂数量不限、可以给自己投喂。余额不足返回 400（或 409，统一用 `HttpError`），不产生部分扣减。

### 5.2 衰减公式与统一时间基准

参照 `tournament/utils.py:36-40` 的 `tournament_score_decay_factor`，在 `media/utils.py` 定义：

```text
MEDIA_HOT_DAILY_RETENTION = 0.99      # 每天衰减 1%
decay(t0, t1) = 0.99 ** ((t1 - t0).total_seconds() / 86400)
real_hot(m, t) = m.hot_value * decay(m.hot_value_updated_at, t)
```

- 允许 `t1 < t0`（因子 > 1），便于把当前时刻的增量折算回更早的基准。
- 连续指数，不按自然日跳变；30 天约 `0.7397`，365 天约 `0.0255`。
- **不变量 I1**：任意时刻，所有 `Media.hot_value_updated_at` 都等于全站 anchor `T`（Redis string `media:hot:anchor`，ISO datetime）。新投稿、投喂、审核通过都不推进该字段；只有月度刷新任务推进 `T`。
  - 原因：用户主页要「不走 Redis，直接按 `hot_value` 排序」。只有所有作品共用同一基准时，`hot_value` 的降序才等于实时热度的降序；若投喂时把单条作品的 `hot_value_updated_at` 改为 `now`，DB 排序会失真，只能改成无法走索引的表达式排序。
  - 这也让用户总热度可以用同一个衰减系数做增量更新，与用户计划中的简化思路一致。
- `T` 以 Redis 为准，DB 中每条作品冗余保存一份，用于重建排行和离线校验；`media/cache.py` 提供 `get_hot_reference()`，缺失时以最早作品的 `hot_value_updated_at` 或当月 1 日 UTC 初始化，并写入 Redis。

### 5.3 投喂 n 个红宝石（时刻 now）

在 `services.like_media()` 的单个 `transaction.atomic()` 内：

1. `select_for_update()` 锁 `UserMedia` 行与 `Media` 行；校验登录、全站封禁、余额 >= n。**已审核与审核中的作品都可投喂**（Q2），只拒绝不存在的作品。
2. `delta_hot = n / decay(T, now)`：把「now 时刻的 +n」折算成以 `T` 为基准的等效热度。
3. `Media.hot_value += delta_hot`，`Media.likes += n`，`hot_value_updated_at` 保持不变（I1）。
4. `MediaLikes` 用 `update_or_create` 累加 `likes += n`；`UserMedia.likes_sent += n`。
5. `transaction.on_commit()` 中写 Redis：**仅当 `media.status='verified'`** 时执行 `ZINCRBY media:rank:hot delta_hot {media_id}`、`ZINCRBY media:rank:likes n {media_id}`，以及作者的两个用户榜 `ZINCRBY media:rank:user:hot delta_hot {author_id}`、`ZINCRBY media:rank:user:likes n {author_id}`。审核中作品只落 DB，等审核通过时由 `verify_media()` 按累计值一次性补齐四个 zset（第 6 节）。

说明：项目现有榜单都用 `ZADD` 覆盖式写入，但本功能是纯增量且并发写同一作品，读-改-写会丢更新，因此用 `ZINCRBY`（原子）。这是有意的例外，需写进 `cache.md`。漂移修复靠 `rebuild_media_rankings`。

### 5.4 每月刷新

- `common/apscheduler.py` 新增 id `refresh_media_hot_reference`，`CronTrigger(day=1, hour=0, minute=10, second=0, timezone=utc)`，`next_run_time=django_timezone.now()`（启动补跑）、`coalesce=True`、`max_instances=1`、`replace_existing=True`、`misfire_grace_time=None`。避开 `00:00` 的其它作业。
- 作业只负责入队 `media.tasks.task_refresh_media_hot_reference`（Django 6 Tasks / `django-tasks-db`），入队前按 `DBTaskResult.task_path + READY/RUNNING` 防堆积，参照 `accountlink/saolei/tasks.py:33-38`。worker 由现有 `db_worker_robust` 执行。
- 任务内 `services.refresh_hot_reference()`：
  1. `T_new` 取当月 1 日 00:00 UTC；`WATCH media:hot:anchor`，若已等于 `T_new` 直接返回（幂等）。
  2. `factor = decay(T_old, T_new)`，`ZUNIONSTORE` 把 `media:rank:hot`、`media:rank:user:hot` 两个 zset 按 `factor` 整体缩放，写回新 `T`（参照 `tournament/cache.py:259-274`）。乘以同一正系数**不改变排序**，所以缩放与 DB 刷新短暂的先后差异不影响页面顺序。
  3. DB 分批（如 1000 条）把 `hot_value *= factor`、`hot_value_updated_at = T_new`，`bulk_update`；只处理 `hot_value_updated_at < T_new` 的行，可中断续跑。
  4. `likes` 榜不衰减，不处理。
- 边界：Redis double 与 MySQL `FloatField` 精度；`hot_value < 1e-9` 可在重建时按 0 清理，但**月度任务不做删除**，避免排行人数抖动。
- 若部署时停机错过月份，启动补跑会一次性按 `decay(T_old, T_new)` 补齐，不按「缺几个月」重复缩放。

### 5.5 驳回作品（Q12 / P1；无用户删除路径）

按 16.1 已确认口径：**没有面向用户的 `POST /delete`，作者不能删除自己的投稿；需要撤下的作品必须在过审前联系管理员驳回；`status='verified'` 严格终态**。Q1（自删不扣减 `likes_sent`）与 Q9（删除接口限流）随之作废。已通过作品如需变动，只能由站长走第 5.6 节硬删除（P2）。

`services.reject_media(media, *, actor_id, reason=None)` 在单个 `transaction.atomic()` 内（权限判定仍在 API 层）：

1. 锁 `Media` 行；校验 `status == 'pending'`，否则拒绝（重复驳回幂等返回 409）；取 `like_records` 的 `(user_id, likes)` 列表与当前 `likes` / `hot_value`。
2. 置 `status='rejected'`，写 `rejected_at` / `rejected_by` / `reject_reason` / `refunded_likes`；`save()` 显式传 `update_fields`（`DJM100`）。**不删 `Media` 行**。
3. 红宝石退还：按 `like_records` 逐条把投喂者 `UserMedia.likes_sent -= likes`（下限 0，用 `Greatest` 或先校验），包括作者给自己投喂的部分（Q12）；投喂者多时分批更新，避免长事务。`refunded_likes` 记录实际退还总数。
4. **立刻清零（P1）**：同一事务内把 `Media.likes = 0`、`Media.hot_value = 0`，并删除该作品全部 `MediaLikes` 行，使退还后的数据库状态与「未投喂过」一致；`hot_value_updated_at` 不动，保持全站 anchor 不变量。**退还与清零必须同事务**，否则中途失败会出现「已退还但仍计数」；删除投喂记录是清零的必要配套，否则恢复后再次投喂会基于旧行累加、与 `Media.likes=0` 不一致。
5. 应用日志：事务内 `logging.getLogger('media').info(...)`（第 4.4 节）。
6. **Redis 无需操作**：审核中作品按第 6 节只写 DB、从未进入四个 zset，驳回发生在 `pending` 状态，因此不需要 `ZREM` 或 user zset 回退；`rejected` 也不参与 `rebuild_media_rankings`。
7. `format+suffix` 全表唯一持续生效，该 URL 无法重新投稿；`/submit` 命中时返回 409 与统一提示「该作品已投稿过，不可重复投稿」，不明说曾被驳回（P4）。改回 `pending` 由 `POST /admin/reopen` 完成（P5），复用同一行，因已清零而无需处理红宝石。

### 5.6 站长硬删除（P2）

`status='verified'` 严格终态，普通管理员不能驳回、改回 `pending`、编辑或删除。**唯一例外**：站长（`is_superuser`）可硬删除已通过作品，用于纠错或合规下架。

- 权限：`auth=django_auth_superuser`（Ninja 会话认证自带 CSRF，现成范式 `videomanager/api.py:192-206`），不走 `staff_required`；管理员 API 按规范不限流，docstring 开头必须列出该 auth。普通 staff 与普通用户一律 403。
- `services.hard_delete_media(media, *, actor_id)` 在单个 `transaction.atomic()` 内：锁行 → 校验 `status == 'verified'` → 取 `like_records` 的 `(user_id, likes)` 与当前 `likes` / `hot_value`、作品快照 → 逐条退还投喂者 `UserMedia.likes_sent`（与第 5.5 节同规则）→ 写 `media.log` 快照（`media_id` / `format` / `suffix` / `title` / `user_id`（本站作者）/ `actor_id` / `likes` / `hot_value` / `refunded_likes`，参照 `videomanager/services.py:51-53`）→ `media.delete()` 级联删除 `MediaLikes`。**不新建审计表**，行删除后唯一可查痕迹是文件日志。
- `transaction.on_commit()`：`ZREM media:rank:hot/likes {media_id}`；`ZINCRBY media:rank:user:hot -hot_value {author_id}`、`ZINCRBY media:rank:user:likes -likes {author_id}`，结果 <= 0 时改为 `ZREM`；重复执行幂等。与驳回不同，`verified` 作品确实在榜，必须回退。
- 唯一约束释放：`format+suffix` 行被物理删除，该外链**可以重新投稿**；这与被驳回（行仍在）不可重投形成明确区别。
- 前端不给普通用户或普通管理员暴露该入口；站长操作在 `StaffMediaReview.vue` 提供二次确认。

### 5.7 数值示例

设 `T = 2026-11-01 00:00 UTC`，`now = 2026-11-07 00:00 UTC`，`decay(T, now) = 0.99^6 ≈ 0.9415`。

- 投喂 1 个红宝石：`delta_hot = 1 / 0.9415 ≈ 1.0621`，`hot_value` 增加 1.0621，实时热度（now）= `1.0621 * 0.9415 = 1`。
- 11 月 7 日再投喂 1 个：`delta_hot ≈ 1.0621`，累计 `hot_value ≈ 2.1242`，实时热度 = `2.1242 * 0.9415 ≈ 2`（两颗都在 now 生效）。
- 12 月 1 日刷新：`factor = 0.99^30 ≈ 0.7397`，所有 `hot_value` 与两个 hot zset 同步乘以 0.7397，`hot_value_updated_at = 2026-12-01`；排序不变。

## 6. Redis 排行

统一使用 `django_redis.get_redis_connection('saolei_website')`（db0），封装在 `media/cache.py`；key 前缀 `media:`，全部参与 `monitor` 的内存统计。

| key | 类型 | score | member | 说明 |
| --- | --- | --- | --- | --- |
| `media:rank:hot` | zset | `hot_value`（`T` 基准） | `media_id` | 热门 tab，只含已审核作品 |
| `media:rank:likes` | zset | `likes` | `media_id` | 精品 tab，只含已审核作品 |
| `media:rank:user:hot` | zset | 用户所有已审核作品 `hot_value` 之和 | `user_id` | 排行榜页《作品》tab 的热度指标 |
| `media:rank:user:likes` | zset | 用户所有已审核作品 `likes` 之和 | `user_id` | 排行榜页《作品》tab 的精品指标 |
| `media:hot:anchor` | string | ISO datetime（`T`） | — | 统一时间基准；`WATCH` 目标 |

- 读取：`ZCARD` 取总数，`ZREVRANGE key start end-1` 取 id 索引，再 `Media.objects.in_bulk(ids)` / `UserProfile.objects.in_bulk(ids)` 回表组装展示字段（参照 `tournament/cache.py:302-315`）。单次返回条数上限 50，响应体远小于 300KB。score 相同按 Redis member 字典序，作为稳定但不承诺业务优先级的次序；API 保持 zset 返回顺序，不二次排序。
- **审核中作品可以被投喂（Q2 已确认）**，但审核期间**只写 DB**（`Media.likes/hot_value` 与 `MediaLikes`），不写四个 zset：热门/精品/《最新》与排行榜页《作品》tab 只展示 `verified` 作品，不做「写入后再过滤」，否则分页会出现空洞。审核通过时 `verify_media()` 按作品当前 `likes/hot_value` 一次性 `ZADD` 补入 `media:rank:hot`、`media:rank:likes`，并对作者的两个 user zset 做同样的 `ZINCRBY`；驳回只改状态并退还红宝石，因从未入榜而无需 `ZREM`（第 5.5 节）；**站长硬删除 `verified` 作品是唯一例外**，必须回退四个 zset（第 5.6 节）。
- 审核中 tab 直接查库 `status='pending' ORDER BY -submitted_at`（走 `media_pending_idx`），展示累计 likes 与实时热度并提供投喂按钮，不额外建 zset。作品页《最新》tab 同样直接查库，不额外建 zset（评估见第 6.1 节）。`rejected` 作品不在四个 tab 中，但在作者主页与数据库页对所有人可见（16.1 第 5 条）。
- 重建：`media/management/commands/rebuild_media_rankings.py` 从 DB 全量重建四个 zset 与 `anchor`，**只取 `status='verified'` 的行**（`pending` / `rejected` 一律排除），使用临时 key（`media:rebuild:*`）+ `rename` 原子发布（参照 `speedranking/top/cache.py:108-138`）；失败保留旧榜。命令供部署、Redis 故障恢复与单测使用，不做请求时懒重建。
- 一致性：DB 是事实来源，Redis 是排序索引。写 Redis 一律放在 `transaction.on_commit`；Redis 写入失败只记日志、不回滚 DB，靠重建命令修复。月度任务与投喂并发通过 `WATCH media:hot:anchor` 的 `cache.transaction` 协调（`tournament/cache.py:208-227`）；投喂的 `ZINCRBY` 不推进 anchor，无需与月度任务互斥。
- 文档：新增 key 与增量/衰减策略写入 `vitepress_doc/zh/guide/development/cache.md`；重建命令写入 `vitepress_doc/zh/guide/development/management-commands.md`。本设计不使用信号接收器，`signals.md` 无需改动。

### 6.1 《最新》tab 是否需要 Redis

**结论：不需要 Redis，直接查库**。作品页《最新》按 `created_at` 倒序展示已审核作品，读 `GET /api/media/latest`，SQL 为 `WHERE status = 'verified' ORDER BY -created_at, -id LIMIT count OFFSET start`，走第 4.1 节 `media_latest_idx`，返回结构与 `/ranking` 一致（复用 `RankingPageOut`）。理由：

1. `created_at` 由上游 API 返回后写入，是静态值（管理员纠错除外），没有衰减、没有高频增量；zset 的核心收益「O(logN) 增量维护 + 统一时间基准」在这里用不上。
2. 规模：投稿限流 `10/h` 且需人工审核，已审核作品数量增长慢；MySQL 的索引范围扫描 + `LIMIT 50` 成本不高于 `ZREVRANGE` + `in_bulk` 回表（后者还多一次 Redis 往返与对象组装），单页响应远小于 300KB。
3. 维护成本：若新增 `media:rank:latest` zset，就必须在审核通过、管理员修改 `created_at` 时同步 `ZADD/ZREM`，并纳入 `rebuild_media_rankings` 与 `cache.md`；任何遗漏都会让 DB 与缓存不一致，而 Redis 在本项目只是排序索引、不是事实来源。
4. 分页与并列：直接查库用 `(created_at, id)` 作为稳定排序键，同时间按 `id` 倒序，必要时可把 offset 分页换成 keyset 游标分页避免深分页退化。Redis zset 的 double score 无法精确表示微秒时间戳，同分只能按 member 字符串排序，仍需在 API 层补 tie-breaker。
5. 一致性：数据库页检索、审核中 tab、用户主页排序都直接查库，《最新》沿用同一模式，避免一个页面两套同步机制。

**何时改为 Redis**（满足任一条件再评估）：已审核作品量级超过约 10 万且首页 QPS 高、需要 O(logN) 查询「某作品当前排第几」、或《最新》要与其它 zset 做集合运算（按语言/format 分榜）。届时新增 `media:rank:latest`，score 由 `created_at` 秒级时间戳加 `id` 编码的 tie-breaker 组成，member 为 `media_id`；score 静态，可直接由 DB 一次性重建，改造成本低。

口径：**已确认（Q13）按外站发表时间 `created_at`**，由上游 API 返回后写入，不随投稿时间变化；审核中作品不进入《最新》，仍在审核中 tab。

## 7. 后端分层与关键流程

| 模块 | 职责 |
| --- | --- |
| `media/utils.py` | `MediaFormat`、`FORMAT_PREFIX`、`MEDIA_HOT_DAILY_RETENTION`、`MEDIA_AUTHOR_ID_MAX_LENGTH`、`decay()`、`real_hot()`、`parse_media_url()`、`format_to_platform()`、`normalize_language()`、`normalize_external_author_id()`（一次性核验输入的字符串归一化，不落库）；纯函数与常量，不引入同 app 其它模块 |
| `media/models.py` | `Media` / `MediaLikes` / `UserMedia` 三张表、`MediaStatus` 状态机、驳回审计字段与 Meta 约束、索引 |
| `media/clients.py` | 外站元数据拉取：`fetch_media_metadata() -> MediaMetadata(title, created_at, author_id: str)` 与 `fetch_media_metadata_optional()` 降级入口；`author_id` 是请求内的临时归属比对值，**不落库**；超时、重试、错误分类；不引入 models/services |
| `media/services.py` | 投稿、投喂、驳回（含退还与幂等）、改回 `pending`、审核通过、封禁/解封、余额计算、月度刷新、Redis 同步编排、应用日志；**不检查操作者角色权限**（`AGENTS.md`） |
| `media/cache.py` | 五个 Redis key、读榜、增量写入、审核通过补齐、anchor 事务、月度缩放、全量重建 |
| `media/schema.py` | `MediaOut`（`create_schema` + `url`/`embed_url`/`hot_now` 等 custom fields，**不含外站作者 id**）、`RankingPageOut`、`QueryOut`、`MeOut`、`SubmitIn`（`url`/`language`）、`LikeIn`、`IdIn`、`VerifyIn`（降级投稿审核的 `title` / `external_author_id` / 可选 `created_at`；`external_author_id` 为一次性核验输入）等 |
| `media/api.py` | Ninja `Router`，所有权限/限流/CSRF 在此层，docstring 开头逐行列装饰器 |
| `media/decorators.py` | `media_banned_blocked`：读 `UserMedia.banned` 拒绝投稿（仅此一处使用） |
| `media/tasks.py` | `@task` 月度刷新任务 + 防重复入队 helper |
| `media/management/commands/rebuild_media_rankings.py` | 全量重建命令 |

投稿校验链（顺序固定）：

1. API 层：`login_required_error` + `banned_blocked` + `media_banned_blocked` + `ratelimit(10/h)`；GET 只读、无 CSRF。
2. API 层：`parse_media_url()` 得到 `format/suffix`；查 `AccountLinkQueue(platform=format_to_platform(format), userprofile=request.user, verified=True)` 是否存在（参照 `accountlink/msgames/api.py:40-52`）。此处只确认「投稿人已绑定该平台账号」，`identifier` 不写入 `Media`。降级投稿仍需该绑定，只是不在此步核对具体作品作者。
3. service 层：`clients.fetch_media_metadata_optional(format, suffix)`。成功返回 `MediaMetadata(title, created_at, author_id: str)`；`timeout` / `upstream_error` 返回 `None` 表示降级；`parse_error` / `invalid_metadata` 抛错并拒绝投稿、不落库（第 7.2 节）。`language` 由用户自由填写，只做长度与 `strip` 归一化。
4. API 层：成功路径把临时 `author_id` 与第 2 步已验证绑定的 `identifier` 比对，不一致返回 403，防止冒领；比对结果不落库。**降级路径没有上游作者 id，自动核对跳过**，改由管理员审核时凭一次性输入核验（第 7.2 节）。
5. service 层：`transaction.atomic()` + 唯一约束防重复外链；`format+suffix` 已存在返回 409；成功路径写入拉取到的 `title` / `created_at`；降级路径写入 `title=''`、`created_at=now`（本站投稿时刻兜底）、`metadata_pending=True`；**两条路径都不接收、不保存外站作者 id**（16.1 第 15 条）；两者都写 `status='pending'`、`likes=0`、`hot_value=0`、`hot_value_updated_at=T`、`submitted_at=auto_now_add`，不写 Redis（审核中未入榜）。
6. 输出：`MediaOut`（不含外站作者 id）；成功路径跳转到「审核中」tab 提示等待审核，降级路径额外提示「标题由管理员审核时补全，并核验投稿人在外站的账号」。

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

**超时链配置**（用户提示需要放宽；以下为必须同步修改的层）：

| 层 | 当前值 | 改动 |
| --- | --- | --- |
| 应用客户端 | 依赖默认 timeout 30s（扫雷网） | 总预算 ≤ 15s：B 站 connect 3s / read 8s，扫雷网 `timeout=8` + 2.1s 节流排队 ≤6s（见上） |
| uWSGI | `uwsgi.ini:29` 普通请求 `harakiri:10`，全局 `harakiri=90`（`:22`） | 在 `:29` 白名单正则末尾追加一个匹配 `/api/media/submit$` 的分支（`route` 按 `PATH_INFO` 匹配），使其保留 90s；否则 10s 即被杀 |
| nginx | `default.conf:152` `^~ /api/` 的 `uwsgi_read_timeout 2` | 新增更精确的 `location = /api/media/submit`：`uwsgi_read_timeout 25s`、`uwsgi_connect_timeout 5s`；location 路径的尾斜杠必须与 Ninja 实际路由一致（本设计为无尾斜杠），否则配置不生效 |
| 前端 | `src/http.ts:7` `$axios` 全局 `timeout: 20000` | 仅投稿请求单独传 `timeout: 25000`，其它请求不变 |
| 生效 | `start.sh:31-33` 每次启动复制 `default.conf` | 改仓库内配置；`nginx -s reload`，`uwsgi.ini` 改动必须重启 uWSGI |

**并发与限流**：投稿 `10/h`/用户，uWSGI `processes=5`；同步外站调用会占用 worker，需配合监控。若上线后观察到排队，可另评审「先落待抓取状态 + Django Task + 前端轮询」的异步方案，但那会改变「失败即拒绝」的即时反馈语义，不在本阶段实现。

### 7.2 降级投稿与审核补录（平台无关）

外站超时或上游不可用**不再拒绝投稿**：`fetch_media_metadata_optional()` 返回 `None`，`services.create_media()` 落一条 `metadata_pending=True` 的作品，`title=''`、`created_at` 用本站投稿时刻兜底；**`Media` 不保存外站作者 id**。仅 `timeout` / `upstream_error`（含 B 站 -509 / -352、扫雷网 401 / 429）降级；`parse_error` / `invalid_metadata` 说明 URL 或响应本身有问题，仍拒绝且不落库。

管理员审核这类作品时，先人工打开外链确认作品作者，再在 `POST /admin/verify` 提交两项：

| 字段 | 用途 | 是否入库 |
| --- | --- | --- |
| `external_author_id` | 投稿人在外站的账号 id，**一次性核验输入**：API 层用它查 `AccountLinkQueue` 确认该账号属于投稿人，从而确认作品归属 | **否**，不写 `Media`、不写日志、不进 `MediaOut` |
| `title` | 对应投稿的标题 | 是，写入 `Media.title` |

可选 `created_at` 用于把兜底的本站投稿时刻修正为真实发表时间（`POST /admin/edit` 也可修正）。`services.verify_media()` 在 `metadata_pending=True` 时缺 `title` 即返回 400 且状态不变；补齐后才置 `verified` 并写四个 zset。**身份核验在 API 层**：`AccountLinkQueue(platform=format_to_platform(format), identifier=external_author_id, userprofile=media.user, verified=True)` 不存在返回 403；该 id 不传进 `verify_media()`，service 层不处理权限（AGENTS.md、16.1 第 15 条）。这条链路只证明「管理员填报的外站账号是投稿人已验证绑定的账号」，作品与该账号的对应关系由管理员人工核对，本站不抓取上游内容复核。

降级作品在审核中 tab 与卡片上以「待补全」标记展示，仍可被投喂（Q2），但标题为空时不进热门/精品/《最新》与排行榜（这些 tab 只取 `verified`）。`metadata_pending` 的作品若被驳回，按第 5.5 节同样退还并清零。

`created_at` 兜底是 Q13 的已知例外：这类作品在《最新》tab 按本站投稿时刻排序，直到管理员修正。不额外引入 Redis key。

## 8. API 清单

路径前缀 `/api/media/`。所有接口都要限流（`AGENTS.md`），管理员专用接口例外；所有装饰器用 `decorate_view` 包装并在 docstring 开头注明；权限只在 API 层。

| 方法 / 路径 | 用途 | 权限与限流 | 备注 |
| --- | --- | --- | --- |
| `GET /ranking?sort=hot\|likes&start&count` | 热门 / 精品 tab | `ratelimit(key='ip', rate='5/s', group='media-ranking')` | zset → `in_bulk`；`count<=50`；只返回已审核 |
| `GET /user-ranking?sort=hot\|likes&start&count` | 排行榜页《作品》tab | `ratelimit(key='ip', rate='5/s', group='media-user-ranking')` | 两个 `user:` zset；只统计已审核作品；落点已确认（Q11） |
| `GET /latest?start&count` | 作品页《最新》tab | `ratelimit(key='ip', rate='5/s', group='media-latest')` | **不走 Redis**，直接查库 `status='verified' ORDER BY -created_at, -id`（走 `media_latest_idx`）；`count<=50`；复用 `RankingPageOut`；评估见第 6.1 节 |
| `GET /pending?start&count` | 审核中 tab | `ratelimit(key='ip', rate='5/s', group='media-pending')` | 直接查库 `status='pending'`，按 `submitted_at` 倒序 |
| `GET /detailbatch?ids=1,2,3` | 批量详情（卡片、嵌入） | `ratelimit(key='ip', rate='5/s', group='media-detail')` | 返回 `url` / `embed_url` / `hot_now`；`ids` 上限 50 |
| `GET /query/{mode}?value=&limit=` | 数据库页作品匹配查找 | `ratelimit(key='ip', rate='6/m', group='media-query', block=False)` + 视图内检查 `request.limited` 抛 429 | `mode` 参照 `identifier/api.py:21`；`title`/`suffix` 字段；最多 1000 条，超出 400 `too_many_matches`；regex 用 MySQL ICU，捕获 `DatabaseError` 3684-3700 转 400；`rejected` 作品也可见（16.1 第 5 条） |
| `GET /user/{user_id}?sort=hot\|likes\|created_at&order=&page=&pageSize` | 个人主页作品 tab | `ratelimit(key='ip', rate='30/m', group='media-user')` | **不走 Redis**，直接查库并用第 4.1 节索引排序；`pageSize<=50`；**展示所有状态且对所有人可见**（16.1 第 5 条） |
| `GET /me` | 本人红宝石余额、`likes_sent`、`banned` | `login_required_error` + `ratelimit(key='user', rate='30/m')` | 未创建 `UserMedia` 行时返回零值，不写库 |
| `POST /submit` | 投稿 | `login_required_error` + `banned_blocked` + `media_banned_blocked` + `ratelimit(key='user', rate='10/h', group='media-submit', block=True)` | 表单只有 `url` / `language`；自动拉取 `title`/`created_at`/外站作者 id 并核对归属（外站作者 id 不入库）；**超时/上游不可用降级为待补全投稿**（第 7.2 节），结构性错误仍拒绝且不落库；409 重复外链（含已被驳回的外链）统一提示「该作品已投稿过，不可重复投稿」，不明说曾被驳回（P4）；403 归属不符 |
| `POST /like` | 投喂红宝石 | `login_required_error` + `banned_blocked` + `ratelimit(key='user', rate='1/s', group='media-like', block=True)` | 参数 `media_id` + `count`（正整数，上限如 100）；**审核中作品也可投喂**，但只写 DB 不写 zset；`rejected` 作品不可投喂；返回最新 `likes` / `hot_now` / `balance` / `status` |
| `POST /admin/verify` | 管理员审核通过 | `staff_required`（含 CSRF），不限流 | 仅 `pending → verified`，按当前 `likes/hot_value` 补齐四个 zset；**降级投稿必填 `title` 与 `external_author_id`**（可选 `created_at`）；`external_author_id` 是 API 层一次性核验输入，用 `AccountLinkQueue` 确认该外站账号属于投稿人，**不写入 `Media`**（第 7.2 节、16.1 第 15 条） |
| `POST /admin/reject` | 管理员驳回 | `staff_required`，不限流 | 仅 `pending → rejected`；**不删行**、填驳回审计字段、写 `media.log`、**退还红宝石**并同步清零 `likes` / `hot_value` 与投喂记录（P1 / Q12，第 5.5 节） |
| `POST /admin/reopen` | 改回待审核 | `staff_required`（含 CSRF），不限流 | 仅 `rejected → pending`，复用同一行（P5）；驳回时已退还并清零，恢复后从零重新累计，无需再处理红宝石 |
| `POST /admin/ban` / `POST /admin/unban` | 投稿封禁 / 解封 | `staff_required`，不限流 | 只改 `UserMedia.banned`；`get_or_create` 惰性建行 |
| `POST /admin/edit` | 修正标题/语言/发表时间/format | `staff_required`，不限流 | 建议项：人工审核需要纠错；**仅 `pending` / `rejected` 可编辑**，`verified` 严格终态不接受编辑（P2，如需变动只能站长硬删除）；改 `created_at` 会影响《最新》排序，改 `format/suffix` 要重跑唯一约束与 URL 解析并复核上游元数据 |
| `POST /admin/delete` | 站长硬删除已通过作品 | `auth=django_auth_superuser`（会话认证自带 CSRF），不限流 | 仅 `status='verified'`；硬删除 + 退还红宝石 + 写 `media.log` 快照 + 回退四个 zset（P2，第 5.6 节）；删除后该外链可重新投稿 |
| `GET /admin/rejected?start&count` | 查看已驳回作品 | `staff_required`（只读，无需 CSRF token），不限流 | 可选；直接查 `status='rejected'` 的 `Media` 行，替代原 `GET /admin/deletion-log`；文件日志仍走 `common/api.py` 的日志接口 |

约定：

- 管理写操作一律 `POST`，`staff_required` 自带 `csrf_protect`；前端复用 `src/services/adminCsrf.ts` 安装的统一拦截器，token 入口复用 `GET /api/userprofile/admin/csrf`；第三方管理员客户端自行维护 Cookie 会话。
- 普通用户 API 不新增 CSRF，不启用全局中间件，不修改 `login_required_error` / `banned_blocked`（`ADMIN_API_CSRF.md`）。
- 错误统一用 `ninja.errors.HttpError`（400/403/404/409/429）或项目 `ExceptionToResponse`；不返回外站原始错误。Q5 的拉取失败按第 7.1 节映射为 504（超时）/ 502（上游、解析、元数据非法）/ 403（作者不匹配）；其中超时与上游错误按第 7.2 节**降级为待补全投稿**，不再返回错误，响应改为 `MediaOut(metadata_pending=true)`；结构性错误仍不落库、不写 Redis。
- `POST /submit` 的响应包含后端拉取到的 `title` / `created_at`，前端只读展示；正常投稿已在投稿链路自动核对作者归属，管理员只判断「是否与扫雷相关」；**降级投稿**因上游不可用，须由管理员按第 7.2 节凭一次性输入的外站作者 id 补做归属核验。所有响应都不含外站作者 id。
- `MediaOut` 的 `hot_now` 由后端按 `real_hot()` 计算并返回，避免前端重复实现衰减公式；同时返回 `anchor` 便于展示与调试。
- 输出 Schema 涉及模型时优先 `create_schema`（`AGENTS.md`），例如 `create_schema(Media, exclude=['suffix'])` + `custom_fields` 提供 `url`、`embed_url`、`hot_now`。`MediaOut` 需输出 `reject_reason` 与 `rejected_by`（P3 已确认对普通访客可见），后者按用户 id 交给前端 `PlayerName` 展示；还需输出 `metadata_pending`，供审核队列标记待补全作品；**不输出外站作者 id**（16.1 第 15 条）；`rejected` 作品也要能返回，不能只在管理接口里可见。
- `GET /latest` 是唯一按 `created_at` 做全站排序的读接口；它与 `/ranking`、`/user-ranking` 共用分页约定，但不读 Redis，也不需要加入 `rebuild_media_rankings`（第 6.1 节）。

## 9. 权限、限流与 CSRF 的两处口径澄清

1. **面向用户不提供删除接口**：作者不能自删，需撤下的作品只能在过审前联系管理员驳回；`verified` 严格终态。原 Q9 的「删除不限流」与 `group='media-delete'` 限流作废，也不再有与投喂 `1/s` 配额串用的问题。管理员驳回 / 改回 `pending` 走 `staff_required`；**站长硬删除是唯一例外**，走 `auth=django_auth_superuser`（Ninja 会话认证自带 CSRF，参照 `videomanager/api.py:192-206`），两者按管理员 API 规范均不限流。
2. **两级封禁**：`banned_blocked` 读 `UserProfile.is_banned`（全站封禁，禁止所有写操作）；`media_banned_blocked` 读 `UserMedia.banned`（只禁止 `POST /submit`）。封禁不撤销已有作品、不禁止浏览/投喂。

另外，`decorate_view` 的参数中最后一个最先执行；docstring 的装饰器清单按实际执行顺序列出（参照 `minigame/api.py:85-92`），并显式写 `group`，避免 Ninja 共享 `Operation.run` 导致多个端点共用配额（`videomanager/api.py:66`）。

## 10. 定时任务、后台任务与文档

| 改动 | 位置 | 说明 |
| --- | --- | --- |
| 月度作业 | `common/apscheduler.py` | 新增 `refresh_media_hot_reference`，`@util.close_old_connections` 包装，只入队 |
| 作业 id 断言 | `common/tests.py:52-65` | 集合里新增 id，否则现有测试会失败 |
| 任务 | `media/tasks.py` | `@task(priority=...)` + `DBTaskResult` 防堆积 |
| 重建命令 | `media/management/commands/rebuild_media_rankings.py` | 临时榜 + 原子发布；支持 `--batch-size` |
| 文档 | `vitepress_doc/zh/guide/development/cache.md` | 五个 key、衰减基准、`ZINCRBY` 例外、重建方式 |
| 文档 | `vitepress_doc/zh/guide/development/management-commands.md` | 月度作业、worker、重建命令与部署顺序 |
| 文档 | `vitepress_doc/zh/guide/development/signals.md` | 本设计无信号，不改动；如实现时改为信号同步缓存再补文档 |
| 驳回日志 | `saolei/settings.py:397-432`、`media/services.py` | 新增 `media` logger 与 `logs/media.log` handler；驳回时写应用日志，不新增审计表（第 4.4 节） |
| 超时链 | `default.conf`、`uwsgi.ini:29`、`src/http.ts:7` | 投稿端点 nginx 25s / harakiri 白名单 / 前端 25s / 应用 ≤15s；详见第 7.1 节 |

生产已有 `runapscheduler` 与 `db_worker_robust` 常驻进程（`start.sh`），不新增进程、不引入系统 crontab。发布顺序：先 `migrate`，确认 `logs/media.log` 可写与外站密钥可用，再 `rebuild_media_rankings`，再 `nginx -s reload`、重启 uWSGI/apscheduler/worker 并实测投稿超时链，最后开放投稿入口。

## 11. 前端

### 11.1 路由与文件

| 文件 | 说明 |
| --- | --- |
| `src/router/index.ts` | 新增 `/works` 顶层路由（4 个子路由：热门/精品/最新/审核中）、`/database/works`、`/player/:id/works`、`/staff/media`；`Menu.vue:118-122` 的 `mainItems` 加入口 |
| `src/views/WorksView/routes.ts`、`App.vue` | 页壳：`ElTabs` + `keep-alive` + `router-view` + 路由名映射，共 4 个 tab，参照 `DatabaseView/App.vue` |
| `src/views/WorksView/HotView.vue`、`LikesView.vue`、`LatestView.vue`、`PendingView.vue` | 四个 tab；热门/精品读 Redis 榜接口，《最新》读 `/latest`（直接查库），审核中读 `/pending` |
| `src/views/RankingView/routes.ts`、`App.vue`、`MediaRanking.vue`、`MediaRanking.cy.ts` | 排行榜页《作品》tab：`ranking_media` 路由与 tab 文案、`BaseTable` + `ElPagination` + `useRankingQuery`、组件测试 |
| `src/components/media/MediaCard.vue`、`MediaEmbed.vue`、`MediaFeedButton.vue`、`SubmitMediaDialog.vue` | 卡片/嵌入/连续投喂/投稿表单；表单只填 `url` 与自由文本 `language`（Q4/Q5）；通用组件放 `src/components/media/` |
| `src/views/DatabaseView/MediaQueryView.vue` | 数据库页作品 tab，交互参照 `IdentifierView.vue` 的模式下拉、1000 条上限、本地分页 |
| `src/views/UserView/UserMediaView.vue` | 个人主页作品 tab，后端排序分页，参数 `hot_value/likes/created_at` |
| `src/views/StaffView/StaffMediaReview.vue` | 管理员审核队列：外链、通过、驳回、改回待审核、封禁/解封；**待补全作品通过前必须填标题与外站作者 id 供归属核验**（该 id 不入库，第 7.2 节）；另有仅站长可见的硬删除入口（二次确认，P2）；管理员页面不追求 UI 质量与复用性 |
| `src/services/mediaService.ts` | 所有请求用 `$axios`，`.catch(httpErrorNotification)`；`src/http.ts` 是唯一 Axios 实例；投稿请求单独传 `timeout: 25000`（第 7.1 节） |
| `src/views/WorksView/*.cy.ts` 等 | 组件测试；临时组件用 `render` 语法 |

### 11.2 tab 与数据源

| tab | 数据源 | 排序 | 可见性 |
| --- | --- | --- | --- |
| 热门 | `GET /ranking?sort=hot` | 实时热度（Redis 索引 + 回表） | 仅 `status='verified'` |
| 精品 | `GET /ranking?sort=likes` | 累计投喂数 | 仅 `status='verified'` |
| 最新 | `GET /latest` | `created_at` 倒序，同时间按 `id` 倒序；**不走 Redis** | 仅 `status='verified'` |
| 审核中 | `GET /pending` | `submitted_at` 倒序 | 所有访客公开，带「待审核」标记；**可以投喂**（Q2），展示累计 likes 与实时热度，但投喂不改变首页排行 |

数据库页作品 tab 与用户主页作品 tab 均展示所有状态（含 `pending` 与 `rejected`）、对所有人可见，并显示 `status` 状态（16.1 第 5 条）；`rejected` 作品同时展示 `reject_reason` 与 `rejected_by`（P3 已确认可见），后者用 `PlayerName` 渲染。

投稿表单与语言展示（Q4/Q5）：`SubmitMediaDialog.vue` 只提交 `url` 与 `language`（自由文本，`maxlength=32`）；标题与发表时间由后端拉取后返回，前端只读展示；超时/上游不可用不再报错，改为提示「投稿已保留，标题由管理员审核时补全并核验外站账号」并跳转审核中 tab；结构性错误仍用 `httpErrorNotification` 显示分类错误（元数据非法 / 归属不符）。语言展示用前端已知 locale 映射，未命中（含空字符串）显示 i18n「未知语言 / Unknown language」；用户输入只作为文本渲染，不作为 i18n key 或 HTML。审核中 tab 的投喂按钮旁标注「审核中」，点击仍走第 11.3 节的连续投喂逻辑。

排行榜页《作品》tab（`ranking_media`）：表头用 `BaseTextButton` 切换 `hot` / `likes` 两个指标，数据来自 `GET /user-ranking`，用 `BaseTable` + `ElPagination` 展示，`useRankingQuery` 管理 `sort/page/page_size` 查询参数（参照 `TournamentRanking.vue`）。榜内只统计已审核作品，行内 `PlayerName` 的组件测试需注入 `$axios` 并 `cy.mockPlayerNameFallback()`。落点已确认（Q11），Redis 数据在阶段 2 已就绪，本 tab 不需要新的后端计算。

### 11.3 连续投喂

用户要求：API 限流 1 秒 1 次、参数是红宝石数量；前端每次点击投喂 1 个，不做前端限流，点击后延迟 1 秒发请求，1 秒内的点击累计进 `count` 并重置计时器。

`MediaFeedButton.vue` 的实现要点：

```text
pending: number; timer; lastSentAt
onClick: pending += 1; clearTimeout(timer); timer = setTimeout(flush, 1000)
flush: 若 now - lastSentAt < 1050ms，改为延后到该时刻（防止服务端 1/s 窗口边界 429）
       取出 pending 置 0，POST /like { media_id, count }
       成功：本地更新 likes / hot_now / balance，lastSentAt = now
       失败：把 count 加回 pending，httpErrorNotification 提示，延迟 1100ms 重试一次；仍失败则丢弃并提示
```

- 页面卸载/切换 tab 时先 `flush()`，避免丢失累计点击；余额不足由服务端返回，前端不做余额预判的硬限制（只做禁用态展示）。
- 服务端 `1/s` 是硬限制，`block=True`；前端不重试第二次以上，不吞掉 429。

### 11.4 其它前端约定

- i18n：新增可复用 messages 放 `src/i18n/locales/{zh-cn,en}.ts`，组件专有 messages 放 SFC 的 `script` 末尾（`AGENTS.md` 的 `i18nMessages` 风格）；至少完整覆盖 zh-cn 与 en，其它 locales 靠 fallback。
- UI：按 `front_end/UI_REFACTOR_PLAN.md`，直角紧凑、原生 HTML + CSS/`BaseTable` 优先、Element Plus 只用于弹窗/表单/Tabs、深浅主题、`src/styles/text.css`、PrimeIcons、vue-tippy 保持不变。
- 表格文本断言用 `cy.getTable` / `cy.extractTableData`；关闭通知用 `cy.closeElNotifications()`；渲染 `PlayerName` 的组件测试需注入 `$axios` 并用 `cy.mockPlayerNameFallback()`。
- 本页不涉及公共 VideoAnalyzer 或离线包，正常不触发 `front_end/local-analyzer/version.json` 递增；若实现时改动会实际影响它们的共享 CSS/i18n/工具/依赖，必须先按 `front_end/local-analyzer/VERSIONING.md` 处理。

## 12. 测试与检查

后端（`back_end/saolei/`，需要 MySQL + Redis）：

- `python -m flake8`：新 app 加入 `application-import-names`、google import 顺序、`save(update_fields=...)`、`print` 等。
- `python manage.py makemigrations --check --dry-run`、`python manage.py migrate`：确认只有 `media.0001_initial`，不产生其它 app 的迁移。
- `python manage.py test media common.tests`：
  - URL 解析：三种 format 的合法/非法 URL、host 白名单、大小写、query 剥离、suffix 正则、`https://saolei.wang/bbs/{id}`、B 站 `/opus/` 动态链接、短链与重定向一律拒绝（Q6/Q7）。
  - 归属与去重：必须有 verified 绑定、重复外链 409、解绑后拒绝投稿。
  - 降级补录：`metadata_pending` 作品不填 `title` 时 `POST /admin/verify` 返回 400 且状态不变；只填 `title` 即可过审、`metadata_pending=False`、`created_at` 可修正；`Media` 无 `external_author_id` 字段，`create_media()` / `verify_media()` 也不接收该参数；字符串外站 id（含 `UC...` 形式）归一化后能在 API 层用于 `AccountLinkQueue` 核验，**任何路径都不落库、不进 `MediaOut`**。
  - 外站拉取（Q5/Q14）：三类 format 的字段映射单测用 `httpx.MockTransport` / `unittest.mock` 固定上游响应（覆盖 `pubdate`、`publish_time`、`post_time` 与 camelCase alias）；解析失败 / 缺字段 / 空 `items` / 标题超长 / 未来时间仍拒绝且不落库；**超时 / 非 2xx / -509 / -352 降级为待补全投稿**（`metadata_pending=true`、空 title）；作者 id 不匹配 403；语言自由文本只校验长度。外站作者 id 字符串化（含非数字 id、`bool` 拒绝）单测通过，该值只作为请求内临时返回值。部署环境用已配置的 `saolei_api_key` 跑一次真实 `post_info` 联调。
  - 审核中投喂（Q2）：审核期间 DB 累加 likes/hot 但不写 zset；审核通过后四个 zset 按累计值一次补齐；驳回后退还红宝石、立刻清零 `likes` / `hot_value` 并删除投喂记录、写 `media.log`；重复驳回幂等。
  - 驳回口径（Q12 / P1）：`pending → rejected` 不删 `Media` 行、逐条退还 `likes_sent`、同事务把 `likes` / `hot_value` 清零并删除 `MediaLikes`、`hot_value_updated_at` 不变；退还与清零必须同事务，失败一起回滚；`verified` 作品拒绝驳回；`rejected` 的同一外链再次投稿返回 409 且提示统一（P4）；无面向用户的 `POST /delete`。
  - 红宝石：`date_joined` 边界（0/23:59/24:00/48:01）、余额不足、给自己投喂、并发投喂不超支（`select_for_update`）。
  - 站长硬删除（P2）：仅 `verified` 可删、`pending` / `rejected` 拒绝；逐条退还全部投喂者 `likes_sent`（含作者自投）；级联删除 `MediaLikes`；`media.log` 快照字段齐全；四个 zset 回退正确且幂等；删除后同一 `format+suffix` 可重新投稿（与被驳回不可重投形成对比）。
  - 衰减：`decay` 单位测试（1 天 = 0.99、6 天幂次、逆向 > 1）、I1 不变量、投喂增量示例（第 5.7 节）、月度刷新幂等（同月重跑不再缩放）、跨月停机补跑、用户总热度与逐作品求和一致。
  - Redis 排行：投喂/审核通过后的四个 zset 数值与顺序、重建命令只取 `status='verified'` 且与 DB 一致；驳回无需 `ZREM`；站长硬删除必须 `ZREM` 两个作品榜并等值扣减作者两个 user zset，结果 <= 0 改 `ZREM`，重复执行幂等。
  - 排行榜《作品》tab：`/user-ranking` 两个指标与 `media:rank:user:*` 一致、只统计已审核作品、分页边界、空榜。
  - 《最新》tab：`created_at` 倒序、`id` tie-breaker、`pending` / `rejected` 不入列、分页稳定、管理员改 `created_at` 后顺序更新；该接口不读 Redis。
  - 权限与限流：投稿 `10/h`、投喂 `1/s`、封禁只禁投稿、管理员接口 GET 只读；无面向用户的删除接口，故无 `media-delete` 限流；`POST /admin/delete` 只允许 `is_superuser`，普通 staff / 普通用户一律 403。
  - CSRF 回归：`Client(enforce_csrf_checks=True)` 覆盖管理员缺 token / 错 token / 不可信 Origin / 合法 token / 普通用户无 CSRF 要求；额外覆盖 `auth=django_auth_superuser` 的 `POST /admin/delete`（缺 token 拒绝、合法 token 放行，参照 `videomanager/test_video_delete.py:212-231`），并把新管理写接口加入现有回归清单（`userprofile/test_admin_csrf.py:39-45` 的做法）。
  - `common/tests.py` 的 APScheduler 作业 id 集合更新。
- 测试统一 `@override_settings(RATELIMIT_ENABLE=False)`（需要验证限流的用例单独覆盖），Redis key 在 `setUp` 清理并 `addCleanup`。

前端（`front_end/`）：`npm run lintfix`、`npm run typecheck`、`npm run vitest -- run`、`npm run build:openms`；组件测试用 `npx cypress run --component --browser chrome --headless --spec "src/views/WorksView/*.cy.ts,src/views/RankingView/MediaRanking.cy.ts"`（CodeBuddy 环境可直接运行）；E2E 与预览/开发服务器由用户按需运行。

CI 参考：`.github/workflows/backend.yml` 会跑 `makemigrations` + `migrate` + `manage.py test`，因此迁移必须与模型同步提交；`.github/workflows/flake8.yml`、`BackendSafety.yml` 同样适用。

## 13. 分阶段实施

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| 0（已完成） | `media` app 外壳、三处项目注册、本文档 | `python manage.py check` 通过；OpenAPI 可加载；`flake8` 通过；无新增迁移 |
| 1 数据层（已按状态机口径重做完成） | `utils.py` 常量/URL 解析/衰减函数/`MediaStatus`、`models.py` 三张表（`status` 状态机 + 驳回审计字段 + `metadata_pending`，**无 `external_author_id`**、无 `MediaDeletionLog`）、`0001_initial` 迁移、纯函数与模型单测 | `makemigrations --check` 干净；迁移可 `migrate`；约束/索引符合第 4 节；语言字段无枚举；`rejected` 行仍占全表唯一、禁止重投 |
| 2 服务与缓存（已完成） | `clients.py` 依赖适配与字段映射（三种 format、不新写 HTTP 客户端）、`services.py` 事务流程（驳回退还并清零、改回 `pending`、审核通过补齐 zset、站长硬删除退还与 zset 回退、应用日志）、`cache.py` 五个 key、月度任务与调度、重建命令（只取 `verified`）、LOGGING 与 nginx/uWSGI 超时链、开发文档 | 三类 format 字段映射与超时/错误分类单测通过；衰减/幂等/回退/重建单测通过；驳回清零与硬删除回退单测通过；`common.tests.APSchedulerRegistrationTests` 通过；《最新》不新增 Redis key。**前端投稿 25s 超时随阶段 4 的 `mediaService.ts` 落地** |
| 3 API 层 | `schema.py`、`api.py`、`decorators.py`、全部读写接口（含 `/submit` 自动拉取与归属校验、`/admin/reject`、`/admin/reopen`、`/admin/delete` 的 `django_auth_superuser`）、限流与 CSRF 回归 | 所有装饰器写入 docstring；管理写接口通过 CSRF 回归；`reject_reason` / `rejected_by` 对普通访客可见；无 GET 写操作；结构性错误不落库、超时降级落库；降级投稿 `/admin/verify` 的一次性 `external_author_id` 经 `AccountLinkQueue` 核验且不落库；无面向用户的 `POST /delete` |
| 4 前端 | 路由、作品页四个 tab、排行榜页《作品》tab、投稿表单（URL + 自由语言）、未知语言展示、审核中投喂、作者主页展示所有状态、组件、服务层、i18n、管理员审核页 | lintfix / typecheck / vitest / `MediaRanking.cy.ts` 等组件测试通过；至少 zh-cn + en 可用 |
| 5 联调与发布 | 部署一次 `makemigrations` + `migrate` → `rebuild_media_rankings` → reload nginx / 重启 uWSGI 与调度器/worker → 实测投稿超时链 → 灰度开放投稿 | 作品页四个 tab 正确（热门/精品走 Redis，审核中/《最新》查库）、排行榜《作品》tab 与两个 user zset 一致；拉取超时降级投稿、结构性错误拒绝；驳回退还清零且日志可查、被驳回外链无法重投；站长硬删除后四个 zset 回退正确且外链可重投；单次响应 < 300KB；回滚方案明确 |

阶段 1-3 可以先合入后端但**不注册**写接口或前端入口，保证未开放时不影响线上；阶段 5 再开放。

阶段 1 验收记录（状态机口径重做后）：`python -m flake8`、`manage.py check`、`makemigrations --check --dry-run`、`migrate media`、`manage.py test media`（18 个测试）均通过；`check` 只剩既有的 `staticfiles.W004`（`dist/` 目录不存在）。全量 `manage.py test` 另有 2 个与本功能无关的既有失败：`accountlink/wom/test/tests.py:198` 的 `test_update_wom`（`update_time` 未变化）与 `videomanager/test_video_hashes.py:11` 的 `test_hashes_entire_memory_or_temporary_upload_and_rewinds_for_parser`（`_safe_remove()` 参数不匹配）。功能尚不完整时不追求全量测试通过，留待后续阶段统一处理。

阶段 2 验收记录（含降级口径修订与「外站作者 id 不入库」修订后）：本地 `migrate media zero` 后重新生成不含 `external_author_id` 的 `0001_initial`；全量 `python -m flake8`、`manage.py check`、`makemigrations --check --dry-run`、`migrate media`、`manage.py test media common.tests.APSchedulerRegistrationTests`（54 个测试：media 48 个、调度作业 6 个）与 `read_lints` 均通过；`check` 只剩既有的 `staticfiles.W004`。`monitor/cache.py` 已把五个 key 纳入固定内存统计清单；`cache.md`、`management-commands.md` 已同步。B 站依赖只有全局 `request_settings`，`clients.py` 在单次调用内临时把 timeout 设为 8s 并在 `finally` 恢复原值，不长期改变 `accountlink` 的 B 站调用行为；该折中在同进程并发请求下仍有短暂影响，部署前应确认 web 进程为单线程。

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
- [ ] 第 14 节 Q1-Q14 已确认/核对；Q1、Q9 按 16.1 作废，Q12 按状态机口径更新；P1-P5 已确认并落实（16.1 第 8-12 条），当前无待定事项。
- [ ] `saolei_api_key` 已由站长配置；部署环境验证 `read_secret('saolei_api_key')` 可读取并跑一次真实 `post_info` 联调；`post_info` 401 归入 `upstream_error`（按第 7.2 节走降级路径），部署联调应确认密钥正确；单测用 MockTransport，不依赖真实密钥。
- [ ] 模型迁移由 `makemigrations` 生成并随代码提交；`migrate` 与 CI 的 `makemigrations` 不产生额外迁移；三张表（`Media` / `MediaLikes` / `UserMedia`）、`status` 状态机、`metadata_pending`、**无 `external_author_id` 字段**（16.1 第 15 条）、无 `MediaDeletionLog`；本地重复生成 `0001` 不影响生产（16.1 第 7 条）。
- [ ] 《最新》tab 不新增 Redis key、不纳入 `rebuild_media_rankings`，但必须有 `media_latest_idx`；排行榜页《作品》tab 复用两个 user zset 并纳入重建验收；重建只取 `status='verified'`。
- [ ] 投稿链路超时链落地：应用客户端 ≤15s、`default.conf` 精确 location 25s、`uwsgi.ini:29` harakiri 白名单已配置；前端投稿 timeout 25s 随阶段 4 的 `mediaService.ts` 落地；部署后 reload nginx / 重启 uWSGI 并实测。
- [ ] 驳回日志：`settings.py` 的 `media` logger 与 `logs/media.log` 可写、驳回与站长硬删除时应用日志可查（硬删除含作品快照）；不新增审计表。`rejected` 行仍占全表唯一、禁止重投；站长硬删除释放唯一性后可重投。
- [ ] `flake8`、`manage.py test`、前端 `lintfix` / `typecheck` / `vitest` / `build:openms` 与指定组件测试全部实际运行并记录结果。
- [ ] `cache.md`、`management-commands.md` 更新；新增管理写接口加入 CSRF 回归清单；`common/tests.py` 作业集合更新。
- [ ] 部署：重建四个 zset 与 anchor，确认月度刷新作业已注册、worker 正常，再开放投稿入口。

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

当前无待定事项。P1-P5（第 8-12 条）与降级投稿、平台扩展、外站作者 id 不入库（第 13-15 条）均已落到第 4.1、7.1、7.2、8、9、11、12、13、14、15、17 节；后续产生新口径时另开条目记录。


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
