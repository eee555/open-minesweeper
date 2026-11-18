# Mineracer Games API 调研

调研日期：2026-10-21。以下来自生产接口的实际只读请求，不是稳定协议或已实现的导入功能。对方明确说明 API 处于 beta，未来可能更改或减少字段。

## 结论

- 单条请求已验证支持录像 ID 和个人成绩 UUID，返回一个 JSON 对象；单人和多人游戏均有样例。
- 多人游戏在 `results[]` 中返回各玩家独立成绩；通过个人成绩 UUID 查询会改变顶层 `resultId`、`outcome` 和 `timeMs`，但仍返回整局录像和所有玩家成绩。
- `results[].userId` 与 `replay.data.players[].uid` 可用于关联玩家，两数组的顺序不同，不能按下标配对。
- 两个样例均未提供可回放的操作序列：单人 `replay.data=null`，多人 `replay.data` 仅包含玩家列表。`replayAvailable=true`、`metadataOnly=false` 不代表响应包含完整录像数据。
- 字段存在可空、缺失、类型和语义差异；规范化字段与 `replay` 中的同义字段不能简单互作 alias。下文分别记录了实际值和待确认内容。
- 批量入口已确认是 `GET /api/games?ids=ID1,ID2`，不是将逗号列表放进路径。返回 `{count, games}`，每项携带 `requestedId`、`status`，以及成功时的 `game` 或失败时的 `error`。结果按请求顺序返回，按请求 ID 字符串去重，最多接受 10 个不同 ID。
- 批量中格式合法但不存在的 ID 返回单项 404，整批 HTTP 仍为 200；格式非法的 ID 则使整批返回 400。可混用录像 ID 和成绩 UUID；两种 ID 指向同一局时仍各自返回一项。
- 现阶段可以取得成绩和局面生成参数；若要在本站回放或验证录像，还需对方提供原始操作数据及必要的局面生成协议。

## 请求方式

```http
GET https://mineracer.com/api/games/bBhN1gEMaWKI
Authorization: Bearer <服务端 partner key>
```

现有账号关联使用的 partner key 已获此接口授权。不要将密钥写入前端、文档或响应；后续实现可复用 `utils.secrets_json.read_secret('mineracer_account_link_partner_key')` 在运行时读取。

单条请求返回一个 JSON 对象，没有 `data` 包装。示例响应为 HTTP 200、`Content-Type: application/json`，响应体 1254 字节。

批量请求使用相同鉴权，将 ID 列表放在 `ids` 查询参数中：

```http
GET https://mineracer.com/api/games?ids=bBhN1gEMaWKI,DSVR3btulXyV
Authorization: Bearer <服务端 partner key>
```

## 单条响应原文

以下仅调整了 JSON 排版，保留实际字段和值：

```json
{
  "id": "bBhN1gEMaWKI",
  "resultId": null,
  "replayId": "bBhN1gEMaWKI",
  "replayAvailable": true,
  "metadataOnly": false,
  "replayUrl": "https://mineracer.com/replay/bBhN1gEMaWKI",
  "mode": "solo",
  "difficulty": "hard",
  "playedAtMs": 1790017932127,
  "outcome": "won",
  "timeMs": 56331,
  "board": {
    "seed": 2317447050,
    "rows": 16,
    "cols": 30,
    "mines": 99,
    "noGuess": true,
    "firstCell": 0,
    "opening": "area",
    "ngOrigin": 0,
    "ngTransform": 0
  },
  "results": [
    {
      "id": "a4e93ffa-99d8-482c-86ad-ca24f0cd8e43",
      "userId": "lehjfewx0",
      "name": "pty",
      "username": "pty",
      "displayName": "pty",
      "mode": "solo",
      "difficulty": "hard",
      "outcome": "won",
      "timeMs": 56331,
      "cleared": 381,
      "threeBV": 154,
      "threeBVPerSec": 2.734,
      "validated": true,
      "suspicious": false,
      "noGuess": true,
      "hintCount": null,
      "chordControl": "left",
      "engineVersion": null,
      "playedAtMs": 1790017932127,
      "replayId": "bBhN1gEMaWKI"
    }
  ],
  "puzzle": null,
  "replay": {
    "id": "bBhN1gEMaWKI",
    "user_id": "lehjfewx0",
    "difficulty": "hard",
    "seed": 2317447050,
    "rows": 16,
    "cols": 30,
    "mines": 99,
    "outcome": "won",
    "time_ms": 56331,
    "created_at": 1790017933568,
    "mode": "solo",
    "first_cell": null,
    "data": null,
    "expires_at": null,
    "no_guess": 1,
    "ng_origin": 0,
    "ng_transform": 0,
    "client": null,
    "opening": null,
    "device": null,
    "cosmetics": {
      "baseStyle": "mineracer",
      "theme": "mineracer-default"
    },
    "owner": {
      "username": "pty",
      "displayName": "pty"
    }
  }
}
```

## 单人样例字段结构与可确定的含义

类型仅表示此样例实际出现的 JSON 类型。单个样例不能确定字段是否必填、其他情况下是否可空、完整枚举或数组长度限制。仅出现 `null` 的字段，无法确定其非空时的结构。

| 路径 | 观察到的类型 | 说明 |
| --- | --- | --- |
| `id`, `replayId`, `replayUrl` | string | 此例的录像 ID 和浏览器播放页地址；`replayUrl` 不是录像文件下载地址。 |
| `resultId` | null 或 string | 用录像 ID 查询时为 null；用下述成绩 UUID 查询时为该 UUID。 |
| `replayAvailable`, `metadataOnly` | boolean | 样例为 true、false，但 `replay.data` 仍为 null，不能仅凭这些标记认定返回了可回放数据。 |
| `mode`, `difficulty`, `outcome` | string | 此例为 `solo`、`hard`、`won`，完整枚举待确认。 |
| `playedAtMs`, `timeMs` | integer | 按字段名和数值判断，分别为 Unix 毫秒时间戳、用时毫秒；56331 对应 56.331 秒。 |
| `board` | object | 局面生成参数；没有直接返回雷格布局矩阵。 |
| `board.seed`, `board.rows`, `board.cols`, `board.mines` | integer | seed 为 2317447050；局面为 16 行、30 列、99 雷。seed 超出有符号 32 位整数范围。 |
| `board.noGuess` | boolean | 此例为 true；无猜规则和判定标准待确认。 |
| `board.firstCell`, `board.ngOrigin`, `board.ngTransform` | integer | 此例均为 0；首格编码、无猜局面来源及变换编码待确认。 |
| `board.opening` | string | 此例为 `area`，完整枚举与生成规则待确认。 |
| `results` | array of objects | 此例包含一条成绩。不能据此假定所有模式只有一位玩家。 |
| `results[].id`, `results[].userId` | string | 成绩记录 UUID 和 Mineracer 玩家 ID，不能混用。玩家 ID 应按字符串处理。 |
| `results[].name`, `results[].username`, `results[].displayName` | string | 此例均为 `pty`；三者语义区别尚未确认。 |
| `results[].mode`, `results[].difficulty`, `results[].outcome`, `results[].replayId` | string | 此例与顶层对应字段一致。 |
| `results[].timeMs`, `results[].playedAtMs` | integer | 此例与顶层对应字段一致。 |
| `results[].cleared`, `results[].threeBV` | integer | 此例分别为 381、154；`cleared` 的精确定义待确认。 |
| `results[].threeBVPerSec` | number | 此例为 2.734，与 154 / 56.331 的三位小数舍入结果一致。 |
| `results[].validated`, `results[].suspicious`, `results[].noGuess` | boolean | 此例分别为 true、false、true；第三方验证规则未知，不能等同于本站录像验证。 |
| `results[].chordControl` | string | 此例为 `left`，其他值与交互语义待确认。 |
| `results[].hintCount`, `results[].engineVersion`, `puzzle` | null | 非空结构未知。 |
| `replay` | object | 录像元数据，字段风格与顶层、results 不同。 |
| `replay.id`, `replay.user_id`, `replay.difficulty`, `replay.outcome`, `replay.mode` | string | 此例与顶层或成绩字段对应。 |
| `replay.seed`, `replay.rows`, `replay.cols`, `replay.mines`, `replay.time_ms` | integer | 此例与规范化字段一致。 |
| `replay.created_at` | integer | 此例为 1790017933568；数值形似 Unix 毫秒时间戳，比 `playedAtMs` 晚 1441 ms，不能直接当作同一字段。 |
| `replay.no_guess` | integer | 此例为 1；`board.noGuess` 和 `results[].noGuess` 则为 JSON boolean。 |
| `replay.ng_origin`, `replay.ng_transform` | integer | 此例均为 0。 |
| `replay.first_cell`, `replay.data`, `replay.expires_at`, `replay.client`, `replay.opening`, `replay.device` | null | 非空结构未知；尤其不能假定 `replay.data` 一定含操作序列。 |
| `replay.cosmetics` | object | 此例包含 string 类型的 `baseStyle`、`theme`。 |
| `replay.owner` | object | 此例包含 string 类型的 `username`、`displayName`。 |

`board.firstCell=0` 而 `replay.first_cell=null`；`board.opening="area"` 而 `replay.opening=null`。这些并非仅有命名差异，后续解析时不应直接合并为字段别名或相互覆盖。

## 多人游戏样例

请求 `GET https://mineracer.com/api/games/DSVR3btulXyV`，返回 HTTP 200、JSON 对象，响应体 2489 字节。结构仍为顶层摘要、`board`、`results[]`、`puzzle`、`replay`，但存在以下差异。

### 局面与玩家成绩

顶层 `mode="multi"`、`difficulty="hard"`、`outcome="won"`、`timeMs=76057`，`playedAtMs=1792583252336`。局面为 16 行、30 列、99 雷，seed 为 2288313，`noGuess=true`、`firstCell=0`、`opening="cell-random"`，`ngOrigin` 和 `ngTransform` 均为 null。

`results` 包含三位玩家，按实际返回顺序如下：

| name | userId | 成绩 UUID | outcome | timeMs | cleared | threeBV | threeBVPerSec | chordControl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pty | `lehjfewx0` | `3a0aa0e3-a4e3-4cb6-9036-3c8a334bd983` | won | 76057 | 381 | 169 | 2.222 | left |
| nnk | `siatb21ij` | `835dfcb6-9ee7-4896-94d6-06e24be44b7f` | lost | 24697 | 130 | 169 | null | left |
| Anondesuwa | `rwuq8ahey` | `cd15cce0-e6bf-4e29-a301-8aaa69ff9458` | lost | 4537 | 54 | 169 | null | left-right |

三条成绩都包含与单人样例相同的字段；`mode="multi"`、`difficulty="hard"`、`validated=true`、`suspicious=false`、`noGuess=true`、`hintCount=null`、`engineVersion=3`，`playedAtMs` 与 `replayId` 相同。每条记录的 `name`、`username`、`displayName` 在本例中相同。

因此，`results[].threeBVPerSec` 可为 null，`results[].engineVersion` 可为 integer，`chordControl` 至少观察到 `left` 和 `left-right`。不能从顶层 outcome 或 timeMs 推断每位玩家的结果，也不能将三个玩家的 cleared 相加当作共享棋盘的开格数。

### replay 字段差异

`replay.user_id=null`，不能假设整局录像只有一个所属玩家。`replay.owner` 字段不存在，`replay.cosmetics=null`，`replay.ng_origin`、`replay.ng_transform` 也为 null；`replay.first_cell=0`、`replay.opening="cell-random"`。

`replay.created_at=1792583254083`，比顶层 playedAtMs 晚 1747 ms。`replay.outcome="won"`、`replay.time_ms=76057`，`replay.no_guess=1`。其余 id、尺寸、seed 等与顶层或 board 对应。

`replay.data` 的完整内容如下；没有动作、鼠标事件或雷格矩阵：

```json
{
  "players": [
    {
      "uid": "rwuq8ahey",
      "name": "Anondesuwa",
      "color": "#2f81f7",
      "outcome": "lost",
      "timeMs": 4537,
      "cosmetics": { "baseStyle": "classic", "theme": "classic-light" },
      "username": "Anondesuwa"
    },
    {
      "uid": "lehjfewx0",
      "name": "pty",
      "color": "#3fb950",
      "outcome": "won",
      "timeMs": 76057,
      "cosmetics": { "baseStyle": "mineracer", "theme": "mineracer-default" },
      "username": "pty"
    },
    {
      "uid": "siatb21ij",
      "name": "nnk",
      "color": "#f0883e",
      "outcome": "lost",
      "timeMs": 24697,
      "cosmetics": { "baseStyle": "classic", "theme": "classic-dark" },
      "username": "nnk"
    }
  ]
}
```

`replay.data.players` 与 `results` 的顺序不同，玩家标识字段分别为 `uid` 与 `userId`。需要按标识关联，不能按数组下标配对。

### 用个人成绩 UUID 查询

用 nnk 的成绩 UUID `835dfcb6-9ee7-4896-94d6-06e24be44b7f` 查询同一接口，返回 HTTP 200。与直接用录像 ID 查询相比，顶层只有三个字段变化：

| 字段 | 用录像 ID 查询 | 用 nnk 的成绩 UUID 查询 |
| --- | --- | --- |
| `resultId` | null | `835dfcb6-9ee7-4896-94d6-06e24be44b7f` |
| `outcome` | won | lost |
| `timeMs` | 76057 | 24697 |

`id` 和 `replayId` 仍为 `DSVR3btulXyV`，`results` 仍返回三位玩家，顺序未变，`replay.outcome` 和 `replay.time_ms` 仍为 won、76057。因此顶层摘要会受查询使用的个人成绩 ID 影响，不能认定它始终代表整局或第一个 results 元素。

## 单条 ID 与路径形式实测

| 请求路径（均以 `/api/games/` 开头） | HTTP | 结果 |
| --- | --- | --- |
| `bBhN1gEMaWKI` | 200 | 上述单条对象。 |
| `a4e93ffa-99d8-482c-86ad-ca24f0cd8e43` | 200 | 同一录像对象，但顶层 `resultId` 从 null 变为查询使用的成绩 UUID；顶层 `id` 仍是录像 ID。 |
| `DSVR3btulXyV` | 200 | 上述多人游戏，results 包含三位玩家。 |
| `835dfcb6-9ee7-4896-94d6-06e24be44b7f` | 200 | 同一多人录像，但顶层 outcome 和 timeMs 改为该玩家的个人成绩。 |
| `000000000000` | 404 | `{"error":"game-not-found"}`。 |
| `bBhN1gEMaWKI,bBhN1gEMaWKI` | 400 | `{"error":"invalid-game-id"}`。 |
| `bBhN1gEMaWKI,000000000000` | 400 | `{"error":"invalid-game-id"}`。 |
| `bBhN1gEMaWKI,a4e93ffa-99d8-482c-86ad-ca24f0cd8e43` | 400 | `{"error":"invalid-game-id"}`。 |
| `bBhN1gEMaWKI,DSVR3btulXyV` | 400 | `{"error":"invalid-game-id"}`；两个分别查询成功的独立游戏也未通过批量查询。 |
| `bBhN1gEMaWKI%2CbBhN1gEMaWKI` | 400 | `{"error":"invalid-game-id"}`，编码逗号也未通过。 |
| 将示例录像 ID 用逗号重复 11 次 | 400 | `{"error":"invalid-game-id"}`；不能据此认定已经验证了 10 条上限。 |
| 示例 ID，不带有效密钥 | 401 | `{"error":"api-key-required"}`。本次只测试了空 Bearer 值，未测试其他无效密钥。 |

这些失败记录对应将逗号列表放进路径的请求。后续已找到并验证下述 `ids` 查询参数入口，因此不能将上述 400 解释为整个批量 API 不可用。`GET /api/games/batch?ids=...` 也返回 `400 invalid-game-id`，不是有效的批量入口。

## 批量 API

### 成功响应结构

`GET /api/games?ids=bBhN1gEMaWKI,DSVR3btulXyV` 返回 HTTP 200，响应体 3868 字节。以下展示包装结构，`game` 仅摘录少数字段；实际 `game` 包含前述完整单条对象：

```json
{
  "count": 2,
  "games": [
    {
      "requestedId": "bBhN1gEMaWKI",
      "status": 200,
      "game": {
        "id": "bBhN1gEMaWKI",
        "mode": "solo",
        "outcome": "won",
        "timeMs": 56331
      }
    },
    {
      "requestedId": "DSVR3btulXyV",
      "status": 200,
      "game": {
        "id": "DSVR3btulXyV",
        "mode": "multi",
        "outcome": "won",
        "timeMs": 76057
      }
    }
  ]
}
```

已将两个游戏的批量 `game` 与相邻时间取得的单条完整响应作结构和值的比较，两者均完全相同。`ids` 中只有一个 ID 时也返回批量包装 `{count: 1, games: [...]}`，不会变成单条响应结构。

### 顺序、去重与 ID 类型

- `ids=DSVR3btulXyV,bBhN1gEMaWKI` 返回的两个元素也按这个顺序排列。
- `ids=bBhN1gEMaWKI,DSVR3btulXyV,bBhN1gEMaWKI` 返回两项，`count=2`，保留各 ID 首次出现的顺序。
- 单人录像 ID、多人录像 ID、个人成绩 UUID 可以混用。
- 同时请求 `835dfcb6-9ee7-4896-94d6-06e24be44b7f` 与 `DSVR3btulXyV` 会得到两项，虽然两者对应同一录像：前者的 game 顶层为 lost、24697，后者为 won、76057。这说明去重依据请求 ID 字符串，而非最终 `game.id`。
- 后续接入应使用 `requestedId` 对应调用方请求，不能仅以 `game.id` 为 key，否则会覆盖同局的不同个人成绩。

### 单项失败与整批失败

对 `ids=bBhN1gEMaWKI,000000000000,DSVR3btulXyV` 的请求，整批 HTTP 200，`count=3`；首尾两项正常，中间项的完整内容为：

```json
{
  "requestedId": "000000000000",
  "status": 404,
  "error": "game-not-found"
}
```

失败项没有 `game` 字段；成功项没有 `error` 字段。`count` 包含失败项，不是成功游戏数量。读取时需要同时处理整批 HTTP 状态与每项 `status`。

| 测试 | 整批 HTTP | 结果 |
| --- | --- | --- |
| 两个有效独立录像 ID | 200 | count=2，两个成功项。 |
| 调换两个 ID 顺序 | 200 | 按调换后的请求顺序返回。 |
| 单人、多人的 ID，再重复单人 ID | 200 | count=2，重复字符串去重。 |
| 两个有效 ID 中夹入 `000000000000` | 200 | count=3，不存在的 ID 是单项 404。 |
| 两个有效 ID 中夹入 `!` | 400 | `{"error":"invalid-game-id"}`，没有 games，未返回其余有效游戏。 |
| 只传一个有效 ID | 200 | 仍返回批量包装，count=1。 |
| `ids=` | 400 | `{"error":"invalid-game-id"}`。 |
| 两个有效 ID 加八个不同的 12 位数字 ID | 200 | count=10，两项成功、八项 404；验证接受 10 个不同 ID，未验证 10 个均存在游戏的情况。 |
| 两个有效 ID 加九个不同的 12 位数字 ID | 400 | `{"error":"too-many-game-ids","maxIds":10}`。 |
| 同一有效 ID 重复 11 次 | 200 | count=1，说明 10 条上限按去重后的数量检查。 |
| 单人录像 ID、多人成绩 UUID、多人录像 ID | 200 | count=3，同一多人录像对应的两个不同请求 ID 不会合并。 |

上限测试中使用的八个、九个数字 ID 分别为 `000000000001` 至 `000000000008`、`000000000009`。它们满足接口格式检查；接受 10 项的请求中，这八项均返回 game-not-found。未调研速率限制、超时或上游内部错误时的单项返回结构。

## 接入前需要向 Mineracer 确认

1. 请对方确认已实测的 `GET /api/games?ids=...`、批量包装与错误语义是否为后续保留的协议；对方此前描述的路径式逗号列表当前不可用。
2. `replayAvailable=true`、`metadataOnly=false` 时，单人 `replay.data=null`、多人 data 仅含 players 的原因；原始操作序列和可下载录像是否另有接口。
3. 若需通过 seed 还原棋盘，所用 PRNG、布雷算法、首格编码、opening 和 ng 参数的协议及版本如何确定。仅有 seed 和尺寸不足以保证本站可以正确还原。
4. `puzzle`、`hintCount` 的非空样例，以及更多模式、难度和录像过期时的样例；两次采样尚不能确定完整字段可空性与枚举。多人已观察到 `engineVersion=3`、失败成绩，以及 `replay.data.players`。
5. `validated`、`suspicious`、`noGuess` 的定义，以及 beta 阶段字段保留策略、速率限制和稳定字段集合。当前样例未返回完整点击、旗标、鼠标移动等指标，不能推断它们的值。
