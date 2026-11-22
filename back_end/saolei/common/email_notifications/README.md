# 多语言邮件调查与管理员试用方案

更新：2026-11-22。本文为[邮件通知系统计划](../EMAIL_NOTIFICATION_PLAN.md)的格式依据与运行说明；事件接收、后台任务与 MIME 构造已实现，真实邮箱兼容性仍待管理员试用。

## 运行配置

- `EMAIL_NOTIFICATIONS_ENABLED`：默认关闭；环境变量设置为 `True` 后启用。入队和 worker 执行时都会检查，关闭后已排队任务也跳过。
- `EMAIL_QUOTA_TIME_ZONE`：每日额度日期的时区，默认 `Asia/Shanghai`（UTC+8），已按确认的供应商时区设置；不受项目 UTC 或浏览器时区影响。
- `EMAIL_WEBSITE_URL`：默认 `https://openms.top`，用于生成后台与本人设置链接。
- `EMAIL_DAILY_LIMIT`：固定 2000，通知和验证码共用单条 `EmailSentQuota` 记录；失败不退额，不保存历史日期。
- `EMAIL_SKIP` 或 `E2E_TEST` 为真时不入队或发送通知。测试使用内存邮件后端，不发送真实邮件。

部署与 CI 沿用现有自动生成迁移流程；本地已自动生成迁移用于校验，不单独提交依赖本地历史链的迁移文件。运行现有 `db_worker` 即可处理任务，无需新增 scheduler。账号默认关闭所有订阅，由管理员在本人主页设置中开启。

首次上线需在服务恢复前初始化供应商当日已用量，或在新的供应商额度日期开始启用；后续重启不得清零。初始化步骤见开发文档的数据库迁移章节。

请求只在提交后写入任务，不查询收件人、占额或等待 SMTP。任务按发送时的角色、订阅和对象当前状态筛选，一次尝试后结束；失败、停机漏信和额度不足不补发。

保存本人通知偏好的 API 不按管理员身份限制通知类型；管理员开关只在前端向管理员显示。普通用户也可通过 API 保存这些位，但 worker 发信时仍要求当前有效管理员身份，订阅本身不授予收件资格。

## 已选方案

首版直接使用 `multipart/multilingual`，利用只开放给管理员的范围测试真实客户端，不再以兼容性尚未实测为由改用普通三语正文。

一封邮件仍完整携带中文、英文和西班牙语。支持标准的客户端可以按自身语言偏好选择；客户端偏好与浏览器偏好可能不同，需要分别观察。当前没有发送测试邮件，也没有验证各客户端的实际显示。

## MIME 结构

按 [RFC 8255](https://www.rfc-editor.org/rfc/rfc8255.html)组织：

```text
multipart/multilingual
├── text/plain：三语前言，不设置 Content-Language
├── message/rfc822；Content-Language: zh-CN
│   └── 中文消息及本地化 Subject
│       └── multipart/alternative：text/plain + text/html
├── message/rfc822；Content-Language: en
│   └── 英文消息及本地化 Subject
│       └── multipart/alternative：text/plain + text/html
└── message/rfc822；Content-Language: es
    └── 西班牙文消息及本地化 Subject
        └── multipart/alternative：text/plain + text/html
```

- 前言必须是第一部分，用三种语言说明邮件含多语版本及后台入口，不能标记 `Content-Language`。
- 每个语言消息部分带对应 `Content-Language`；内层主题使用相应语言，发件邮箱与外层相同。
- 外层主题用简短三语表达。默认语言消息顺序为中、英、西；不另外保存发送前语言偏好。
- 三份语言消息使用同一业务数据与链接，仅翻译模板文案，不对用户内容自动翻译。
- 普通 `multipart/alternative` 只用于每种语言内部的 HTML/纯文本，不替代外层多语言类型。

根据 [RFC 8255 第 4 节](https://www.rfc-editor.org/rfc/rfc8255.html#section-4)，不支持该类型的客户端会按混合内容处理。因此显示全部语言部分或附件是需要观察的兼容性结果，不能先假定所有客户端都自动选语言，也不能据此断言所有客户端都不支持。

## 复用现有设施

使用 [Python 标准库 email.message](https://docs.python.org/3/library/email.message.html)构造 MIME 树，复用 Django 邮件对象的 `message()` 扩展点、当前 SMTP 后端及全站额度入口。已核实本地 Django 提供该扩展点；实施时增加必要封装及序列化测试，不手工拼接 boundary、邮件头或编码。

不能只改 `EmailMultiAlternatives` 的 subtype 就认为满足标准：必须有前言、正确的 `message/rfc822` 包装、语言头和内层主题。为每位管理员发送一封包含全部语言部分的邮件，额度按一封占用。

不使用邮件内 JavaScript、网页邮箱外层 DOM、CSS 隐藏或远程图片来模拟选语言，也不预先实现第二套降级格式。

## 实测与反馈

先自动解析序列化结果，确认结构、三语内容、UTF-8 编码、主题及内外发件邮箱，再由少量主动订阅的管理员接收真实邮件。

反馈记录客户端及版本、网页或独立应用、邮箱界面语言、浏览器或系统语言；观察实际选择的语言、前言和附件展示、是否提供切换，以及主题、HTML/纯文本、深色模式和后台链接。

优先覆盖 Gmail、Outlook、QQ 邮箱及常用独立客户端，只记录实际结果。若体验不合适，再根据反馈决定是否三语平铺或采用其他方案；本轮不预先建设两套格式。

通知允许偶发失败，不为语言试用增加邮件历史或批次表。额度保护、业务事务隔离、登录设置及实施顺序以[主计划](../EMAIL_NOTIFICATION_PLAN.md)为准。
