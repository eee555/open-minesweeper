# 用户资料

## 管理员权限

站长可在 `/superuser/staff` 按本站用户 ID 设置或取消管理员权限，页面通过 `is_superuser` 授权并初始化 CSRF 令牌。纪念账号不能拥有管理员权限。

## 纪念账号

为已经不活跃的传奇玩家保存资料，成绩、录像和自动勋章正常计入榜单，并显示“纪念账号”标识。“纪念”不表示玩家已经去世。

### 建档与维护

由有服务器访问权的站长低频维护。核实、清理和资料修改使用已有管理命令及 Django shell；普通管理员沿用管理普通账号的权限。

站长先确认原账号已注销且旧身份数据已清理。新玩家可以与原持有人不同，复用后旧个人主页链接会指向新玩家。普通录像删除仍保留 `newest_queue` 快照，站长须在复用 ID 前处理这些旧快照及相关关系、排行、勋章和后台任务。

`create_memorial_account` 要求手动指定 UserProfile ID、UserMS ID 和用户名。两个 ID 可以不同，但分别必须未占用且小于各自表当前最大主键；空表拒绝建档。命令在事务内创建全新的 UserMS 和账号，冲突或验证失败回滚；已有孤立 UserMS 先按下节清理。命令参数与示例见[管理命令](../../../vitepress_doc/zh/guide/development/management-commands.md)。

`is_memorial` 身份与模型约束使账号保持停用、无管理员权限、不可用密码及唯一占位邮箱。纪念账号不能登录、找回密码、被任命管理员或通过通用编辑更换占位邮箱。

### 补录像

站长从纪念玩家主页进入 `/superuser/memorial`。API 通过 `is_superuser` 授权，不额外要求 `is_staff`；参数和响应以 Ninja API 文档为准。

1. 批量解析文件，逐个手动勾选标识；默认全部不选，没有全选。仅上传所选标识的录像，空标识按原值匹配。
2. 设置上传时间锚点，复用 GSC 的结束时间排序和耗时倒推算法。指定日期参与排名及同分排序。
3. 前端依次提交文件，首个请求携带全部所选标识；后端先逐个尝试注册绑定，再上传。全部绑定失败仍尝试上传，录像状态遵循原有校验。
4. 上传失败保留已成功的绑定；重试跳过成功文件、保留原日期，重试失败或结果未知的绑定。全部文件成功后，如只需修正标识，在服务器复用 `common.services.bind_import_identifier`。

同玩家重复文件复用已有录像并保留更早上传时间；他人文件冲突返回 409，不转移归属。录入错误使用现有站长删除录像接口或 `/superuser/delete-videos` 页面删除后重传。普通删除保留比赛结算结果，重算规则见[比赛录像删除方案](../tournament/VIDEO_DELETION_PLAN.md)。

服务器建档和补录沿用应用日志，记录目标账号、标识、录像及日期。公开资料和头像沿用正常缓存周期，其他浏览器可能暂时显示旧姓名或缺少纪念标识。

## 账号删除与孤立扫雷资料

`UserProfile.post_delete` 按真实 `userms_id` 在同一数据库事务内删除关联 `UserMS`，其标识通过外键级联删除；覆盖实例和 QuerySet 删除。从 `UserMS` 发起的原有级联跳过重复清理，未关联 `UserMS` 的账号可正常删除。

历史孤立 `UserMS` 使用 `python manage.py cleanup_orphan_userms --dry-run` 预览，去掉 `--dry-run` 执行清理。支持 `--batch-size`（默认 1000）和 `--database`（默认 `default`）；实际删除分批加锁并重新检查用户关联，已关联用户的资料保留。两种用户 ID 无需相等，不使用同值主键推断归属。

## 用户姓名隐藏

### 授权与设置

- `can_hide_realname` 记录资格，`hide_realname` 记录用户选择，默认均为 False。管理员可授权或撤销；撤销同时关闭隐藏。
- 新的 MSGames 正式绑定事件自动授权，不自动开启隐藏；绑定与资格同事务提交，第三方资料同步在提交后执行。远端请求失败或返回空白姓名不影响绑定成功及已有资格，后续可刷新或重试验证以补齐资料。解绑保留资格及选择，重复验证、登录和同步不重新授权；上线前已绑定的用户由管理员手动补发资格。
- 有效实名是非空、非纯空白且不为“匿名”的 `realname`。没有实名时不能开启隐藏；已有资格的用户可以在首次设置有效实名时同时选择隐藏。清除实名会关闭隐藏并保留资格。
- 设置入口位于 `EditProfile.vue` 的 Real Name 区域，与其他资料共用 Save，提交 `POST /api/userprofile/update_profile`。姓名与隐藏选择同事务保存；失败按原有字段结果返回。管理员沿用 `/api/userprofile/admin/update/{user_id}` 修改资格。

### 姓名读取与缓存

`_realname`、`_firstname`、`_lastname` 保存原值，数据库列名仍为 `realname`、`firstname`、`lastname`。模型同名公开 getter 在有效隐藏时返回精确字符串 `hidden`，包括原本为空的英文名。`has_realname()`、姓名写入服务和本人／管理员 Schema 读取底层原值；ORM 查询、`values()`、`update_fields` 使用下划线字段名。

公共单用户、批量资料和录像查询返回公开姓名；前端识别 `hidden` 后统一显示“用户 #ID”／`User #ID`，忽略姓名格式偏好。本人 `info/0`、登录响应及管理员资料返回原值。三个姓名字段都禁止设置为规范化后的精确值 `hidden`。

这是展示偏好。账号关联返回的姓名、原始录像内容和原文件名保持原样；导出目录沿用 `{用户ID}_{公开姓名}/原文件名`。录像查询禁用按姓名排序。本人保存资料成功后立即使该用户的本地姓名缓存失效，已显示的 `PlayerName` 重新读取公开姓名；失败则恢复复选框为已保存的选择。其他浏览器仍按正常检查周期更新，不保证同时变化，缓存机制见 [userService.md](../../../front_end/src/services/userService.md)。

## 用户数据库列表

数据库默认页 `/database/users` 使用公开接口 `GET /api/userprofile/query`。通过 `platform + id` 精确查询；平台省略或为空时查本站用户，`c`、`a`、`w`、`m` 分别查扫雷网、MSGames、WoM、Mineracer 的已验证关联。ID 留空显示全部用户。响应字段和分页、排序参数由 Ninja API 文档提供。

没有 `UserMS` 的用户按零展示及排序；等待重算的负统计值仍保留。统计同值时按用户 ID 升序分页。关联 ID 使用字符串，未绑定的平台省略；Mineracer 暂无个人主页链接，仅显示 ID。

查询及索引见 [数据库与缓存说明](../../../vitepress_doc/zh/guide/development/cache.md)。`AccountLinkQueue` 的新增联合索引需使用 Django 生成并应用 `accountlink` 迁移。

## 数据库迁移

纪念账号的身份字段和认证约束需要迁移。仓库按现有约定忽略编号迁移文件，部署时保留服务器已有迁移历史，在 `back_end/saolei` 目录执行：

```sh
python manage.py makemigrations userprofile
```

如果环境尚未应用姓名隐私字段重命名，三个重命名确认均回答 yes。检查生成的迁移及 `sqlmigrate` 输出：原姓名列必须保留，姓名隐私部分仅新增两个布尔列；不能应用“删除旧姓名字段再新增空字段”的迁移。纪念账号部分另有身份字段和认证约束。确认后执行：

```sh
python manage.py migrate
```

存量资格不自动回填；由管理员按需授予。

## 验证

后端在 `back_end/saolei` 运行：

```sh
python manage.py test userprofile.tests accountlink.tests.NamePrivacyBindingTests --keepdb
python manage.py test common.test_memorial tournament.tests.test_gsc_history userprofile.test_deletion msuser.test_cleanup_orphans --keepdb
```

前端单元测试在 `front_end` 运行：

```sh
npm run vitest -- run src/utils/userprofile.test.ts src/services/userService.test.ts
npm run vitest -- run src/services/memorialService.test.ts src/components/GSCAdmin/history.test.ts
```

Cypress 由用户运行：

```sh
npx cypress run --component --browser chrome --headless --spec "src/components/PlayerName.cy.ts,src/views/UserView/EditProfile.cy.ts"
npx cypress run --component --browser chrome --headless --spec "src/views/StaffView/MemorialAccounts.cy.ts"
npx cypress run --e2e --browser chrome --headless --spec "cypress/e2e/realname-privacy.cy.ts"
```

E2E 使用隔离的测试数据库及 Redis，启用 `E2E_TEST=True` 并完成迁移，前后端地址按 `.github/workflows/CypressE2E.yml` 准备。用例会重置测试数据。合成 MSGames 账号 `2147483000`、`2147483001` 仅在 `E2E_TEST=True`、`DEBUG=True` 且无 `.production` 标记时返回固定外部资料，本地绑定与授权仍经过实际业务接口。
