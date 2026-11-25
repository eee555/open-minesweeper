# 作品页维护说明

`media` 管理外站作品的投稿、审核、红宝石投喂与排行，不托管作品内容。用户使用说明见[中文作品指南](../../../vitepress_doc/zh/guide/works.md)和[英文作品指南](../../../vitepress_doc/en/guide/works.md)。

## 来源与输出契约

| format | 投稿输入 | 落库的 suffix | 来源归属 |
| --- | --- | --- | --- |
| `B_v` | BV 号或 B 站视频完整链接 | BV 号，大小写敏感 | Bilibili 作者 ID |
| `B_a` | 专栏数字 ID 或完整链接 | 无前导零的专栏 ID | Bilibili 作者 ID |
| `c_p` | 帖子数字 ID 或 HTTPS 扫雷网帖子链接 | 无前导零的帖子 ID | 扫雷网作者 ID |
| `g_r` | `OWNER/REPO` 或 HTTPS GitHub 仓库主页 | GitHub 仓库数字 ID | GitHub 仓库所有者数字 ID |

`MediaOut` 使用 `create_schema` 输出 `format`、`suffix` 和其他作品字段，不返回 `url`、`embed_url` 或外站作者 ID。`suffix` 始终为字符串，仓库 ID、所有者 ID 与本站用户 ID 独立使用。

展示链接统一由前端处理：`utils/media.ts` 生成 B 站/扫雷网链接及 B 站视频嵌入地址；`MediaSourceLink.vue` 在用户点击 GitHub 作品时匿名请求 `https://api.github.com/repositories/{id}`，校验返回 ID 和 HTTPS GitHub 主页后打开。请求使用原生 fetch，不携带本站 Cookie 或认证头。解析失败可重试，弹窗被拦截时保留可再次点击的真实外链。地址只在组件存续期复用，不保存 `source_url`，不新增持久化缓存、同步任务或 Webhook。

后端保留投稿链接的 host/path 白名单和来源 ID 归一化，不接受短链或用户自定义请求目标。投稿输入上限为 255 字符，以容纳完整 URL；它不同于落库后 `suffix` 的 128 字符限制，GitHub 仓库路径会先转换成数字 ID。`language` 是用户填写的自然语言，不使用 GitHub 的编程语言字段。

## 投稿与归属核验

`api.py` 处理登录、封禁、账号关联及作者归属权限；`clients.py` 获取并校验来源元数据；`services.py` 负责业务状态、持久化与一致性，不处理操作者权限。

所有投稿都需要本人已验证的对应平台关联，成功后为 `pending`，不会因身份已确认而自动过审。外站作者 ID 只在请求内与 `AccountLinkQueue` 比对，不额外保存到 Media。数据库 `(format, suffix)` 全表唯一约束处理重复及并发投稿，`rejected` 记录继续占用唯一性。

B 站/扫雷网作品依赖非公开 API，因此超时或上游不可用可创建 `metadata_pending=True` 的待补全投稿：保留语言和来源 ID，使用空标题与当前时间。结构性错误不降级。管理员审核时须补标题、一次性输入作者 ID 验证归属，可修正发表时间。

### GitHub 仓库

- 只接受当前已关联个人账号名下的公开、非 fork 仓库。组织仓库、协作参与的他人仓库及 fork 拒绝；归档仓库可投稿。
- 服务端匿名调用 `GET https://api.github.com/repos/{owner}/{repo}`，验证 `private=false`、`fork=false`、`owner.type='User'` 及两个数字 ID；必要字段缺失不能当作已验证。
- `MediaMetadata.source_id` 将仓库数字 ID 传给投稿逻辑。仓库 ID 限制在 `1..2^53-1`，与浏览器 JSON number 的安全整数范围一致。标题使用 `full_name`，发表时间使用仓库 `created_at`，不保存主页地址、Stars、代码或令牌。
- GitHub 拉取失败不创建作品。降级规则集中在 `fetch_media_metadata_optional()`，API 使用同一错误转换入口；不为 GitHub 重复实现降级开关。
- 网络请求在事务外执行。完成后 API 锁定本站用户行，在同一事务内重新核验 `AccountGitHub` 与已验证队列并按数字仓库 ID 创建作品，防止等待期间解绑后仍成功投稿。投稿仍为待审核状态，不更新作者榜。
- 仓库改名仍是同一来源 ID，不能重复投稿；同一路径删除重建后若数字 ID 不同，则是另一仓库。后续改名、转移、私有化或解绑不自动改变本站作品归属、审核状态及排行。

GitHub 使用现有 requests，无新增 scope、PAT 或 SDK。单次连接上限 2 秒、读取空闲上限 3 秒，按 8 KiB 块流式读取并检查整轮 8 秒预算和 300 KiB 响应体上限；最多跟随两次固定 HTTPS `api.github.com` 重定向，不自动重试。requests 超时不是硬性墙钟截止，块内阻塞阶段可能延后预算检查。404、限流、网络失败、元数据错误分别转换为受控错误，不记录原始响应或凭据。匿名配额按来源 IP 共享，浏览器地址解析与服务器投稿核验各使用自己的出口配额。

## 状态与管理操作

| 操作 | 状态与效果 |
| --- | --- |
| 投稿 | 创建 `pending`，管理员判断是否与扫雷相关 |
| 审核通过 | `pending → verified`，累计投喂一次性加入排行；正常投稿只接受作品 ID，不允许改信息 |
| 驳回 | `pending → rejected`，退还投喂、清零作品热度/累计值及投喂记录，保留原因与操作人 |
| 恢复 | `rejected → pending`，复用原作品，不重新发放已退还的红宝石 |
| 补录 | 仅 `metadata_pending=True` 且未过审的作品可改标题、语言、发表时间；不得修改 URL、format、suffix |
| 硬删除 | 仅站长可删除 `verified`，退还投喂并更新排行、记录快照日志；释放来源唯一性 |

作者没有删除作品入口。待审核和已驳回作品仍可由公开个人页与数据库查询读取；作品页与排行榜只展示 `verified`。管理员接口沿用 staff CSRF 校验，硬删除使用 Ninja 的 superuser 会话认证与 CSRF。API 请求/响应结构以 Ninja 自动文档为准。

## 作品查询与语言

公开作品列表使用 `/api/media/works`，只返回已审核作品，支持类型和语言组合筛选。热度、累计投喂、发表时间均倒序，同值按数值 `id DESC` 排序。默认每批 20 条，最多 50 条，每批只查询一次作品数据，没有总数查询或 OFFSET。输入输出字段以 Ninja 自动文档为准。

游标由 Django signing 签名，绑定原始排序值、作品 ID、排序与筛选条件。客户端原样传回，同值通过 ID 继续，删除边界作品不影响查询。投喂数、ID 和整数微秒以字符串保存在 token 中，热度保持 DOUBLE 往返精度。前端按 ID 去重，刷新时重排；切换查询或卸载时取消旧请求，并根据其 signal 忽略迟到响应。

三个基础排序索引为 `(hot_value DESC, id DESC)`、`(likes DESC, id DESC)`、`(created_at DESC, id DESC)`。类型筛选复用 `(format, suffix)` 唯一索引的首列，语言增加单列索引，避免重复添加类型索引。`status` 不进入新增索引，SQL 仍保留已审核条件。允许 MySQL 根据选择性过滤或使用 `filesort`；游标消除深分页增加的跳过扫描，不保证整条查询恒定成本。旧 `/ranking` 已移除；`/latest` 仍服务管理员已审核列表，其他个人、数据库、作者榜分页保留原契约。

作品语言预设 `zh-cn`（中文）、`en`（英文）、`es`（西班牙语），也可自填其他自然语言。新投稿缺省或空白时，GitHub 默认 `en`，BiliBili / Saolei 默认 `zh-cn`；手动指定优先。预设代码统一小写，其他文本 strip 后保留，最多 32 字符。历史值不批量回填，自定义语言按原文展示和精确筛选，不回退为英语或“未知语言”。

## 投喂与作者缓存

红宝石余额为注册以来完整 24 小时数减去 `UserMedia.likes_sent`。登录用户可给自己或他人的 `pending` / `verified` 作品投喂，每次消耗一个红宝石，每 UTC 自然日最多 10 次成功投喂。失败不计次数，驳回/硬删除退余额但不退当日额度。`UserMedia.banned` 只禁止投稿。

热度每天保留 99%，累计投喂不衰减。数据库用统一基准 `T_db = Media.hot_value_updated_at`；投喂增量为 `1 / decay(T_db, now)`，实时热度为 `hot_value * decay(T_db, now)`。因此列表直接按原始 `hot_value` 排序。推进 `T_db` 是罕见维护事件，不兼容此时的查询竞态，不绑定游标基准或增加检测、重试和失效恢复。

Redis 仅保留作者榜 `media:rank:user:hot`、`media:rank:user:likes` 和 `media:hot:anchor`（`T_r`）。只汇总已审核作品，零分作品的作者也入榜；分数按 `decay(T_db, T_r)` 折算。作品页不读写单件作品排行缓存，作者榜分数与 anchor 继续以 Redis 为准。

审核通过、已审核作品投喂和硬删除后，`services.sync_user_scores()` 在数据库中聚合作者的已审核作品总分，`cache.set_user_scores()` 用一个 `MULTI/EXEC` 覆盖作者两个分数，不累加请求路径增量。Redis 错误只记日志，不回滚业务、不排任务或重试。新投稿仍未审核，不同步作者榜。

`refresh_media_rankings` 仍是低频人工命令，不加入部署流程或调度器：`--reference <ISO UTC>` 推进数据库基准后重建作者两榜和 `T_r`；`--rebuild-only` 仅纠偏作者榜；`--check` 只读检查作者两榜及基准。重建使用临时键与原子发布，失败时报错，可重跑恢复。

部署新版本并确认旧进程退出后，定向删除废弃的 `media:rank:hot`、`media:rank:likes`；不要清空作者榜及 anchor。

```powershell
python manage.py shell -c "from media.cache import cache; print(cache.delete('media:rank:hot', 'media:rank:likes'))"
```

监控固定键清单已缩减为上述三个键。运维参数见[缓存说明](../../../vitepress_doc/zh/guide/development/cache.md#作品排行)及[管理命令说明](../../../vitepress_doc/zh/guide/development/management-commands.md#refresh-media-rankings)。

## 部署与验证

索引修改使用 Django 自动生成迁移；迁移文件沿用仓库忽略规则，部署入口 `start.sh` 仍先执行 `makemigrations`、`migrate`，核实索引完成后再启用新查询。前后端配套发布；回退旧版本时需先用旧版本重建单件作品 Redis 榜。

`/api/media/submit` 沿用 25 秒 Nginx/前端预算及 uWSGI 外部 I/O 白名单；B 站/扫雷网客户端保留各自超时策略，GitHub OAuth callback 的 5 秒预算不变。日志使用 `media` logger，排行异常通过低频命令巡检与恢复。

后端定向检查为 `python -m flake8 media` 和 `python manage.py test media`（需本地 MySQL、Redis）。测试分别覆盖解析和模型、外站适配、API 权限/降级、业务/退款、缓存/重建；GitHub HTTP 使用离线响应。前端定向 Vitest 为 `src/utils/media.test.ts`、`src/services/githubService.test.ts`。

用户在 `front_end` 运行相关 Cypress 组件测试：

```powershell
npx.cmd cypress run --component --browser chrome --headless --spec "src/components/media/MediaSourceLink.cy.ts,src/components/media/MediaListPanel.cy.ts,src/components/media/MediaCard.cy.ts,src/components/media/SubmitMediaDialog.cy.ts,src/views/WorksView/App.cy.ts,src/views/StaffView/StaffMediaReview.cy.ts"
```

作品 E2E 为 `cypress/e2e/media.cy.ts`。离线测试不能代替部署后的真实仓库投稿、浏览器弹窗及网关超时链验证。
