"""扫雷网真人验证的命令行交互：由操作者看局面并输入点击，不自动识别或求解。"""
from urllib.parse import urlsplit

import httpx

CHALLENGE_ORIGIN = 'https://saolei.wang'
CHALLENGE_PATH = '/bot/challenge'
CHALLENGE_API = '/api/bot/challenge'
MAX_MOVES = 200
ACTIONS = {'o': 'open', 'f': 'flag', 'c': 'chord', 'open': 'open', 'flag': 'flag', 'chord': 'chord'}


class BotChallengeError(Exception):
    """验证未完成；命令应停止本轮并保留已提交的进度。"""


def is_bot_challenge(location):
    """只接受扫雷网自己的验证跳转，避免把请求引向任意地址。"""
    parts = urlsplit(location)
    return parts.scheme == 'https' and parts.netloc == 'saolei.wang' and parts.path == CHALLENGE_PATH


def check_board(board):
    width, height = board['width'], board['height']
    cells = board['cells']
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0 or len(cells) != width * height:
        raise BotChallengeError('验证盘面尺寸异常')
    # 失败局面会下发全量盘面，其中可能含有展示雷的特殊状态，不限制为 open/flag。
    if not board['token'] or any(not isinstance(cell['state'], int) for cell in cells):
        raise BotChallengeError('验证盘面格式异常')


def render_board(board, write):
    width, height, cells = board['width'], board['height'], board['cells']
    write('     ' + ' '.join(f'{x:>2}' for x in range(1, width + 1)))
    for y in range(height):
        marks = []
        for x in range(width):
            cell = cells[y * width + x]
            if cell['state'] == 2:
                marks.append('F')
            elif cell['state'] == 1:
                marks.append(str(cell['num'] or '·'))
            else:
                marks.append('#')
        write(f'{y + 1:>3}   ' + '  '.join(marks))
    moves = board.get('moves', 0)
    write(f'图例：# 未开，F 旗，· 已开空格，1-8 数字；已进行 {moves} 步')
    mine_cell = board.get('mine_cell', -1)
    if mine_cell >= 0:
        write(f'踩中的雷：第 {mine_cell // width + 1} 行第 {mine_cell % width + 1} 列')


def parse_move(line, board):
    parts = line.strip().lower().split()
    if not parts:
        raise BotChallengeError('请输入「行 列 [o|f|c]」')
    if parts[0] in ('q', 'quit', 'exit'):
        return None
    width, height = board['width'], board['height']
    try:
        row, column = int(parts[0]), int(parts[1])
    except (IndexError, ValueError) as exc:
        raise BotChallengeError('行列必须是两个数字') from exc
    if not 1 <= row <= height or not 1 <= column <= width:
        raise BotChallengeError('行列超出盘面范围')
    index = (row - 1) * width + column - 1
    default = 'c' if board['cells'][index]['state'] == 1 else 'o'
    action = ACTIONS.get(parts[2] if len(parts) > 2 else default)
    if action is None:
        raise BotChallengeError('动作只能是 o（打开）、f（插旗）或 c（连开）')
    return action, index


def start_board(session, write):
    response = session.post(CHALLENGE_API)
    if response.status_code != 200:
        raise BotChallengeError(f'验证开局失败：HTTP {response.status_code}')
    try:
        board = response.json()
        check_board(board)
    except (ValueError, KeyError, TypeError) as exc:
        raise BotChallengeError('验证开局响应格式异常') from exc
    write('已从扫雷网取得新盘面')
    return board


def send_move(session, board, action, index, write):
    base = ''.join(str(cell['state']) for cell in board['cells'])
    response = session.put(CHALLENGE_API, json={'token': board['token'], 'action': action, 'cell': index, 'base': base})
    if response.status_code == 410:
        write('盘面已过期，重新开局')
        return start_board(session, write)
    if response.status_code != 200:
        raise BotChallengeError(f'验证提交失败：HTTP {response.status_code}')
    try:
        data = response.json()
    except ValueError as exc:
        raise BotChallengeError('验证提交响应格式异常') from exc
    if 'cells' in data:
        updated = {**board, **data, 'cells': [dict(cell) for cell in data['cells']]}
    else:
        cells = [dict(cell) for cell in board['cells']]
        for change in data.get('diff', []):
            cells[change['i']] = {'state': change['s'], 'num': change.get('n')}
        states = data.get('states', '')
        if len(states) == len(cells) and states.isdecimal():
            for cell, value in zip(cells, states):
                cell['state'] = int(value)
        updated = {**board, 'cells': cells, 'won': data['won'], 'lost': data['lost'], 'moves': data['moves']}
    updated['token'] = data['token']
    updated['mine_cell'] = data.get('mineCell', -1)
    check_board(updated)
    return updated


def solve_bot_challenge(location, *, read_line, write, client=None):
    """由人完成一次验证，返回本次会话的 Cookie；凭证只保存在当前进程内。"""
    if not is_bot_challenge(location):
        raise BotChallengeError('上游返回了非扫雷网的验证地址')
    session = client if client is not None else httpx.Client(base_url=CHALLENGE_ORIGIN, timeout=30, follow_redirects=False)
    try:
        board = start_board(session, write)
        for _ in range(MAX_MOVES):
            render_board(board, write)
            write('输入「行 列 [o打开 / f插旗 / c连开]」，省略动作按格子状态选 o 或 c；q 退出：')
            try:
                line = read_line()
            except EOFError as exc:
                raise BotChallengeError('没有交互输入；请在终端运行本命令') from exc
            if not line or not line.strip():
                raise BotChallengeError('没有交互输入；请在终端运行本命令')
            try:
                move = parse_move(line, board)
            except BotChallengeError as exc:
                write(f'输入无效：{exc}')
                continue
            if move is None:
                raise BotChallengeError('已取消验证')
            action, index = move
            board = send_move(session, board, action, index, write)
            if board['won']:
                write('验证成功，继续下载录像')
                return dict(session.cookies)
            if board['lost']:
                raise BotChallengeError('踩到雷，验证失败；重跑命令可重新开局')
        raise BotChallengeError('验证步数超出上限')
    finally:
        if client is None:
            session.close()
