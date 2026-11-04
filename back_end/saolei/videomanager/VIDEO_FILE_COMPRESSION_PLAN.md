# 录像文件压缩方案（已完成）

更新：2026-11-01。

**状态：已完成。管理员于 2026-11-01 确认本计划全部完成，按此结项。** 以下保留最终实现约定、生产完成记录和后续维护说明。

哈希字段、存量回填、解析前查重和唯一约束已完成生产迁移。管理员于 2026-10-29 确认空哈希数量为 `0`，于 2026-10-30 确认唯一约束迁移完成。

后端存储和前端解压已实现并部署，**新上传、导入时立即压缩，历史文件使用手动管理命令转换，不注册 APScheduler 压缩任务**。压缩字段及索引已完成生产迁移，播放、下载、文件名及旧文件清理核对通过，历史录像全量转换结果为 `converted=240751, failed=0, skipped=0`。

flop-player 和 StrangeDust 的播放器包装、选择入口和信任设置移除；旧持久化设置自动清除相应键，统一使用原生播放器。VideoAnalyzer 页保留 StrangeDust 外链，继续通过 `replay` 参数传递本站录像预览 API 地址，由对方处理压缩格式。

## MSRC 与版本

- 后端使用官方 `msrc==0.2.0` release wheel，复用 `requirements-wheels.txt → wheels/ → --find-links` 流程；平台和 SHA-256 固定，不在生产编译 Rust。
- 前端依赖 `@putianyi888/msrc@0.2.0`，使用浏览器 ESM 构建。库维护算法、格式和旧解码器，网站不重复实现算法。
- `videomanager.config.TARGET_COMPRESSION_FORMAT = (1, 1, 2)` 是唯一目标常量，压缩时显式传入算法版本 `2`。包发布号与格式版本分开。
- `compression_format` 使用无符号 32 位整数，按容器版本 8 位、算法 ID 8 位、算法版本 16 位打包；原始文件为 `0`，当前目标为 `0x01010002`。没有另外的算法编号或运行时位宽检查。
- Python 与 JS 均调用 MSRC。现有上游性能报告已经包含 CPython/PyO3 绑定；本轮复用该结果，不增加浏览器性能 benchmark，只验证加载和还原正确性。

## 数据库与缓存字段对照

| 字段 | 改动前 | 改动后 |
| --- | --- | --- |
| `VideoModel.file` | 原始文件相对路径 | 当前存储的原文件或独立 `.msrc` 文件路径；增加普通索引用于清理时检查引用 |
| `original_filename` | 无 | 可空 `CharField(max_length=255)`；新上传直接保存原始 basename，旧记录转换时补齐 |
| `stored_file_size` | 无 | 可空 `PositiveIntegerField`；新录像记录实际存储字节数，压缩校验失败保存源文件时等于原始大小，历史原文件空值回退到原始大小 |
| `compression_format` | 无 | `PositiveIntegerField(default=0)`，建立普通单列索引，保存实际文件头格式的打包值 |
| `compression_failed` | 无 | `BooleanField(default=False)`，失败后跳过常规转换，仅手动重试 |
| `file_size` | 原始录像大小 | 含义不变，不被归档大小覆盖 |
| `original_hash` | 原始字节 SHA-256 前 96 位，24 位小写十六进制，唯一且可空 | 保持不变；查重仍只按该哈希，转换不改变摘要 |
| 前端录像静态缓存 | 解析字段及原始 `file_size` | 不变，不增加压缩文件缓存或升级缓存版本 |
| 监控中的录像占用 | 汇总 `file_size` | 汇总 `stored_file_size`，旧原文件空值回退到 `file_size` |
| `UserMS.video_size_total/tournament/all` | 汇总原始 `file_size` | 汇总实际 `stored_file_size`，空值回退到 `file_size`；部署统计口径变更后运行一次 `refresh_video_counts` |

新增字段和索引的迁移由 Django 自动生成，沿用仓库忽略各环境迁移文件的约定。不在结构迁移中读取、解析或压缩录像。

## 后端文件生命周期

上传和各平台导入继续在解析前计算一次哈希、索引查重；命中则按原业务拒绝或复用，不重新解析或压缩。未命中只解析一次，再由共用的 `VideoModel.create_from_parser` 在内存中按目标常量压缩并完整解压校验；成功后直接保存 UUID `.msrc` 文件及实际存储元信息，不先向录像存储写入原文件、不执行路径切换。压缩或校验失败时正常创建录像，但只保存源文件，`compression_format=0`、`stored_file_size=file_size`、`compression_failed=True`，并记录失败日志；不会保存未通过校验的归档，后续可用 `--retry-failed` 手动重试。源文件读取、存储写入或数据库失败仍正常报错。原始上传文件保持可读并复位，原始文件名、大小和哈希的业务含义不变。

普通上传、纪念账号导入及 GSC 历史录像相关路径的 Nginx `uwsgi_read_timeout` 设为 12 秒，略高于普通请求的 uWSGI 10 秒上限；MSGames 保留外部 I/O 请求的既有 95 秒网关和 90 秒后端上限。部署时需同步应用对应 Nginx location 并校验、重载配置，仅重启 Django 不会更新网关超时。

`videomanager.files` 不引入模型，统一负责恢复原始字节、调用 MSRC、检查实际格式及完整往返还原。重解析、后台 pluck、哈希回填使用原始字节；原始文件的哈希回填仍分块读取，不对 MSRC 容器字节算原始摘要。默认解压输出上限 64 MiB、解码器工作内存上限 64 MiB；这不是整个进程的内存上限。

历史原文件及需要升级格式的已有文件，由 `videomanager.services.compress_video_file` 编排转换；已符合目标格式的新录像直接跳过：

1. 记录原路径、实际格式、原文件名、原始长度及哈希。
2. 在数据库事务及行锁之外读取原始字节，核对已存长度、哈希；已有 MSRC 文件先还原，不给旧容器再套一层压缩。
3. 使用目标常量压缩，`inspect` 的三元组必须严格相符；完整解压后逐字节比较原始内容。
4. 写入同目录下独立 UUID `.msrc` 文件，再检查实际保存字节与已校验归档一致。
5. 以主键、原路径及原格式未变化为条件，在短事务内锁定录像并一次更新所有存储元信息。使用 `QuerySet.update()`，不触发普通保存信号或排行、录像数量、缓存更新；仅通过 `video_storage_changed` 在同一事务按大小差额同步 `UserMS` 文件空间。
6. 提交成功后检查旧路径引用并立即清理。允许已取得旧路径的瞬间播放、下载失败，重新请求读取当前文件。不增加旧文件宽限期、清理队列、转换中状态或 503 管线。

条件更新未命中时不覆盖新状态，仅检查并清理无引用的新归档。数据库提交结果不明时保留文件供核对；旧文件清理失败记录日志，进程中断残留的无引用文件由后续人工处理。django-cleanup 继续处理一般模型删除；本转换流程显式管理文件切换和清理。

单个文件缺失、损坏、大小或哈希不符、往返校验失败时，保留原路径及实际格式，设置 `compression_failed=True` 并继续。磁盘空间不足、只读存储、权限或依赖配置错误停止整批，不把后续正常文件批量标记失败。目标版本变化也不自动清除失败标记。

## 手动转换命令

```sh
python manage.py compress_video_files --dry-run
python manage.py compress_video_files --start 1000 --end 1100 --batch-size 100
python manage.py compress_video_files --retry-failed
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--start` | `0` | 包含的起始 ID |
| `--end` | 不限制 | 不包含的结束 ID |
| `--batch-size` | `100` | 每批读取记录数 |
| `--dry-run` | 关闭 | 仅列出候选，不读写文件或修改标记 |
| `--retry-failed` | 关闭 | 仅重试失败文件 |

普通模式先排除失败文件，再 `exclude(compression_format=target)`，不指定 ID 排序、格式分组或持久化游标。一次命令固定目标和候选 ID 集合，分批读取元信息并显示逐条进度；每条在本次执行中最多尝试一次。显式失败重试即使实际格式已经匹配目标，也重新转换并完整校验。成功清除失败标记，再次失败则保留原文件、原格式及标记。

## 文件接口对照

| 接口或响应 | 改动前 | 改动后 |
| --- | --- | --- |
| `GET /api/video/preview?id=123` | `id=123.evf`，返回当前存储的原文件或 MSRC 容器 | 仅传数字 ID，返回存储字节；已压缩录像返回 MSRC，旧录像或压缩失败的录像仍返回源文件 |
| `GET /api/video/download/123` | 返回当前存储的原文件或 MSRC 容器 | 仅传数字 ID；后端解压 MSRC，始终返回原始录像字节 |
| `Content-Type` | `application/octet-stream` | 不变，不使用自定义 `Content-Encoding` |
| `Content-Disposition` | 原文件使用原名；MSRC 使用原名加 `.msrc` | preview 保持原规则；download 始终使用原文件名，不加 `.msrc` |
| `X-Replay-Container-Version` | 原文件 `0`，MSRC 为实际容器版本 | preview 保持原规则；download 始终返回 `0` |
| 按 IP 限流 | 两个接口均为 `20/m` | preview 为 `20/m`；download 收紧为 `5/m`，限制请求中的解压消耗 |
| `Access-Control-Expose-Headers` | preview 暴露文件名 | 两个接口均暴露文件名及容器版本头 |
| `analyzer-info.filename` | 物理路径 basename | 逻辑原文件名；旧原文件元信息为空时回退原 basename |
| `GET /api/tournament/download` | 整场录像包 | 删除 |
| `GET /api/tournament/download/participant` | 个人比赛录像包 | 删除 |

preview 在生产环境使用 `X-Accel-Redirect`，DEBUG 返回相同存储字节的 `FileResponse`，不在请求中压缩。download 对压缩录像复用 `original_file`，在内存中解压并通过 `HttpResponse` 返回，避免将内存缓冲区交给 uWSGI 的文件发送接口；不创建临时文件、不修改存储、不缓存解压结果。源文件下载在生产环境仍可使用 `X-Accel-Redirect`。当前存储路径、版本和文件名来自同一份录像记录。保留原权限：公开录像可访问，未公开比赛录像仅本人可访问，staff 无新增豁免。公共 CORS 路径范围不扩大，内部媒体 location 仍禁止外部直接访问。

生产 CORS 统一由 `default.conf` 中的 map 和 HTTPS server 响应头管理，沿用原公开 API 白名单，只允许跨域 GET，不允许跨域凭据；按原始 `$request_uri` 匹配，内部重定向不会把权限扩大到全部媒体。Nginx 隐藏上游 CORS 头以避免旧 worker 造成重复，并从 `$upstream_http_x_replay_container_version` 恢复版本头。GET 的 OPTIONS 预检由 Nginx 返回 204，`Access-Control-Allow-Methods` 仅声明 `GET`；其他方法不返回允许跨域的响应头，不改变接口自身的 HTTP 方法及权限。DEBUG 直连 Django 的开发和 Cypress 请求仍使用原有 `django-cors-headers` 策略，统一暴露录像文件名、版本和小游戏成绩头；业务 API 不自行设置 CORS 头。

直接调用 preview 的外部客户端需要识别响应头并处理两种格式；需要原始录像的客户端可调用 download，无需解码 MSRC。网站按钮保存还原后的原始录像。整场和个人比赛打包 API、专用文件流及前端转换工具已移除，比赛录像列表、成绩、单条访问规则保留。

## 前端加载与保存

`replayFileService` 统一请求、识别协议、恢复文件名、转交 Worker 解压，返回原始 `{ data, filename }`。原文件直接返回，不创建 Worker、不加载 MSRC；缺失或无效协议头报告错误。

第一次实际处理压缩录像时才创建本站 Worker，由它动态加载固定版本 jsDelivr `web/msrc.js` 和配套 Wasm，失败或超时回退本站同版本副本。副本来自固定 npm 依赖，通过 Vite URL 资产构建；不在首次访问首页、浏览榜单或显示录像链接时下载解码器。初始化和串行队列复用，失败后允许重试。

Worker 使用可转移 ArrayBuffer 返回结果，按请求 ID 对应调用方；取消或切换录像后丢弃旧结果，避免覆盖新录像。请求、解压及下载保留 loading，错误允许重试。网站不维护算法分派或自行解析 MSRC 二进制头。

原生播放器及站内分析器通过纯 ID 请求 preview；打开播放器无需先查询软件，文件名由响应头提供。原生播放器保存已解压的 File；分析器下载按钮复用 preview 已加载、解压后的 `source.data` 及 `source.filename`，通过 `downloadBlob` 保存原始录像，不额外请求 preview 或 download，也不重复解压。录像来源尚未就绪或切换后已清空时禁用该按钮，网站元信息加载失败不影响已加载录像的保存。StrangeDust 链接仍传递 preview 地址，不再等待软件信息。公共分析器和离线分析器继续接收原始录像，不引入网站存储协议；Analyzer 版本号保持不变。

## 生产完成记录

- 压缩字段及索引迁移完成；MySQL 迁移中断后核对实际结构、补齐剩余操作，再记录该迁移完成。
- 新上传录像的 preview 返回 MSRC，网页正常解压播放；播放、下载和文件名核对通过。
- 历史录像小范围转换后的旧文件清理核对通过。
- 历史录像全量压缩完成：成功 240751 条、失败 0 条、跳过 0 条，本批无需失败重试。
- 管理员确认计划全部完成，不再保留待验收事项。

## 后续维护与回归

未来调整目标格式时，更新目标常量并使用手动转换命令处理存量；失败记录按需 `--retry-failed`，不启用定时自动压缩。备份清理独立安排。

重新部署时先安装固定版本依赖、执行结构迁移，完整同步 `default.conf` 的 http 层 map、HTTPS server 响应头和上传/导入超时配置，执行 `nginx -t` 后重载，再更新后端及前端资源。MySQL DDL 失败后须核对实际字段和索引状态，不假定整批结构修改自动回滚。

回退需要同时考虑数据库路径、对应文件和前后端协议。只回滚前端不能播放已返回的 MSRC；只回滚数据库也不能恢复已删除的原文件。

后端验证覆盖新录像仅写入已校验归档、往返字节或格式校验失败后保存源文件并返回版本 `0`、手动重试，以及历史文件的实际 MSRC 往返、存储条件切换、失败跳过和重试、原文件保留、路径并发变化、重解析、哈希回填和访问权限。前端单元测试使用 Python 生成的 MSRC 样本和实际 npm 解码器；不重复上游算法 benchmark。

相关 Cypress 组件测试命令，供后续回归使用：

```sh
npx cypress run --component --browser chrome --headless --spec "src/components/VideoPlayer/NativePlayer.cy.ts,src/components/VideoPlayer/App.cy.ts,src/views/VideoAnalyzerView/App.cy.ts,src/views/VideoAnalyzerView/WebsiteReplayInfo.cy.ts"
```

