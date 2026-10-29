# MSGames 资料与录像导入

记录日期：2026-10-14；更新日期：2026-10-19。当前使用 [msgames-api v0.1.1](https://github.com/putianyi889/msgames-api/releases/tag/v0.1.1)。首次调研基于 v0.1.0，源码提交为 `fad7a5df77e02c87508106f3282278c082761584`。当前业务通过 `accountlink/msgames/client.py` 调用库，由 `services.py` 保存资料和录像列表；旧的 MSGames XPath 抓取已移除。

## 结论

已使用同步 `Client.get_profile()` 替换资料页抓取，保留姓名、本地姓名和加入日期，新增国家、地区、惯用手和鼠标的原文文本。根据用户决定，这四个字段不限定枚举。昵称、外部网站链接和排名不保存，也不增加排行榜、世界纪录或历史排名的业务入口。

新增 `VideoMSGames` 保存原始录像 URL、文件名、上传日期、分类字符串和成绩字符串，以及站内录像引用。原始 URL 的 SHA-256 保存为全局唯一的 `source_key`，`user` 记录账号归属；同步仍按账号和键查找，避免将其他账号的记录改绑。跨指标、普通和 NF 标签中的分类与成绩合并为多行字符串，不存完整响应或独立数值成绩列。不同 URL 的相同文件可关联同一个站内 `VideoModel`。列表同步和单条导入在普通 API 中同步执行；批量由前端循环等待每次响应，不创建 MSGames 后台任务。

该包是 MIT 许可的非官方 Alpha 客户端，仍通过公开 HTML 和网站脚本中明确出现的 GET 入口获取数据，不是官方稳定 JSON API。替换可以把网站专有解析交给独立包维护，但不能消除页面结构变化的风险。公开资料不能证明账号归属，现有账号审核流程继续适用。

## 当前调用和字段覆盖

管理员验证先通过 `services.verify_account_link()` 提交绑定及隐藏资格，再调用 `update_account()` → `update_msgames_account()` → `msgames.client.fetch_profile()`，只读一次公开资料页。第三方拉取或资料保存失败不影响绑定成功，验证接口仍返回成功并记录同步失败日志；资料暂缺不表示绑定失败。用户可主动刷新资料，管理员也可重试空名绑定的验证以补齐资料，但不会重新授权。独立资料拉取的客户端错误使用 HTTP 503；五类成绩历史由单独的列表同步 API 读取，不在刷新基本资料时抓取。

管理员解绑使用 `POST /api/accountlink/unverify/`，以表单提交 `id`、`platform`、`identifier`；旧 `/accountlink/unverify/` 已移除。关联账号与申请队列行同事务删除，待验证申请也可取消，用户随后可以申请正确的 MSGames ID。已有隐藏资格及选择保留。Mineracer 继续禁止人工解绑。

资料模型为 `AccountMinesweeperGames`，Ninja 输出通过 `create_schema` 自动生成；前端 `AccountMSGames` 和 `CardMsgames.vue` 展示资料，并以按需创建的对话框提供分页录像列表与导入管理。

| 现有字段 | 包字段 | 接入处理 |
| --- | --- | --- |
| `id` | `Profile.player_id` | 包中的 ID 是请求上下文，不是额外的账号归属证明 |
| `name` | `Profile.name: str` | 直接映射，校验不超过模型的 128 字符限制 |
| `local_name` | `Profile.local_name: str \| None` | 保留现有行为时使用 `str(profile.local_name)`，使缺失值仍为字符串 `"None"` |
| `joined` | `Profile.joined: date \| None` | 直接保存已解析日期；非空原始日期解析失败时应报错，避免清空已有日期 |
| `update_time` | 本地同步时间 | 显式加入 `update_fields`，仅成功刷新时更新 |
| `country`, `state`, `hand`, `mouse` | 可空公开文本 | 保存为无枚举的 TextField，缺失时用空字符串 |
| `video_update_time` | 本地列表同步时间 | 全部五类历史读取、校验和保存成功后更新 |

旧实现将缺失本地姓名转为字符串 `"None"`，适配层继续保持这个约定。资料与原始日期校验失败时，已有资料和成功刷新时间均保留。

旧保存逻辑没有包含 `update_time`，导致 `auto_now=True` 不会在刷新时运行；当前实现已修正。

## 包提供的额外数据

以下是由 [API 文档](https://github.com/putianyi889/msgames-api/blob/v0.1.1/docs/api.md)和源码核对的包能力。本次仅使用资料读取、五类成绩历史中的录像元数据和原始文件下载；其余入口不调用：

| 能力 | 公开数据 | 接入边界 |
| --- | --- | --- |
| `get_profile()` | 昵称、国家、地区、惯用手、鼠标、外部网站链接，以及世界／国家各项目的排名和参加人数 | 资料刷新仍是一个请求；扩展哪些字段需按业务需求决定，不保存整个 `fields` 字典 |
| `get_records()` | Time、3BVS、IOE、Density、Problems 五类成绩历史；日期、难度／分组、FL/NF 风格、时间、3BV、3BV/s、IOE、雷数、程序、版本、类别、备注与原始录像链接 | 每个类别单独请求；公开成绩历史不等于累计游戏次数、胜场或游玩时长 |
| `get_ranking()` 等 | 世界、Arbiter、国家／地区和密度排行榜；显式分页及选项 | 排名刷新与资料同步应分别设计；国家／地区查询依赖匿名会话状态 |
| `get_world_records()` | 世界纪录历史，包括被拒绝成绩及说明 | 编辑维护的历史清单可能落后于当前排行榜，不能相互覆盖 |
| `download_replay()` | 公开链接的原始 AVF、MVF、MVR、RMV 文件 | 下载不等于解析或完成站内录像导入；MVR 不在本项目现有上传解析器支持的扩展名中 |
| `get_historical_ranking()` | 历史排名入口 | 实验性功能；上游调查中请求返回 HTTP 500，本轮未复测，不作为替换依据 |

照片和传记需要登录，不在包的公开数据范围内。包不提供登录、上传、修改资料或绑定授权。

成绩数值使用 `Decimal`，时间是页面显示的秒值；`to_dict()` 会把 Decimal 和日期转为字符串。若后续增加毫秒成绩，需显式转换单位，不能将整个 `to_dict()` 直接赋给现有模型。库默认合并普通和 NF 标签中的重复录像并保留分组；计算 NF 成绩时应结合 `style` 与分组，不能把标签当作互斥分类。计算 PB 还需明确哪些 `category` 可计入，不能把 Problems 或被拒绝成绩当作普通有效成绩。

## 同步、导入与日期规则

资料读取使用上下文管理器释放同步 Client。请求采用 HTTPX 各阶段五秒超时，HTML 采用库默认八 MiB 上限，原始文件采用本站五 MiB 上限；不关闭 TLS 验证。超时映射为 `import/timeout`，其他请求错误为 `import/requestexception`，解析或字段校验失败为 `import/indexerror`。非空但无效的 Joined／录像日期不作为缺失值保存。

列表同步 API 在同一个客户端中依次读取 Time、3BVS、IOE、Density、Problems，收集全部带原始链接的行；无原始链接的行不创建录像记录。五类全部读取和校验成功后才在事务内保存，失败不会留下部分新列表。库在单个实例内串行并至少间隔一秒，多个客户端不提供全站共享限流。

v0.1.0 会将缺少难度标签和成绩表格的正常空成绩页误判为 `ParseError`，使整次同步返回 `import/indexerror`、HTTP 502。2026-10-19 已用账号 7714 复现：五类页面均返回 HTTP 200，但空 Problems 页触发该异常。v0.1.1 修复了正常空内容区的识别，仍会拒绝非空异常页面和缺失内容结构；网站继续读取全部五类，不跳过 Problems。

导入业务参考 VideoSaolei：仅已验证关联账号本人能够导入；API 调用包的 `download_replay()`，对原始文件计算一次 SHA-256 的前 96 位，通过 `original_hash` 索引查重。命中时直接复用已有录像，不读取已存文件、不运行 parser；未命中才用本站 `MSVideoParser` 检查完整性和合法性，并对标识不匹配的合法录像保留 `IDENTIFIER` 审核状态。原文分类中的 Official 不会强制改变本站审核状态。新录像通过 `VideoModel.create_from_parser(..., original_hash=...)` 保存已算好的摘要。成功返回站内录像 ID 和审核状态，已导入的来源再次请求直接返回已有录像；外站请求失败返回 HTTP 502，文件解析／校验失败返回 HTTP 400，保留 `type/object/category` 错误正文，前端显示失败原因并允许重试。下载后先锁定同一来源并复查导入引用，再查重、解析及保存，避免重复创建该来源的录像。

用户已确认页面 Date 为上传日期。模型保留日粒度的 `upload_date`，回填站内 `upload_time` 时取**次日 00:00:00 UTC**，作为上传日期用于纪录 tiebreaker 的最坏边界。例如 `2020-02-29` 回填为 `2020-03-01T00:00:00Z`。不取当日零点或 23:59:59，也不把今天上传的次日边界截断到当前时刻。如果相同文件在站内已有更早的上传时间，则保留更早的时间；缺少来源日期时保留站内导入时间。

列表保留 MVR 链接与成绩，但本站解析器当前只支持本来源的 AVF、MVF、RMV；前端批量循环跳过 MVR，前端明确显示不支持导入。原始链接仍可直接查看。解绑只删除该关联账号的来源记录，已导入站内的文件保留。

Density 对应 custom 配置，导入范围复用 `config/customranking.py` 的四种配置：8×8／40 雷、16×16／100 雷、30×16／150 雷、30×24／200 雷（尺寸按列×行展示）。同步时从上游的棋盘分组和 `Mines` 解析配置，不能仅根据棋盘尺寸或文件名判断；分类和成绩仍保存为原文字符串，内部 `density_levels` 仅用于配置检查，不在列表 API 中暴露。列表不返回 `can_import`；前端根据文件扩展名、分类中的棋盘尺寸和成绩中的雷数判断，复用 `utils/customlevel.ts` 的四种 Density 配置。其他配置、缺失尺寸或雷数、合并后有不支持配置的录像，均保留原始链接但隐藏导入／重试按钮，并从批量候选中排除；后端单条导入仍在下载前独立校验。旧 Density 记录缺少内部结构化配置时，需重新同步列表后才能通过后端校验。

## API 与前端

MSGames 专属路由、响应 Schema 和接口权限检查位于 `accountlink/msgames/api.py`，由 `saolei/api.py` 注册到 `/accountlink/msgames/`；通用账号关联接口仍位于 `accountlink/api.py`。

| Ninja 路径 | 用途 |
| --- | --- |
| `GET /api/accountlink/msgames/videos?msgames_id={id}` | 一次返回全部本地录像，响应为数组 `[...]`，不返回 `count` 或 `can_import`，不需要 `page`，不抓取外站；已验证账号可公开查看 |
| `GET /api/accountlink/msgames/summary?msgames_id={id}` | 列表更新时间、总数和已导入数量 |
| `POST /api/accountlink/msgames/{id}/sync` | 无需 `mode`；同步五类历史后返回 `status=SYNCED`、`count`、`video_update_time`，不导入录像 |
| `POST /api/accountlink/msgames/videos/{id}/import` | 本人单条同步导入；返回 `status=IMPORTED/ALREADY_IMPORTED`、`import_video_id`、`video_state` |

新增接口均限流，单条导入限制为每用户每分钟 60 次，列表同步限制为每用户每小时 6 次。未验证账号的列表只向本人或管理员开放；其他用户看不到。前端显示原始链接、上传日期、分类和保留精度的成绩字符串，可翻页；本人能够同步列表、批量导入或重试失败的单条请求。

录像列表使用 PrimeVue DataTable。打开／刷新时一次请求取得完整列表，分页、上传日期升降序排序、分类包含查询和导入状态筛选全部在前端完成；默认每页 10 条，翻页不重新请求 API。分类输入框与状态选择框和各自的表头标题放在同一行；查询或筛选改变时回到第一页。状态包括未导入、正在导入、已导入、失败和不支持，失败状态与原因保留在当前对话框中。筛选只影响表格展示，批量仍处理完整列表中尚未导入且支持的录像。

批量先等待列表同步完成，再从完整列表中选出未导入且前端判断支持的候选，逐条发送单条导入 API 并等待响应。每条之间至少间隔 1.1 秒以适配接口限流；失败项记录在当前对话框中并继续后续项，显示已处理数和失败数。停止按钮在当前请求结束后停止后续请求；关闭对话框或切换账号后也不再发送下一条，已经在服务器执行的请求仍可能完成。无需状态轮询，重新打开时读取已保存的导入引用；请求响应有版本检查，避免账号／页面切换后旧响应覆盖新列表。同步与导入请求单独使用 120 秒客户端等待时间，其他接口仍使用项目原有超时配置。

## 生产请求超时

仓库原配置对 API 设置 `uwsgi_read_timeout 2`，uWSGI 全局 `harakiri=10`。同步列表涉及五次外站读取，单条导入还包括下载、解析和保存，仅增加 Axios 的等待时间无法绕过这两层限制。

当前配置将超时分层设置：

| 层 | MSGames 配置 | 范围与含义 |
| --- | --- | --- |
| 外站 HTTPX | 5 秒 | 建连、读、写和连接池各阶段的等待限制；不是整个导入的总耗时上限 |
| uWSGI | 90 秒 | 全局上限设为 90 秒；内部路由为其他路径额外设置 10 秒计时器，仅 `/api/accountlink/msgames/{id}/sync` 和 `/api/accountlink/msgames/videos/{id}/import` 使用完整 90 秒预算 |
| Nginx | 95 秒 | `default.conf` 中更具体的 `/api/accountlink/msgames/` location；上游建连限制为 5 秒，其他 API 的读取超时仍为 2 秒 |
| 浏览器 Axios | 120 秒 | 同步列表与单条导入两个请求，其他接口保持原配置 |

Nginx [`uwsgi_read_timeout`](https://nginx.org/en/docs/http/ngx_http_uwsgi_module.html#uwsgi_read_timeout) 是两次读取之间的等待时间；这些 API 完成后才返回 JSON，因此通常体现为等待后端完成的时间。[HTTPX 的 read timeout](https://www.python-httpx.org/advanced/timeouts/) 同样约束等待下一个数据块，不是总下载时长。90 秒 uWSGI 上限为整次请求保留有限预算，超过上限时 worker 会被终止，不能视作应用返回了完整的失败结果；重新读取列表可确认录像是否已保存。

uWSGI 的 [`harakiri` 内部路由](https://uwsgi-docs.readthedocs.io/en/latest/InternalRouting.html#harakiri) 需要其构建包含 PCRE 和相应路由支持。该动作设置的是独立的 user harakiri，不能延长已有的全局计时器：[路由源码](https://github.com/unbit/uwsgi/blob/master/core/routing.c)调用 `set_user_harakiri`，[主进程源码](https://github.com/unbit/uwsgi/blob/master/core/master_checks.c)分别检查两种计时器。因此不能保留全局 10 秒、仅给 MSGames 加一条 90 秒路由；当前采用全局 90 秒加普通请求 10 秒路由的组合。

部署时核对启动日志没有 `no internal routing support` 或未知 `route`／`harakiri` 动作错误，并确认内部路由表加载了上述限制。如果构建不支持内部路由，普通请求的 10 秒限制不会生效，应先补齐相应支持再部署这份配置。不能仅重载 Nginx，否则正在运行的旧 uWSGI 配置仍会在 10 秒终止长请求。

将 `default.conf` 同步到服务器实际加载的配置文件后，先检查再重载：

```bash
sudo nginx -t && sudo nginx -s reload
```

然后按现有部署方式重启 uWSGI，让更新的 `uwsgi.ini` 生效。仓库 `start.sh` 会复制 `default.conf` 并使用 `uwsgi.ini` 启动；仅推送代码不会保证正在运行的服务已加载这些设置。可通过 `sudo nginx -T` 核对实际 location，通过 uWSGI 启动配置／日志核对路由支持，再通过 Nginx 入口测试列表同步和单条导入。本地 Windows 环境未执行 Nginx 配置检查或 uWSGI 路由运行测试，也未修改生产服务器。

## 依赖与服务器分发

包支持 Python 3.11+，运行依赖为 `httpx>=0.27,<1` 和 `beautifulsoup4>=4.12,<5`。网站当前本地 Python 3.12 环境已有 HTTPX 0.28.1、Beautiful Soup 4.15.0，满足要求；生产环境版本未核对，不据此宣称生产安装不会修改依赖。

当前发布 wheel 为 `msgames_api-0.1.1-py3-none-any.whl`，大小 17,275 字节。实际下载文件的 SHA-256 与 GitHub Release 资产 digest 一致：

```text
e4727ce3cbdf11426c30ac00b974618acdad7525165019d6e0922a5caf4d1fe2
```

`requirements.txt` 已添加：

```text
msgames-api==0.1.1
```

`requirements-wheels.txt` 已添加：

```text
msgames-api @ https://github.com/putianyi889/msgames-api/releases/download/v0.1.1/msgames_api-0.1.1-py3-none-any.whl#sha256=e4727ce3cbdf11426c30ac00b974618acdad7525165019d6e0922a5caf4d1fe2
```

当前网站部署 workflow 按整份 `requirements-wheels.txt` 下载、对 `wheels/*.whl` 生成校验清单，并上传整个 `wheels/` 目录，无需增加第二套上传步骤。开发端下载后、生产端收到上传包后，继续使用 `pip install --find-links wheels -r requirements.txt`；仅执行 `pip install -r requirements.txt` 不会发现该目录。

迁移 `accountlink/migrations/0013_msgames_profiles_and_replays.py`、`0014_msgames_density_levels.py`、`0015_msgames_synchronous_import.py`、`0016_msgames_unique_source_key.py` 由 Django `makemigrations` 生成。0015 移除 MSGames 的账号批量任务和录像单条任务引用；0016 移除账号与键的联合唯一约束，将 `source_key` 改为单独唯一。已在本地 MySQL 测试数据库应用，未在生产数据库执行。项目忽略新迁移文件，提交时需显式收录：

```bash
git add -f back_end/saolei/accountlink/migrations/0013_msgames_profiles_and_replays.py back_end/saolei/accountlink/migrations/0014_msgames_density_levels.py back_end/saolei/accountlink/migrations/0015_msgames_synchronous_import.py back_end/saolei/accountlink/migrations/0016_msgames_unique_source_key.py
```

## 验证证据

2026-10-19 升级验证：0.1.1 发布 wheel 的实际 SHA-256 与发布资产 digest 一致，在本站 Python 3.12 虚拟环境中安装成功，`pip check` 通过。网站回归用例使用真实 SDK 与 HTTPX MockTransport，覆盖四类有成绩、Problems 内容区为空的完整五类读取；该用例在 0.1.0 下复现原异常，在 0.1.1 下通过。实际只读调用 `fetch_replays(7714)` 成功取得 99 个原始录像链接，上传日期均存在；未写入实际账号数据库，也未下载或导入这些录像。实时数量仅记录该次样本，不作长期断言。

以下为首次接入 v0.1.0 时的验证记录：

- 发布源码检出固定 tag，85 项离线测试在现有 MSGames 开发环境的 Python 3.14 上全部通过。测试使用合成 HTML 和 HTTPX MockTransport，不代表所有实时入口都经本轮验证。
- 发布提交的 [CI](https://github.com/putianyi889/msgames-api/actions/runs/38555507997) 和[发布 workflow](https://github.com/putianyi889/msgames-api/actions/runs/38555507931) 已确认成功。
- 真实发布 wheel 通过固定哈希下载，使用网站 Python 3.12 的 pip 安装到临时 `--target` 目录，未改变网站虚拟环境中的包；HTTPX 和 Beautiful Soup 使用该环境已有依赖。
- 在网站 Python 3.12 中用发布 wheel 的同步 `Client` 读取原有测试账号 7872，取得 `Ze-En JU`、`鞠泽恩`、`2019-05-28`，与现有断言一致。
- 读取原有隐私账号测试 ID 8371，取得姓名 `Private`、本地姓名 `None`、加入日期 `2020-06-09`，确认需要保留缺失本地姓名的适配。
- 同账号 7872 的 Time 和 3BVS 历史读取分别得到 92 和 121 条去重成绩，都带原始录像链接；本轮样本的类别均为 `Official`，同时包含 FL 和 NF。实时数量可能变化，不能作为长期固定断言。
- 下载一份公开 AVF，大小 67,086 字节，SHA-256 为 `4a493254c90c08cf393c87ebfe9d9bbf7eb4a59e46d5fe9c5529834ec5b6e21f`。项目现有 `ms_toollib.AvfVideo` 完成 `parse()` 与 `analyse()`，识别为已完成的 16×30、99 雷棋盘，时间 199210 毫秒，3BV 181。原始文件仅存临时目录，不纳入仓库。
- 本轮默认 HTTPX TLS 验证即可访问两个资料页，无需关闭证书校验或使用系统证书注入；其他环境仍需单独核对 TLS。

MSGames 专项测试覆盖文本字段、全指标链接合并、次日零点回填、去重、审核状态、失败保留数据、完整列表契约、本人权限、解绑保留站内文件、Density 四种配置和未知／冲突配置，以及同步导入响应、重复请求幂等、失败响应与重试。测试与合成 HTML fixture 统一放在 `test/`，不依赖实时资料值；四种 Density 配置与 MVR 格式拦截统一由导入 API 用例覆盖，资料文本映射合并到数据库刷新用例，删除重复的成功路径断言。不维护旧分页参数或后台任务表断言：

```powershell
python manage.py test accountlink.msgames.test --keepdb --noinput
```

本轮清理后，28 项 MSGames、13 项 WOM 和 12 项现有任务删除／重启测试共 53 项通过，修改的后端测试文件 flake8 通过。跨账号重复 `source_key` 被拒绝且保留原归属，完整列表直接返回数组且不含 `can_import` 的断言继续保留。此前接入轮的后端静态安全测试 7 项、迁移一致性检查和 `pip check` 通过。静态检查仍有既有 Django 邮件配置弃用等警告，Django 系统检查仍报告缺少前端 `dist/` 和重复 API namespace。此前适配层在实际 Python 3.12 环境只读核对玩家 7872 的公开资料与五类历史，取得 224 个链接（223 AVF、1 RMV），上传日期均存在、成绩均为字符串；没有写入实际数据库。这些数量是该次实时样本，不作为长期断言。

前端 lintfix/typecheck 按跨轮工作流启动，结果见对应交付；没有运行 Cypress，命令留给用户：

```powershell
npx.cmd vitest run src/services/accountLinkService.test.ts src/utils/accountlinks/msgames.test.ts src/utils/customlevel.test.ts
npx.cmd cypress run --component --browser chrome --headless --spec "src/components/accountlinks/CardMsgames.cy.ts,src/components/accountlinks/MSGamesVideoImportQueue.cy.ts,src/components/accountlinks/CardWoM.cy.ts"
```

本轮上述三个 Vitest 文件共 15 项通过，包括账号更新错误映射、公共 custom 配置和 4 项 MSGames 前端导入判断测试；导入判断覆盖文件格式、全部四种 Density 配置、缺失／未知／冲突配置和跨指标合并。完整列表响应契约由后端接口测试覆盖；录像列表保留 5 项组件用例，访客展示与本地分页合并到一次挂载，继续覆盖单条失败重试、日期排序、表头同行查询／筛选与不支持项、批量顺序等待和停止。模拟列表中的每条录像使用独立原始 URL，加入日期使用 API 的日粒度字符串，尚未执行 Cypress。

前期实时验证没有独立复测所有排行榜、异步实时请求及其他录像格式；支持范围依据发布源码、离线测试和[上游验证记录](https://github.com/putianyi889/msgames-api/blob/v0.1.0/docs/research/live-validation.json)。生产部署与浏览器中的真实批量下载尚未验证；本地数据库测试使用模拟下载和解析，AVF 真实解析证据来自上面的前期验证。组件 spec 已覆盖顺序等待、跳过不支持项、失败后继续、停止后续请求与单条重试，留给用户运行。

进一步依据：[客户端实现](https://github.com/putianyi889/msgames-api/blob/v0.1.1/src/msgames_api/client.py)、[解析器](https://github.com/putianyi889/msgames-api/blob/v0.1.1/src/msgames_api/parsers.py)、[上游调查报告](https://github.com/putianyi889/msgames-api/blob/v0.1.1/docs/research/README.md)。网站对相关路径的抓取有访问约定，包文档记录了 robots 限制；应保持授权范围内的按需读取，不将公开接口扩展为全站账号扫描。
