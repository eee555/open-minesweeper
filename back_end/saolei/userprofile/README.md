# 用户资料

## 管理员权限

站长可在 `/superuser/staff` 按本站用户 ID 设置或取消管理员权限，页面通过 `is_superuser` 授权并初始化 CSRF 令牌。纪念账号不能拥有管理员权限。

## 纪念账号

为已经不活跃的传奇玩家保存资料，成绩、录像和自动勋章正常计入榜单，并显示“纪念账号”标识。“纪念”不表示玩家已经去世。

### 建档与维护

由有服务器访问权的站长低频维护。核实、清理和资料修改使用已有管理命令及 Django shell；普通管理员沿用管理普通账号的权限。

站长先确认原账号已注销且旧身份数据已清理。新玩家可以与原持有人不同，复用后旧个人主页链接会指向新玩家。普通录像删除仍保留 `newest_queue` 快照，站长须在复用 ID 前处理这些旧快照及相关关系、排行、勋章和后台任务。

`create_memorial_account` 要求手动指定 UserProfile ID、UserMS ID 和用户名。两个 ID 可以不同，但分别必须未占用且小于各自表当前最大主键；空表拒绝建档。命令在事务内创建全新的 UserMS 和账号，冲突或验证失败回滚；已有孤立 UserMS 先按下节清理。命令参数与示例见[管理命令](../../../vitepress_doc/zh/guide/development/management-commands.md)。

`is_memorial` 身份与模型约束使账号保持停用、无管理员权限、不可用密码及唯一占位邮箱。纪念账号不能登录、找回密码、被任命管理员或通过通用编辑更换占位邮箱。

### 补录像

站长从纪念玩家主页进入 `/superuser/memorial`。API 通过 `is_superuser` 授权，不额外要求 `is_staff`；参数和响应以 Ninja API 文档为准。

1. 批量解析文件，逐个手动勾选标识；默认全部不选，没有全选。仅上传所选标识的录像，空标识按原值匹配。
2. 设置上传时间锚点，复用 GSC 的结束时间排序和耗时倒推算法。指定日期参与排名及同分排序。
3. 前端依次提交文件，首个请求携带全部所选标识；后端先逐个尝试注册绑定，再上传。全部绑定失败仍尝试上传，录像状态遵循原有校验。
4. 上传失败保留已成功的绑定；重试跳过成功文件、保留原日期，重试失败或结果未知的绑定。全部文件成功后，如只需修正标识，在服务器复用 `common.services.bind_import_identifier`。

同玩家重复文件复用已有录像并保留更早上传时间；他人文件冲突返回 409，不转移归属。录入错误使用现有站长删除录像接口或 `/superuser/delete-videos` 页面删除后重传。普通删除保留比赛结算结果，重算规则见[比赛录像删除方案](../tournament/VIDEO_DELETION_PLAN.md)。

服务器建档和补录沿用应用日志，记录目标账号、标识、录像及日期。公开资料和头像沿用正常缓存周期，其他浏览器可能暂时显示旧姓名或缺少纪念标识。

## 账号删除与孤立扫雷资料

`UserProfile.post_delete` 按真实 `userms_id` 在同一数据库事务内删除关联 `UserMS`，其标识通过外键级联删除；覆盖实例和 QuerySet 删除。从 `UserMS` 发起的原有级联跳过重复清理，未关联 `UserMS` 的账号可正常删除。

历史孤立 `UserMS` 使用 `python manage.py cleanup_orphan_userms --dry-run` 预览，去掉 `--dry-run` 执行清理。支持 `--batch-size`（默认 1000）和 `--database`（默认 `default`）；实际删除分批加锁并重新检查用户关联，已关联用户的资料保留。两种用户 ID 无需相等，不使用同值主键推断归属。

## 用户姓名隐藏

### 授权与设置

- `can_hide_realname` 记录资格，`hide_realname` 记录用户选择，默认均为 False。管理员可授权或撤销；撤销同时关闭隐藏。
- 新的 MSGames 正式绑定事件自动授权，不自动开启隐藏；绑定与资格同事务提交，第三方资料同步在提交后执行。远端请求失败或返回空白姓名不影响绑定成功及已有资格，后续可刷新或重试验证以补齐资料。解绑保留资格及选择，重复验证、登录和同步不重新授权；上线前已绑定的用户由管理员手动补发资格。
- 有效实名是非空、非纯空白且不为“匿名”的 `realname`。没有实名时不能开启隐藏；已有资格的用户可以在首次设置有效实名时同时选择隐藏。清除实名会关闭隐藏并保留资格。
- 隐藏开关位于个人设置的“真实姓名”标题旁，已有实名时通过独立接口自动保存；首次填写实名时与姓名一起点击“保存”，同事务提交。失败恢复原选择，说明放在开关的 title 中。接口参数与限流以 Ninja API 文档为准。

### 姓名读取与缓存

`_realname`、`_firstname`、`_lastname` 保存原值，数据库列名仍为 `realname`、`firstname`、`lastname`。模型同名公开 getter 在有效隐藏时返回精确字符串 `hidden`，包括原本为空的英文名。`has_realname()`、姓名写入服务和本人／管理员 Schema 读取底层原值；ORM 查询、`values()`、`update_fields` 使用下划线字段名。

公共单用户、批量资料和录像查询返回公开姓名；前端识别 `hidden` 后统一显示“用户 #ID”／`User #ID`，忽略姓名格式偏好。本人 `info/0`、登录响应及管理员资料返回原值。三个姓名字段都禁止设置为规范化后的精确值 `hidden`。

这是展示偏好。账号关联返回的姓名、原始录像内容和原文件名保持原样；导出目录沿用 `{用户ID}_{公开姓名}/原文件名`。录像查询禁用按姓名排序。本人保存资料成功后立即使该用户的本地姓名缓存失效，已显示的 `PlayerName` 重新读取公开姓名；失败则恢复复选框为已保存的选择。其他浏览器仍按正常检查周期更新，不保证同时变化，缓存机制见 [userService.md](../../../front_end/src/services/userService.md)。

## 用户数据库列表

数据库默认页 `/database/users` 使用公开接口 `GET /api/userprofile/query`。通过 `platform + id` 精确查询；平台省略或为空时查本站用户，`c`、`a`、`w`、`m` 分别查扫雷网、MSGames、WoM、Mineracer 的已验证关联。ID 留空显示全部用户。响应字段和分页、排序参数由 Ninja API 文档提供。

没有 `UserMS` 的用户按零展示及排序；等待重算的负统计值仍保留。统计同值时按用户 ID 升序分页。关联 ID 使用字符串，未绑定的平台省略；Mineracer 暂无个人主页链接，仅显示 ID。

查询及索引见 [数据库与缓存说明](../../../vitepress_doc/zh/guide/development/cache.md)。`AccountLinkQueue` 的新增联合索引需使用 Django 生成并应用 `accountlink` 迁移。

## 数据库迁移

纪念账号的身份字段和认证约束需要迁移。仓库按现有约定忽略编号迁移文件，部署时保留服务器已有迁移历史，在 `back_end/saolei` 目录执行：

```sh
python manage.py makemigrations userprofile
```

如果环境尚未应用姓名隐私字段重命名，三个重命名确认均回答 yes。检查生成的迁移及 `sqlmigrate` 输出：原姓名列必须保留，姓名隐私部分仅新增两个布尔列；不能应用“删除旧姓名字段再新增空字段”的迁移。纪念账号部分另有身份字段和认证约束。确认后执行：

```sh
python manage.py migrate
```

存量资格不自动回填；由管理员按需授予。

## 验证

后端在 `back_end/saolei` 运行：

```sh
python manage.py test userprofile.tests accountlink.tests.NamePrivacyBindingTests --keepdb
python manage.py test common.test_memorial tournament.tests.test_gsc_history userprofile.test_deletion msuser.test_cleanup_orphans --keepdb
```

前端单元测试在 `front_end` 运行：

```sh
npm run vitest -- run src/utils/userprofile.test.ts src/services/userService.test.ts
npm run vitest -- run src/services/memorialService.test.ts src/components/GSCAdmin/history.test.ts
```

Cypress 由用户运行：

```sh
npx cypress run --component --browser chrome --headless --spec "src/components/PlayerName.cy.ts,src/views/UserView/EditProfile.cy.ts"
npx cypress run --component --browser chrome --headless --spec "src/views/StaffView/MemorialAccounts.cy.ts"
npx cypress run --e2e --browser chrome --headless --spec "cypress/e2e/realname-privacy.cy.ts"
```

E2E 使用隔离的测试数据库及 Redis，启用 `E2E_TEST=True` 并完成迁移，前后端地址按 `.github/workflows/CypressE2E.yml` 准备。用例会重置测试数据。合成 MSGames 账号 `2147483000`、`2147483001` 仅在 `E2E_TEST=True`、`DEBUG=True` 且无 `.production` 标记时返回固定外部资料，本地绑定与授权仍经过实际业务接口。

## QQ 登录接入（规划，未实施）

本节记录「用 QQ 账号登录本站」的外部约束、待决问题和实施计划。当前仓库没有任何 QQ 登录能力，本节是排期依据而非现状描述；实现落地后需改写为现状描述。QQ 互联的网站应用接入属于登录侧能力，与本站现有的「账号关联」是两件事。

**文档维护约定**：计划制定阶段本节随讨论进度同步更新，每轮讨论的结论、方案补充和编码授权当轮写入，不攒到实现阶段补记。条目状态以文末「待办清单」为准：`[阻塞]`、`[待决]`、`[已决策待实施]`、`[方案已评估]`、`[已落地]`、`[已确认]`；除明确获准写代码的条目外，本阶段只维护文档，不改动代码。

### 外部硬性要求

依据 QQ 互联 WIKI 的[应用审核规范](https://wiki.connect.qq.com/%e7%bd%91%e7%ab%99%e5%ae%a1%e6%a0%b8%e8%a7%84%e8%8c%83)与[网站前端页面规范](https://wiki.connect.qq.com/%e7%bd%91%e7%ab%99%e5%89%8d%e7%ab%af%e9%a1%b5%e9%9d%a2%e8%a7%84%e8%8c%83)（2026-11-11 核对）：

- **备案优先于开发**：网站地址与回调地址都必须在工信部完成备案，且 QQ 互联平台填写的备案信息需与工信部一致；该条款在审核规范中出现两次。不满足时不要开始编码，也不要先申请 appid。
- **标准标识不得修改**：必须使用腾讯提供的标准「QQ登录」标识，规格为长图标 230×48 / 170×32 / 120×24 / 105×16、中图标 63×24 / 50×16、小图标 16×16 + 文字链接；7 种规格均为矩形文字按钮或 16×16 企鹅小图标，**官方没有圆形图标**。图标版权归腾讯，不允许做任何修改，否则腾讯有权单方面中止 QQ 登录连接服务；《应用审核规范》另要求「网站应用需按照腾讯提供的 UI 规范放置 QQ 登录按钮」，不得擅自修改。小图标配文字时文字可微调，但必须含「QQ登录」「QQ」「登录」字样；中/小规格标识旁建议加「QQ账号登录」等说明文字。项目方 2026-11-12 提出改用其他网站常见的圆形 QQ 图标，该形态不是腾讯标准标识，自绘或替换会命中驳回项，故不采用；合规范围内最接近的是官方 16×16 企鹅小图标 + 文字链接，2026-11-12 起三处入口统一采用（「标准标识素材」）。
- **放置位置**：按钮必须「易于用户查找」，官方建议放在首页、登录页以及注册页；审核驳回明细明确列出「在首页、注册页、登录页等页面主要位置没有放置 QQ 登录入口」。本站登录弹窗由 `front_end/src/components/Login/App.vue` 控制，现已有 `/login`、`/register` 路由别名可直达；首页主要位置由**常驻菜单栏**承载：`front_end/src/views/Menu.vue` 的未登录导航项里，官方小图标 + 文字链接放在「登录」项左边，首页及全站页面均可见，登录/注册弹窗内为同款入口（同一个 `QQLoginEntry.vue` 组件）。窄屏下 ElMenu 的 ellipsis 可能把导航项收进「更多」，审核通常在宽屏进行，联调阶段需确认。
- **上线前功能必须已完成**：提交申请时 QQ 登录开发需已完成且授权流程可跑通，审核 1–3 个工作日人工检查，驳回后按邮件整改再申请。审核上线规范要求 QQ 登录用户与注册用户享有同等权限（浏览、发表、评论等）、禁止应用要求用户填写单独的密码、不得诱导用户泄漏 QQ 账号信息及好友关系链。
- **用户引导与展示**：网站前端页面规范要求首次登录成功后提供欢迎引导页（建议显示 QQ 昵称、头像及登录途径），强烈建议一键开通新账号而非要求其它注册资料，绑定时操作量最小化，允许绑定后修改用户名，并在显示用户名处同时显示 QQ 昵称与头像。这与本站现有注册表单（邮箱验证码 + 密码 + 密码确认 + 同意协议）和 GitHub「不保存用户名、头像」的约定都冲突，首次登录流程需单独设计，昵称/头像是否落库需单独决策。

### 与现有约定的关系

- `Platform.QQ`（平台码 `q`）和 `AccountQQ` 属于私密的手填数字 QQ 号关联，由管理员审核，见 [Discord 人工关联](../accountlink/discord/README.md)。登录身份不能复用 `AccountQQ.id`：它是 QQ 号而非 QQ 互联返回的 `openid`，且可手填、可由管理员解绑。官方明确 QQ 互联**不返回 QQ 号**，也不允许以任何理由获取 QQ 账号相关信息，因此两套身份既不能互相推导，也不能在登录流程里要求用户补填 QQ 号去「打通」关联，核实依据见「QQ 互联返回的身份信息」一节。建议关联流程保持不变，登录身份另建模型。
- `discord/README.md` 的「Discord 不再使用官方接口或提供第三方登录」和 `test_private_links.py` 中 OAuth 路由返回 404 的回归只针对 Discord，不限制新增 QQ 登录路由；GitHub 章节的「不提供 GitHub 登录、注册或邮箱合并」同样只限定 GitHub，这些表述主语明确，不需要删除。
- `github/api.py` 的 `current_session_user` 要求已登录会话，`start` / `callback` / `cancel` / `unlink` 全部带 `login_required_error`，整套流程只做「已登录用户绑定外部账号」，不能直接改造为登录。但 `github/cache.py` 的随机 state、一次性占用与撤销、600 秒 TTL，以及回调的 `never_cache`、固定返回地址、不把 code/token 带进日志和结果地址的做法，可作为 QQ 回调的安全基线。
- `accountlink/models.py` 中「使用QQ互联提供的登录接口需要开发者注册，步骤繁琐，不利于去中心化」是账号关联侧的历史设计决策。**模块归属已决策（2026-11-12）**：QQ 互联登录属于登录侧能力，放在 `userprofile` app，与 `accountlink` 分开；`accountlink` 继续只管第三方账号关联，不提供登录。这样登录侧不需要引入 `accountlink` 的任何模型，符合仓库 APP 分层（`userprofile` 是基础 APP，不引用其他 APP 的模型），也不再构成「推翻 `accountlink` 去中心化决策」的问题；该注释保留其历史语境，实现时可补一句指向 `userprofile` 的说明。相应地 `QQConnectIdentity`、`schema.py` / `client.py` / `cache.py` / `services.py`、Ninja Router 与结构迁移都归 `userprofile`，迁移命令为 `python manage.py makemigrations userprofile --noinput`。
- 实现后需同步修订：`vitepress_doc/zh/guide/account-links.md` 及对应英文版（补登录入口说明）、`front_end/src/views/UserView/AccountLinks/README.md`（QQ 关联卡片与登录入口的区别）、本节自身。VitePress 用户文档按仓库约定需中英文各一份。**文档归属**：2026-11-12 已把 QQ 登录规划章节从 `accountlink/README.md` 迁到本文件，`accountlink/README.md` 只保留一条交叉引用；`accountlink` 继续只管第三方账号关联。

### 待决问题

1. 域名与回调域名是否已完成 ICP 备案、备案主体与 QQ 互联开发者主体是否一致、个人主体能否申请网站应用。回调地址需固定 HTTPS 路径并与平台登记值完全一致，不启用通配，参照 GitHub 的 `/api/accountlink/github/callback`。
2. 是否推翻 `models.py` 的去中心化决策；QQ 登录仅作为额外登录方式，还是同时取代手填 QQ 号关联。建议前者。
3. 身份模型：QQ 互联返回 `openid` 字符串及可选 `unionid`，与 `AccountQQ.id` 的 `PositiveBigIntegerField` 不兼容。需在 **`userprofile` app** 新建一对一模型（例如 `QQConnectIdentity`），`related_name` 不得与 `account_qq` 冲突；明确是否保存 `access_token`（建议只用于换取 openid 与资料，不落库）。结构迁移必须用 `python manage.py makemigrations userprofile --noinput` 自动生成，禁止手写迁移脚本。`openid` 官方格式为 32/36 位十六进制字符串（默认大写）且与 appid 绑定，换 appid 会让全部已有 openid 失效，需连同 appid 一起记录并预留迁移方案；`unionid` 可后补，见「QQ 互联返回的身份信息」一节。核实依据见该节。
4. 首次登录的账号策略：一键开通还是引导绑定已有账号；如何创建与现有注册用户等价的 `UserProfile` / `UserMS`；自动生成的用户名（昵称 + 随机数）如何避让重名，是否允许后续修改；openid 已绑定他人或当前会话属于另一用户时如何拒绝，参照 `save_verified_account_link` 的冲突校验。一键开通情形下的邮箱与密码初始化已有结论，见「一键开通的邮箱与密码初始化」一节；已注册用户再用 QQ 登录时的重复账号与 id 占用方案见「已注册用户再用 QQ 登录：避免占用 id」一节。
5. 会话与权限：现有登录由 `userprofile/views.py` 的 `authenticate` + `login(request, user)` 签发会话，QQ 回调需签发等价会话并保证同等权限。按仓库约定用 Ninja API，权限校验统一在 API 层，普通用户 API 全部加 `ratelimit`，回调按 IP 限流且不能要求登录态；管理员 CSRF 规范不适用于普通用户 API。
6. 前端实现形式：官方开发流程另有「放置『QQ登录』按钮」与「QQ互联登录 CDN 接入」。项目方 2026-11-12 **最终确定不引入官方 CDN JS SDK**，本站采用 server-side OAuth2.0 自建跳转 + 原样使用官方标准标识图片；两套 SDK 的功能、维护质量、不引入的五项理由与将来引入的条件见「官方 CDN JS SDK 调研」一节。
7. UI 与合规：官方图标素材需原样存放，不得改色、重绘，也不得为适配深色主题而变色；同时在首页可见位置、登录弹窗 `LoginForm.vue`、注册弹窗 `RegisterForm.vue` 三处放置。与 `front_end/UI_REFACTOR_PLAN.md` 的直角紧凑风格冲突时以 QQ 互联合规优先。需补齐中英文文案、首次登录欢迎页及全站用户名展示处的昵称头像。三处入口与 `/login`、`/register` 路由骨架已于 2026-11-12 获准并落地（见「登录页与注册页路由方案」「已决策事项与编码授权」）；路由只提供登录页与注册页地址，不能替代首页常驻可见入口。
8. 安全与运维：state 一次性、回调不接受任意 `return_url`、code/token 不进入日志与前端结果地址；`default.conf` / `uwsgi.ini` 需为回调预留超时并关闭 access log，参照 GitHub 回调配置；凭证放 `secrets.json`，由 settings 启动时读取，不进入构建产物。
9. 审核自查：提交上线前逐项核对「首页、注册页、登录页主要位置」「登录成功后能完成页面授权」「网站首页及模块已建设完成」三条驳回项。

### 登录页与注册页路由方案（2026-11-12 已实施）

提议：在 `front_end/src/router/index.ts` 增加登录页与注册页路由，访问后仍渲染首页 `HomeView/App.vue`，但默认打开对应弹窗，以此给 QQ 互联审核提供明确的「登录页」「注册页」地址，并让首页、登录页、注册页三处都能承载 QQ 登录入口。登录页是 `/#/login` + 登录弹窗；注册页同样可用路由 + 弹窗实现，即 `/#/register` + 注册弹窗，两者共用同一套机制。

**技术可行，改动很小。** 根 `App.vue` 用常驻的 `Menu.vue` 包裹 `<router-view />`，`Menu.vue` 里的 `<Login v-slot="controls">` 也常驻，`Login/App.vue` 的弹窗状态（`dialogVisible`、`activeDialog`）不随路由切换销毁。因此路由只需指向首页组件，再由 `Login/App.vue` 通过 `useRoute()` 判断路径或路由 `meta`，调用已有的 `openDialog('login')` / `openDialog('register')` 即可，无需新建登录页或注册页组件，也不用搬动弹窗。两种写法：为 `/login`、`/register` 各新增一条记录指向 `HomeView/App.vue`；或给现有 `home` 记录加 `alias: ['/login', '/register']`，后者不新建路由记录，首页组件实例及其局部状态（新闻队列、录像队列）不会重建。路由使用 `createWebHashHistory`，实际地址是 `https://openms.top/#/login`、`https://openms.top/#/register`；备案按域名计算，hash 不影响。

**实现时需要处理的点**（2026-11-12 已按下列要点实现）：

- 登录态时序：`store.login_status` 初值为 `LoginStatus.Undefined`，`Login/App.vue` 的 `onMounted` 异步请求 `/api/common/loginauto` 后才置为 `IsLogin` / `NotLogin`。若在会话恢复完成前打开弹窗，已登录用户会短暂看到登录或注册框；已登录访问这两个地址应重定向回首页。注册页还需与 `RegisterForm` 的 `@login` 事件协作，避免注册成功后停留在注册页地址。
- URL 与视图一致：手动关闭弹窗后 URL 仍是 `/#/login` 或 `/#/register`，需在 `dialogVisible` 变为关闭时 `router.replace({ path: '/', force: true })`；登录成功关闭弹窗时同样要处理。`alias` 与原路由是同一条记录，Vue Router 的 `isSameRouteLocation` 不比较 `path`，普通 `replace('/')` 会被判为重复导航而不改变地址，必须加 `force`。
- 导航高亮：`Menu.vue` 的 `activeSection` 按 `route.path.split('/')[1]` 计算，`/login`、`/register` 会得到没有对应导航项的 `login`、`register`，两者都需显式归入 `home`。
- `navigationItems` 里登录/注册是 `action` 而非 `to`，当前没有可外部引用的登录/注册 URL；新增路由也补上了这一点，QQ 登录失败回跳或邮件链接可直接指向该地址。
- 弹窗内三个表单可互相切换（`@forget-password`、`@login`），路由只决定初始弹窗；用户从登录弹窗切到修改密码时 URL 不跟随变化，属于可接受的前端局部行为。

**合规结论：可行，但不能替代首页常驻入口。** 审核驳回项要求「首页、注册页、登录页等页面主要位置」都有 QQ 登录入口，放置准则是「必须易于用户查找」。本方案覆盖登录页与注册页，但 QQ 标识仍只存在于弹窗内；审核人员从 QQ 互联登记的网站地址（通常是首页）进入时不会主动访问 `/#/login` 或 `/#/register`，首页依旧看不到图标。因此首页导航栏放常驻可见的官方标识不可省略，已单列决策见下节。另需记录风险：hash 路由加 `ElDialog` 的 `append-to-body` 动态渲染意味着静态 HTML 中没有按钮；官方审核为 1–3 个工作日人工审核，是否存在自动化预检需在联调阶段确认。

**实施记录（2026-11-12）**：采用 `alias` 方案，`front_end/src/router/index.ts` 的 `home` 记录加 `alias: ['/login', '/register']`，首页组件实例与队列状态不重建；`front_end/src/components/Login/App.vue` 用 `useRoute()` / `useRouter()`，在 `loginauto` 会话恢复完成后才按路径调用 `openDialog`（`sessionReady` 开关），已登录访问这两个地址用 `router.replace({ path: '/', force: true })` 回跳首页，弹窗关闭时同样处理；`Menu.vue` 的 `activeSection` 把两段路径显式归入 `home`，标题与导航高亮跟随首页。导航项仍为 `action`（点击开弹窗、不改 URL），两个地址只用于外部引用与审核。表单互切不改变 URL，按原设计保留。

**2026-11-12 代码审查修复（P2 × 3）**：① `alias` 下 `router.replace('/')` 被判为重复导航，关闭弹窗、登录成功、已登录重定向时地址仍停在 `/login`、`/register`；已核对本地 Vue Router 的 `RouteLocationOptions.force`（「位置相同也触发导航」），三处统一改为 `router.replace({ path: '/', force: true })`，并用本地脚本实测 `plain replace: /login` → `force replace: /`。② QQ 菜单入口按钮补 `@keydown.stop`，与 `NavigationControl` 一致，避免键盘事件冒泡到 ElMenu 后被转成点击外层菜单项（该项无 `action`），导致 Enter / 空格无法触发占位提示。③ `syncRouteDialog` 增加 `routeOpenedDialog` 标志：浏览器后退或导航离开这两个路由时，只关闭「由路由打开」的弹窗，用户点导航栏打开的弹窗不受影响。三项均补了组件测试回归。

**CI 修复（2026-11-12）**：固定文案「QQ登录」会让 E2E 的 `cy.contains('登录')` 优先命中 QQ 入口（它在「登录」菜单项左边），`account.cy.ts` 中 4 处打开登录弹窗的点击改为 `[data-cy=app-header] [data-navigation-id=login] .navigation-control` 精确定位，弹窗内的登录提交按钮改用 `^\s*登录\s*$` 精确正则；`Login/App.cy.ts` 不再用 UI 点击关闭弹窗：Element Plus 的 `useDialog` 要到关闭动画结束（`afterLeave`）才 emit `update:modelValue`，而 Cypress 组件测试禁用过渡，动画不会结束，`dialogVisible` 始终为 `true`，回跳的 watch 便不会触发；通知浮层还会盖住关闭按钮，`click({ force: true })` 只会把事件送到浮层，同样无效。测试改为直接把 `dialogVisible` 置为 `false` 来验证关闭回跳；产品侧回跳判定改用 `routeOpenedDialog` 标志，不再依赖关闭瞬间的 `route.path`。以后再新增含「登录」字样的入口，需同步检查 `contains('登录')` 一类的模糊断言。

### 已决策事项与编码授权

按讨论进度记录当前状态，计划阶段默认只维护文档：

| 事项 | 结论 | 状态 |
| --- | --- | --- |
| 首页常驻 QQ 登录入口 | 现在直接添加，不排到实施计划阶段 3；承担「首页主要位置」与「易于用户查找」；2026-11-12 按项目方要求从首页内容区移到常驻菜单栏「登录」项左边，三处入口统一为官方 16×16 小图标 + 固定中文「QQ登录」 + 站点现代排版 | 已落地（菜单栏 + 两处弹窗 + 占位点击），真实授权地址待接入 |
| 登录页 | 路由 + 首页 + 默认打开登录弹窗 | 已落地（`home` 的 `alias`） |
| 注册页 | 同法用路由 + 首页 + 默认打开注册弹窗 | 已落地（`home` 的 `alias`） |
| 一键开通的邮箱/密码初始化 | 每账号唯一的 `@accounts.invalid` 占位邮箱 + `set_unusable_password()`，后续自愿补全 | 结论已明确，未实施 |
| 回调未命中 openid 的引导 | 文案区分两套 QQ 身份、警告会创建第二个号、引导正常登录后关联 openid；坚持注册则直接创建 `UserProfile` | 已决策采用，未实施 |
| 前端实现形式 | 项目方最终确定不引入官方 CDN JS SDK，采用 server-side OAuth2.0 自建跳转 + 官方标准标识图片 | 已最终决策，入口骨架已落地 |
| 其余条目 | 备案、身份模型、会话、OAuth 后端、授权目标 | 待决，不写代码 |

**2026-11-12 编码授权**：项目方明确「确定不引入官方 CDN JS SDK」，并授权实现页面入口骨架（仅前端三处入口与 `/login`、`/register` 路由，不含 OAuth 后端、appid 申请、回调与会话签发）；同时允许通过互联网获取图片资源。当日后续追加授权：把首页入口移到菜单栏「登录」项左边、改用官方小图标 + 文字链接。据此联网下载 `Connect_logo_1.png` 原样入库为 `front_end/public/img/qq_login_16x16.png`；非官方圆形图标未采用，理由见「外部硬性要求」。当日第三轮追加授权：按「官方现代 UI 选项调研」的建议方案统一三处入口，文案固定中文、不做英文界面，弹窗内淘汰 120×24 长图标，已实施。

第一项约束已解决：两张官方标准标识均已下载入库并联网核对哈希，见下节（当前代码只用 16×16 小图标，120×24 长图标已淘汰、文件保留）。`front_end/src/views/UserView/AccountLinks/platforms.ts` 外链的 `03_qq_symbol` 是账号关联展示用的 QQ symbol，不是标准登录按钮素材，不用于登录入口。剩余约束是点击目标：appid 尚未申请、回调尚未实现，不能编造授权地址。三处入口统一由 `front_end/src/components/Login/QQLoginEntry.vue` 承载（菜单栏通过 `NavigationItem.component` 渲染并传 `compact`），均为可点击占位，点击只显示中文「QQ 登录尚未开放」提示，不跳转、不落库、不拼接任何授权地址；阶段 1/2 完成后把占位点击替换为真实授权地址即可。提交上线审核前必须确认图标可点击且授权流程跑通，否则会命中「没有完成 QQ 登录功能开发」驳回项。

### 标准标识素材（已下载）

腾讯官方 CDN `https://qzonestyle.gtimg.cn/qzone/vas/opensns/res/img/Connect_logo_{n}.png` 提供 7 种标准「QQ登录」标识，尺寸与[网站前端页面规范](https://wiki.connect.qq.com/%e7%bd%91%e7%ab%99%e5%89%8d%e7%ab%af%e9%a1%b5%e9%9d%a2%e8%a7%84%e8%8c%83)列出的规格逐一对应：

| 文件 | 尺寸 | 官方规格分类 |
| --- | --- | --- |
| `Connect_logo_1.png` | 16×16 | 小图标 + 文字链接 |
| `Connect_logo_2.png` | 105×16 | 长图标 |
| `Connect_logo_3.png` | 120×24 | 长图标 |
| `Connect_logo_4.png` | 170×32 | 长图标 |
| `Connect_logo_5.png` | 230×48 | 长图标 |
| `Connect_logo_6.png` | 50×16 | 中图标 |
| `Connect_logo_7.png` | 63×24 | 中图标 |

已把 `Connect_logo_3.png` 原样保存为 `front_end/public/img/qq_login_120x24.png`（3719 字节，SHA-256 `021F899C259C5776E6D3CC6DC45079C4D636E966D76610E0C85FD57BC1410D32`），2026-11-12 统一入口后不再被代码引用，文件保留备用；`Connect_logo_1.png` 原样保存为 `front_end/public/img/qq_login_16x16.png`（19865 字节，SHA-256 `18E4D80549A113576999D08531AC5E4648F5E12166AE7106C01419D6BBE07146`），供三处入口使用。两张图均与官方 CDN 原图哈希一致，未重编码或修改；其余 5 种规格需要时按同一 CDN 再下载，仓库暂不冗余存放。官方[视觉素材下载](https://wiki.connect.qq.com/%e8%a7%86%e8%a7%89%e7%b4%a0%e6%9d%90%e4%b8%8b%e8%bd%bd)页声明这些标准素材仅供开发应用使用、不得修改，因此代码里不对图片做滤镜、改色、重绘或深色主题适配，只把 `width` / `height` 设为原始尺寸。

三处入口统一由 `QQLoginEntry.vue` 承载，均使用官方 16×16 原图、原样尺寸（图标不加滤镜、改色、重绘或深色反转）：菜单栏（首页主要位置）在「登录」项左边，经 `NavigationItem.component` 渲染并传 `compact` 去掉分隔线，菜单项同时透传 `.navigation-control` 布局类（`display:flex` / `align-items:center` / `height:100%` / `padding:0 10px`）保持行高与纵向居中；登录/注册弹窗在表单下方以细分隔线呈现。整个入口即原生 `<button>` 便于键盘操作与审核点击，`alt` 留空、可见文字固定中文「QQ登录」（不做 i18n），按钮用继承字体与颜色、0.375rem 间距、主题色 hover，路径按项目惯例用 `` `${import.meta.env.BASE_URL}img/...` `` 拼接。点击统一显示中文「QQ 登录尚未开放」的 `ElMessage` 提示，不跳转、不编造 appid；阶段 1/2 后替换为真实授权地址。官方 7 种规格里没有圆形图标，其他网站常见的圆形 QQ 图标不是腾讯标准标识，未采用（「外部硬性要求」）。

### 官方现代 UI 选项调研（2026-11-12）

项目方提出「不一定要圆形，但不要看起来太老」。核对官方页面后的结论：

- **按钮素材层面没有现代版**。官方[视觉素材下载](https://wiki.connect.qq.com/%e8%a7%86%e8%a7%89%e7%b4%a0%e6%9d%90%e4%b8%8b%e8%bd%bd)页只有 1.1 QQ LOGO（`01_qq_logo` / `02_qq_logo_ver` / `03_qq_symbol`，PSD 品牌素材，不是登录按钮）、1.2 QZONE 素材、1.3 QQ 分享素材、2.「QQ登录框标准样式」（大图标 92×120、蓝色/灰色 76×24、蓝色/灰色 24×24）、3. 功能组件样式（指向各组件介绍页）。[《网站前端页面规范》](https://wiki.connect.qq.com/%e7%a7%bb%e5%8a%a8%e5%ba%94%e7%94%a8%e6%8e%a5%e5%85%a5%e6%b5%81%e7%a8%8b%ef%bc%88%e6%94%b9%ef%bc%89test/)第 1 节仍只列 7 种标准标识，没有 SVG、扁平化、深色或圆形新版。所以「看起来老」是官方按钮素材本身的年代问题，不是规格选错。
- **官方的现代 UI 在登录页层，不在入口按钮**。新版 CDN 登录 SDK 渲染的是互联侧 iframe 里的托管登录页：扫码 / PC QQ 快捷登录 / 账密登录，`color_theme`（light / dark / auto 跟随系统）、`lang`（zh_CN / zh_TW / en_US）、`setConfig` 热切换、`app:set_theme` 事件、280×280 起自适应、380px 切大组件，脚本始终指向最新版本。但这是登录面板而非按钮，且项目方已最终确定不引入 SDK（下一节）。自建 server-side 跳转打开的 QQ 统一授权页同样是腾讯维护的现代登录界面，用户点完按钮后即看到。
- **合规的「不显老」空间在文字与容器，不在图标**。《网站前端页面规范》原文限制的是「以下各种规格的**图标**……请勿更改」；1.3 把「16×16 小图标 + 文字链接」列为标准形态，2.3 建议中/小规格旁加「QQ登录」「QQ账号登录」等说明文字；审核产品 UI 规范进一步写明「小图标不允许做任何修改，**文字可以稍作调整**，但是文字中必须标有『QQ登录』『QQ』『登录』相关文字标示」。因此可用官方 16×16 原图不动，配本站现代排版的中文文字与容器（站点字体、直角/紧凑间距、主题色、hover 反馈、细分隔线），视觉上远新于 120×24 渐变长条按钮；图标本身仍不得改色、重绘、加深色反色滤镜。
- **已实施（2026-11-12，项目方确认「按这个方案统一」）**：三处入口统一由 `front_end/src/components/Login/QQLoginEntry.vue` 承载（菜单栏经 `NavigationItem.component` 渲染并传 `compact`），内容为官方 16×16 原图 + 固定中文「QQ登录」，配站点现代排版（继承字体与颜色、0.375rem 间距、主题色 hover、弹窗内细分隔线、菜单栏无分隔线）；120×24 长条按钮从代码中淘汰，图片文件保留。文案固定中文、不做 i18n，同时满足「QQ 登录不使用英文界面」与规范字面要求（英文 `QQ Login` 不严格含「QQ登录 / QQ / 登录」字样）；占位提示统一为中文 `ElMessage.info`。深色主题下图标不加滤镜，容器只用继承色与主题变量、不改图标像素；「容器加背景/圆角是否算修改按钮」官方无明文，阶段 4 审核确认。

### 官方 CDN JS SDK 调研（2026-11-12 结论）

结论：**项目方 2026-11-12 最终确定不引入官方 CDN JS SDK，本站采用 server-side OAuth2.0 自建跳转**，只在首页/登录/注册弹窗用已入库的官方标准标识图片，当前方案不再保留「将来可能引入」这一分支。官方「网站开发流程」把「QQ互联登录 CDN 接入」列为一步，但《应用审核规范》没有任何条款要求必须引入 SDK；新版 SDK 自己也提供 `QQLogin.getAuthUrl(config)`「不嵌入登录组件，只返回完整的 QQ 授权地址，接入方拿到地址后自行决定打开方式」，说明自建跳转是官方支持的路径。传统流程（准备工作_OAuth2.0 → 放置按钮 → 获取 Access_Token → 获取用户 OpenID）在文档里完整可用。另需区分：扫码登录、PC QQ 快捷登录、账密登录都是 QQ 互联授权页 `https://graph.qq.com/oauth2.0/authorize` 自身提供的能力，自建跳转打开的就是该页面，因此不引入 SDK **不代表没有扫码/快捷登录**；SDK 独有的只是把这些方式嵌进本站页面内的 iframe 容器，边界见本节末尾。

| | 新版 CDN 登录 SDK | 旧版 JS SDK |
| --- | --- | --- |
| 脚本 | `https://res.connect.qq.com/jssdk/index.js`（固定指向最新版本） | `//connect.qq.com/qc_jssdk.js` |
| 全局对象 | `QQLogin` | `QC` |
| 形态 | 容器内渲染托管登录组件（互联侧 iframe，扫码 / PC QQ 快捷登录 / 账密登录） | 只渲染登录按钮 + 封装 client-side OAuth |
| 文档 | 2026-10-30 首次发布，结构完整 | 陈旧，仍写「老浏览器需要 Flash 插件完成跨域通信」、明文 `http://` 脚本 |

## 玩家认证

完整规则与实施决策见 `PLAYER_VERIFICATION_PLAN.md`，本节只记录部署与维护要点。

- `UserProfile.verified` 是当前有效认证结果，不是「已实名」，也不代表管理身份。`UserVerifyEdge` 只保存当前存在的有向边（`from_user`、`to_user`、`created_at`），以 `UniqueConstraint(from_user, to_user)` 防止同向重复边，以检查约束禁止自认证边；允许多入边、多出边、反向边和环，没有申请表、根节点或历史表。
- 三类写入（普通主动认证、管理员设置 `verified`、站长完整图批次）都在 HTTP 请求内的单个数据库事务中同步完成，不使用 Django Tasks、任务查询或任务清理配置。普通认证只新增当前用户到目标的边并把目标设为已认证，不遍历下游；管理员只改指定节点；站长一次提交全部边与节点命令，后端不推导可达性或撤销范围。
- 站长批次先开启独占维护会话（时长由站长指定，上限 1 小时）。会话状态与图写入串行锁放在 Redis 缓存 `userprofile/verification/cache.py`，TTL 到期自动恢复服务；提交成功或站长主动结束会立即释放。维护期间 `/verification/verify` 与 `/admin/verification/set-verified` 返回 409，读接口与站长批次提交仍可用。没有 `UserVerifyCoordinator` 表。
- API 集中在 `userprofile/verification/api.py`：`/api/userprofile/verification/status|verify` 为普通用户接口，`/api/userprofile/admin/verification/*` 为管理接口。管理员设置 `verified` 用 `staff_or_superuser_required`，站长读取、维护会话与批次用 `auth=django_auth_superuser`；管理员接口无限流，普通接口按项目约定限流。
- 部署顺序：先执行 `migrate` 应用 `0010`、`0011` 建表并移除旧树表，再发布新前端；现有用户 `verified` 缺省为 false，已有实名用户仍按实名条件准入。旧树方案未部署到生产，不需要数据转换；本地切换前停止旧 worker 并确认没有 READY/RUNNING 的旧认证任务。
- 录像上传已迁移到 Ninja 的 `POST /api/common/uploadvideo`，旧 Django view 和 `/common/uploadvideo/` 路由已移除；nginx 的限流 location 与排名维护锁路径需同步部署。上传、`create_weekly_participant` 和 `create_gsc_participant` 统一使用 `userprofile.utils.has_identity_access`，错误为 `userprofile/identity_access_required`。登录、自动登录和本人资料返回 `verified` 与 `can_submit_replays`，公开资料只返回 `verified`，不返回认证来源。

新版功能：静态 `QQLogin.init(config)` / `getAuthUrl(config)` / `QQLogin.VERSION`；实例 `show()` / `hide()` / `isVisible()` / `destroy()` / `setConfig(patch)`。config 必填 `appid`、`redirect_uri`、`element`、`onMessage`，可选 `response_type`（code/token）、`state`、`scope`、`redirect_type`（parent/self）、`lang`（zh_CN/zh_TW/en_US）、`color_theme`（light/dark/auto）。事件有 `app:page_loaded`、`app:page_ready`、`app:page_error`（reason 为 `invalid_config` / `qr_load_failed` / `runtime_error`）、`app:set_theme`、`login:success`；`setConfig` 可在 `app:page_loaded` 后热切换语言、主题、跳转方式与回调。容器最低 280×280，宽高都超 380px 时切大组件。登录成功后把 code/token/state 拼到 `redirect_uri` 并跳转。登录页最佳 Chrome 49+，运行时下限 IE 10；外链脚本无需 polyfill。旧版功能：`QC.Login()` 渲染按钮（7 种尺寸）、`showPopup()`、`check()`、`getMe()`、`signOut()`、`QC.api()` 封装全部 OpenAPI 及 `cbLoginFun` 资料回调。

**维护质量判断**：官方「重要更新」页自 2012 年起，Web/JS SDK 只有 **2026-10-30 一条**（首次支持 CDN 接入），此前全是移动端 SDK 发版（Android / iOS / HarmonyOS 在 2020–2026 持续迭代）和协议侧通知（回调地址校验、头像域名变更、登录短信验证、`access_token` 有效期调整等）。所以团队整体活跃、服务端协议可信，但 **Web JS SDK 是发布仅约两周的新产物**，没有版本历史、changelog、社区反馈或生产验证沉淀；新版文档质量明显高于旧版（API 参考、事件清单、错误原因、兼容性表齐全），但旧版 `qc_jssdk.js` 应视为遗留，不要照旧博客接入。

**不引入的五项理由**：① `index.js` 始终指向最新版本，无法锁版本、无法做 SRI、构建不可复现，第三方脚本行为随时可能变；② 没有 npm 包和 TypeScript 类型定义，与本站 Vue 3 + `vue-tsc` 严格检查冲突，需自己写 `declare global`，且不能用 `any` / `@ts-ignore` 绕过；③ 登录页在互联侧 iframe，要放行 `res.connect.qq.com` 与 iframe 域的 CSP（`script-src` / `frame-src` / `connect-src`），离线与内网环境不可用；④ 组件最低 280×280 且自适应大组件，与「直角紧凑、高数据密度」的 UI 风格冲突，塞进登录弹窗会占满空间；⑤ `response_type=token` 会把 token 拼进 URL，若使用必须用 `code` 并校验 `state`。

**不引入 SDK 的准确边界**：受影响的是「页内嵌入式扫码 / 快捷登录（不离开本站页面）」，不是扫码能力本身。官方《使用Authorization_Code获取Access_Token》明确写「非 qq.com 域接入互联登录，如果用 iframe 会导致无法成功携带登录态信息」，《放置『QQ登录』按钮》也注明移动端不建议 iframe 嵌入，因此自己用 iframe 嵌授权页不是受支持路径；想要站内无跳转的扫码组件，只能走官方 SDK 托管的互联侧 iframe。SDK 还提供 `app:page_ready` / `login:success` / `app:page_error` 事件、`setConfig` 热切语言与主题、显隐不重载且保留扫码进度；自建跳转（整页或 `window.open` 弹窗）没有这些能力，页面状态需自行保存恢复。相应地在跳转方案下，「不引入理由」③ 的 CSP 放行与 ④ 的 280×280 大组件并不存在。**将来若要支持页内嵌入式扫码 / PC QQ 快捷登录**，再评估引入：先补 `declare global` 类型、CSP 放行、`app:page_error` 时降级回自建跳转，并确认「始终最新版本」可接受。也可只取 `getAuthUrl()`，但为此加载远程脚本不如自己拼授权地址简单可测。阶段 4 另需确认：官方「放置『QQ登录』按钮」页现把 CDN 接入列为开发流程一步，人工审核是否会因未用 SDK 而预期弹窗式登录；《应用审核规范》无强制 SDK 条款，按驳回邮件整改即可。

### 一键开通的邮箱与密码初始化（结论，未实施）

官方要求一键开通「无需提供其它注册资料」、「禁止应用要求用户填写单独的密码」，QQ 登录也不返回邮箱；但 `userprofile/models.py` 的 `UserProfile.email` 是 `EmailField(unique=True, blank=False, null=False)`，不能留空，`password` 继承 `AbstractUser`。两者按以下方式初始化：

| 字段 | 取值 | 依据 |
| --- | --- | --- |
| `email` | 每账号唯一的占位邮箱，沿用项目既有 `...@accounts.invalid` 后缀，例如 `qq-{openid 哈希}-{随机}@accounts.invalid` | 满足非空与唯一；`userprofile/forms.py` 的 `account_email()` 已在 `EmailForm` / `UserRegisterForm` / `UserRetrieveForm` 拒绝该后缀，`userprofile/services.py` 的 `send_email()` 也直接跳过，占位邮箱天然收不到验证码、不能走注册或找回密码 |
| `password` | `set_unusable_password()`，不生成随机密码、不要求用户填写 | 符合「禁止应用要求用户填写单独的密码」；`authenticate()` 对该账号返回 None，只能经 QQ 登录进入 |

项目已有同一模式的先例：`common/management/commands/create_memorial_account.py` 用 `memorial-{id}-{uuid4().hex}@accounts.invalid` + `set_unusable_password()` + `is_active=False` 创建纪念账号，`userprofile/models.py` 的 `memorial_auth_disabled` 约束检查 `password__startswith='!'` 与 `email__endswith='@accounts.invalid'`。该约束条件是 `is_memorial=False OR (...)`，`UserProfile.clean()` 也只在 `is_memorial=True` 时校验 `has_usable_password()`，因此 QQ 账号取 `is_memorial=False`、`is_active=True` 不违反约束。**不等价于纪念账号**：必须 `is_active=True` 并享有与注册用户同等权限。不尝试从 QQ 接口取邮箱，也不强制填写 QQ 邮箱（审核规范禁止）。

**其余必要初始化**：`userms = UserMS.objects.create()`（录像额度，与 `userprofile/services.py` 的 `register_user` 一致）；`username` 唯一且不超过 30 字符，若用「昵称 + 随机数」需过 `verify_text` 内容审核（QQ 昵称可能违规），并允许后续改名；`_realname`、`left_*_n` 等沿用模型默认值。`UserMS`、`UserProfile`、`QQConnectIdentity` 的创建与会话签发放在同一个 `transaction.atomic()`，失败整体回滚；对已有账号的 `save()` 显式传 `update_fields=`，首次 INSERT 参照 `register_user` 的 DJM100 例外处理。

**后续补全路径**（官方允许「连接成功以后使用其他方式引导用户完善资料」）：用户中心提供自愿的「绑定邮箱」，走现有 `get_email_captcha` + 邮箱验证码流程，校验通过后替换 `email`；`EmailForm.clean_email()` 只校验新输入的真实邮箱，不拦截旧占位值。绑定真实邮箱前该账号无法使用 `views.user_retrieve` 找回密码，但不会锁死，仍可经 QQ 登录；绑定后才可走找回密码。若提供自愿「设置密码」，`set_password()` 会改变 session auth hash，需像 `user_retrieve` 那样重新 `login(request, user)`，否则当前会话失效。邮箱与密码都不作为一键开通的必填项。

**审核视角**：「一键开通」在《网站前端页面规范》3.2 的措辞是「强烈建议使用一键开通的方式开通新账号，而无需提供其它注册资料」，属于建议性 UI 规范，不在《应用审核规范》的硬性条款或常见驳回明细里；官方也没有公开「如何判定是否一键开通」的检测细则。审核规范只写「QQ互联审核团队进行QQ登录功能和网站审核（1-3个工作日）」，即人工走一遍流程并以邮件说明驳回理由，公开案例里的驳回理由也是「点击QQ登录按钮提示登录失败或错误（不跳转、提示失败、错误信息）」这类外部表现。审核方能观察到的只有黑盒行为：点登录按钮 → 授权 → 回到网站后能否完成页面授权、是否被要求填密码／邮箱／注册资料、是否享有与注册用户同等权限；看不到后端如何建账号，占位邮箱、`set_unusable_password()`、同事务创建都不可见。因此本节的初始化方案在审核视角就是「一键开通」，前提是**首次登录不被任何表单阻断**。真正硬性的是「禁止应用要求用户填写单独的密码」「不能强制用户填写QQ邮箱」「享有与应用注册用户同等权限」，以及驳回项「QQ登录成功后无法完成页面授权」和「在首页、注册页、登录页等页面主要位置没有放置QQ登录入口」。规范 3.3 允许「连接成功以后使用其他方式引导用户完善资料」，因此欢迎页和资料补全入口必须可跳过、非阻断，且首次路径要顺畅（审核通常只用新 QQ 号走一次）。另注意未通过审核的 appid 仅允许开发者自己的 QQ 号测试登录，联调自测账号需与注册开发者一致。

**待确认**：`account_email()` 的报错文案现为「Memorial accounts cannot use email authentication.」，用于 QQ 占位账号语义不符，需泛化；是否新增字段区分占位邮箱与真实邮箱仍未定，与已有本站账号的合并方案另见「已注册用户再用 QQ 登录：避免占用 id」一节。审核团队内部的具体判定标准未公开，如驳回邮件提出额外要求，按邮件整改并回填本节。

### QQ 互联返回的身份信息（核实结论）

针对「QQ 互联是否返回 QQ 号」，依据 QQ 互联 WIKI 的[开发接入相关问题](https://wiki.connect.qq.com/%e5%bc%80%e5%8f%91%e8%81%94%e8%b0%83%e7%9b%b8%e5%85%b3%e9%97%ae%e9%a2%98/)第 3 问与 [get_user_info](https://wiki.connect.qq.com/get_user_info) 文档（2026-11-11 核对）：

**不返回 QQ 号。** 官方原文：「不能。用户登录成功后跳转回网站时，URL中传递的是openid而非QQ账号，openid是经过转换的字符串。此外，QQ账号涉及用户隐私，接入QQ登录的网站应该遵守开发者协议不允许以任何理由获取或用户QQ账号相关的信息。」OAuth2.0 实际链路是回调拿 `code`、换 `access_token`、再由 `oauth2.0/me` 取得 `openid`（可选 `unionid`）；`get_user_info` 返回 `nickname`、各级 `figureurl` / `figureurl_qq_*` 头像、`gender`、`gender_type`、`province`、`city`、`year`、`constellation` 及黄钻字段，**没有任何 QQ 号或 uin 字段**。新版 JS SDK 的 `getMe()` 同样返回 openid，登录回调拿到的仍是 `get_user_info` 数据。

`openid` 与 QQ 号一一对应但不可逆，官方描述为 32/36 位十六进制字符串（默认大写），且随 appid 变化；`access_token` 有效期 60 天，与某一 openid 对应。

**可以先用 openid、后面再申请 unionid**（2026-11-12 确认）。依据官方 [UNIONID介绍](https://wiki.connect.qq.com/unionid%E4%BB%8B%E7%BB%8D)：`GET https://graph.qq.com/oauth2.0/me?access_token=...&unionid=1` 返回 `client_id` / `openid` / `unionid`，`unionid` 参数可选，未申请权限时返回错误码 100048「companyid not set」，官方称已支持官网自助获取。QQ 开放平台小程序 FAQ 明确「unionID打通后，不会对openID造成任何影响」，且对已上线应用提供「openID + appID 转 unionID」的存量转换接口（2000/S，**仅限使用 2 个月**处理完存量数据），并提示「打通后请换用 unionID 作为识别用户标识」。因此先只按 openid 建号可行，后补时已有账号不会登录不上；但有四点要注意：① 一开始就要把 `appid` 与 `openid` 一起存，否则无法用存量转换接口；② 建议模型预留可空 `unionid` 字段（官方称至少 36 字节，**建议预留 64 字节**），避免后期加字段 + 迁移 + 回填；③ unionid 保证的是同一 QQ 互联开发者账号下跨应用统一，**换开发者主体仍会变**，不能当成跨主体的全局唯一键；④ 打通后需改用 unionid 作为识别标识，存在一次识别逻辑迁移，且本站只有一个网站应用时是否需要打通、申请条件（是否要求企业资质）需按官网自助指引确认。

**对本站的影响**：`AccountQQ` 里的手填数字 QQ 号与 QQ 登录身份是两套互不对应的标识，不能互相推导，也不要在登录流程里索取 QQ 号（既触及开发者协议，也违背「操作量最小化」）；现有私密关联继续独立运行。换 appid（重新申请应用、更换主体）会让全部已有 openid 改变、用户无法登录，因此 `QQConnectIdentity` 需与 appid 一起记录并预留迁移方案，不要只把 openid 当全局唯一键。官方要求展示的 QQ 昵称与头像只能取自 `get_user_info`，不能由 QQ 号拼头像地址；昵称/头像是否落库的决策见「用户引导与展示」条目。

### 已注册用户再用 QQ 登录：避免占用 id（方案，未实施）

问题：已有本站账号的人首次点 QQ 登录，一键开通会再建一个 `UserProfile` + `UserMS`，消耗一个 `BigAutoField` 自增 id，并产生重复账号。

**根因是无法自动识别**：QQ 互联只返回 `openid`（无 QQ 号、无邮箱，见「QQ 互联返回的身份信息」），首次出现的 openid 在本站没有任何对应记录，系统无法知道这个人已经注册过；`AccountQQ` 的手填数字 QQ 号也不能用来反推（不可逆，且开发者协议不允许在登录流程索取 QQ 号）。因此**要完全不建号，关联必须发生在 QQ 登录之前**。另外 `UserProfile.id` 是 `BigAutoField`，删除账号也不会回收自增 id（事务回滚、删号同样留空洞），所以「消除重复账号」与「不消耗 id 数字」是两件事：后者只有在从不 INSERT 时才能保证。

| 方案 | 做法 | id 消耗 | 风险 |
| --- | --- | --- | --- |
| A 预绑定（推荐） | 已登录用户在账号关联页授权绑定 QQ，openid 写入 `QQConnectIdentity(parent=已有用户)`；此后登录回调先按 openid 查询，命中就直接 `login(request, 已有用户)` | 无 | 绑定流程与登录回调要分开：前者要求登录态（参照 `github/api.py` 的 `current_session_user`），后者必须匿名可用；归属冲突时拒绝、不转移（参照 `save_verified_account_link`） |
| B 事后认领（兜底 A 未覆盖的情况） | 一键开通后在欢迎页/用户中心提供**可跳过**的「我已有账号」入口，用密码或邮箱验证码验证所有权，把 openid 改指已有账号并删除自动生成的账号 | 已消耗，不可回收 | 若新账号期间产生录像/成绩，自动合并风险高，建议有数据时拒绝并转人工；入口不得阻断首次登录，否则命中「QQ登录成功后无法完成页面授权」 |
| C 回调后提示（**已决策采用**） | 回调未命中 openid 时先展示说明页、不落库：讲清手填 QQ 号与 QQ 互联的区别、明确继续会创建第二个号、引导正常登录后关联 openid；出口为「仍用 QQ 注册」与「我已有账号」 | 只有选「仍用 QQ 注册」才消耗 | 审核人员首次会看到说明页；须保证「仍用 QQ 注册」无需填任何资料、一次点击即可完成，否则命中「QQ登录成功后无法完成页面授权」 |

推荐组合调整为 **A 预绑定 + C 文案引导 + 一键开通兜底**：A 在上线前让存量用户把 openid 绑到原账号，C 处理仍未命中 openid 的人并靠文案把双号风险讲清楚，用户坚持注册时才 INSERT。B 降级为「已经创建第二个号之后」的可跳过补救，有数据时转人工不自动合并。C 已由项目方决策采用，不再作为待确认项；审核风险按上表缓解。若真正介意的只是自增数字空洞，说明它是常态（删号、事务回滚同样产生），不值得为此改 `AUTO_INCREMENT`；真正要防的是重复账号导致的录像、成绩与排行分裂。

**共同约束**：验证已有账号所有权必须严格（密码或邮箱验证码；`userprofile/views.py` 的 `check_collision` 只做查重，不能当身份凭证）；openid 与本站账号保持一对一，已有绑定时拒绝转移到他人账号；登录回调不得要求登录态。是否允许 B 的自动合并仍需项目方决策。

**回调未命中时的引导流程（已决策）**：项目方确认无法用技术手段区分两套 QQ 身份，改由文案区分。OAuth 授权成功 → 回调取得 openid → 查 `QQConnectIdentity`：命中就直接 `login(request, 已有用户)`；未命中则展示说明页，**此时不落库、不创建 `UserProfile`**。说明页必须写明三件事：①「绑定 QQ 号」是手填数字 ID 的私密关联，仅用于展示，与 QQ 互联登录是两回事；②继续用 QQ 注册会创建**第二个账号**（新 id、空资料、与原号不互通，合号很麻烦）；③如果已有本站账号，请先用用户名密码正常登录，再到账号关联页（`/#/player/{id}/accountlink`，与 GitHub 授权回跳一致）点「绑定 QQ 登录」关联 openid。两个出口：「仍用 QQ 注册」→ 直接按「一键开通的邮箱与密码初始化」创建 `UserProfile`（新用户正常分配 id，这是预期行为）；「我已有账号」→ 关闭本次流程、打开登录弹窗，**不持久化 openid**，用户登录后重新发起一次已登录态授权完成绑定，避免跨会话保存 openid 与临时凭证。

**触发条件的准确含义与三个易错点**：一是「未命中 openid」不等于 OAuth 失败，用户取消、state 过期、令牌交换失败等应走错误分类，不进入说明页。二是系统**无法判断该用户是否已在某个账号里手填过 QQ 号**（openid 与 QQ 号无对应，见「QQ 互联返回的身份信息」），文案必须面向所有未命中的人通用表述，不能写成「检测到你已绑定 QQ 号」，是否已有账号由用户自己判断。三是若用户此前已选过「仍用 QQ 注册」，openid 已绑定到新号，再按引导去关联会命中归属冲突，应拒绝转移（参照 `save_verified_account_link`）并转人工，不要自动合并录像/成绩。

**审核缓解**：引导方向优先指向「我已有账号」，但说明页不得要求填写任何资料、不得设置必选表单，「仍用 QQ 注册」必须保持明显可见、一次点击即完成授权后开通；两个出口都不阻断。文案引导与官方「一键开通」「禁止要求单独密码」并不冲突，但提交审核前需实测审核人员走「仍用 QQ 注册」能一次完成，否则按驳回邮件整改并回填「审核视角」段。

**存量 `AccountQQ` 的认知陷阱**：现有手填数字 QQ 号关联在界面上就叫「腾讯QQ」（`front_end/src/i18n/locales/zh-cn.ts` 的 `platform.q`），`front_end/src/views/UserView/AccountLinks/linking/QQLink.vue` 的引导文案只提示「QQ号信息网站管理员可见。请注意隐私安全。」，`vitepress_doc/zh/guide/account-links.md` 里只有 Discord 写了「关联 Discord 不提供登录功能」，QQ 没写。已有 `AccountQQ` 的用户极可能认为绑定过 QQ 就能用 QQ 登录，结果一键开通进入一个空的新账号，而合号很麻烦。QQ 互联不返回 QQ 号（见「QQ 互联返回的身份信息」），本站无法把 openid 与手填号码自动对应，**也不能拿私密的 `AccountQQ` 做登录匹配或自动把关联转成登录身份**：腾讯只保证 openid 属于当前授权的 QQ，本站无法核对该 QQ 与手填号码是否一致（手填值由管理员审核，理论上可能被冒领）。因此只能靠用户主动做一次「绑定 QQ 登录」，并靠产品文案消除误解。

防混淆措施（上线前必须完成）：`QQLink.vue` 引导文案补「QQ 号关联仅用于展示，不能用于登录本站」；用户文档给 QQ 补上与 Discord 相同的「不提供登录功能」说明，并说明 QQ 登录需单独绑定（中英文各一份）；QQ 登录入口旁与首次登录欢迎页明确提示「已填写 QQ 号 ≠ 已开通 QQ 登录」，新开通的账号要显著标注「这是新账号」，避免用户以为进错了号。是否把手填平台显示名改成「QQ 号（仅展示）」、以及 QQ 登录上线后是否停止新的手填 QQ 号关联（存量保留），需项目方决策。

**上线节奏**：先上线「绑定 QQ 登录」（已登录态的 OAuth 关联，只写 `QQConnectIdentity`，不提供登录），给存量用户特别是已有 `AccountQQ` 的人一段预绑定窗口并做站内通知；窗口结束后再让首页/登录/注册页的 QQ 登录按钮可点击并接入授权入口。这样点按钮时 openid 大多已命中已有账号，不分配新 id。未预绑定的人进入上文「回调未命中时的引导流程」，文案优先引导其正常登录并关联 openid；仍选 QQ 注册才一键开通（**新用户正常分配 id，这是预期行为**）。已经创建第二个号的由方案 B 的可跳过认领入口兜底；有录像/成绩时不自动合并，转人工。提交审核前按「审核视角」段确认按钮可点击且授权流程跑通。

### 实施计划

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| 0 前置确认 | 备案与主体资质（已确认）、模块归属决策（已定，**归 `userprofile`**）、SDK 最终决策（不引入）；**页面入口骨架已落地（2026-11-12）**：三处入口统一为 `QQLoginEntry.vue`（官方 16×16 小图标 + 固定中文「QQ登录」 + 站点现代排版），菜单栏「登录」左边与登录/注册弹窗内同款、占位点击、`home` 的 `/login` / `/register` alias + 默认开弹窗、关闭回跳与导航高亮；剩余：创建 QQ 互联网站应用取得 appid / appkey 并登记回调地址 | 入口页面可被审核人员访问、按钮为占位不跳转、两个路由地址可访问；结论已落到文档。剩余验收为 appid / appkey 与回调地址登记 |
| 1 后端 OAuth | 在 `userprofile` app 新增 Ninja Router 与 `schema.py` / `client.py` / `cache.py` / `services.py`；自动生成并应用结构迁移；补齐 `secrets.json` 与 Nginx/uWSGI 配置 | 离线测试覆盖成功、取消、过期、重复回调、归属冲突、未配置、限流 |
| 2 登录与账号 | 会话签发、一键开通或绑定流程、首次登录引导、同等权限校验；不改动 `AccountQQ` 关联流程 | 后端回归与登录态等价性验证 |
| 3 前端入口 | 三处入口与 `/login`、`/register` 路由已提前到阶段 0 落地；剩余：把占位点击替换为真实授权地址、欢迎页、昵称头像展示、全站用户名处文案 | 组件测试覆盖共用入口组件与菜单/弹窗渲染、两个路由打开弹窗与关闭回跳；审核前确认菜单栏图标可点击且授权流程跑通 |
| 4 部署联调与审核 | 真实 QQ 授权、备案一致性、平台后台配置、Secrets 实际值只能部署后核对；提交上线审核并按驳回邮件整改 | 审核通过、状态为「已上线」 |
| 5 文档与回归 | 本节改写为现状，同步用户文档中英文版与 AccountLinks README，改写 `models.py` 注释 | 全站无过时表述 |

离线回归与模拟响应不等于真实 QQ 联调：授权页、备案一致性、回调地址登记与 Nginx/uWSGI 配置需部署后核对；Cypress E2E 测试由用户运行，组件测试可由助手运行。

### 待办清单（2026-11-12 整理，含当日结论）

按依赖顺序汇总，条目细节见上文对应章节；本节只作索引，结论变化时同步更新。状态标记：`[阻塞]`、`[待决]`、`[已决策待实施]`、`[待排期]`、`[已落地]`、`[已确认]`。

**[已确认]**（原阻塞项）

1. 域名与回调域名的 ICP 备案、备案主体与开发者主体一致、主体能否申请网站应用：项目方已确认（2026-11-12），不再是阻塞。
2. 原「是否推翻 `accountlink` 去中心化决策」：由模块归属决策化解——QQ 互联登录放 `userprofile`，`accountlink` 维持关联侧不变，无需推翻（「与现有约定的关系」）。

**[阻塞] 顺序依赖（第 3 条已解除，仅剩第 4 条）**

3. **[已落地] 页面入口骨架**：2026-11-12 完成三处统一入口（`QQLoginEntry.vue`，官方 16×16 小图标 + 固定中文「QQ登录」）、`home` 的 `/login` / `/register` alias + 默认开弹窗、登录态时序、关闭回跳（强制导航）与导航高亮，并同步组件测试与本节状态。项目方要求的「申请 appid 之前先把入口做出来」已满足，此项不再阻塞。
4. **[阻塞]** 创建 QQ 互联网站应用，取得 appid / appkey 并登记固定 HTTPS 回调地址（实施计划阶段 0）；入口已就绪，此项现为唯一顺序阻塞项。
5. 该项已决、不再阻塞：项目方 2026-11-12 **最终确定不引入官方 CDN JS SDK**，采用 server-side OAuth2.0 自建跳转（「官方 CDN JS SDK 调研」「待决问题」6）；`unionid` 已明确可后补，见第 11 条与「QQ 互联返回的身份信息」。

**[已落地]**

6. 官方标准标识核实与入库：7 规格清单，`Connect_logo_3.png` → `qq_login_120x24.png`、`Connect_logo_1.png` → `qq_login_16x16.png`；2026-11-12 联网下载并与官方 CDN 原图核对 SHA-256 一致（「标准标识素材」）。官方无圆形规格，非官方圆形图标不采用。
7. 三处入口落地：菜单栏「登录」项左边（未登录时可见）与登录/注册弹窗内，统一为 `QQLoginEntry.vue` 的 16×16 官方小图标 + 固定中文文字，原样尺寸、可键盘激活的可点击占位（「标准标识素材」）；文案不做英文界面。**剩余：阶段 1/2 后把占位点击替换为真实授权地址**，不编造 appid。
8. 官方规范、接口返回与审核视角的核实结论（「外部硬性要求」「QQ 互联返回的身份信息」「审核视角」）。
9. 模块归属决策：登录侧归 `userprofile`，与 `accountlink` 分开（「与现有约定的关系」）。

**[待决] 需项目方拍板（10–15）**

10. 身份模型细节：`QQConnectIdentity` 是否额外加字段区分占位/真实邮箱、`access_token` 不落库、appid 与 openid 一并记录及换 appid 的迁移方案（待决问题 3）。
11. 是否预留可空 `unionid` 字段（官方建议 64 字节）、本站只有一个网站应用时的申请条件（「QQ 互联返回的身份信息」）。
12. 是否允许方案 B 的自动合并；建议有录像/成绩时拒绝并转人工（「已注册用户再用 QQ 登录」）。
13. 是否把手填平台显示名改为「QQ 号（仅展示）」、QQ 登录上线后是否停止新的手填 QQ 号关联（「防混淆措施」）。
14. 昵称/头像是否落库、用户名生成规则（昵称 + 随机数需过 `verify_text`、≤30 字符、允许改名）、是否提供自愿绑定邮箱/设置密码的补全入口（「用户引导与展示」「一键开通的邮箱与密码初始化」）。
15. `account_email()` 的「Memorial accounts...」报错文案泛化（「待确认」）。

本规划文档归属已于 2026-11-12 完成迁移（迁到本文件，`accountlink/README.md` 保留交叉引用），不再是待决项，详见「与现有约定的关系」。

**[已决策待实施]**

16. 一键开通初始化：每账号唯一 `@accounts.invalid` 占位邮箱 + `set_unusable_password()` + `UserMS` + `is_active=True` + 同事务创建（「一键开通的邮箱与密码初始化」）。
17. 回调未命中 openid 的说明页：三要素文案、两个出口、不落库、不持久化 openid、归属冲突拒绝转人工、审核缓解（「回调未命中时的引导流程」）。
18. 防混淆文案与「先绑定后开放」节奏：`QQLink.vue`、用户文档中英文、入口旁/欢迎页提示、「这是新账号」标注；先上「绑定 QQ 登录」+ 预绑定窗口 + 站内通知，再开放按钮（「存量 `AccountQQ` 的认知陷阱」「上线节奏」）。

**[已落地] 与 [待排期]**

19. **[已落地]** `/login`、`/register` 路由 + 首页 + 默认开对应弹窗，含登录态时序、关闭回跳、导航高亮、表单互切（「登录页与注册页路由方案」）：2026-11-12 按第 3 条提前到阶段 0 完成。
20. **[待排期]** 各阶段代码与联调：阶段 1 后端 OAuth（在 `userprofile` app，Ninja、限流、state、secrets、Nginx/uWSGI、自动生成迁移）、阶段 2 会话与账号、阶段 3 剩余的欢迎页/昵称头像/真实授权地址、阶段 4 部署联调与审核、阶段 5 文档与测试回归（「实施计划」表）。

**提交审核前自查**：首页/注册页/登录页三处入口、按钮可点击且授权流程跑通、审核人员走「仍用 QQ 注册」能一次完成、同等权限、备案一致、未过审 appid 仅开发者 QQ 可测（「待决问题」9、「审核视角」「审核缓解」）。

