---
title: Minigame Replay Data Format v1 - Open Minesweeper
description: Board compression, mouse, touch and special event encoding, and frontend and backend migration rules from minigame replay format v0 to v1.
---

# Minigame Replay Data Format v1

Status: implemented. The website and offline edition save new recordings as v1 and can read v0 recordings. IndexedDB upgrades automatically; backend history has completed its compression migration.

This specification defines the v1 JSON payload used for playback and persistence, and its 7z storage container. Standalone replay downloads and file extensions are not defined yet. JSON text uses UTF-8. Object property order and whitespace do not affect meaning; tuple field order and event order must be preserved.

## 1. Payload and Enclosing Result

The enclosing record continues to supply the game, mode, score and completion time. The replay does not duplicate them:

| Information | IndexedDB | Backend |
| --- | --- | --- |
| Game and mode | `game`, `mode` | Determined by `ranking_key` |
| Total duration, integer milliseconds | `scoreMs` | `score` |
| Completion time | `playedAt`, Unix milliseconds | `achieved_at`, server time |
| Replay for all games | `replay`, a 7z `ArrayBuffer` | `replay_archive` BinaryField, 7z bytes |
| Missing cell rounds | `rounds` in the decompressed JSON | `rounds` in the decompressed JSON |
| Replay format version | `version` in the decompressed JSON | `version` in the decompressed JSON |

Board dimensions come from the enclosing mode. Do not infer dimensions from the compressed string or question array. All board coordinates use zero-based `[row, column]` cell indices; mouse events still use pixel coordinates `x, y`.

Only successful runs are persisted. Failed or unfinished runs that are restarted are neither uploaded nor saved to local history. Runtime playback may use the same event representation for failed runs.

### Storage Container

Each recording is an independent, unencrypted 7z archive containing exactly one regular file named `replay.json`, whose content is the UTF-8 JSON defined here. Use LZMA2; current writers use level 1 and a 1 MiB dictionary, without compression across recordings. The JSON `version` still identifies the payload format; the 7z wrapper does not change its meaning.

The frontend uses [7z-wasm](https://github.com/use-strict/7z-wasm) and stores a raw `ArrayBuffer` in IndexedDB, without Base64 conversion. The offline package inlines the compression Wasm and needs no network loading. The backend uses [py7zr](https://py7zr.readthedocs.io/en/latest/api.html) and stores bytes of the same container in BinaryField, outside Redis.

The submission API still accepts a v1 JSON string in the form. The backend compresses it when creating or improving a score. Read stored data in this order: extract 7z → parse UTF-8 JSON → identify `version` → decode the board and events.

### Version Detection

Read `version` from the location specified above to identify the replay format. Do not guess the version from the shape of the board or event array:

| `version` | Interpretation |
| --- | --- |
| Property absent, or integer `0` | v0, the previous format: two-dimensional board arrays and mouse event objects; the missing cell target is the board's only `10` |
| Integer `1` | The v1 format defined here |
| Any other non-negative integer | Unsupported version; report it and stop parsing without falling back to v0 |

When present, the property must be a non-negative integer. Values such as `null`, strings and booleans are format errors, not an absent property. Identify existing data without `version` as v0, then validate the required v0 fields. New writes must explicitly store `version: 1`.

### Left-click and Flag-and-chord Training

```ts
interface TrainingRecordingV1 {
    version: 1;
    cellSize: number | null;
    initialBoard: string | [row: number, column: number, mineDirection: number][];
    events: [dt: number, x: number, y: number, action: number][];
    specialEvents: [dt: number, index: number, type: number][];
}
```

| Field | Convention |
| --- | --- |
| `version` | Fixed integer `1`, identifying this replay format; read old data without this property as v0 |
| `cellSize` | Reference cell side length in CSS pixels, either a positive integer or `null`; new recordings fix it at the event that starts timing; v0 migration writes `null`, which readers interpret using the fixed reference value `32` |
| `initialBoard` | A Base64 mine string for left-click training, or a question array containing each question's center and mine direction for flag-and-chord training; see Section 2; the enclosing game determines which representation applies |
| `events` | Ordinary mouse events from the start to the end of timing, in processing order; each tuple contains exactly four integers, as defined in Section 3 |
| `specialEvents` | Special events such as focus loss and cancellation, containing a time delta, insertion index and type; store an empty array when there are none; see Section 3.5 |

The format version, IndexedDB database version and rule version in ranking keys are maintained separately. IndexedDB is now version `3`, supporting upgrades from v0 data in database version `1` and v1 JSON in database version `2` to 7z storage. Ranking rules and keys remain unchanged. Future changes to tuple fields, units, encoding or the meaning of existing enum values require a new format version, rather than changing the interpretation of v1.

### Multi-touch Training

The enclosing `game: 'multi-touch'` or `multi-touch-*` ranking selects this structure. It is separate from mouse recordings and does not change the existing v1 four-tuples. Multi-touch training has no v0 format.

Successful multi-touch games are compressed in this format and saved to IndexedDB. Manual uploads submit the same JSON, which the backend compresses into BinaryField. Replays stay out of Redis.

```ts
interface TouchRecordingV1 {
    version: 1;
    cellSize: number | null;
    initialBoard: string;
    events: [dt: number, dx: number, dy: number, contact: number, action: number][];
}
```

`cellSize` and the Base64 `initialBoard` have the same meaning as in left-click training. All contacts share one ordered event stream. Time and pixel coordinates are deltas from the **previous array entry**, even when it belongs to another contact; the first entry is relative to zero and has absolute coordinates. Keep signed deltas without ZigZag. `contact` is not delta-encoded: assign a new consecutive ID starting at `0` for every touch down, including when the browser reuses a `pointerId`.

| `action` | Meaning |
| --- | --- |
| `0` | Down: create the contact and attempt to open its cell |
| `1` | Move: update that contact's position only |
| `2` | Up: remove the contact without opening a cell |
| `3` | Cancel: remove the contact without opening a cell |

Move, up and cancel must reference an active contact. Global cancellation such as blur or hiding the page writes one `3` event per active contact, so no `specialEvents` array is needed. Timing starts on the first down event. Preserve array order for equal timestamps. Recording stops at completion, so contacts may remain active at the end. Rebuild each contact's path and current-position marker independently, applying only down events to the game board. Do not render pressed-cell previews.

Example: two fingers go down, the first moves, then the second lifts:

```json
[[0,16,16,0,0],[10,32,0,1,0],[5,-30,2,0,1],[5,30,-2,1,2]]
```

Adding this game does not change the IndexedDB schema or version. Existing mouse and missing cell recordings need no migration.

Expert always uses 16×30 board and event coordinates. Vertical display transposes the board and traces and swaps input coordinates. Orientation is a local user setting, excluded from replays, and does not change the ranking key. Switching orientation preserves the current game and replay contents.

### Missing Cell Training

Missing cell training does not record mouse events. Each round stores a mine string, target coordinates and duration:

```ts
interface MissingCellRecordingV1 {
    version: 1;
    rounds: { board: string; target: [row: number, column: number]; timeMs: number }[];
}
```

`rounds` follows the order of play and contains exactly 10 entries for a successful run. `board` encodes only mines. `target` separately identifies the only unopened safe cell and must not point to a mine; visible numbers are recalculated from the mines. `timeMs` is the round duration in non-negative integer milliseconds, and the sum of all round durations equals the enclosing total score. There is no cell-size-dependent trace, so missing cell recordings do not store `cellSize`. Compress the entire `{version, rounds}` object into the IndexedDB entry's `replay` field.

## 2. Board Encoding

### 2.1 Base64 Mines for Left-click and Missing Cell

Each cell occupies one bit: `1` for a mine and `0` for a non-mine. Use the standard Base64 alphabet from [RFC 4648 Section 4](https://www.rfc-editor.org/rfc/rfc4648.html#section-4), indexed from `0..63`:

```text
ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/
```

Starting at the top-left corner, traverse rows from top to bottom and cells from left to right, continuing directly into the next row. Every 6 cells form one character, with earlier cells occupying more significant bits:

```text
i = row * columns + column
characterIndex = floor(i / 6)
bitPosition = 5 - i % 6

value[j] = sum(mine[6 * j + k] * 2 ** (5 - k), k = 0..5)
board[j] = alphabet[value[j]]
```

If the final group contains fewer than 6 cells, pad its low bits with `0`; these padding bits do not represent cells. The string length is exactly `ceil(rows * columns / 6)`. Do not store `=` padding characters, spaces or line breaks. Trailing padding bits must be `0`.

| Level | Rows × columns | Cell count | Mine string length |
| --- | --- | --- | --- |
| Beginner | `8 × 8` | `64` | `11` |
| Intermediate | `16 × 16` | `256` | `43` |
| Expert | `16 × 30` | `480` | `80` |

For example, the mine bits `1, 0, 1, 0, 0, 1` form binary `101001`, whose value is `41`, corresponding to character `p`. Six consecutive non-mines produce `A`; six consecutive mines produce `/`.

Implementations may pack the row-ordered bits into bytes, most significant bit first, and reuse an existing Base64 codec. All three current board sizes contain a multiple of 8 cells, so removing trailing `=` from that encoding produces this representation. Temporarily restore `=` when a decoder requires padding; the persisted value remains unpadded.

### 2.2 Flag-and-chord Question Array

`initialBoard` is a question array, with exactly three integers per item:

```text
[row, column, mineDirection]
```

`row, column` are the cell indices of the central number `1`, not pixel coordinates. Add the direction offset to the center to locate the mine. Direction codes follow the existing row-by-row neighbor traversal, skipping the center:

| `mineDirection` | Direction | Row offset | Column offset |
| --- | --- | --- | --- |
| `0` | Top-left | `-1` | `-1` |
| `1` | Top | `-1` | `0` |
| `2` | Top-right | `-1` | `1` |
| `3` | Left | `0` | `-1` |
| `4` | Right | `0` | `1` |
| `5` | Bottom-left | `1` | `-1` |
| `6` | Bottom | `1` | `0` |
| `7` | Bottom-right | `1` | `1` |

For example, `[3, 5, 2]` places the question center at row `3`, column `5`, with its mine at `(2, 6)`. Every question has exactly one mine and its number is always `1`, so neither the number nor the other safe cells are stored separately. Beginner has exactly 4 items and Intermediate has 15. Each question's complete 3×3 region must stay within the board and must not overlap another question.

Writers sort questions by the center's `row`, then `column`, in ascending order to give each layout a consistent representation. Array order does not indicate the player's solving order.

### 2.3 Missing Cell Target Coordinates

Each round's `board` uses the mine encoding in Section 2.1, with a separate `target: [row, column]`. The target must be within the board and its mine bit must be `0`. Round order and duration belong only to the enclosing `rounds` array, not to the mine string.

### 2.4 Reconstructing Runtime Boards

The storage layer uses the compact representations above. Decoding restores the project's existing two-dimensional main-board matrices:

| Value | Left-click `initialBoard` | Flag-and-chord `initialBoard` | Missing cell round `board` |
| --- | --- | --- | --- |
| `0` | Unused | Blank area outside questions | Open blank cell |
| `1..8` | Unused | Only `1`, the question center | Open adjacent-mine count |
| `10` | Safe cell not yet clicked | Safe neighboring cell not yet opened | The only unopened safe target |
| `16` | Visible mine | Visible mine | Hidden mine, converted to `10` for display during review |

For left-click training, restore `16` and `10` from the mine bits. For flag-and-chord training, fill the board with `0`, then restore each center as `1`, its mine as `16` and its other neighbors as `10`. For missing cell training, calculate safe cells' adjacent-mine counts, then set mines to `16` and the target to `10`. When displaying a missing cell round, convert mine values from `16` to covered `10` and highlight the separately stored target coordinates.

The initial board preserves all mine locations, not a random seed or adjacent-mine counts. Flags, wrong flags, exploded mines and boards after operations are reconstructed by the game rules. Per-operation snapshots, remaining counts and analysis results are not persisted.

## 3. Mouse Event Tuples

```text
[dt, x, y, action]
```

| Index | Field | First event | Subsequent events |
| --- | --- | --- | --- |
| `0` | `dt` | Integer milliseconds from timing start to this event, normally `0` for new recordings | Non-negative integer milliseconds since the previous ordinary event |
| `1` | `x` | Absolute horizontal coordinate relative to the board's top-left corner, in integer pixels; may be negative | Signed integer horizontal delta from the previous ordinary event |
| `2` | `y` | Absolute vertical coordinate relative to the board's top-left corner, in integer pixels; may be negative | Signed integer vertical delta from the previous ordinary event |
| `3` | `action` | Input event code | Same |

Deltas always refer to the preceding item in the ordinary event array, including movement and ineffective button events, rather than the last effective game operation. Special events are stored separately and do not participate in ordinary timestamp or coordinate deltas. `dt = 0` is allowed. Events within the same millisecond retain array order and must not be deduplicated or reordered by timestamp.

### 3.1 Time

Use the game's monotonic clock in milliseconds; the Unix completion time does not participate. Quantize cumulative timestamps before calculating deltas:

```text
t[i] = max(0, round(now[i] - startedAt))
dt[0] = t[0]
dt[i] = t[i] - t[i - 1]       // i > 0
```

For non-negative values, `round` means `floor(value + 0.5)`. Neither frontend nor backend may round each interval separately. Old `timeMs` values are already quantized, so migration subtracts them directly.

- Left-click training starts when the first left-button release triggers an operation. That release is recorded at `t = 0`; its preceding press and observation movements are omitted, so the first click has no paired press within the timed recording.
- Flag-and-chord training starts with the first effective flag placement. That right-button press is recorded at `t = 0`.
- After timing starts, movement, presses and releases go into `events`; cancellation and resets go into `specialEvents`. Ineffective game operations are included. The ending event must be included, with no events appended after the run ends.
- Empty event arrays are allowed and mean there is no input to replay. Normally completed new recordings should contain the events required to start and finish. Migration must not discard a history entry just because its event array is empty.

Each array independently accumulates its own `dt` values to recover timestamps relative to the same timing origin. Total duration comes from the enclosing score. Preserve the existing minimum successful score of `1ms`; do not forcibly replace total duration with the last event timestamp.

### 3.2 Pixel Coordinates and Cell Size

The board content's top-left corner is `(0, 0)`. `x` increases to the right and `y` downward. Coordinates are logical CSS pixels at the reference cell size. They exclude counters, borders and page scroll offsets, and are not multiplied by `devicePixelRatio`.

`cellSize: null` means the original recording size is unknown. Use the fixed reference value `32`, independent of the current cell size in settings. The property is still required; an absent property or another invalid value is not treated as `null`. All following formulas use the effective reference value:

```text
referenceCellSize = cellSize === null ? 32 : cellSize
```

Let the displayed cell size at the event be `displayCellSize`, and the pointer's logical pixel position on that displayed board be `displayX, displayY`:

```text
x[i] = floor(displayX / displayCellSize * referenceCellSize)
y[i] = floor(displayY / displayCellSize * referenceCellSize)
```

If CSS scaling is applied, first map the board's actual displayed rectangle back to logical pixels. Use the same `referenceCellSize` throughout the run. Changing the displayed cell size during play neither restarts the run nor changes the metadata; subsequent events are mapped into the original reference system. Floor coordinates before taking deltas, avoiding rounding a click near a cell's right edge into its neighbor.

Do not clamp coordinates to the board: negative coordinates and positions beyond its width or height are retained. Replay determines hits from whether coordinates are within the board and does not preserve browser occlusion or scroll clipping information.

During playback, restore pixel coordinates, then convert them to the cell units expected by the existing renderer:

```text
column = x / referenceCellSize
row = y / referenceCellSize
```

Game operations use `floor(column)` and `floor(row)` as cell indices. Rendering may rescale to the current displayed cell size; playback does not need to restore the recording's display size. Pixel quantization discards fractions smaller than one reference pixel without changing the containing cell.

### 3.3 Coordinate Deltas

Write the first event's `x, y` directly. Subsequent events store `dx, dy` relative to the previous ordinary event as signed JSON integers, without ZigZag conversion.

```text
storedX[0] = x[0]
storedY[0] = y[0]

storedX[i] = x[i] - x[i - 1]       // i > 0
storedY[i] = y[i] - y[i - 1]

x[0] = storedX[0]
y[0] = storedY[0]
x[i] = x[i - 1] + storedX[i]       // i > 0
y[i] = y[i - 1] + storedY[i]
```

A stationary coordinate has delta `0`; moving left or up produces a negative delta on the corresponding axis. Stored values, reconstructed coordinates, accumulated timestamps and calculation intermediates must all remain within JavaScript's safe integer range.

### 3.4 Input Event Codes

| `action` | Input event | Existing name |
| --- | --- | --- |
| `0` | Mouse movement | `mv` |
| `1` | Left-button press | `lc` |
| `2` | Left-button release | `lr` |
| `3` | Right-button press | `rc` |
| `4` | Right-button release | `rr` |

The input adapter continues to convert touch input into left-button events; no touch-specific code is added. Cancellation and resets use the special event array, rather than ordinary event codes.

### 3.5 Special Events and Insertion Indices

Each `specialEvents` item contains exactly three non-negative integers:

```text
[dt, index, type]
```

| Field | Meaning |
| --- | --- |
| `dt` | Integer milliseconds since the previous special event; for the first item, time since timing started; it is not relative to ordinary events |
| `index` | Zero-based insertion index in the ordinary event array, within `0..events.length` |
| `type` | Special event type; v1 defines only `0`, meaning cancel and reset the input state |

`index = i` means execute before `events[i]`. `index = 0` executes before the first ordinary event; `index = events.length` executes after the last. Indices always address the original `events` array and do not increase when other special events are inserted. Multiple special events may share one insertion index; execute them in `specialEvents` order without deduplication.

Record special events in occurrence order, with non-decreasing `index` values. Let a special event's accumulated timestamp be `s`, its insertion index be `i`, and ordinary event timestamps be `t`. If a previous ordinary event exists, require `t[i - 1] <= s`; if a next ordinary event exists, require `s <= t[i]`. Within a single millisecond, insertion indices and array order determine execution order. Do not merge the arrays by timestamp alone.

Focus loss, a hidden page, touch cancellation and inconsistent button state all use type `0`. Executing it resets the automaton, clears press previews and unpaired press timestamps, and triggers no left-click, flag or chord operation. Special events do not store coordinates: retain the preceding ordinary event's position without changing the delta reference for ordinary events. There is no known pointer position before the first ordinary event. The specific reset reason is not stored separately.

### 3.6 Derived State and Starting Events

Button state, operation intent and press previews are not persisted. Reconstruct them from the existing `ClassicMouseAutomaton`, event coordinates and current board. During playback, process ordinary events through the automaton first, then forward any resulting intent to the game rules if coordinates are within the board. Ineffective operations remain in the event sequence.

- The first ordinary left-click training event is the `lr` that starts timing. Initialize the automaton with the left button held before processing it. This only supplies the known initial state; it does not generate a timed `lc`, so the first click remains excluded from press-duration statistics.
- Flag-and-chord training starts from the idle automaton state. Its first ordinary event is the `rc` that starts timing, producing a flag operation under the normal rules.
- After a reset, process subsequent ordinary events from idle. Events outside the board still update button state, but produce no board operation or press preview.

Previews follow the existing shared rules: a single-button preview excludes only flagged cells; a chord preview covers the center and surrounding 3×3 area, with flagged cells remaining raised. Use the full automaton state to distinguish an ordinary held button from a button still held after a chord has triggered.

## 4. Shared Frontend and Backend Encoding Examples

These are event fragments, not complete successful runs. `cellSize = 32`; coordinates are decoded reference pixels.

### Left-click, Movement and Cancellation

| Index | Cumulative time | Coordinates `(x, y)` | Input | State / intent / preview | Stored tuple |
| --- | --- | --- | --- | --- | --- |
| `0` | `0` | `(16, 16)` | `lr` | `uu` / `left` / none | `[0, 16, 16, 2]` |
| `1` | `10` | `(48, 16)` | `lc` | `du` / none / single cell | `[10, 32, 0, 1]` |
| `2` | `25` | `(45, 18)` | `mv` | `du` / none / single cell | `[15, -3, 2, 0]` |
| `3` | `25` | `(45, 18)` | `lr` | `uu` / `left` / none | `[0, 0, 0, 2]` |

If cancellation occurs at `30ms`, store it separately:

```json
{"specialEvents": [[30, 4, 0]]}
```

Here `4` is the insertion position at the end of the ordinary event array. If cancellation instead occurs at `25ms` after movement but before release, store:

```json
{"specialEvents": [[25, 3, 0]]}
```

Process ordinary event `2`, then reset, then process ordinary event `3`. The `lr` after the reset produces no left-click operation. Ordinary timestamp and coordinate deltas are unchanged in either case. The state / intent / preview column only illustrates derived results and is not part of the stored fields.

### Flag Placement Followed by a Chord

| Index | Cumulative time | Coordinates `(x, y)` | Input | State / intent / preview | Stored tuple |
| --- | --- | --- | --- | --- | --- |
| `0` | `0` | `(16, 16)` | `rc` | `ud` / `right` / none | `[0, 16, 16, 3]` |
| `1` | `10` | `(16, 16)` | `rr` | `uu` / none / none | `[10, 0, 0, 4]` |
| `2` | `30` | `(48, 48)` | `lc` | `du` / none / single cell | `[20, 32, 32, 1]` |
| `3` | `40` | `(48, 48)` | `rc` | `dd` / none / 3×3 | `[10, 0, 0, 3]` |
| `4` | `50` | `(48, 48)` | `lr` | `ud` / `chord` / none | `[10, 0, 0, 2]` |

If the chord successfully completes a question, its three statistical timestamps are `0ms`, `30ms` and `50ms`. The stacked bar's lower segment is `30ms` and its upper segment is `20ms`. Failed and ineffective chords stay in the event sequence but do not produce successful chord statistics.

## 5. Decoding and Playback

1. Determine the game and mode from the enclosing record. Identify the format by `version`; read an absent property as v0 and convert it using Section 6 before decoding as v1.
2. For mouse replays, accumulate each array's time deltas independently, restore ordinary event coordinates, then merge using special event insertion indices. For multi-touch replays, accumulate the single event stream and track each contact. Use decoded sequence indices for runtime snapshots and positions within one millisecond; do not change persisted insertion indices.
3. Decode `initialBoard` into a two-dimensional matrix using Section 2, then create the game controller. For mouse replays, supply the initial state from Section 3.6, process ordinary inputs and special resets in order, derive operation intents and apply game rules. Multi-touch replays attempt to open cells only on down events. Reuse the existing automaton and left-click / flag-and-chord rules without introducing `ms-toollib`. For missing cell training, separately decode each round's mines and restore the board using its target coordinates.
4. Rebuild all board snapshots, remaining counts and successful chord timings once. Keep this derived data only in memory.
5. Calculate mouse speed, click speed and press durations from the decoded trace and timestamps. Use the enclosing score as the playback endpoint.

After identifying the version, format errors include missing required fields for that version, invalid enum values, negative time deltas, non-integer values in integer fields and safe integer overflow. They also include out-of-range or decreasing special insertion indices, conflicting event order and timestamps, invalid mine-string length / characters / padding bits, out-of-range coordinates, a target on a mine, or a flag-and-chord layout that cannot be reconstructed. Readers report the error and stop parsing that record rather than defaulting missing data to zero. An absent `version` means v0 under Section 1, while `cellSize: null` uses reference value `32` under Section 3.2. Do not interpret an unknown `version` as the old format. These checks support data reading and migration; they do not add score authenticity, gameplay legality or anti-cheat validation.

## 6. Migrating v0 to v1

### 6.1 Shared Conversion Rules

v0 left-click / flag-and-chord recordings contain `{initialBoard, events}`, with a two-dimensional board and event objects containing `timeMs`, `row`, `column`, `action`, `state`, `pressed`, `trigger` and `cancelled`. v0 missing cell recordings contain `{rounds}`, with each round represented as `{board: number[][], timeMs}`. An absent `version` or explicit integer `0` is validated and converted as v0. Empty mouse event arrays must also be converted.

Convert boards using the enclosing game and mode:

- Left-click: encode each `16` in the old `initialBoard` as mine bit `1` and each safe cell as `0`, producing the Base64 string.
- Flag-and-chord: find each number `1` in the old `initialBoard`, extract its center and the only `16` among its eight neighbors, and convert the mine offset to a direction code. Sort by center coordinates to form the question array.
- Missing cell: for each old `board`, encode `16` as mine bit `1` and all other cells as `0`. Extract the only `10` as `target` and preserve its `timeMs`. Numbers are no longer stored; decoding recalculates them from mines.

Old mouse coordinates use cell units and do not include the recording cell size, so its original pixel size cannot be recovered. Migrated left-click / flag-and-chord recordings store `cellSize: null` and use the default reference `32` to convert old cell coordinates to pixels. Split ordinary and cancellation events in their original order, then calculate deltas independently:

```text
normal = old.events.filter(event => !event.cancelled)
x[i] = floor(normal[i].column * 32)
y[i] = floor(normal[i].row * 32)
dt[0] = normal[0].timeMs
dt[i] = normal[i].timeMs - normal[i - 1].timeMs
```

Store ordinary events with signed coordinate deltas and `action` codes from Section 3. Convert old `cancelled: true` entries into type `0` special events. Their insertion index is the number of ordinary events retained before reaching them in the old sequence. A special event's `dt` is relative only to the preceding special event; the first uses the original `timeMs`. Do not calculate deltas across all old events and then delete cancellation entries, as that loses elapsed intervals.

Old `state`, `pressed` and `trigger` values are no longer persisted; reconstruct them from the automaton and coordinates when reading. Do not separately retain old DOM hit information. Board contents and merged input order remain the same; only their representation changes.

`cellSize: null` preserves the fact that the original size is unknown. The 32px value is only a shared decoding reference, not a claim that the replay was recorded at 32px. Migration preserves cell positions while discarding trace fractions smaller than `1/32` of a cell; playback can still scale to any display size.

Add `version: 1` only after the entire board and events, or all missing cell rounds, have been converted successfully. Do not write partially converted records. Repeated migration leaves valid v1 recordings unchanged. Preserve and report unknown versions and corrupt data.

### 6.2 Frontend IndexedDB

Reuse the existing `idb` library and upgrade `saolei-minigame` to version `3`, supporting v0 in database version `1` and v1 JSON in version `2`. Initialize the compressor before opening the upgrade transaction. Traverse `results` inside the transaction, read and convert each game's payload, and write the 7z `ArrayBuffer` to the common `replay` field. Move old missing cell entries' top-level `rounds` and `version` into the compressed payload. Preserve `id`, `playedAt`, `scoreMs`, `game`, `mode`, and both the `playedAt` and `scoreMs` indexes.

Fresh installations create the new schema directly. If one replay cannot be converted, log a warning, compress its complete original JSON into 7z, preserve the entry and all original payload fields, and continue migrating other records. Do not add `version: 1`; subsequent reads still apply normal validation and report parsing errors. Left-click and flag-and-chord retain the original `replay` object; missing cell retains the original `rounds` and any existing `version`. If compression or a database operation fails, abort the transaction and retain the old data instead of deleting the database or clearing history. Old pages continue to close their connections on a version change to avoid blocking the upgrade. Use IndexedDB's [upgradeneeded mechanism](https://developer.mozilla.org/en-US/docs/Web/API/IDBOpenDBRequest/upgradeneeded_event).

When old records need conversion, the website and offline edition display “Optimizing replay format. Please do not close this page.” with completed / total progress. The dialog closes after the upgrade transaction commits or rolls back on failure. Allow the browser to paint the notice before compression, keeping database requests active while waiting so the upgrade transaction cannot finish prematurely. Empty or already upgraded databases do not show the notice.

### 6.3 Backend Storage

Backend history has completed conversion to v1 and 7z compression. Replays are stored only in the `replay_archive` BinaryField. The old `replay` JSONField, one-time migration command and its conversion code have been removed. Migration files remain ignored by Git; the deployment script generates and applies the schema migration that drops the old column, preserving binary replays, players, rankings, scores, achievement times and primary keys. For manual deployment, run these commands from `back_end/saolei`:

```bash
python manage.py makemigrations
python manage.py migrate
```

The submission API still accepts a JSON object string and compresses it when creating or improving a score. Replays stay out of Redis; the schema migration does not require rebuilding ranking caches. Old frontend IndexedDB data continues to upgrade as described in Section 6.2, with v0 read compatibility retained.
