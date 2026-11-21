# 录像 board 存储、传输与缓存计划

更新：2026-11-20。

状态：已选定方案 B-lite（board 随批量元数据响应返回，保留全部衍生指标）。尚未修改模型、API 或前端缓存。

## 1. 目标与已知条件

- 计划为 `VideoModel` 添加 `board`，保存雷的分布。ms-toollib 的 `board` 是 `List[List[int]]`，不是 bytes；本计划将其编码为位图后存储。
- 前端在页面加载时通过 `/api/video/staticdetailbatch` 批量拉取页面上所有录像的元数据，hover 时立即显示，不存在专门的"等待 board"阶段。
- hover 是密集的：用户划过鼠标就会触发大量悬停响应，首盘的加载延迟会被明显感知。
- 单 board 请求本身很快，但延迟主要受地域往返影响，按需逐盘请求无法保证 hover 的即时性。
- "独立 API 每次只返回一个 board"的初衷是减少打包与转码的设计成本。B-lite 在现有批量响应中增加一个标准 Base64 字段，不新增接口，也不需要自定义二进制 framing。
- 前端需要缓存 board。
- 本文讨论存储与数据获取方式；棋盘预览的渲染 UI 不在范围内。

## 2. 共同基础

### 数据库存储

建议使用 `BinaryField`，直接保存 bytes。当前 Django MySQL 后端将其映射为 `longblob`；`CharField` 和 `TextField` 需要先将数据编码为文本，不会因为最终采用 JSON API 而更适合存储原始棋盘。

数据库字段与 API 表示分开设计：数据库保存 bytes；JSON API 使用 Base64。

数据库继续保留现有的 `bv` 等指标及生成字段，支持服务端检索、排序、排名和统计。这一份字段是指标的真相源，前端不重算，`staticdetailbatch` 响应继续携带它们。

新增字段允许为空，以区分"尚未取得数据"和历史录像。历史录像缺少 board 时只影响棋盘预览，不影响任何指标读取；回填完成前保留现有统计读取路径。

### 棋盘编码

存雷的位图，每格一位，1 表示雷、0 表示非雷。不存邻雷数字，需要时从雷的分布计算。

- **尺寸来源**：不写入格式头。行列数从 `level` 取得：`b` 为 8×8，`i` 为 16×16，`e` 为 16×30，自定义等级 `c{rows}_{columns}_{mines}` 直接给出 `rows` 和 `columns`。`level` 已在 `ParsedVideoOut` 中返回，前端不需要额外数据即可展开棋盘。
- **排列顺序**：行主序。第 `r` 行第 `c` 列（零起）对应位索引 `r * columns + c`，与 ms-toollib 的 `board[row][column]` 遍历顺序一致。
- **位序**：每字节低位在前（LSB-first）。位索引 `i` 落在第 `i // 8` 字节的第 `i % 8` 位。末字节高位补 0；总字节数为 `(rows * columns + 7) // 8`。
- **不改 level**：位图与 `level` 一一对应，解析时校验 `board` 的行列数与 `level` 推导出的尺寸一致，不一致视为解析失败。
- **版本**：不设格式版本字节。若未来编码变化，通过新增字段区分，历史 `board` 保持原格式。

`BinaryField` 不会自动进行位打包或压缩，由解析代码按上述规则显式生成。第 6 节的体积测算与选定编码一致。

### 解析链路与访问控制

- 当前解析子进程通过 JSON 文件返回元数据，原始 bytes 需要在该内部边界显式编码并在主进程还原，或另行使用二进制结果文件；不能直接交给 `json.dumps`。
- 新上传、导入和重新解析录像都应走同一 board 提取逻辑，历史数据通过现有的 `refresh_videos` 命令统一刷新。
- board 的访问权限沿用对应录像规则，由 API 层处理。B-lite 复用 `staticdetailbatch` 已有的可见性过滤，不新增权限入口。
- 前端缓存继续区分公开录像和用户作用域，复用现有登录状态变化处理。
- 模型变更通过 Django 命令自动生成迁移并按项目规范提交，不手写迁移脚本。

## 3. 选定方案：B-lite

### 数据路径

```text
BinaryField → staticdetailbatch 中的 Base64 board（同时保留全部指标）
            → 前端解码、还原棋盘
            → 现有 ParsedVideoInfo 与 IndexedDB 缓存
            → hover 时从缓存直接渲染棋盘
```

在 `/api/video/staticdetailbatch` 的记录中增加 `board` 字段，类型为 `str | None`，由 `ParsedVideoResolvers` 的 resolver 将模型 bytes 编码为 Base64。继续携带原有的 `bv`、`op`、`isl`、`cell0–8` 等全部指标，不改动 `ParsedVideoOut` 的现有字段。

只改变批量详情响应，不影响排行榜、Redis 摘要或其他列表接口。

### 前端与缓存

- 在 `videoInfoService` 的数据边界统一解码 Base64，缓存前转换为 `Uint8Array` 或 `ArrayBuffer`，不把 Base64 字符串写入 IndexedDB。
- `ParsedVideoInfo` 增加可选的 board 字段，UI 调用方式保持兼容；不引入 ms-toollib WASM，也不重算任何指标。
- 对 UI 继续提供补齐后的 `ParsedVideoInfo`，表格、tooltip、导出、排序继续读取后端返回的指标，不依赖 hover 操作才补齐数据。
- 新增 board 字段直接复用现有缓存的版本与公开/用户作用域规则。缓存中的旧记录缺少 board 时视为"未缓存预览"，不必强制清理缓存。
- 历史录像缺少 board 时返回 `null`，前端不显示棋盘预览；指标全部保持原值，因此不需要双轨回退逻辑。

### 选择依据

- 密集 hover 与地域 RTT 使按需单盘接口无法保证即时性；广撒网预取在大量录像页面上退化为 N 个请求，不如批量。
- 页面加载时已有批量元数据请求，board 随行返回即可实现 hover 零额外请求。
- 文档的原始 B 方案把"board 随批量响应传输"和"移除 12 个指标并由前端 WASM 重算"捆绑在一起，后者与 board 传输没有因果关系。hover 预览不消费重算结果，而重算会带来 WASM 加载与初始化、前后端指标双实现、算法版本纳入缓存失效、历史数据双轨回退等成本。
- 重算方案相对 B-lite 的流量优势只有 gzip 后约 2.2 KB/100 盘（见第 6 节），不足以抵消上述成本。

## 4. 备选方案：独立二进制 board 接口

```text
现有摘要 JSON：继续返回全部指标
需要棋盘时：单盘 API → 原始 bytes → ArrayBuffer / Uint8Array → IndexedDB
```

候选接口为 `GET /api/video/{id}/board`，成功响应使用 `application/octet-stream`，正文只含该盘 board。前端以 Axios `responseType: 'arraybuffer'` 接收，不需要 Base64。

本方案保留为备选：它在只看统计、几乎不 hover 的场景下最轻量，也不依赖棋盘计算模块。但在当前"页面加载即批量拉取 + 密集 hover + 地域延迟"的条件下，会带来大量请求和可见延迟，因此不作为实施方向。若将来出现独立的单盘棋盘分析场景，可在此基础上增加接口；若需要批量棋盘，应评估复用 B-lite 的批量响应，而不是堆叠独立请求。

## 5. 对比

| 比较项 | 备选 A：独立二进制 | 选定 B-lite |
| --- | --- | --- |
| 密集 hover | 每次付地域 RTT，请求数随 hover 增长 | 随批量响应到达，零额外请求 |
| 只展示统计 | 不下载 board | 下载 board，但无计算成本 |
| 前端依赖 | 无棋盘计算模块 | 仅 Base64 解码，无 WASM |
| 指标真相源 | 后端单点 | 后端单点 |
| 历史缺 board | 不显示棋盘 | 不显示棋盘，指标照常 |
| 主要维护成本 | 独立接口、请求合并、缓存入口 | 数据解码与缓存字段兼容 |

两个方案均使用 `BinaryField`，传输方案不改变数据库字段类型的建议。

## 6. 体积测算与限制

使用当前 ms-toollib 1.6.2 WASM，以固定种子 `20261120` 生成随机棋盘，每种尺寸 100 盘。board 按第 2 节选定的位图编码生成（行主序、LSB-first、不含格式头），JSON 采用带补位的 Base64；gzip 使用 Node `node:zlib` 默认参数。

只比较 `id` 与 12 个衍生指标，或 `id` 与 Base64 board。单条数据取对应序列中的第一盘，批量数据包含全部 100 盘。

| 棋盘 | 原始 board 字节 | 单条指标 JSON | 单条 board JSON | 100 盘指标 JSON，经 gzip | 100 盘 board JSON，经 gzip |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8×8 / 10 雷 | 8 | 123 | 31 | 1,399 | 1,021 |
| 16×16 / 40 雷 | 32 | 126 | 63 | 1,735 | 2,810 |
| 16×30 / 99 雷 | 60 | 130 | 99 | 2,005 | 5,298 |
| 32×32 / 200 雷 | 128 | 133 | 191 | 2,224 | 10,648 |

表中单位均为字节。数字字段名、零值和相近数值在批量数据中容易压缩，因此不能由"增加 board 字段"推断必然大幅增加流量。项目已配置 Django `GZipMiddleware`，评估时应覆盖压缩后的响应。

B-lite 在指标之外增加 board，单条增量约 31–191 字节，批量 gzip 后为 1.0–10.6 KB/100 盘。初级棋盘由于位图很小，gzip 后 board 甚至比指标更省。即使采用移除指标的原始 B 方案，最多也只能再省 1.4–2.2 KB/100 盘，代价是引入 WASM 与指标重算，因此不采纳。

这只是合成样本的字段片段测算，不是生产接口实测：未计其他元数据、HTTP 请求和响应头、网络时延或前端计算耗时。

本地调查脚本、完整结果和日志保存在 `.tmp/checks/board-transport-comparison-20261120/`，不作为运行时依赖。Base64 体积规律参考 [RFC 4648](https://www.rfc-editor.org/rfc/rfc4648.html#section-4)；IndexedDB 支持二进制缓存，参考 [结构化克隆支持类型](https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API/Structured_clone_algorithm#supported_types)。

## 7. 不纳入本次范围

- 移除 `staticdetailbatch` 响应中的衍生指标字段。
- 前端使用 ms-toollib WASM 重建 `bv`、`op`、`isl`、`cell0–8`。
- 独立 board API、批量 board API 及自定义二进制打包格式。
- 算法语义变化引起的衍生指标缓存失效机制。

上述内容是原始 B 方案的组成部分，与 B-lite 的选取无关；如未来需求变化，单独评估。

## 8. 实施顺序与验收

### 阶段一：模型与数据

只完成存储和数据处理，不改动任何 API 响应或前端。

1. 确认并测试 board 编码，覆盖标准等级、自定义尺寸、补位及无效数据。
2. 增加模型字段和自动生成的迁移。
3. 接入统一解析路径，使新上传、导入和重新解析都写入 board。
4. 历史数据通过现有的 `refresh_videos` 命令统一刷新，与其他新增字段一起回填，不单独提供 board 回填命令。

阶段一验收：

- 位图长度正确、位序与行主序一致，边界尺寸和末字节补位正确，历史缺失数据不伪造棋盘。
- 新上传、导入、重新解析和 `refresh_videos` 刷新得到一致 board。
- 所有现有 API 的响应字段与取值保持不变，前端行为不变。

### 阶段二：接口与前端

在阶段一完成后单独实施。

1. 在 `ParsedVideoOut` 增加 Base64 board 字段及其 resolver，接入 `staticdetailbatch`。
2. 在 `videoInfoService` 的数据边界解码 board、写入 IndexedDB，处理旧缓存缺少字段与历史录像 `null` 的情况。
3. 用真实录像验证生产压缩响应体积、缓存命中与 hover 时的读取成本，再确认棋盘预览的接入方式。

阶段二验收：

- Base64 编解码正确，`board: null` 不显示预览且不影响指标。
- 缓存中的旧记录缺少 board 时表格与指标正常显示，登录状态变化后公开/用户作用域的缓存隔离保持现有行为。
- `staticdetailbatch` 的 12 个指标字段与取值保持不变，表格、排序、tooltip、散点图和导出语义一致。
- hover 时从缓存读取棋盘，不产生额外的 board 请求。

相关实现入口：后端 `models.py`、`schema.py`、`api.py`、`services.py`，解析链路 `utils/parser.py` 与 `utils/parser_process.py`；前端 `services/videoInfoService.ts`、`services/database.ts`。
