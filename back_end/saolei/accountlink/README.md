# Account Link

## 绑定与资料同步

管理员验证先提交绑定；MSGames 的隐藏资格与绑定同事务提交。提交后的第三方资料拉取或同步失败不影响绑定成功，验证接口保持成功响应并记录同步失败日志。用户可稍后刷新资料，管理员重试空名 MSGames 绑定时也会补拉资料，不重复发放隐藏资格。

`POST /api/accountlink/unverify/` 以表单接收 `id`、`platform`、`identifier`。管理员解绑时同事务删除关联账号和申请队列行，待验证申请也可取消；用户随后可以用正确 ID 重新申请。已有隐藏资格与选择保留，Mineracer 仍禁止人工解绑。旧 `/accountlink/unverify/` 已移除。

## 扫雷网迁移期间

首批迁移已实现，使用 `saolei-api==0.4.0` 的官方 Release wheel，版本与 SHA256 固定在依赖文件中。完整业务约定及下次更新范围见[扫雷网官方 API 接入方案](SAOLEI_API_IMPORT_PLAN.md)。本次未对现有业务库执行迁移或真实账号导入。

接入分两次更新：首次仅由服务器管理命令完成已绑定账号的同步与录像导入，现有刷新、同步和导入接口继续关闭，旧列表和统计接口也关闭，不开发或改接新 API。前端代码不动；API 相关改动仅限关闭旧查询所需的路由和引用清理。接口关闭情况由站长人工鉴定，不新增自动化测试。同步完成后保持关闭，下次更新再开放新 Ninja API 和前端操作。账号关联申请、审核和已有绑定保留，审核成功不自动触发扫雷网同步。

自动生成的结构迁移删除旧 `VideoSaolei` 来源模型及全部数据，创建独立的 `SaoleiApiVideo` 来源表；不按相同数字对应新旧来源 ID。账号绑定、已导入本站的 `VideoModel`、扩展记录和文件保留。重新取得的原文件按本站哈希查重，同主复用已有录像，异主冲突不关联或修改既有录像。`SaoleiApiVideo.import_video` 使用可空的 `OneToOneField`，同一条本站录像最多关联一条扫雷网来源记录。仓库不跟踪迁移文件，部署时沿用目标服务器的历史迁移自动生成并核对，不依赖开发机的迁移编号。

新旧扫雷网用户 ID 保持一致，沿用现有绑定。新来源录像的 `status` 仅展示，不影响是否导入；上游 `hash` 不采集或保存。取得文件后继续复用本站原有录像解析及查重业务。

`SaoleiApiVideo.file_url` 保存客户端规范化后的录像文件后缀，例如 `2023/04/16/sample.evf`；获取详情时更新并落库，导入从该字段下载文件。目录列表没有文件地址，刷新目录不会清空已保存的后缀；详情明确返回无文件时清空该字段并保留来源供重试。原录像网页链接的 `url` getter 已移除。

账号资料只接入 `id`、`name` 和 `banned`，不使用任何账号成绩数据（`scores`、`scores_nf`）或 `signatures`，不进行账号成绩精度升级。`AccountSaolei` 删除旧成绩、人气、三级录像数量和 `video_import_task` 字段，仅保留账号 ID、用户关联、姓名、封禁状态、资料更新时间及录像目录的游标和完成时间。录像自身的成绩解析和文件内标识校验继续沿用现有业务。

账号新增本地进度字段 `video_sync_cursor`（默认 0），保存上次成功落库的目录页对应的 `next_cursor`，供增量更新和中断续跑使用。后续请求返回 ID 大于游标的录像，`next_cursor` 可等于本页最后一条 ID，不自行加 1；本轮超过 `stats().max_video_id` 的记录留待下次处理，游标最多保存到该上界。目录记录与游标同事务提交，失败不推进；录像文件导入失败单独重试，不回退目录进度。`video_update_time` 仅在目录扫描完成后更新，不代表所有文件均已导入。

新来源录像保存 `software` 原始软件名称，下次开放的目录接口和录像管理列表再使用此字段；本站录像的软件类型仍由实际文件解析确定。已完成[官方 API 软件名称抽样](SAOLEI_SOFTWARE_SURVEY.md)，包含 `Vienna` 和 `元扫雷3.3.4` 等实际取值。

新接入方案按软件白名单导入，仅接受 `software` 原字符串精确匹配的 `Clone`、`Vienna`、`Arbiter`、`元扫雷3.3.4`。`Saolei.wang` 和其他白名单外取值保留来源目录记录，单条、批量、全站重建及重试均跳过导入，不下载文件；跳过与失败分别统计，`status` 仍不作为导入筛选条件。

旧站资料页、录像列表和下载地址的爬取逻辑已删除。账号关联申请、人工审核、绑定关系、已保存资料和历史录像继续保留；审核扫雷网关联时不再自动刷新资料。

- 资料刷新 `/accountlink/update/` 的 `platform=c` 返回 HTTP 410，错误类别为 `saolei/crawling_disabled`；其他平台沿用原流程。
- 触发爬取的 `/accountlink/saolei_import_video/`、`/accountlink/saolei_import_videos/` 已移除，返回 HTTP 404。
- 历史列表 `/accountlink/saolei/videolist/get/` 和统计 `/accountlink/saolei/videoimport/stat/` 已移除，对应视图及旧模型引用一并清理。
- 三个旧 Django Task 路径保留为失败入口，处理升级前已入队的任务，并禁止管理员重启这些爬取任务。部署时需要重启 Web 和任务 worker，使它们加载新代码；不清除历史任务或业务数据。
- 本轮不修改前端，保留现有禁用的同步操作；旧查询接口已关闭，下次更新再接入新目录与统计。

管理命令在同一进程共用客户端，串行完成资料、目录和文件导入，不创建 Django Task。部署后在服务器配置 `secrets.json` 中的 `saolei_api_key`，先核对原文件哈希并运行结构迁移，再小范围联调：

```bash
python manage.py backfill_video_hashes
python manage.py makemigrations accountlink --noinput
python manage.py migrate
python manage.py sync_saolei_api --account-id 101 --full
python manage.py sync_saolei_api --all-linked --full
```

`--account-id` 是扫雷网账号 ID，可重复指定；只处理已验证且与 `AccountSaolei.parent` 一致的绑定，不自动修复绑定。命令发现存量录像缺少哈希时拒绝同步。旧任务指针随结构迁移删除，不另设清理接口。

中断续跑或以后增量更新使用 `python manage.py sync_saolei_api --all-linked`，去掉 `--full`。每次运行还会扫描本地白名单内、尚未关联本站录像的记录，补导已入库但未完成的录像。`--full` 从 0 重新对账目录，不清空新表，也不回退已保存的成功游标。

资料或单条录像失败不撤销绑定和既有成功结果；失败会汇总并返回非零退出码。鉴权失败或限流立即停止，不自动重试。来源缺少详情或文件保留重试机会；执行期间请勿并行运行多个使用同一 key 的同步命令。同步完成后接口和前端操作继续保持关闭。

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
