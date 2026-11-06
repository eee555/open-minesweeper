# 该APP仅作为测试用途，所有API需使用`@local_only`限制访问权限，且仅允许测试环境使用。

## E2E 账号准备

多个账号使用 `cy.registerUsers([...])`，一次请求调用 `register_bulk`，返回按输入顺序排列的用户 ID。单账号仍用 `cy.registerUser(...)`；两者共用邮箱、密码和实名默认值，并通过相同 service 创建 UserProfile 与各自的 UserMS。

批量注册仍逐个走 Django `create_user`，保留密码哈希与保存逻辑；任一记录失败则整批数据库写入回滚，不保留孤立 UserMS。所有注册入口仍受 `local_only` 和 `E2E_TEST` 限制，不用于验证正式注册界面。

## 本地公开数据快照

- `public_snapshot.py`：导入及初始化编排，保留生产标记和本地测试环境检查。
- `download_public_data.py`：公开元数据快照下载入口，支持断点续传，下载所有已知公开用户的标识列表。
- `init_local_test.py`：本地快照导入及测试数据初始化入口，会清空本地数据库和对应 Redis 数据库，导入后自动重建扫雷网普通/NF 榜、强无猜普通/NF 榜、PB 普通/NF 榜等派生缓存。
- `cache.py`：本地快照的 Redis 检查与清理。
- `utils.py`：快照路径、JSON 读写及完整性校验，不依赖 Django 初始化。

两个入口均位于本 app 内，不在后端根目录保留转发脚本，也不注册管理命令，避免其他模块导入 `dangerzone`。在 `back_end/saolei` 目录使用模块方式运行，确保包导入和 Django 配置路径正确：

```bash
python -m dangerzone.download_public_data
python -m dangerzone.download_public_data --skip-details
python -m dangerzone.init_local_test
python -m dangerzone.init_local_test --no-weekly
```

默认数据目录仍为 `back_end/saolei/tmp/public-data`，不因入口迁移而改变。下载使用 `--output-dir`，导入使用 `--snapshot-dir` 指定其他目录。导入前停止本地 worker、定时任务及其他写入；生产标记和本地测试环境限制保持不变。

下载串行执行，每次响应完成后至少等待 1.25 秒再发送下一请求，保证 `/api/userprofile/videolist` 不超过每秒一次，并留出余量。`--interval` 可增加等待时间，不能降到 1.25 秒以下；遇到 429 仍按原有机制等待重试。

快照 v2 通过 `/api/userprofile/identifier?user_id=...` 获取每位用户的标识，保存在 `identifiers/<用户 ID>.json`。清单记录文件校验和、用户归属和标识总数，零标识用户也保留空列表。导入前检查所有用户均有标识文件、标识长度及全局唯一性；异常会在清空本地数据前中止。

同一用户列表中的重复标识会在下载时去重并写回缓存文件；不同用户重复拥有同一标识仍视为归属冲突并中止。

导入同时恢复 `UserMS.identifiers` 和已审核通过的 `Identifier` 记录及其归属。快照恢复批量写入这两处数据，不调用日常绑定服务，避免改变快照已有的录像状态；排行和缓存仍在导入后统一重建。下载范围是绑定到公开用户的标识，不包含未绑定或未公开的标识记录。

对旧版已完成快照，重新运行下载入口会仅补充标识文件并升级清单，不重新请求用户资料或录像；补充过程可断点续传。旧版快照仍能导入，但标识为空，初始化会提示先补下载。

生产录像列表已提供 `right_ce`，使用 `--skip-details` 的列表回退也能保留 NF 判断所需的数据。详情缺少该字段或值为 NULL 时，使用列表提供的值，包括 0；旧快照缺失时仍保持 NULL，不根据旧 NF 模式推测。已完成的快照不重新下载已有数据（旧版补充标识除外），更新这类数据请使用新的 `--output-dir`，初始化时指定对应的 `--snapshot-dir`。

仅检查入口和静态安全限制，不下载数据或清库：

```bash
python -m dangerzone.download_public_data --help
python -m dangerzone.init_local_test --help
python -m pytest static_tests/
```
