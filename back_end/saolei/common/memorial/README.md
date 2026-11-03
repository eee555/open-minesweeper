# 纪念账号的账号关联与录像导入

纪念账号（`UserProfile.is_memorial`）不能登录，因此原先“本人申请 → 管理员核实”的账号关联流程对它不可用。本功能为纪念账号补两条站长/管理员通道。

## 权限边界

| 操作 | 允许的角色 | 接口 |
| --- | --- | --- |
| 查看已设关联 | 站长（superuser） | `GET /api/common/admin/memorial/users/{id}/account-links` |
| 设置关联 | 站长（superuser） | `POST /api/common/admin/memorial/users/{id}/account-links` |
| 解除关联 | 站长（superuser） | `DELETE /api/common/admin/memorial/users/{id}/account-links?platform=c` |
| 同步目录、导入录像 | 管理员（staff）或站长（superuser） | `/api/accountlink/saolei/{account_id}/sync/*`、`/videos/{source_id}/import` |
| 刷新资料、切换自动同步 | 仅站长（superuser） | `/api/accountlink/saolei/{account_id}/profile`、`/settings` |

- 关联路由挂在纪念账号的 `Router(auth=django_auth_superuser)` 下，自带会话与 CSRF 校验，符合 [ADMIN_API_CSRF.md](../../ADMIN_API_CSRF.md)。
- 扫雷网写接口使用 `@decorate_view(login_required_error, admin_csrf_required, ratelimit(...))`：普通用户保持原有无 CSRF 要求，管理员调用必须携带 `X-CSRFToken`。

## 可指定的平台

只有 `c`（扫雷网）、`a`（MSGames）、`w`（Minesweeper.Online）。Discord 依赖本人 OAuth 身份，Bilibili/QQ/经典/Mineracer 依赖各自的身份验证流程，均不可由站长代指定，调用会返回 `400 memorial/platform_not_assignable`。

## 规则

- 目标必须是纪念账号，否则 `409 memorial/not_memorial`；不存在为 `404 memorial/not_found`。
- 平台账号已被其他用户占用时返回 `409 accountlink/collision`，不抢占归属。
- 同一平台重复设置会替换旧值：先删除该用户在此平台的旧账号记录（`OneToOne` 约束），再写入新记录；其他平台的关联保留。
- 其他用户尚未核实的申请记录若与本次指定冲突，会被移除，不留下两条指向同一平台账号的队列项。
- 解除关联会同时删除平台账号记录与队列项，与既有 `delete_account()` 行为一致。
- 关联结果参与该平台的排行与勋章计算，不做“纪念账号不参与”的特殊处理。

## 前端

`/superuser/memorial`（[MemorialAccounts.vue](../../../front_end/src/views/StaffView/MemorialAccounts.vue)）新增两块：

- **账号关联**：选择平台、填写平台 ID 后设置，列表展示已设关联并可逐条解除。
- **扫雷网录像导入**：设置 `c` 关联后出现，复用现有 `VideoImportQueue` 组件完成同步与导入。

CSRF token 取自关联列表接口返回的 `csrf_token`，与该页既有的补录像流程一致。

## 回归测试

- `common.test_memorial.MemorialAccountLinkTests`：站长设置/换绑/解除、平台白名单、目标校验、非站长拒绝、他人账号冲突、待审申请替换、CSRF 必需。
- `accountlink.test_saolei_api.SaoleiMemorialAdminTests`：站长与管理员可同步与导入纪念账号，普通用户与非纪念账号仍被拒绝，管理员不能改资料与自动同步，本人同步不受影响。
