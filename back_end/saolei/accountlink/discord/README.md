# Discord 绑定与登录

使用 Authlib 1.9.1 的 Requests OAuth2Session 执行授权码流程及 S256 PKCE，只申请 `identify`，取得 Discord ID、用户名、显示名、头像及横幅哈希、强调色和 `public_flags`。不读取邮箱，不自动注册或合并本站账号。Discord ID 全程使用字符串，避免前端整数精度丢失。

## 配置与部署

在后端运行目录的 `secrets.json` 配置以下字段，不提交真实密钥：

```json
{
  "discord_oauth_client_secret": "CLIENT_SECRET"
}
```

Client ID 和回调地址是公开配置，直接定义在 `saolei/settings.py`；将 `DISCORD_OAUTH_CLIENT_ID` 填为真实的 Discord Application ID 字符串，留空时不开启授权入口：

```python
DISCORD_OAUTH_CLIENT_ID = 'APPLICATION_ID'
DISCORD_OAUTH_REDIRECT_URI = 'https://openms.top/api/accountlink/discord/callback'
```

在 Discord Developer Portal → OAuth2 → Redirects 登记与该设置完全一致的地址，无末尾斜杠。不再读取 `secrets.json` 中的 `discord_oauth_client_id` 和 `discord_oauth_redirect_uri`，已有旧字段可删除。Client Secret 在每次请求时读取；修改 settings 中的 Client ID 或回调地址后需要重启后端。配置缺失或无效时隐藏授权入口，启动授权返回 `discord/not_configured`（503）。公钥、Bot Token 和 Interactions Endpoint 不参与本功能。

前后端同域部署时无需额外配置。分离开发时可在 settings 中把 `DISCORD_OAUTH_REDIRECT_URI` 改为 `http://127.0.0.1:8000/api/accountlink/discord/callback`，并在 `secrets.json` 另加 `discord_oauth_frontend_url`，例如 `http://127.0.0.1:8080`。前端地址填写网站根地址，不带查询参数或 hash。浏览器中访问的地址应与此配置一致，以便继续使用同一登录会话。无需 GitHub Actions 回调地址。

安装更新后的依赖，并沿用目标环境的历史自动生成迁移：

```bash
python -m pip install -r requirements.txt
python manage.py makemigrations accountlink --noinput
python manage.py migrate
```

仓库忽略迁移文件。本地已由 Django 自动生成 `AccountDiscord`、平台枚举及四项资料字段的迁移，未对本地业务库执行 migrate；部署环境需自行生成并应用，然后部署后端及网站前端。已有绑定在下次绑定确认、重新授权或 Discord 登录时补齐资料，无后台持续同步。

## 业务规则

- 首次必须登录本站，在本人账号关联页授权绑定。一个 Discord 账号和一个本站账号各自最多有一个对应绑定。重新授权只能更新同一 Discord 身份的展示资料，不能覆盖其他绑定。
- 绑定后，登录表单提供 Discord 登录，并沿用“记住我”设置。未绑定、关联记录未验证、本站账号停用或属于纪念账号时不能登录。普通封禁账号沿用本站现有登录规则，上传等限制继续由原权限逻辑处理。
- 本人确认解绑后，同事务删除 Discord 身份及关联记录。本站密码和已建立的登录会话保留，之后的 Discord 登录失败。管理员可通过原解绑接口撤销绑定，但不能通过人工认证或手填 ID 建立 Discord 身份。
- Discord 与 QQ 同属 `private_platforms`，关联摘要、ID 和详细资料仅本人及本站管理员可见；匿名访问和其他普通用户均不返回这些关联。用户目录不支持按这两类 ID 查询。
- 关联查询响应禁止 HTTP 缓存。前端在登录身份或管理员权限变化时清空并重取关联资料，忽略此前未完成的查询及添加结果，避免退出登录后保留私密卡片。
- 头像及横幅只保存哈希，由前端生成 Discord 官方 CDN 链接；无图片时不显示占位图。强调色及 `public_flags` 可为空，缺失字段会清除旧资料，颜色 `0` 和标志 `0` 保持原值。卡片展示已知公开徽章，未知标志位仍保留在原始字段中。
- 公共 `accountlink.services.save_verified_account_link` 负责用户行锁、冲突检查、身份及已验证记录的事务保存；Mineracer 确认后也调用它，保留原轮询、错误分类和禁止解绑规则。

协议接口由 Ninja 自动生成文档。普通用户接口沿用项目 CSRF 约定；OAuth `state` 与浏览器会话和发起用户绑定，回调时再次验证。回调只把固定结果类别和本站用户 ID 放入前端 hash 路由 `/#/discord`，不转发授权码、令牌或上游错误描述。访问令牌和刷新令牌仅留在本次请求的 Authlib 客户端中，不落库、不返回前端。

## 临时缓存

`caches['default']` 保存以下键，TTL 均为 600 秒：

- `accountlink:discord:flow:{state}`：模式、发起用户、浏览器随机标识、PKCE verifier、Client ID、回调地址及登录有效期。验证浏览器标识后消费并删除。
- `accountlink:discord:used:{state}`：通过原子 `cache.add` 抢占，阻止多个 Web worker 重复消费同一授权状态，失败回调同样不能再次使用。

Django Session 的 `discord_oauth_browser` 保存浏览器随机标识。清除会话、缓存过期或 Redis 丢失状态时需要重新授权，不影响已有绑定。缓存没有 Client Secret 或访问令牌。

## 验证

按本次约定只进行离线测试：后端拦截 HTTP 传输，实际经过 Authlib 的 URL、表单编码、PKCE 和 Bearer 请求，使用 Django 测试客户端验证回调、绑定、登录、停用账号、解绑、资料更新及 Discord/QQ 的本人、管理员、匿名和其他用户可见性。状态消费包含并发检查。前端 Vitest 检查授权请求、跳转目标、错误映射、ID 精度、CDN 地址、颜色和徽章解码。

Cypress 由用户在 `front_end` 运行：

```bash
npx cypress run --component --browser chrome --headless --spec "src/components/discord/DiscordAuthorizeButton.cy.ts,src/components/accountlinks/CardDiscord.cy.ts,src/components/accountlinks/App.cy.ts,src/components/Login/LoginForm.cy.ts,src/views/DiscordResultView.cy.ts"
```

真实授权、生产 Cookie 行为及浏览器跳转尚未验证，留待部署后首次实际绑定和登录时检查。

## 参考与复用选择

- [Discord OAuth2](https://docs.discord.com/developers/topics/oauth2)：授权码流程、表单令牌交换、scope、state。
- [Discord User](https://docs.discord.com/developers/resources/user#get-current-user)：`identify` 用户字段。
- [Discord CDN](https://docs.discord.com/developers/reference#image-formatting)：头像和横幅路径及动画哈希规则。
- [Authlib OAuth2Session](https://docs.authlib.org/en/stable/oauth2/client/http/requests.html)：复用成熟 OAuth 客户端，避免手写协议。

Mineracer 使用自定义确认和轮询协议，不能共用 Discord 的协议客户端；共同部分限于本站绑定业务。当前不额外建立通用 provider 框架。
