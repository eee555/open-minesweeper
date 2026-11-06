---
title: "Replay Expressions - Open Minesweeper"
description: "Fields, operators, functions and sample differences for the native video player, analyzer counters and custom events."
---

# Replay Expressions

This reference covers the native video player and the counters and custom events on the video analysis page. It does not apply to third-party players. All three use `expr-eval` syntax, but their fields and result requirements differ.

## Three Contexts

| Feature | Video player | Analyzer counter | Analyzer custom event |
| --- | --- | --- | --- |
| Location | Custom counter in the native player dialog | Numeric counter on the analysis page; data tracks reference its results | Custom event rows on the analysis page |
| Input | Replay getters at the current playback position | Native event snapshots and static replay data | The same fields as analyzer counters |
| Final result | Converted to text; numbers and strings can be concatenated | Must be a single number; `NaN` and positive/negative infinity are allowed | Must be a boolean, number or string |
| Evaluation | When playback position updates | At samples selected by each row's sampling mode | Continuous sampling: the last native event in each millisecond |
| Between samples | Does not use analyzer sample interpolation | Linear interpolation over time; outside the sample range, holds the nearest endpoint | Uses sampled occurrence states, not interpolated truth values |
| Display format | `toFixed`, `roundTo` or string concatenation inside the expression | Separate `d3-format` format input, default `.3f` | Color and marker/line styles; no numeric format |
| Errors | Displays the error text | Displays the error in the value cell | Parse/evaluation errors or invalid result types mean the event does not occur |
| Difference function `d` | Not supported | Supported; predecessors follow the row's sampling mode | Supported; predecessors follow continuous sampling |

Custom events use native JavaScript truthiness: `true`, nonzero numbers and nonempty strings mean occurrence; `false`, `0`, `-0`, `NaN` and empty strings mean no occurrence. Positive/negative infinity mean occurrence. `"false"`, `"0"` and whitespace-only strings also mean occurrence. Other types, including arrays and functions, mean no occurrence.

Continuous sampling includes all native event types and samples every millisecond. It uses the last event in that millisecond, or all fields of the latest preceding native event when there is no event, including `time`. The sample timestamp advances, but `time` keeps the source event's original time. Counter button/board-change modes filter eligible events first, then keep the last eligible event in each millisecond without filling gaps. Counter row sampling settings do not affect custom events.

The timeline and board use the same event hover details: pulses show their time and the numeric or string expression result, omitting boolean values; sustained events show their full start time, end time and duration, even when the visible range clips them. Times are displayed in seconds with three decimal places.

The custom-event “Board marker size” setting affects only the board layer. Timeline markers stay at 8px and retain the event shape, color and opacity.

New configurations enable the board custom-event layer with `pluck` selected. Hover over a pulse marker to see its time and value (omitting booleans), or over a sustained-event trace to see its full start time, end time and duration, even when only part of the trace is shown. Saved layer settings are preserved.

## Supported Fields

“Yes” means the name is available directly as an expression variable; “—” means it is not. Names are case-sensitive. Analyzer dynamic values come from sampled events; static values describe the entire replay. The player reads its current getters without substituting 0. Names outside these tables, including `currentMs`, `current_time`, `timeMs` and `bvs`, are not supported. Counter row keys and event keys are not variables in other expressions.

### Static Board and Replay Fields

| Field | Meaning and unit | Video player | Analyzer counter | Custom event |
| --- | --- | --- | --- | --- |
| `row` | Board row count | Yes | Yes | Yes |
| `column` | Board column count | Yes | Yes | Yes |
| `mine_num` | Total mine count | Yes | Yes | Yes |
| `pix_size` | Original replay cell size in pixels, not the displayed size | Yes | Yes | Yes |
| `bbbv` | 3BV of the entire board | Yes | Yes | Yes |
| `op` | Opening count of the entire board | Yes | Yes | Yes |
| `isl` | Island count of the entire board | Yes | Yes | Yes |
| `cell0` | Number of zero (blank) cells on the entire board | Yes | Yes | Yes |
| `cell1` | Number of cells showing 1 on the entire board | Yes | Yes | Yes |
| `cell2` | Number of cells showing 2 on the entire board | Yes | Yes | Yes |
| `cell3` | Number of cells showing 3 on the entire board | Yes | Yes | Yes |
| `cell4` | Number of cells showing 4 on the entire board | Yes | Yes | Yes |
| `cell5` | Number of cells showing 5 on the entire board | Yes | Yes | Yes |
| `cell6` | Number of cells showing 6 on the entire board | Yes | Yes | Yes |
| `cell7` | Number of cells showing 7 on the entire board | Yes | Yes | Yes |
| `cell8` | Number of cells showing 8 on the entire board | Yes | Yes | Yes |
| `zini` | Flagging operation count estimated by a greedy algorithm (ZiNi) | Yes | Yes | Yes |
| `hzini` | Operation count after opening all openings first, then applying the greedy algorithm (Human ZiNi) | Yes | Yes | Yes |
| `rtime` | Total replay duration in seconds, not current playback progress | Yes | Yes | Yes |
| `level` | Replay difficulty level code | Yes | Yes | Yes |
| `mode` | Replay game mode code | Yes | Yes | Yes |

`cell0` through `cell8` are nine separate variables. `cell0-8` is not a variable name.

### Dynamic and Player-Only Fields

| Field | Meaning and unit | Video player | Analyzer counter | Custom event |
| --- | --- | --- | --- | --- |
| `time` | Original sampled event time in seconds; may be negative before the game timer starts and differs from page playback progress | — | Yes | Yes |
| `path` | Cumulative mouse path length, retaining the library's value regardless of displayed cell size | Yes | Yes | Yes |
| `bbbv_solved` | 3BV solved so far | Yes | Yes | Yes |
| `left` | Cumulative left clicks | Yes | Yes | Yes |
| `right` | Cumulative right clicks | Yes | Yes | Yes |
| `double` | Cumulative double clicks | Yes | Yes | Yes |
| `lce` | Cumulative effective left clicks | Yes | Yes | Yes |
| `rce` | Cumulative effective right clicks | Yes | Yes | Yes |
| `dce` | Cumulative effective double clicks | Yes | Yes | Yes |
| `flag` | Flag count | Yes | Yes | Yes |
| `op_solved` | Openings opened so far | — | Yes | Yes |
| `isl_solved` | Islands solved so far | — | Yes | Yes |
| `mouse_state` | Mouse state code; analyzer samples use the state after the native event | Yes | Yes | Yes |
| `bbbv_s` | 3BV per second | Yes | — | — |
| `ce` | Total effective clicks | Yes | — | — |
| `ce_s` | Effective clicks per second | Yes | — | — |
| `cl` | Total clicks | Yes | — | — |
| `cl_s` | Clicks per second | Yes | — | — |
| `left_s` | Left clicks per second | Yes | — | — |
| `right_s` | Right clicks per second | Yes | — | — |
| `double_s` | Double clicks per second | Yes | — | — |
| `flag_s` | Flagging rate | Yes | — | — |
| `etime` | Estimated completion time in seconds | Yes | — | — |
| `rtime_ms` | Total replay duration in milliseconds | Yes | — | — |
| `rqp` | RQP speed metric | Yes | — | — |
| `stnb` | STNB completion and speed metric | Yes | — | — |
| `corr` | Operation accuracy metric | Yes | — | — |
| `thrp` | Throughput efficiency metric | Yes | — | — |
| `ioe` | Index of efficiency | Yes | — | — |
| `pluck` | Cumulative Pluck metric | Yes | Yes | Yes |
| `current_event_id` | Current native event array index, not a time value | Yes | — | — |
| `game_board_state` | Game board state code | Yes | — | — |
| `video_start_time` | Replay start time offset in seconds | Yes | — | — |
| `video_end_time` | Replay end time coordinate in seconds | Yes | — | — |

The analyzer does not expose `bbbv_s`, `cl` or `ce` directly. You can combine supported fields, for example `bbbv_solved / time`, `left + right + double` or `lce + rce + dce`. Such formulas are not guaranteed to match player getter algorithms in every special state.

The Analyzer computes per-event `pluck` when loading a replay. Raw values are preserved: unavailable values may be `NaN`, and the mine-hit failure value is `Number.MAX_VALUE`, without replacement by zero or infinity.

### mouse_state Codes

| Value | State | Meaning |
| --- | --- | --- |
| 1 | `UpUp` | Both left and right buttons released |
| 2 | `UpDown` | Left released, right pressed |
| 3 | `UpDownNotFlag` | Left released, right pressed without placing or removing a flag |
| 4 | `DownUp` | Left pressed, right released |
| 5 | `Chording` | Both buttons pressed |
| 6 | `ChordingNotFlag` | Both pressed after pressing the right button first on a cell that cannot be right-clicked |
| 7 | `DownUpAfterChording` | Right released first after chording, left still pressed |
| 8 | `Undefined` | Uninitialized state |

Names such as `DownUp` are not expression constants. Use their numeric codes, for example `mouse_state == 4`.

## Operators and Syntax

All three contexts support the following operations, but a counter's **final result must still be numeric**. Arrays, strings and booleans may be intermediate results. The table roughly follows precedence from highest to lowest; use parentheses when unsure.

| Operator or syntax | Meaning and example | Video player | Analyzer counter | Custom event |
| --- | --- | --- | --- | --- |
| `(...)` | Grouping, e.g. `(left + right) / time` | Yes | Yes | Yes |
| `f(...)`, `a[i]`, `x.y` | Function call, zero-based indexing and property access, e.g. `[left, right][0]` or `[left, right].length`; does not bypass the variable whitelist | Yes | Yes | Yes |
| `[a, b, ...]`, `"text"`, `'text'` | Array and string literals | Yes | Yes | Yes |
| `x!` | Postfix factorial: `5!` is 120, not logical NOT | Yes | Yes | Yes |
| `x ^ y` | Exponentiation: `2 ^ 3` is 8, not XOR | Yes | Yes | Yes |
| `+x`, `-x`, `not x` | Numeric conversion, negation and logical NOT; unary math functions are listed below | Yes | Yes | Yes |
| `*`, `/`, `%` | Multiplication, division and remainder | Yes | Yes | Yes |
| `+`, `-` | Numeric addition and subtraction; `+` is not string concatenation | Yes | Yes | Yes |
| `x \|\| y` | String concatenation, or array concatenation when both operands are arrays; not logical OR | Yes | Yes | Yes |
| `==`, `!=`, `<`, `<=`, `>`, `>=` | Comparisons, e.g. `left > right` | Yes | Yes | Yes |
| `x in a` | Array membership, e.g. `mouse_state in [4, 5, 7]` | Yes | Yes | Yes |
| `x and y` | Logical AND; skips the right operand if the left is false | Yes | Yes | Yes |
| `x or y` | Logical OR; skips the right operand if the left is true | Yes | Yes | Yes |
| `c ? a : b` | Conditional expression; only evaluates the selected branch; nesting allowed | Yes | Yes | Yes |
| `a; b` | Evaluates in sequence and returns the last result; not a variable declaration | Yes | Yes | Yes |
| `x = value` | Assignment | No | No | No |
| `f(x) = expr` | Function definition | No | No | No |
| `if (...) { ... }`, `&&`, `!x`, `**`, `===`, `=>` | JavaScript statements/operators or arrow functions; not this expression grammar | No | No | No |

Use the keywords `and`, `or` and `not`. Logical results are booleans; use `condition ? 1 : 0` for a numeric counter result. Scientific notation such as `1e-3` is supported. Prefer parentheses around unary function arguments, e.g. `sin(time)^2`, to avoid precedence ambiguity.

### Constants

| Constant or expression | Meaning | All three contexts |
| --- | --- | --- |
| `PI` | Pi | Supported |
| `E` | Euler's number | Supported |
| `true`, `false` | Booleans | Supported, but not valid final counter results |
| `0 / 0` | Produces `NaN` | Supported; retained as a counter number, false for custom events |
| `1 / 0`, `-1 / 0` | Produces positive/negative infinity | Supported; retained as counter numbers, true for custom events |
| `NaN`, `Infinity`, `Inf`, `null`, `undefined` | These names are not built-in constants | Not supported |

## Functions

The table lists built-in functions, application extensions and function-form unary operators, with their supported contexts. `x`, `a` and `f` are argument placeholders, not extra replay fields. Angles are in radians.

Use `toFixed` in the player to retain trailing zeros. It returns text; `roundTo` still returns a number. New default expressions use three decimal places. Saved expressions are preserved; replace display-only `roundTo` calls with `toFixed` where needed. Analyzer counters continue to use their separate format field, such as `.3f`.

<!-- functions -->

| Function | Meaning and example | Video player | Analyzer counter | Custom event |
| --- | --- | --- | --- | --- |
| `abs(x)` | Absolute value, e.g. `abs(-3)` | Yes | Yes | Yes |
| `sign(x)` | Sign; negative/zero/positive numbers normally produce -1/0/1 | Yes | Yes | Yes |
| `ceil(x)` | Round up | Yes | Yes | Yes |
| `floor(x)` | Round down | Yes | Yes | Yes |
| `round(x)` | Round to the nearest integer using JavaScript rounding rules | Yes | Yes | Yes |
| `trunc(x)` | Remove the fractional part towards zero | Yes | Yes | Yes |
| `roundTo(x, n)` | Round to n decimal places, e.g. `roundTo(time, 3)`; negative n rounds to tens, hundreds, etc.; does not pad trailing zeros | Yes | Yes | Yes |
| `toFixed(x, n)` | Return text with fixed decimal places, e.g. `toFixed(3.4, 3)` yields `"3.400"`. Omitted n defaults to 0; precision follows JavaScript `Number.toFixed` (0–100). Combine with `\|\|` | Yes | No; use the separate format field | No |
| `min(a, b, ...)` | Minimum; also accepts an array, e.g. `min([left, right])` | Yes | Yes | Yes |
| `max(a, b, ...)` | Maximum; also accepts an array, e.g. `max([left, right])` | Yes | Yes | Yes |
| `sqrt(x)` | Square root | Yes | Yes | Yes |
| `cbrt(x)` | Cube root | Yes | Yes | Yes |
| `pow(x, y)` | Exponentiation, equivalent to `x ^ y` | Yes | Yes | Yes |
| `hypot(a, b, ...)` | Square root of the sum of squared arguments | Yes | Yes | Yes |
| `pyt(a, b, ...)` | Alias for `hypot` | Yes | Yes | Yes |
| `exp(x)` | `E ^ x` | Yes | Yes | Yes |
| `expm1(x)` | `exp(x) - 1` | Yes | Yes | Yes |
| `ln(x)` | Natural logarithm | Yes | Yes | Yes |
| `log(x)` | Alias for `ln`; not base 10 | Yes | Yes | Yes |
| `log2(x)` | Base-2 logarithm | Yes | Yes | Yes |
| `log10(x)` | Base-10 logarithm | Yes | Yes | Yes |
| `lg(x)` | Alias for `log10` | Yes | Yes | Yes |
| `log1p(x)` | `ln(1 + x)` | Yes | Yes | Yes |
| `sin(x)` | Sine | Yes | Yes | Yes |
| `cos(x)` | Cosine | Yes | Yes | Yes |
| `tan(x)` | Tangent | Yes | Yes | Yes |
| `asin(x)` | Inverse sine | Yes | Yes | Yes |
| `acos(x)` | Inverse cosine | Yes | Yes | Yes |
| `atan(x)` | Inverse tangent | Yes | Yes | Yes |
| `atan2(y, x)` | Direction angle of vector (x, y); y comes first | Yes | Yes | Yes |
| `sinh(x)` | Hyperbolic sine | Yes | Yes | Yes |
| `cosh(x)` | Hyperbolic cosine | Yes | Yes | Yes |
| `tanh(x)` | Hyperbolic tangent | Yes | Yes | Yes |
| `asinh(x)` | Inverse hyperbolic sine | Yes | Yes | Yes |
| `acosh(x)` | Inverse hyperbolic cosine | Yes | Yes | Yes |
| `atanh(x)` | Inverse hyperbolic tangent | Yes | Yes | Yes |
| `gamma(x)` | Gamma function; for positive integer n, `gamma(n) = (n - 1)!` | Yes | Yes | Yes |
| `fac(x)` | Factorial, corresponding to `x!`; non-integers use the Gamma extension | Yes | Yes | Yes |
| `random(n)` | Random number in [0, n); uses 1 if n is omitted or zero; unsuitable for reproducible analysis | Yes | Yes | Yes |
| `length(x)` | String or array length | Yes | Yes | Yes |
| `indexOf(x, a)` | First zero-based index of x in string or array a; -1 if absent | Yes | Yes | Yes |
| `join(sep, a)` | Join array elements into a string using separator sep | Yes | Yes | Yes |
| `map(f, a)` | Apply a function to array elements and return an array, e.g. `map(abs, [-1, 2])` | Yes | Yes | Yes |
| `filter(f, a)` | Keep elements whose function result is truthy; returns an array, e.g. `filter(abs, [-1, 0, 2])` | Yes | Yes | Yes |
| `fold(f, initial, a)` | Reduce an array to one value, e.g. `fold(pow, 2, [3, 2])` produces 64 | Yes | Yes | Yes |
| `if(c, a, b)` | Select a or b based on c, but evaluates both arguments first; use `c ? a : b` for short-circuiting | Yes | Yes | Yes |
| `not(x)` | Logical NOT, also written `not x`; returns a boolean | Yes | Yes | Yes |
| `d(expr)` | Numeric expression at the current sample minus its value at the preceding sample | — | Yes | Yes |
| `d(expr, n)` | Subtract the value n samples earlier; n must be a positive integer | — | Yes | Yes |

<!-- /functions -->

Function arguments to `map`, `filter` and `fold` may use compatible built-ins, not JavaScript arrow functions or new function definitions. There are no general `String`, `Number`, `isNaN`, `isFinite` or `Math.*` functions. Use unary `+` for numeric conversion, `"" || value` for text concatenation and `value != value` to test for `NaN`, replacing value with an actual field or expression. `d` requires a direct call and cannot be used as an array-function callback.

### Difference Rules

| Rule | Explanation |
| --- | --- |
| Operand | A field or numeric expression, e.g. `d(left)`, `d(left + right)` or `d(bbbv_solved) / d(time)` |
| Default step | `d(expr)` equals `d(expr, 1)`; counts retained samples, not milliseconds or native event count |
| Step expression | n is evaluated at the current sample, e.g. `d(left, time > 1 ? 2 : 1)`; nonpositive/noninteger steps are errors |
| Missing predecessors | Returns `NaN`; counters retain it, custom events treat it as no occurrence |
| Nesting | `d(d(left))` and `d(d(left, 2), 3)` work; their first two and five samples respectively are `NaN` |
| No automatic normalization | Does not divide by the step or elapsed time; explicitly divide by `d(time)` for a rate |
| Evaluation order | Filter and deduplicate millisecond samples, then evaluate differences; counter interpolation and formatting happen afterwards |
| Conditional branches | Skipping a difference call does not change which sample is the predecessor |

## Default Counters

On first use, the counters use continuous sampling and the `.3f` display format:

| key | Expression | Default Plot |
| --- | --- | --- |
| `Bvs` | `d(bbbv_solved, 1000) / d(time, 1000)` | Plot 1 |
| `Ces` | `d(lce+rce+dce, 1000)/d(time, 1000)` | Plot 1 |
| `Mov` | `d(path, 1000) / d(time, 1000) / 16` | Plot 2 |

Here, 1000 counts continuous millisecond samples; the denominator uses the difference in the original event's `time`. The first 1000 samples are `NaN`, and a zero time difference can also produce non-finite values. The lowercase `bvs` is no longer a default counter. Saved counter and Plot configurations are preserved.

## Default Custom Events

On first use, the following events are included:

| key | Type | Expression |
| --- | --- | --- |
| `left` | Sustained | `mouse_state in [4, 5, 6, 7]` |
| `right` | Sustained | `mouse_state in [2, 3, 5, 6]` |
| `pluck` | Pulse | `d(pluck)` |

The `pluck` pulse occurs when the cumulative value changes from the previous millisecond. An unchanged value or a `NaN` difference produces no pulse. Existing saved custom events are preserved.

## Examples

| Context | Expression | Result |
| --- | --- | --- |
| Video player | `toFixed(bbbv_s, 3) \|\| "@" \|\| bbbv_solved \|\| "/" \|\| bbbv` | Combine a rate with three decimal places, solved BV and total BV as text |
| Analyzer counter | `time > 0 ? bbbv_solved / time : 0` | Cumulative 3BV/s; the separate format can be `.3f` |
| Analyzer counter | `d(bbbv_solved) / d(time)` | 3BV/s between samples; first sample is `NaN` |
| Pulse custom event | `d(left) > 0` | A pulse when cumulative left clicks increase |
| Sustained custom event | `mouse_state in [4, 5, 6, 7]` | Continuous segments where the left button is pressed |
| Custom event | `mouse_state == 4 and d(left) > 0` | Require both a mouse state and a click increase |

Syntax reference: [expr-eval](https://github.com/silentmatt/expr-eval). Separate counter display formatting: [d3-format](https://d3js.org/d3-format); format is not an expression function.
