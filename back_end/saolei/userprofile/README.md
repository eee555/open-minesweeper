# 用户姓名隐藏

纪念账号的业务规则、注销 ID 复用与站长代管方案见 [纪念账号方案](./MEMORIAL_ACCOUNT_PLAN.md)（规划中，尚未实现）。

## 账号删除与孤立扫雷资料

`UserProfile.post_delete` 按真实 `userms_id` 在同一数据库事务内删除关联 `UserMS`，其标识通过外键级联删除；覆盖实例和 QuerySet 删除。从 `UserMS` 发起的原有级联跳过重复清理，未关联 `UserMS` 的账号可正常删除。

历史孤立 `UserMS` 使用 `python manage.py cleanup_orphan_userms --dry-run` 预览，去掉 `--dry-run` 执行清理。支持 `--batch-size`（默认 1000）和 `--database`（默认 `default`）；实际删除分批加锁并重新检查用户关联，已关联用户的资料保留。两种用户 ID 无需相等，不使用同值主键推断归属。

## 授权与设置

- `can_hide_realname` 记录资格，`hide_realname` 记录用户选择，默认均为 False。管理员可授权或撤销；撤销同时关闭隐藏。
- 新的 MSGames 正式绑定事件自动授权，不自动开启隐藏；绑定与资格同事务提交，第三方资料同步在提交后执行。远端请求失败或返回空白姓名不影响绑定成功及已有资格，后续可刷新或重试验证以补齐资料。解绑保留资格及选择，重复验证、登录和同步不重新授权；上线前已绑定的用户由管理员手动补发资格。
- 有效实名是非空、非纯空白且不为“匿名”的 `realname`。没有实名时不能开启隐藏；已有资格的用户可以在首次设置有效实名时同时选择隐藏。清除实名会关闭隐藏并保留资格。
- 设置入口位于 `EditProfile.vue` 的 Real Name 区域，与其他资料共用 Save，提交 `POST /api/userprofile/update_profile`。姓名与隐藏选择同事务保存；失败按原有字段结果返回。管理员沿用 `/api/userprofile/admin/update/{user_id}` 修改资格。

## 姓名读取与缓存

`_realname`、`_firstname`、`_lastname` 保存原值，数据库列名仍为 `realname`、`firstname`、`lastname`。模型同名公开 getter 在有效隐藏时返回精确字符串 `hidden`，包括原本为空的英文名。`has_realname()`、姓名写入服务和本人／管理员 Schema 读取底层原值；ORM 查询、`values()`、`update_fields` 使用下划线字段名。

公共单用户、批量资料和录像查询返回公开姓名；前端识别 `hidden` 后统一显示“用户 #ID”／`User #ID`，忽略姓名格式偏好。本人 `info/0`、登录响应及管理员资料返回原值。三个姓名字段都禁止设置为规范化后的精确值 `hidden`。

这是展示偏好。账号关联返回的姓名、原始录像内容和原文件名保持原样；导出目录沿用 `{用户ID}_{公开姓名}/原文件名`。录像查询禁用按姓名排序。本人保存资料成功后立即使该用户的本地姓名缓存失效，已显示的 `PlayerName` 重新读取公开姓名；失败则恢复复选框为已保存的选择。其他浏览器仍按正常检查周期更新，不保证同时变化，缓存机制见 [userService.md](../../../front_end/src/services/userService.md)。

## 用户数据库列表

数据库默认页 `/database/users` 使用公开接口 `GET /api/userprofile/query`。通过 `platform + id` 精确查询；平台省略或为空时查本站用户，`c`、`a`、`w`、`m` 分别查扫雷网、MSGames、WoM、Mineracer 的已验证关联。ID 留空显示全部用户。响应字段和分页、排序参数由 Ninja API 文档提供。

没有 `UserMS` 的用户按零展示及排序；等待重算的负统计值仍保留。统计同值时按用户 ID 升序分页。关联 ID 使用字符串，未绑定的平台省略；Mineracer 暂无个人主页链接，仅显示 ID。

查询及索引见 [数据库与缓存说明](../../../vitepress_doc/zh/guide/development/cache.md)。`AccountLinkQueue` 的新增联合索引需使用 Django 生成并应用 `accountlink` 迁移。

## 数据库迁移

仓库按现有约定忽略编号迁移文件。部署时保留服务器已有迁移历史，在 `back_end/saolei` 目录交互执行：

```sh
python manage.py makemigrations userprofile
```

三个姓名字段的重命名确认均回答 yes。检查生成的迁移及 `sqlmigrate` 输出：原姓名列必须保留，实际结构变更只新增两个布尔列；不能应用“删除旧姓名字段再新增空字段”的迁移。确认后执行：

```sh
python manage.py migrate
```

存量资格不自动回填；由管理员按需授予。

## 验证

后端在 `back_end/saolei` 运行：

```sh
python manage.py test userprofile.tests accountlink.tests.NamePrivacyBindingTests --keepdb
```

前端单元测试在 `front_end` 运行：

```sh
npm run vitest -- run src/utils/userprofile.test.ts src/services/userService.test.ts
```

Cypress 由用户运行：

```sh
npx cypress run --component --browser chrome --headless --spec "src/components/PlayerName.cy.ts,src/views/UserView/EditProfile.cy.ts"
npx cypress run --e2e --browser chrome --headless --spec "cypress/e2e/realname-privacy.cy.ts"
```

E2E 使用隔离的测试数据库及 Redis，启用 `E2E_TEST=True` 并完成迁移，前后端地址按 `.github/workflows/CypressE2E.yml` 准备。用例会重置测试数据。合成 MSGames 账号 `2147483000`、`2147483001` 仅在 `E2E_TEST=True`、`DEBUG=True` 且无 `.production` 标记时返回固定外部资料，本地绑定与授权仍经过实际业务接口。
