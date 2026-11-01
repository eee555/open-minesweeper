# Discord 人工账号关联

Discord 与 QQ 共用手工申请及管理员审核流程，平台代码分别为 `d`、`q`。两者均属于私密关联，只有本人及本站管理员可以读取待验证申请、已验证摘要和账号 ID；其他普通用户及匿名请求不返回这些信息，公共用户目录也不支持按这些 ID 查询。

## 申请与审核

1. 已登录用户在本人账号关联页点击加号，选择 Discord，填写数字 User ID，调用现有 `POST /api/accountlink/create/` 提交待验证申请。
2. 管理员确认申请人拥有该账号后，在现有管理页调用 `POST /api/accountlink/verify/` 审核。沿用管理员会话认证与 CSRF 校验。
3. QQ 和 Discord 使用同一个私密账号卡片展示 ID、待验证状态或已验证状态。更正错误 ID 或解除关联时联系管理员，通过现有 `POST /api/accountlink/unverify/` 处理。

Discord ID 全程按字符串保存及传输，接受无前导零的 1–20 位 ASCII 正整数，避免 JavaScript 整数精度损失。ID 获取方法见 [Discord 官方说明](https://support.discord.com/hc/en-us/articles/206346498)：开启开发者模式后使用“复制用户 ID”，不填写用户名或显示名。

## 数据与部署

`AccountDiscord` 与 `AccountQQ` 一样只保存 `id`、`parent`。已有 Discord ID、本站用户归属和关联审核状态保留；自动获取的用户名、显示名、头像、横幅、强调色、徽章及更新时间字段随结构迁移删除。

部署时沿用目标环境历史迁移，由 Django 自动生成并应用；不要复制其他环境的迁移编号：

```bash
python -m pip install -r requirements.txt
python manage.py makemigrations accountlink --noinput
python manage.py migrate
```

官方 OAuth 接口、Discord 登录入口、回调页面、Authlib 依赖、Client ID / Redirect URI 设置以及专用 Nginx / uWSGI 超时配置已移除。绑定与审核不再访问 Discord 的 API 或 CDN。旧 `/api/accountlink/discord/` 授权接口返回 404；新的申请与审核使用上文通用接口。

原 `secrets.json` 中的 `discord_oauth_client_secret`、`discord_oauth_frontend_url` 及更早的 Client ID / Redirect URI 字段不再读取，可由运维删除。原 OAuth flow / used 缓存会在 600 秒 TTL 到期后自然消失，旧 Session 浏览器随机标识不再使用并随 Session 过期。无需清空 Redis 或使所有用户退出登录。若部署过专用 callback 超时配置，同步删除对应 Nginx location 和 uWSGI 路由并按原部署流程校验、重载。

本地只生成迁移，不对业务库执行 migrate；回归测试使用独立测试库。

## 验证

后端覆盖 QQ / Discord 的申请、审核、冲突、解绑、私密可见性、管理员 CSRF、Discord 长 ID 及旧 OAuth 路由移除。测试禁止外部 HTTP 请求。Mineracer 继续使用原自动确认流程。

在 `front_end` 运行单元测试：

```bash
npx vitest run src/utils/accountlinks/discord.test.ts src/services/accountLinkService.test.ts
```

Cypress 由用户执行：

```bash
npx cypress run --component --browser chrome --headless --spec "src/components/accountlinks/CardAdd.cy.ts,src/components/accountlinks/CardPrivate.cy.ts,src/components/accountlinks/App.cy.ts,src/components/Login/LoginForm.cy.ts"
npx cypress run --e2e --browser chrome --headless --spec "cypress/e2e/accountlink.cy.ts"
```
