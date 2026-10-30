# 管理员 API 的 CSRF 规范

## 适用范围

管理员、站长使用 Cookie 会话调用管理写接口时，必须同时通过角色权限和 CSRF 校验。普通用户 API 不新增 CSRF 要求，包括普通账号担任比赛主办方时的共用接口；普通 API 也不因为调用者恰好是管理员就自动启用后端 CSRF。

不启用全局 `CsrfViewMiddleware`，不在 `login_required_error`、`banned_blocked` 中增加统一校验。Django Admin 自带的保护、Ninja 现有站长会话认证继续保留。仅用于本地测试的 `dangerzone` 继续使用原有本地访问限制。

## 后端

- 管理员专用接口使用 `@decorate_view(staff_required)`。该公共装饰器先检查原有管理员权限，再通过 Django `csrf_protect` 校验 POST、PUT、PATCH、DELETE 等非安全方法，涵盖现有 Ninja 和旧 Django 管理写入口。
- 站长专用接口使用 Ninja 的 `auth=django_auth_superuser`，沿用内置会话及 CSRF 校验。需要同时接受管理员和站长的接口也可使用 Ninja 的 `SessionAuthIsStaff()`。
- 管理员与普通主办方共用的接口使用 `@decorate_view(login_required_error, admin_csrf_required, ...)`，并保留资源权限检查。`admin_csrf_required` 只在调用者的 `is_staff` 或 `is_superuser` 为真时执行 CSRF 校验，不赋予资源访问权限。`GSC_admin_required` 使用相同的条件校验，普通 GSC 主办方不新增 token 要求。
- GET、HEAD、OPTIONS 必须只读。管理修改不得通过 GET 执行。需要调整的旧 Django 写接口迁移到 Ninja，移除原 GET 写入口，更新调用说明。
- 权限只在 API 层检查，service 不重复检查操作者角色。API docstring 开头注明对应权限及 CSRF 装饰器。

复用 Django 的 [CSRF 保护和 AJAX 请求头机制](https://docs.djangoproject.com/en/6.0/howto/csrf/)，不自行实现 token 生成、签名或来源校验。

## 前端和第三方管理员客户端

登录入口 `src/components/Login/App.vue` 在登录、注册、找回密码或自动恢复会话成功后，通过 `applyLoginSession` 检查返回用户的 `is_staff || is_superuser`。只有管理账号才动态加载 CSRF 模块，为项目 `$axios` 安装拦截器；安装完成后才发布登录状态，避免首个管理请求缺少 token。模块加载失败时不发布该管理登录状态，显示现有错误通知。同一 Axios 实例的并发或重复登录复用安装任务；等待期间发生退出或新的登录时，不再发布旧登录结果。

网站启动入口不静态引入 CSRF 模块，访客和普通用户首次进入不加载该模块。退出管理账号后，已安装的拦截器按实时角色跳过普通用户请求。普通用户不获取、不发送 CSRF token；安全方法和发往第三方地址的请求不自动添加本站 token。

拦截器保留显式传入的 `X-CSRFToken`。前后端同主机且 Cookie 可读取时，每次写操作读取当前的 `csrftoken`；否则调用 `GET /api/userprofile/admin/csrf` 获取掩码 token。该入口仅允许管理员或站长，响应含 CSRF Cookie 和 `csrf_token`，禁止缓存。同一批并发请求共用正在进行的 token 获取，后续批次重新读取 Cookie 或获取 token，不长期缓存旧会话的 token，也不写入 localStorage。

获取 token 失败或等待期间角色发生变化时，不发送该写请求。不自动重试写操作。已有冻结、删除、管理员授权、纪念账号上传等入口显式获取 token 的方式继续兼容。

第三方管理员客户端同样需要维护一个 Cookie 会话，先请求上述 token 入口，再在管理写请求中附带 `X-CSRFToken`。普通用户客户端的原调用方式保持不变。

## 旧 GET 写入口迁移

| 原入口（已移除） | 新入口 | 请求和响应 |
| --- | --- | --- |
| `GET /article/update_list/` | `POST /api/article/admin/refresh` | 无请求体；返回文章条数，仅管理员或站长 |
| `GET /userprofile/del_user_info/?id=123` | `POST /api/userprofile/admin/clear-info` | 表单 `id=123`；返回 204，仅管理员，清理管理员资料仍需站长权限 |

清空资料会持久化清空姓名、签名和头像；头像文件沿用 `django-cleanup` 的提交后清理。文章索引在读取有效文件列表后，通过 Redis 事务替换，保留原目录筛选和列表顺序。

## 回归测试

后端使用 `Client(enforce_csrf_checks=True)` 验证管理员缺 token、错误 token、不可信 Origin 均在业务执行前被拒绝；合法 token 可执行；管理员只读请求无需 token；普通主办方共用接口和普通用户装饰器保持无 CSRF 要求。

前端测试覆盖普通用户跳过模块加载、管理登录等待安装、重复及并发登录、退出时的加载竞态、管理员动态读取 Cookie、跨域 token 获取、并发合并、失败时不发送写请求、显式 token 保留以及第三方地址不自动附带本站 token。单独挂载管理组件不会运行登录入口，组件测试如需验证拦截器，应自行安装它。

Cypress E2E 的 `cy.request()` 不经过页面 Axios 拦截器。成功的管理写请求使用 `cy.adminRequest()`：每次通过当前会话获取 token，再携带 `X-CSRFToken` 发送请求，保留表单格式和已有请求头，适配 `cy.session()` 切换账号后恢复 Cookie 的行为。普通用户请求以及缺失或错误 CSRF 的拒绝测试继续使用 `cy.request()`。
