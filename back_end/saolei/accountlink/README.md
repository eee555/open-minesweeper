# Account Link

## Discord 与 QQ

Discord 和 QQ 共用填写数字 ID、提交申请、管理员审核及管理员解绑流程，均为仅本人和管理员可见的私密关联。Discord ID 按字符串保存，前后端不转换为 JavaScript 数字。两者只保存 ID 与本站账号归属；Discord 不再使用官方接口或提供第三方登录。部署及测试说明见 [Discord 人工关联](discord/README.md)。

## 绑定与资料同步

管理员验证先提交绑定；MSGames 的隐藏资格与绑定同事务提交。提交后的第三方资料拉取或同步失败不影响绑定成功，验证接口保持成功响应并记录同步失败日志。用户可稍后刷新资料，管理员重试空名 MSGames 绑定时也会补拉资料，不重复发放隐藏资格。

`POST /api/accountlink/unverify/` 以表单接收 `id`、`platform`、`identifier`。管理员解绑时同事务删除关联账号和申请队列行，待验证申请也可取消；用户随后可以用正确 ID 重新申请。已有隐藏资格与选择保留，Mineracer 仍禁止人工解绑。旧 `/accountlink/unverify/` 已移除。

## 扫雷网同步

首批迁移已由站长执行完成，使用 `saolei-api==0.4.0` 的官方 Release wheel，版本与 SHA256 固定在依赖文件中。完整业务约定见[扫雷网官方 API 接入方案](SAOLEI_API_IMPORT_PLAN.md)。

现在开放 `/api/accountlink/saolei/` 下的新 Ninja API 和前端账号卡片。权限统一在 API 层处理：只有已验证关联账号本人可以刷新资料、修改自动同步设置、同步目录或导入录像；本地目录和摘要可公开读取。每次手动请求只同步一页目录或导入一条录像，由前端顺序控制整个流程；关闭窗口或停止后保留已完成的进度。旧爬取接口和旧 Task 仍关闭，不恢复网页爬虫。

`AccountSaolei.auto_sync` 默认 `True`，迁移后已有账号及新绑定账号均默认启用。自动同步分两阶段：统一 APScheduler 每天 03:30（调度器时区，当前 UTC）直接执行资料和增量目录同步，按每批最多 50 个录像 ID 调用 `video_info`，将详情及 URL 落库，不创建后台任务或下载文件；每小时整点入队一条低优先级 Django Task，只按已存 URL 逐个导入，整轮最多尝试 100 条，失败也计入上限，不再逐条请求详情。缺少 URL 的来源留待下一次目录阶段补取。小时任务仍 READY／RUNNING 时不重复入队。两个阶段都尊重开关和有效绑定；关闭后仍可手动同步，也不影响站长命令。

网页、每日目录调度、每小时导入任务和管理命令通过 `ThrottledTransport` 共用 Redis 节流键，数据请求至少间隔 2.1 秒，文件请求至少间隔 0.4 秒。只协调站内共享配额，HTTP、认证、响应校验和下载继续复用依赖。竞争等待最多 6 秒，超时或上游限流返回 429 并停止当前手动流程，不无限重试。

自动生成的结构迁移删除旧 `VideoSaolei` 来源模型及全部数据，创建独立的 `SaoleiApiVideo` 来源表；不按相同数字对应新旧来源 ID。账号绑定、已导入本站的 `VideoModel`、扩展记录和文件保留。重新取得的原文件按本站哈希查重，同主复用已有录像，异主冲突不关联或修改既有录像。`SaoleiApiVideo.import_video` 使用可空的 `OneToOneField`，同一条本站录像最多关联一条扫雷网来源记录。仓库不跟踪迁移文件，部署时沿用目标服务器的历史迁移自动生成并核对，不依赖开发机的迁移编号。

新旧扫雷网用户 ID 保持一致，沿用现有绑定。新来源录像的 `status` 仅展示，不影响是否导入；上游 `hash` 不采集或保存。取得文件后继续复用本站原有录像解析及查重业务。

`SaoleiApiVideo.file_url` 保存客户端规范化后的录像文件后缀，例如 `2023/04/16/sample.evf`；获取详情时更新并落库，导入从该字段下载文件。目录列表没有文件地址，刷新目录不会清空已保存的后缀；详情明确返回无文件时清空该字段并保留来源供重试。原录像网页链接的 `url` getter 已移除。

账号资料只接入 `id`、`name` 和 `banned`，不使用任何账号成绩数据（`scores`、`scores_nf`）或 `signatures`，不进行账号成绩精度升级。`AccountSaolei` 删除旧成绩、人气、三级录像数量和 `video_import_task` 字段，保留基础资料、同步游标及时间，并新增本地 `auto_sync` 设置。录像自身的成绩解析和文件内标识校验继续沿用现有业务。

账号新增本地进度字段 `video_sync_cursor`（默认 0），保存上次成功落库的目录页对应的 `next_cursor`，供增量更新和中断续跑使用。后续请求返回 ID 大于游标的录像，`next_cursor` 可等于本页最后一条 ID，不自行加 1；本轮超过 `stats().max_video_id` 的记录留待下次处理，游标最多保存到该上界。目录记录与游标同事务提交，失败不推进；录像文件导入失败单独重试，不回退目录进度。`video_update_time` 仅在目录扫描完成后更新，不代表所有文件均已导入。

新来源录像保存 `software` 原始软件名称，目录接口和录像管理列表使用此字段；本站录像的软件类型仍由实际文件解析确定。已完成[官方 API 软件名称抽样](SAOLEI_SOFTWARE_SURVEY.md)，包含 `Vienna` 和 `元扫雷3.3.4`（上游现已改名为 `元扫雷`）等实际取值。

新接入方案按软件白名单导入，仅接受 `software` 原字符串精确匹配的 `Clone`、`Vienna`、`Arbiter`、`元扫雷`。`Saolei.wang` 和其他白名单外取值保留来源目录记录，单条、批量、全站重建及重试均跳过导入，不下载文件；跳过与失败分别统计，`status` 仍不作为导入筛选条件。

旧站资料页、录像列表和下载地址的爬取逻辑已删除。账号关联申请、人工审核、绑定关系、已保存资料和历史录像继续保留；审核扫雷网关联时不再自动刷新资料。

- 资料刷新 `/accountlink/update/` 的 `platform=c` 返回 HTTP 410，错误类别为 `saolei/crawling_disabled`；其他平台沿用原流程。
- 触发爬取的 `/accountlink/saolei_import_video/`、`/accountlink/saolei_import_videos/` 已移除，返回 HTTP 404。
- 历史列表 `/accountlink/saolei/videolist/get/` 和统计 `/accountlink/saolei/videoimport/stat/` 已移除，对应视图及旧模型引用一并清理。
- 三个旧 Django Task 路径保留为失败入口，处理升级前已入队的任务，并禁止管理员重启这些爬取任务。部署时需要重启 Web 和任务 worker，使它们加载新代码；不清除历史任务或业务数据。
- 前端使用新 Ninja 目录、摘要和同步接口，不再查询旧任务状态或旧来源字段。

管理命令在同一进程共用客户端，串行完成资料、目录和文件导入，不创建 Django Task。部署后在服务器配置 `secrets.json` 中的 `saolei_api_key`，先核对原文件哈希并运行结构迁移，再小范围联调：

```bash
python manage.py backfill_video_hashes
python manage.py makemigrations accountlink --noinput
python manage.py migrate
python manage.py sync_saolei_api --account-id 101 --full
python manage.py sync_saolei_api --all-linked --full
python manage.py sync_saolei_api --all-linked --phase metadata
python manage.py sync_saolei_api --all-linked --phase videos --limit 100
```

`--account-id` 是扫雷网账号 ID，可重复指定；只处理已验证且与 `AccountSaolei.parent` 一致的绑定，不自动修复绑定。`--phase` 默认为 `all`，先批量更新所有选中账号的目录和详情，再逐个下载；`metadata` 只运行第一阶段，`videos` 只按本地 URL 导入，不请求 `stats`、列表或详情。`--limit` 限制整轮导入尝试数，默认不限；`--full` 仅用于 `all` 或 `metadata`。只有涉及文件导入的阶段要求存量录像哈希完整。旧任务指针随结构迁移删除，不另设清理接口。

中断续跑或以后增量更新使用 `python manage.py sync_saolei_api --all-linked`，去掉 `--full`。每次运行还会扫描本地白名单内、尚未关联本站录像且未被本站文件校验拒收的记录，补导已入库但未完成的录像。`--full` 从 0 重新对账目录，不清空新表，也不回退已保存的成功游标。

资料或单条录像失败不撤销绑定和既有成功结果；管理命令失败会汇总并返回非零退出码。鉴权失败或限流立即停止，不自动重试。来源缺少详情或文件保留重试机会；执行期间请勿并行运行多个同步命令。手动流程遇到明确文件拒收或冲突继续下一条，网络故障、鉴权或限流则停止后续请求；重新同步可补导未完成项。

本站文件校验直接拒收（`file/type`、`file/incomplete`、`file/level`、`file/review`）后，导入事务回滚，再将来源的 `import_rejected` 置为 `True`。首次拒收仍计为失败并记录原因；之后的增量同步及 `--full` 都在下载前跳过，计入跳过数量，目录刷新不清除此标记。站长确认需要重试时，通过 Django shell 将该来源的 `import_rejected` 清为 `False` 后重跑即可，不提供额外接口。网络、上游、配置、绑定或写入故障不设置此标记。冻结、待审核及标识不匹配等能正常保存为本站录像的结果仍记为导入成功。

扫雷网导入使用 `MSVideoParser(file, isolate=True)`，每份文件在独立 Python 子进程中执行 `ms_toollib` 的解析、分析和审核，超时为 60 秒；子进程不启动 Django 应用或访问数据库。原生中止（如 SIGABRT）、异常退出或超时归为 `rust/panic`，当前文件的导入事务回滚，自动任务及管理命令继续处理后续录像；本轮仍汇总为失败。这类故障不设置 `import_rejected`，后续同步会重试。解析前记录来源 ID、账号 ID 和文件相对 URL，进程失败时记录文件名、退出码和诊断尾部，供站长提取样本定位上游问题。其他上传入口保持原有解析路径。

## 95经典扫雷接入

95经典扫雷是微信小游戏，合规限制使它不能引导玩家跳转外链，因此采用「本站发起、小游戏内确认、对方回调」的绑定模型，与 Mineracer 的轮询模型和手填 ID 的人工审核模型都不同。

### 流程

1. 已登录用户提交自己在小游戏荣誉页看到的 8 位 UID。
2. 本站带 `api_key` 请求对方的 `/v1/ext/bind/request`，`account` 传本站用户名，`callback` 传本站回调地址；请求体不带 `app`，应用名由 `api_key` 在对方开户时绑定的名称决定，玩家在「我的荣誉」看到的即为「应用名 | 本站用户名」。
3. 玩家在小游戏内确认或拒绝。
4. 对方回调本站，`result` 为 `allow` / `deny`，玩家之后主动解绑时为 `revoke`。
5. 玩家在小游戏「我的荣誉 → 外部绑定账户 → 录像同步」里勾选录像后，对方把 EVF 文件一次性 POST 到同一回调地址；本站验签、校验 SHA-256 后同步导入。

只有 `allow` 回调会建立绑定，`deny` 只记录结果；`revoke` 回调删除本站绑定和申请队列行。受理本身不代表绑定成功，未确认前不写 `AccountLinkQueue`。

### 数据模型

- `Platform.CLASSIC` 使用平台码 `x`。
- `AccountClassicMinesweeper.id` 保存 8 位 UID，`parent` 使用 `related_name='account_classic'`。
- `ClassicBindRequest` 按 `uid` 与 `request_id` 各唯一一行，保存申请状态、过期时间和错误分类；同一 UID 重新申请会覆盖该行，`request_id` 是回调幂等键。
- `ClassicReplay.difficulty` 保存 `b` / `i` / `e`（初 / 中 / 高），由请求头 `X-Ext-Difficulty` 的 `easy` / `hard` / `expert` 映射。
- `ClassicReplay` 按 `key` 唯一保存一条推送记录（对方保证 key 全局唯一），`sync_id` 也唯一；同一 key 换 `syncId` 覆盖同一行，key 出现在不同 uid 时返回 `key_conflict`。`import_video` 为空表示尚未导入，解析失败时保留记录与 `error_category`，玩家再次勾选即可重试。

### 接口

- `POST /api/accountlink/classic/start/`：登录用户提交 `uid`，限流 `6/h`。已有未过期申请时直接复用，不重复请求对方；UID 已被他人绑定或他人有未处理申请时返回 `identifier_conflict` / `pending`。
- `GET /api/accountlink/classic/status/`：返回当前用户最近一次申请，前端据此轮询；`status` 为 `none` 表示没有申请。
- `POST /api/accountlink/classic/callback`：接收对方回调，不登录，仅靠签名鉴权。同一地址接收两类报文，先按 `Content-Type` 分流：
  - `application/json`：绑定事件，3 秒内返回 2xx；
  - `application/octet-stream`（带 `X-Ext-Event: replay`）：玩家授权推送的 EVF 文件，最多 8MB，10 秒内返回 2xx。

旧接口一律拒绝：`create_account_link`、staff `verify_link`、staff `unverify_link`、`delete_link`、`update_link`，以及 `delete_account` 的内部调用，避免绕过回调伪造绑定或绕过对方解除绑定。对方已下线的 `GET /v1/ext/replay/list` / `download` 本站从未接入，无需清理。

### 录像推送

- 请求头 `X-Ext-Sync-Id`、`X-Ext-Uid`、`X-Ext-Key`、`X-Ext-Season`、`X-Ext-Platform`、`X-Ext-Difficulty`、`X-Ext-Played-At`、`X-Ext-Time-Ms`、`X-Ext-Bv3`、`X-Ext-Nf`、`X-Ext-Sha256`、`X-Ext-Format` 都会校验格式与范围；`X-Ext-Key` 的赛季必须与 `X-Ext-Season` 一致；`X-Ext-Difficulty` 的 `easy` / `hard` / `expert` 映射为 `b` / `i` / `e`。`X-Ext-Bv3s` 忽略，不校验也不入库。
- 签名与绑定回调相同：`HMAC_SHA256(app_secret, timestamp + "." + 原始请求体)`，时间戳窗口 300 秒。签名通过后还要用 `X-Ext-Sha256` 校验文件完整，失败返回 400，让对方重试。
- 文件内容才是成绩来源：导入复用本站 `MSVideoParser` 与录像查重，难度、用时、3BV 等都以 EVF 解析结果为准，请求头只用于归属、审计与幂等。新建的 `VideoModel.software` 标记为 `x`（95 经典扫雷），文件仍按 EVF 解析、下载和播放；`state` 统一置为 `State.PLAIN`，等待人工审核，不参与机审排行与勋章。
- 只有当前仍绑定本站的 UID 才导入；若绑定在排队期间被解除，记录 `unbound` 并返回 2xx，避免对方无意义重试。
- `X-Ext-Platform=mobile` 的推送直接返回 2xx 并跳过：不入库、不导入，只记录 info 日志；目前只处理 `pc`。
- 同一 `sync_id` 重试直接返回；同一 `key` 换了 `syncId` 也只保留一行。key 出现在其他 uid 时返回 409 `key_conflict`，不覆盖归属。命中本站已有录像（同哈希）时关联已有录像，不重复入库；同哈希属于其他玩家时返回 409，不修改既有录像。
- `revoke` 只删除绑定和申请队列，不删除已经推送并导入的录像：这些录像属于玩家本人，删除会同时影响成绩与排行；解绑后对方停止推送新录像。

### 签名与错误分类

回调必须携带 `X-Ext-Timestamp` 与 `X-Ext-Signature`，签名内容为 `HMAC_SHA256(app_secret, timestamp + "." + 原始请求体)`，使用原始字节、常量时间比较，时间戳窗口 300 秒。校验通过后再用 `requestId` 反查申请，并核对 `uid`、`account` 与申请一致，不直接信任请求体。

远端错误码映射：`40001 → bad_request`、`40002 → bad_callback`、`40101 → unauthorized`、`40301 → app_mismatch`、`40401 → uid_not_found`、`40901 → already_bound`、`40902 → denied_recently`、`40903 → revoked_recently`、`42901 → rate_limited`；其余响应与网络故障分别映射为 `response`、`requestexception`、`timeout`。

录像推送的本地错误分类：`invalid_signature`（401）、`bad_checksum` / `bad_request` / `sync_id_conflict`（400）、`payload_too_large`（413）、`key_conflict`（409）、`import`（500）；文件解析拒收沿用 `file/type`、`file/incomplete`、`file/level`、`file/review`，同哈希归属他人为 `file/collision`（409）。

### 一致性与重试

- 整个绑定回调在一个事务内完成：先按 `requestId` 加锁命中原申请行，再核对 `uid` / `account`，然后才分支处理。同一 UID 的新申请会覆盖旧行，此时迟到的旧回调查不到 `requestId`，返回 404，不会绑定到新申请人。
- `allow` 复用 `save_verified_account_link`，在事务内完成绑定，重复投递直接返回成功。
- 发起绑定的写库是幂等的：远端对同一 `(uid, app, account)` 会返回同一个 `requestId`，此时保留已有的 `allow` / `deny` / `revoke`，不退回 `pending`，也不清空 `handled_at`；覆盖前还会重新检查该用户是否已完成绑定。
- 本地冲突重试无法自愈，记 `conflict` 并写 ERROR 日志，仍返回 2xx 停止对方重试，留待人工处理。
- 状态查询只把「仍是 pending 且已过期」的记录用条件 UPDATE 收敛为 `expired`，不会覆盖并发到达的 `allow`。
- 绑定回调只做数据库写入，不触发资料同步或录像导入，满足对方 3 秒响应的要求。
- 录像先落 `ClassicReplay` 再导入：解析失败保留记录并返回非 2xx，对方按 `立即` → `+5 秒` → `+30 秒` → `+5 分钟` 重试 4 次；导入与排行刷新在同一把排行读锁内完成，排行重建占用写锁时立即返回 503，由对方重试。玩家侧显示失败时可重新勾选。
- 录像导入按 `uid` 重新校验绑定，并复用 `revoke` 的加锁顺序（先锁 `UserProfile` 再删绑定），避免与解绑回调互相等待。
- 发起绑定会同步等待对方受理。`requests` 的 `timeout` 只是单次读空闲上限，慢速滴流响应会让整次调用远超预算，因此客户端改为 `stream=True` 逐字节读取并按 `CLASSIC_TIMEOUT` 检查整体截止时间（连接 2 秒、总计 5 秒）；`default.conf` 为该路径预留 8 秒网关预算，三者依次递增，浏览器才能拿到后端 JSON 错误而不是 504。
- 对方没有绑定状态查询接口，回调 4 次重试全部失败即丢失事件，只能按 `requestId` 人工对账；`ClassicBindRequest` 因此不设自动清理。

### 配置

`settings.py` 提供 `CLASSIC_BIND_URL`、`CLASSIC_BIND_CALLBACK_URL`、`CLASSIC_BIND_EXPIRES_IN`（60~604800，默认 86400）、`CLASSIC_BIND_TIMEOUT` 与 `CLASSIC_CALLBACK_TOLERANCE_SECONDS`。凭证不入代码、不入构建产物：

- `secrets.json` 的 `classic_bind_api_key`：发起绑定用，运行期读取。
- `secrets.json` 的 `classic_callback_app_secret`：绑定回调与录像推送验签用，运行期读取。

回调地址必须是对方报备白名单内的 https 公网域名，并按其要求公开可达。`default.conf` 为 `/api/accountlink/classic/callback` 单独设置 `client_max_body_size 8m` 与 `uwsgi_read_timeout 12s`：前者容纳 EVF 文件，后者高于对方 10 秒超时；导入本身必须在该预算内完成，否则由对方重试。

部署顺序：先在 `secrets.json` 写入两项凭证，并把回调地址报备给对方，再生成并应用结构迁移（新增 `ClassicReplay`），最后重启 Web 进程让新路由生效：

```bash
python manage.py makemigrations accountlink --noinput
python manage.py migrate
```

回调用例需要真实签名，联调时可先在对方测试环境用一个小号 UID 走完整流程，再观察 `logs/accountlink.log` 中的「绑定申请已提交 / 绑定完成 / 玩家解除绑定 / 录像已导入」记录。`conflict` 表示回调时本地已存在冲突（该 UID 或该用户已绑定其他账号），需要人工核对并处理冲突的绑定关系，用户重新提交即可覆盖旧申请。

## Mineracer 接入现状

Mineracer 提供的账号关联方式不是现有的“用户手填平台 ID，管理员人工验证”流程，而是更接近 OAuth 2.0 Device Authorization Grant 的确认模型。

参考标准模型：[OAuth 2.0 Device Authorization Grant](https://www.rfc-editor.org/rfc/rfc8628.html)。

### 已确认协议

关联流程：

1. OpenMS 服务端使用 Mineracer 提供的 partner key 请求一次性 `deviceCode`。
2. Mineracer 返回一个 10 分钟有效的账号关联链接。
3. OpenMS 前端把该链接交给当前登录用户。
4. 用户在 Mineracer 站点打开链接并点击确认关联。
5. OpenMS 服务端使用 `deviceCode` 轮询 Mineracer，直到 Mineracer 确认并返回该用户的 `userId`。
6. OpenMS 使用返回的 `userId` 完成本地账号绑定。

限制和约定：

- 一个 Mineracer 账号不允许绑定多个 OpenMS 账号，双方均进行检查并拒绝。
- 用户取消或拒绝时没有独立错误码；玩家不确认时会让 10 分钟有效期自然过期。
- Mineracer 不支持确认后 redirect 回 OpenMS 账号关联页。
- Mineracer 不提供测试环境或测试账号，需要使用生产接口联调。
- Mineracer 当前不支持解绑，因此 OpenMS 不提供 Mineracer 解绑能力。

### Mineracer 接口

Start 请求：

```http
POST https://mineracer.com/api/partner/link/start
Authorization: Bearer MINERACER_ACCOUNT_LINK_PARTNER_KEY
```

start 请求不需要 request body。成功响应：

```json
{
  "deviceCode": "PRIVATE_REQUEST_CODE",
  "userCode": "ABCD-EFGH",
  "verificationUri": "https://mineracer.com/link",
  "verificationUriComplete": "https://mineracer.com/link?code=ABCD-EFGH",
  "intervalMs": 2500,
  "expiresAt": 1780000000000
}
```

`deviceCode` 只保存在 OpenMS 服务端；前端使用 `verificationUriComplete`，不需要单独展示 `userCode`。

Poll 请求：

```http
POST https://mineracer.com/api/partner/link/poll
Authorization: Bearer MINERACER_ACCOUNT_LINK_PARTNER_KEY
Content-Type: application/json
```

请求体：

```json
{
  "deviceCode": "PRIVATE_REQUEST_CODE"
}
```

已知 poll 响应：

```text
202 - {status: "pending", intervalMs}  - not yet approved
200 - {status: "linked", userId} - approved
400 - {error: "invalid-device-code"} - missing or incorrect deviceCode
404 - {error: "invalid-device-code"} - same error
404 - {error: "account-not-found"} - edge case, account row missing (rare)
409 - {error: "link-superseded"} - newer overlapping flow created (rare)
410 - {error: "code-expired"} - past the 10-minute TTL
```

OpenMS 使用 `intervalMs` 控制本地 `next_poll_at`，避免前端每次 status 请求都触发第三方 poll。

第三方响应只按上述已确认字段解析；不兼容历史猜测字段名或大小写变体，例如 `device_code`、`userid`、`interval_ms`、`retry_after_ms`、`expires_in`、`error_category`。

### 后端实现

平台和账号模型：

- `Platform.MINERACER` 使用平台码 `m`。
- `AccountMineracer.id` 保存 Mineracer 返回的 `userId`，最大长度为 64。
- `AccountMineracer.parent` 使用 `related_name='account_mineracer'` 指向 `UserProfile`。
- `AccountMineracer.update_time` 记录本地绑定更新时间。
- `AccountMineracer` 已加入 `PLATFORM_CONFIG` 和 `get_account_links` 输出。
- 迁移脚本为 `accountlink/migrations/0009_alter_accountlinkqueue_platform_accountmineracer.py`。

Redis 临时会话：

- Mineracer 关联会话保存到 `caches['default']`，不使用 Django session 的 `saolei_website` cache alias。
- `accountlink:mineracer:session:{session_id}` 保存完整临时会话，TTL 为 Mineracer `expiresAt` 加少量 grace time。
- `accountlink:mineracer:user:{user_id}:pending` 保存当前用户 pending `session_id`，TTL 到 `expiresAt`。
- `accountlink:mineracer:user:{user_id}:start_lock` 避免并发创建多个 Mineracer 链接。
- `accountlink:mineracer:session:{session_id}:poll_lock` 避免多个 OpenMS 进程同时用同一个 `deviceCode` poll。

Redis session 内容：

- `user_id`：OpenMS 当前登录用户 ID。
- `device_code`：Mineracer 返回的 `deviceCode`，只在服务端保存。当前长度 43。
- `user_code`：Mineracer 返回的 `userCode`。长度 9，格式为 `XXXX-XXXX`。
- `verification_uri`：当前为 `https://mineracer.com/link`，仍按 Mineracer 返回值保存以兼容未来变化。
- `verification_uri_complete`：提供给用户打开的完整确认链接，当前为 `verification_uri + '?code={user_code}'`，仍按 Mineracer 返回值保存以兼容未来变化。
- `expires_at`
- `status`：`pending`、`confirmed`、`expired`、`failed`
- `remote_userid`
- `last_polled_at`
- `next_poll_at`
- `error_category`

API：

- `POST /api/accountlink/mineracer/start/`
  - 登录用户调用，限流。
  - 如果当前用户已经绑定 Mineracer，返回 `already_linked`。
  - 如果当前用户已有 pending 会话，复用同一个会话。
  - 返回 `session_id`、`status`、`verification_uri_complete`、`expires_at`、`next_poll_at`、`remote_userid`、`error_category`。

- `GET /api/accountlink/mineracer/status/{session_id}`
  - 登录用户调用，限流。
  - 只允许读取自己的会话。
  - 未到 `next_poll_at` 时直接返回本地状态。
  - 到达轮询时间后请求 Mineracer poll 接口。
  - Mineracer 返回 `userId` 后，在数据库事务中完成绑定。

绑定成功时，`AccountMineracer.id` 和 `AccountLinkQueue.identifier` 都保存 Mineracer `userId`，`AccountLinkQueue.verified=True`。

旧账号关联接口：

- `create_account_link` 拒绝 Mineracer，不能手动提交 Mineracer ID。
- staff `verify_link` 拒绝 Mineracer，不能人工验证 Mineracer。
- `delete_link` 和 staff `unverify_link` 拒绝 Mineracer，返回 `unlink_not_supported`。
- `update_link` 拒绝 Mineracer，返回 `update_not_supported`。
- `delete_account` 对 Mineracer 也会拒绝，避免绕过 view 层误删。

错误分类：

- `invalid-device-code` 映射为 `invalid_device_code`。
- `account-not-found` 映射为 `account_not_found`。
- `link-superseded` 映射为 `link_superseded`。
- `code-expired` 映射为本地 `expired` 状态。
- 未识别响应映射为 `response`。
- 请求超时映射为 `timeout`。
- 其他请求异常映射为 `requestexception`。

审计记录：

- 使用现有 `accountlink` logger，写入 `logs/accountlink.log`。
- 记录 start 创建、start 复用、start 拒绝、poll 发送、poll pending、第三方请求临时失败、confirmed、expired、failed、identifier_conflict。
- 日志字段包含 OpenMS `user_id`、Redis `session_id`、状态、错误分类和确认后的 Mineracer `userId`。
- 不记录 partner key，也不完整记录可复用的 `deviceCode`。

### 前端实现

- `front_end/src/utils/accountlinks/platforms.ts` 已加入 `AccountLinkPlatform.Mineracer`、官网地址和 profile URL 函数。
- 中英文 `common.platform` 已加入 Mineracer。
- `front_end/src/utils/accountlinks/mineracer.ts` 定义 `AccountMineracerResponse`、`AccountMineracer` 和 Mineracer session 类型。
- `AccountLinksResponse` 与 `AccountLinks` 已支持 Mineracer 数据。
- Mineracer 不使用 `CardAdd.vue` 的手动 ID 流程，而是使用 `CardAddMineracer.vue` 的专用流程。
- `CardAddMineracer.vue` 显示生成链接按钮、外链按钮、过期倒计时、当前状态，并按后端返回的 `next_poll_at` 请求 status API。
- `CardMineracer.vue` 显示 Mineracer `userId`、验证状态和绑定时间。
- `mineracerService.ts` 集中处理 Mineracer start/status API 与错误分类映射。
- 前端打开 Mineracer 链接使用新窗口，并设置 `rel="noopener noreferrer"`。
- Mineracer 当前没有资料或统计 API，因此不显示同步按钮。
- Mineracer 当前不支持解绑，因此前端不显示解绑入口。

### 安全与一致性

- partner key 只在服务端使用，每次调用 Mineracer start/poll 时读取 `secrets.json` 的 `mineracer_account_link_partner_key`，不在 settings 加载时读取。文件或键缺失时直接抛出读取异常，空字符串返回 `mineracer/not_configured`（503）；更新密钥后无需重启服务。密钥不进入构建产物和接口响应。
- start/status API 都需要登录校验与限流。
- status API 必须校验会话归属，不能让用户查询或完成他人的会话。
- Redis 临时会话必须使用 `default` cache alias，不能放进 `saolei_website` session cache。
- 绑定成功逻辑放在数据库事务中，并锁定相关记录，避免并发重复绑定。
- 过期会话不能继续绑定；如果 Mineracer 返回过期状态，本地也会标记为 expired。

### 剩余事项

1. 由于 Mineracer 不提供测试环境或测试账号，联调需要使用生产接口小范围验证。
2. 部署后观察 `logs/accountlink.log`、第三方请求失败率和用户绑定成功率。
