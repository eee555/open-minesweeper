# 账号关联页面

`UserAccountLinkView.vue` 为路由入口，本目录维护页面、平台表单、资料面板及专用样式。

## 文件职责

| 位置 | 职责 |
| --- | --- |
| `App.vue` | 按目标 userId、登录用户和 sessionRevision 隔离页面，在 KeepAlive 失活时卸载状态 |
| `AccountPage.vue` | 请求聚合资料，保存选中平台、各平台草稿、发送状态、错误和确认会话 |
| `PlatformGrid.vue`、`platforms.ts` | 全平台按钮、顺序、图标来源和私密平台标记 |
| `linking/*Link.vue` | 各平台的表单、指引、本地化和局部样式；手动提交事件交给 AccountPage |
| `linking/useClassicLink.ts`、`useMineracerLink.ts` | 分别管理确认状态和轮询；仅当前平台轮询，切换回来复用会话，卸载后忽略响应 |
| `panels/` | 连续显示平台资料和操作；扫雷网导入说明合并在录像列表的小字中，操作说明分别放在按钮及自动同步开关的 title 中 |

`components/accountlinks/` 保留共享的两种导入队列、UnverifiedNotice 和测试工具。扫雷网录像列表提供“全量刷新列表”“增量刷新列表”“导入全部录像”三个独立操作：`refreshSaoleiCatalogue` 仅逐页更新目录，`importPendingSaoleiVideos` 仅逐条导入当前目录中符合条件的待导入录像，已导入录像不重复处理。停止或关闭窗口只停止后续请求，自动同步配置独立保存。管理员纪念账号页也使用该队列。

GitHub 使用 `linking/GitHubLink.vue` 发起 OAuth，回到本人的关联页后由 `AccountPage.vue` 显示受控结果并选中 GitHub 平台。`panels/GitHubPanel.vue` 默认仅展示公开数字 ID，用户点击后通过原生 fetch 直接匿名获取公开用户名，不使用本站 axios、Cookie 或持久缓存；网络失败保留已验证 ID。本人可解除关联，管理员沿用后台解除关联接口。

## 图标来源

`platforms.ts` 每项配置图标地址、图片/遮罩方式及可见性。未关联图标使用 50% 透明度，待验证的关联保持正常；首次加载或首次失败时不推断状态，无权查看的 QQ / Discord 不通过透明度区分是否关联。

| 平台 | 来源 |
| --- | --- |
| 扫雷网 | [官方 SVG](https://saolei.wang/icon.svg) |
| 国际网 | [官网 favicon](https://minesweepergame.com/favicon.ico) |
| WoM | [官方 SVG](https://minesweeper.online/img/minesweeper-online.svg) |
| Bilibili | [官方 favicon](https://www.bilibili.com/favicon.ico) |
| Mineracer | [官网 SVG favicon](https://mineracer.com/favicon.svg) |
| 95 经典扫雷 | 已有本地 `Classic95Icon` |
| QQ | [QQ 互联标识](https://wiki.connect.qq.com/wp-content/uploads/2013/10/03_qq_symbol-1-250x300.png) |
| Discord | [Font Awesome Free Brands 6.7.2，经 npmmirror 加载](https://registry.npmmirror.com/@fortawesome/fontawesome-free/6.7.2/files/svgs/brands/discord.svg) |
| GitHub | [Font Awesome Free Brands 6.7.2，经 npmmirror 加载](https://registry.npmmirror.com/@fortawesome/fontawesome-free/6.7.2/files/svgs/brands/github.svg) |

外链图标不下载到项目素材目录。Discord 使用 CSS mask 随主题着色，其 Font Awesome 图标按 [CC BY 4.0](https://fontawesome.com/license/free) 授权，品牌商标归各自所有者。中国大陆真实网络下的加载及显示效果仍需人工确认。

## 组件测试

| 文件 | 行为范围 |
| --- | --- |
| `App.cy.ts` | 固定导航顺序、键盘选择、草稿、六个平台的提交参数、待验证状态与图标反馈、刷新和 KeepAlive |
| `App.states.cy.ts` | 加载重试、无 summary 的已有绑定、跨平台/用户异步隔离、私密查看权限 |
| `linking/Forms.cy.ts` | 六个独立表单的校验、字符串保留、回车提交、发送中禁用与失败后编辑 |
| `linking/ConfirmationFlows.cy.ts` | Classic / Mineracer 的确认、冲突/过期重试、跨平台保留会话及完成后只刷新一次 |
| `panels/Profiles.cy.ts` | 资料、空值格式、国际网资料暂缺、同步错误和未验证状态 |
| `panels/SaoleiPanel.cy.ts` | 资料、统一录像列表入口、本人导入/访客只读、自动同步受控保存和失败回退 |

在 `front_end` 下运行；代理不自动执行 Cypress：

```powershell
npx.cmd cypress run --component --browser chrome --headless --spec "src/views/UserView/AccountLinks/**/*.cy.ts,src/components/accountlinks/VideoImportQueue.cy.ts,src/components/accountlinks/MSGamesVideoImportQueue.cy.ts"
```
