import base64
import math
import re

from config.global_settings import MAX_SAFE_INTEGER


LEVEL_SIZES = {'b': (8, 8), 'i': (16, 16), 'e': (16, 30)}
MINE_DIRECTIONS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
MOUSE_ACTIONS = ('mv', 'lc', 'lr', 'rc', 'rr')


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, minimum=-MAX_SAFE_INTEGER):
    _require(type(value) is int and minimum <= value <= MAX_SAFE_INTEGER, 'Expected a safe replay integer')
    return value


def replay_version(replay):
    _require(isinstance(replay, dict), 'Expected a replay object')
    version = _integer(replay.get('version', 0), 0)
    _require(version in (0, 1), f'Unsupported replay version: {version}')
    return version


def _matrix(value, rows, columns):
    _require(isinstance(value, list) and len(value) == rows, 'Invalid replay board height')
    for row in value:
        _require(isinstance(row, list) and len(row) == columns, 'Invalid replay board width')
        for cell in row:
            _integer(cell)
    return value


def _encode_mines(board):
    cells = [cell for row in board for cell in row]
    data = bytes(sum((cells[index + offset] == 16) << (7 - offset) for offset in range(8)) for index in range(0, len(cells), 8))
    return base64.b64encode(data).decode('ascii').rstrip('=')


def _decode_mines(value, rows, columns):
    _require(isinstance(value, str) and len(value) == math.ceil(rows * columns / 6) and re.fullmatch(r'[A-Za-z0-9+/]+', value), 'Invalid replay mine string')
    data = base64.b64decode(value + '=' * (-len(value) % 4), validate=True)
    _require(len(data) * 8 == rows * columns and base64.b64encode(data).decode('ascii').rstrip('=') == value, 'Invalid replay mine padding')
    return [[16 if data[(row * columns + column) // 8] & (1 << (7 - (row * columns + column) % 8)) else 10 for column in range(columns)] for row in range(rows)]


def _decode_questions(value, rows, columns):
    _require(isinstance(value, list) and len(value) == (4 if rows == 8 else 15), 'Invalid replay question count')
    board = [[0] * columns for _ in range(rows)]
    for item in value:
        _require(isinstance(item, list) and len(item) == 3, 'Invalid replay question')
        row, column, direction = map(_integer, item)
        _require(0 < row < rows - 1 and 0 < column < columns - 1 and 0 <= direction < 8, 'Invalid replay question position')
        for r in range(row - 1, row + 2):
            for c in range(column - 1, column + 2):
                _require(board[r][c] == 0, 'Overlapping replay questions')
                board[r][c] = 10
        board[row][column] = 1
        dr, dc = MINE_DIRECTIONS[direction]
        board[row + dr][column + dc] = 16
    return board


def _encode_questions(board, rows, columns):
    questions = []
    for row, cells in enumerate(board):
        for column, cell in enumerate(cells):
            if cell != 1:
                continue
            directions = [
                index for index, (dr, dc) in enumerate(MINE_DIRECTIONS)
                if 0 <= row + dr < rows and 0 <= column + dc < columns and board[row + dr][column + dc] == 16
            ]
            _require(len(directions) == 1, 'A replay question must have one mine')
            questions.append([row, column, directions[0]])
    _require(_decode_questions(questions, rows, columns) == board, 'Invalid replay question board')
    return questions


def _missing_board(mines, target, rows, columns):
    _require(isinstance(target, list) and len(target) == 2, 'Invalid replay target')
    row, column = map(_integer, target)
    _require(0 <= row < rows and 0 <= column < columns and mines[row][column] != 16, 'Invalid replay target')
    board = [
        [
            16 if mines[r][c] == 16 else sum(0 <= r + dr < rows and 0 <= c + dc < columns and mines[r + dr][c + dc] == 16 for dr, dc in MINE_DIRECTIONS)
            for c in range(columns)
        ]
        for r in range(rows)
    ]
    board[row][column] = 10
    return board


def _validate_events(replay):
    events = replay.get('events')
    special_events = replay.get('specialEvents')
    _require(isinstance(events, list) and isinstance(special_events, list), 'Missing replay event arrays')
    times = []
    time, x, y = 0, 0, 0
    for event in events:
        _require(isinstance(event, list) and len(event) == 4, 'Invalid replay mouse tuple')
        dt, dx, dy, action = map(_integer, event)
        _require(dt >= 0 and 0 <= action < len(MOUSE_ACTIONS), 'Invalid replay mouse event')
        time, x, y = _integer(time + dt, 0), _integer(x + dx), _integer(y + dy)
        times.append(time)
    time, previous_index = 0, 0
    for event in special_events:
        _require(isinstance(event, list) and len(event) == 3, 'Invalid replay special tuple')
        dt, index, kind = (_integer(value, 0) for value in event)
        time = _integer(time + dt, 0)
        _require(kind == 0 and previous_index <= index <= len(events), 'Invalid replay insertion index or special type')
        _require((index == 0 or times[index - 1] <= time) and (index == len(events) or time <= times[index]), 'Conflicting replay event order')
        previous_index = index


def _validate_v1(ranking, replay, rows, columns):
    if ranking.game == 'missing-cell':
        rounds = replay.get('rounds')
        _require(isinstance(rounds, list) and len(rounds) == 10, 'Invalid replay round count')
        for item in rounds:
            _require(isinstance(item, dict), 'Invalid replay round')
            mines = _decode_mines(item.get('board'), rows, columns)
            _missing_board(mines, item.get('target'), rows, columns)
            _integer(item.get('timeMs'), 0)
        return
    _require('cellSize' in replay, 'Missing replay cell size')
    if replay['cellSize'] is not None:
        _integer(replay['cellSize'], 1)
    if ranking.game == 'left-click':
        _decode_mines(replay.get('initialBoard'), rows, columns)
    else:
        _decode_questions(replay.get('initialBoard'), rows, columns)
    _validate_events(replay)


def _pixel(value):
    _require(type(value) in (int, float) and abs(value) <= MAX_SAFE_INTEGER and math.isfinite(value), 'Invalid legacy mouse coordinate')
    return _integer(math.floor(value * 32))


def migrate_replay(ranking, replay):
    """Convert v0 source data only; no game simulation, model writes or Redis access."""
    version = replay_version(replay)
    rows, columns = LEVEL_SIZES[ranking.level]
    if version == 1:
        _validate_v1(ranking, replay, rows, columns)
        return replay
    if ranking.game == 'missing-cell':
        rounds = replay.get('rounds')
        _require(isinstance(rounds, list) and len(rounds) == 10, 'Invalid replay round count')
        converted = []
        for item in rounds:
            _require(isinstance(item, dict), 'Invalid legacy replay round')
            board = _matrix(item.get('board'), rows, columns)
            targets = [[row, column] for row, cells in enumerate(board) for column, cell in enumerate(cells) if cell == 10]
            _require(len(targets) == 1, 'Missing cell replay must have one target')
            encoded = _encode_mines(board)
            _require(_missing_board(_decode_mines(encoded, rows, columns), targets[0], rows, columns) == board, 'Invalid legacy missing cell board')
            converted.append({'board': encoded, 'target': targets[0], 'timeMs': _integer(item.get('timeMs'), 0)})
        result = {'version': 1, 'rounds': converted}
    else:
        board = _matrix(replay.get('initialBoard'), rows, columns)
        if ranking.game == 'left-click':
            _require(all(cell in (10, 16) for row in board for cell in row), 'Invalid legacy left-click board')
        initial = _encode_mines(board) if ranking.game == 'left-click' else _encode_questions(board, rows, columns)
        events, special = [], []
        previous_time, previous_special_time, previous_x, previous_y = 0, 0, 0, 0
        old_events = replay.get('events')
        _require(isinstance(old_events, list), 'Missing legacy replay events')
        for event in old_events:
            _require(isinstance(event, dict), 'Invalid legacy replay event')
            time = _integer(event.get('timeMs'), 0)
            if event.get('cancelled') is True:
                special.append([time - previous_special_time, len(events), 0])
                previous_special_time = time
                continue
            x, y = _pixel(event.get('column')), _pixel(event.get('row'))
            _require(event.get('action') in MOUSE_ACTIONS, 'Invalid legacy mouse action')
            events.append([time - previous_time, x - previous_x, y - previous_y, MOUSE_ACTIONS.index(event['action'])])
            previous_time, previous_x, previous_y = time, x, y
        result = {'version': 1, 'cellSize': None, 'initialBoard': initial, 'events': events, 'specialEvents': special}
    _validate_v1(ranking, result, rows, columns)
    return result
