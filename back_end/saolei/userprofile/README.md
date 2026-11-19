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

- 隐藏实名资格现在由 `verified`（玩家认证）触发，不再有独立的 `can_hide_realname` 字段；`hide_realname` 记录用户选择，默认 False。管理员可通过通用 `PATCH /api/userprofile/admin/update/{id}` 修改 `verified` 来授权或撤销；撤销同时关闭隐藏。
- 账号绑定（含 MSGames）不再自动授予隐藏资格，也不改动 `verified` 或 `hide_realname`；资格来自玩家认证（由已认证玩家认证你，或管理员设置 `verified`）。绑定与第三方资料同步在提交后执行，远端请求失败或返回空白姓名不影响绑定成功，后续可刷新或重试验证补齐资料。
- 有效实名是非空、非纯空白且不为“匿名”的 `realname`。没有实名时不能开启隐藏；已有资格的用户可以在首次设置有效实名时同时选择隐藏。清除实名会关闭隐藏并保留认证（verified）。
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

## 玩家认证

完整规则与实施决策见 `PLAYER_VERIFICATION_PLAN.md`，本节只记录部署与维护要点。

- `UserProfile.verified` 是当前有效认证结果，不是「已实名」，也不代表管理身份。`UserVerifyEdge` 只保存当前存在的有向边（`from_user`、`to_user`、`created_at`），以 `UniqueConstraint(from_user, to_user)` 防止同向重复边，以检查约束禁止自认证边；允许多入边、多出边、反向边和环，没有申请表、根节点或历史表。
- 三类写入（普通主动认证、管理员设置 `verified`、站长完整图批次）都在 HTTP 请求内的单个数据库事务中同步完成，不使用 Django Tasks、任务查询或任务清理配置。普通认证只新增当前用户到目标的边并把目标设为已认证，不遍历下游；管理员只改指定节点；站长一次提交全部边与节点命令，后端不推导可达性或撤销范围。管理员修改 `verified` 不再走单独的按钮接口，而是复用通用的 `PATCH /api/userprofile/admin/update/{id}`（字段列表 `ADMIN_USERPROFILE_FIELDS` 已含 `verified`）；`/admin/verification/set-verified` 接口保留，仅在维护期返回 409，供程序化调用。
- 站长批次先开启独占维护会话（时长由站长指定，上限 1 小时）。会话状态与图写入串行锁放在 Redis 缓存 `userprofile/verification/cache.py`，TTL 到期自动恢复服务；提交成功或站长主动结束会立即释放。维护期间 `/verification/verify` 与 `/admin/verification/set-verified` 返回 409，读接口与站长批次提交仍可用。读路径只判断状态、不删除 key（避免删掉读取之后新建的会话），过期键由 TTL 清理；主动删除只在写入锁内进行。没有 `UserVerifyCoordinator` 表。
- 批次用批量 SQL：一次读出相关边、`bulk_create(ignore_conflicts=True)`、按主键分块删除、节点按目标值最多两次 `update()`；所有 IN 列表按 `GRAPH_BATCH_CHUNK_SIZE=500` 分块，SQL 次数不随命令数逐条增长。超时链为 uWSGI `harakiri:10` < nginx `location = /api/userprofile/admin/verification/graph-update` 的 `uwsgi_read_timeout 12s` < 前端 `$axios` 20s；网关必须晚于 worker 超时，否则会先返回 504 而后端静默提交。部署需 `nginx -t` 后 reload Nginx，仅重启 Django 不更新网关配置。
- API 集中在 `userprofile/verification/api.py`：`/api/userprofile/verification/status|verify` 为普通用户接口，`/api/userprofile/admin/verification/*` 为管理接口。管理员设置 `verified` 用 `staff_or_superuser_required`，站长读取、维护会话与批次用 `auth=django_auth_superuser`；管理员接口无限流，普通接口按项目约定限流。
- 部署顺序：先执行 `migrate` 应用 `0010`、`0011` 建表并移除旧树表，再发布新前端；现有用户 `verified` 缺省为 false，已有实名用户仍按实名条件准入。旧树方案未部署到生产，不需要数据转换；本地切换前停止旧 worker 并确认没有 READY/RUNNING 的旧认证任务。
- 录像上传已迁移到 Ninja 的 `POST /api/common/uploadvideo`，旧 Django view 和 `/common/uploadvideo/` 路由已移除；nginx 的限流 location 与排名维护锁路径需同步部署。上传、`create_weekly_participant` 和 `create_gsc_participant` 统一使用 `userprofile.utils.has_identity_access`，错误为 `userprofile/identity_access_required`。登录、自动登录和本人资料返回实名与 `verified`，前端 `UserProfile.canSubmitReplays` 统一根据有效用户 ID、实名（含隐藏姓名）或认证计算准入，不保存额外的准入字段；认证状态刷新原地更新 `verified` 并校验会话版本。公开资料返回 `verified`，不返回认证来源。

## QQ 登录

QQ 互联登录在 `userprofile/qqconnect/` 实现，独立于 `accountlink.AccountQQ` 的手填数字 QQ 号，不提供自动匹配或账号合并。三处原有「QQ登录」入口使用官方 16×16 原图，已接入后端授权地址；不引入腾讯 CDN JS SDK，也不重绘登录标识。界面和使用说明覆盖简体中文、英文、西班牙语，入口品牌文字仍固定为「QQ登录」。

### 登录、绑定与恢复

- 已有本站账号：先正常登录，在本人账号关联页选择 QQ，点击「绑定 QQ 登录」。授权后写入该账号的 `QQConnectIdentity`，不创建用户；已绑定时可重新授权刷新资料。同一身份不能转移到其他用户，每个用户仅有一个 QQ 登录身份。
- QQ 登录：已有身份时签发普通 Django 会话；停用和纪念账号均拒绝。首次遇到未绑定身份先回到 `/#/qq-login` 说明页，不写数据库。选择「我已有账号」会清除临时身份并打开普通登录；选择「仍用 QQ 注册」才原子创建 `UserMS`、`UserProfile` 与 QQ 身份并登录，不要求密码、邮箱或其他注册资料。
- 新账号启用正常权限与默认额度，不自动获得玩家认证或真实姓名。系统生成唯一的 `qq_` 用户名、唯一的 `@accounts.invalid` 邮箱，并使用不可用密码。欢迎页明确标注新用户 ID 与双号风险，不合并录像或成绩。
- 管理区可自愿把系统生成的用户名设置一次（沿用模型校验、唯一约束和内容审核），或通过现有图形／邮箱验证码组件绑定真实找回邮箱。之后使用普通「找回密码」流程设置本站密码。邮箱和用户名均不阻断首次开通。
- 解绑前必须已有可用本站密码或真实找回邮箱，防止丢失唯一登录方式。解绑不撤销腾讯侧应用授权；换绑须本人重新授权，冲突转人工处理。

QQ 昵称和头像仅保存用于本人欢迎页、QQ 登录管理区，不写入公共资料 Schema，不替换本站姓名和头像。只请求 `get_user_info`，不索取 QQ 号、好友、邮箱等数据；token 换取身份后即丢弃，不落库或回传。资料接口失败不影响已验证身份的登录／绑定，下次授权补齐。头像只接受腾讯 `qlogo.cn` 子域并升级到 HTTPS。

### 配置与腾讯审核

腾讯要求先完成链路再申请凭据。本轮已实现可测试的完整链路；没有真实应用凭据时，授权开始接口返回 `qq_login/not_configured`（503），页面明确说明并保留普通登录／注册，不伪造 appid 或授权成功。真实腾讯联调仍需取得凭据并部署后完成。

后端 `secrets.json` 只需新增以下两项，使用实际申请值；不得提交密钥文件：

```json
{
  "qq_oauth_client_id": "申请得到的 App ID",
  "qq_oauth_client_secret": "申请得到的 App Key / App Secret"
}
```

固定登记的回调地址为 **`https://openms.top/api/userprofile/qq/callback`**。代码中的默认值不是 secret。部署环境可用 `QQ_OAUTH_REDIRECT_URI` 覆盖用于测试，但生产必须 HTTPS、固定 callback 路径且与腾讯登记值一致；`QQ_OAUTH_FRONTEND_URL` 指定可信 SPA 地址，不接受用户提供 return URL。`QQ_OAUTH_LOGIN_ENABLED=false` 可先仅开放已登录用户绑定，默认 true 提供完整登录／注册链路。

部署顺序：自动生成并检查迁移 → `python manage.py migrate` → 重启后端并发布配套前端 → `nginx -t` 后 reload。本轮 Django 自动生成 `userprofile/migrations/0013_qqconnectidentity.py`，仅新增身份表；仓库忽略迁移文件，提交时须显式纳入该生成文件。后续不更换 appid；身份以 `(appid, openid)` 唯一，换 appid 不是透明升级。预留可空 unionid，但未申请权限时不主动请求或用它跨应用合并。

QQ 回调沿用 uWSGI 10 秒普通请求计时，Nginx 单独放宽至 12 秒。token、OpenID、资料读取各有 1 秒连接／1.5 秒读取超时，不自动重试。Nginx 与 uWSGI 均关闭该回调 access log；Authlib、urllib3 日志限制为 WARNING，避免 GET 查询参数中的 appkey/token 被 DEBUG 记录。业务日志只记录用户 ID、错误分类、异常类型，不记录 code、state、openid、原始响应或令牌。API 参数与响应以 Ninja 自动文档为准。

### 临时状态与并发

授权 state 随机生成、绑定当前会话指纹并只使用一次。回调提交前复核实际服务端会话和用户状态；退出、换号、授权覆盖、重复回调、删除或过期均拒绝。绑定与解绑锁定同一用户行，删除身份时同步撤销在途绑定授权，回滚可能要求重新授权，不能让已解绑身份被回调复活。

未绑定身份只在 Redis 保存最多 600 秒用于确认注册，不进入浏览器 URL 或永久数据库；选择已有账号、取消、再次开始或超时即失效。新账号确认凭证只使用一次，冲突时数据库回滚，不留下孤立 UserMS。缓存键及信号见[缓存说明](../../../vitepress_doc/zh/guide/development/cache.md#qq-登录临时状态)与[信号说明](../../../vitepress_doc/zh/guide/development/signals.md)。

### 验证与尚待部署确认

```sh
python -m flake8 userprofile/qqconnect userprofile/models.py userprofile/signals.py
python manage.py test userprofile.qqconnect.tests userprofile.test_registration userprofile.test_deletion --keepdb --noinput
```

前端执行 `npm run vitest -- run src/services/qqLoginService.test.ts src/services/loginSession.test.ts`。Cypress 由用户运行：

```sh
npx.cmd cypress run --component --browser chrome --headless --spec "src/components/Login/QQLoginEntry.cy.ts,src/components/Login/QQLoginManager.cy.ts,src/views/QQLoginView/App.cy.ts,src/components/Login/App.cy.ts"
```

离线回归使用测试应用设置和受控 HTTP 响应，不代表已完成腾讯真实联调或通过审核。凭据到手后人工确认：首页、登录页 `/#/login`、注册页 `/#/register` 的入口均可跳转；扫码／授权与固定回调成功；取消及过期可重试；绑定用户能登录原号；未绑定用户可一次确认开通并看到新账号提示；普通权限相同；本人资料仅本人可见；生产 Cookie、备案主体与应用回调登记正确。

协议依据：[授权码换取令牌](https://wiki.connect.qq.com/使用authorization_code获取access_token/)、[取得 OpenID](https://wiki.connect.qq.com/获取用户openid_oauth2-0/)、[get_user_info](https://wiki.connect.qq.com/get_user_info/)。
