from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
import logging
import os
from pathlib import Path
import re
import stat
from tempfile import NamedTemporaryFile

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

from .config import SHARE_PREVIEW_CACHE_LIMIT, SHARE_PREVIEW_CACHE_TARGET, SHARE_PREVIEW_CELL_SIZE, SHARE_PREVIEW_MAX_COLUMNS, SHARE_PREVIEW_MAX_ROWS, SHARE_PREVIEW_VERSION

logger = logging.getLogger('videomanager')
STANDARD_BOARDS = {'b': (8, 8, 10), 'i': (16, 16, 40), 'e': (16, 30, 99)}
CUSTOM_BOARD = re.compile(r'c([1-9][0-9]?)_([1-9][0-9]?)_([0-9]{1,3})')
CACHE_FILENAME = re.compile(r'[1-9][0-9]*-v[1-9][0-9]*-[0-9a-f]{16}\.png')
PLACEHOLDER_FILENAME = f'placeholder-{SHARE_PREVIEW_VERSION}.png'
PLACEHOLDER_SIZE = (192, 192)


@dataclass(frozen=True)
class PreviewBoard:
    level: str
    rows: int
    columns: int
    mines: int
    bitmap: bytes | None

    @property
    def image_size(self):
        if self.bitmap is None:
            return PLACEHOLDER_SIZE
        return self.columns * SHARE_PREVIEW_CELL_SIZE, self.rows * SHARE_PREVIEW_CELL_SIZE

    def filename(self, video_id: int):
        if self.bitmap is None:
            return PLACEHOLDER_FILENAME
        digest = sha256(self.level.encode('ascii') + b'\0' + self.bitmap).hexdigest()[:16]
        return f'{video_id}-{SHARE_PREVIEW_VERSION}-{digest}.png'


def preview_board(level: str, bitmap: bytes | None) -> PreviewBoard:
    dimensions = STANDARD_BOARDS.get(level)
    if dimensions is None:
        match = CUSTOM_BOARD.fullmatch(level)
        if match is None:
            raise ValueError('Invalid preview level')
        dimensions = tuple(map(int, match.groups()))
    rows, columns, mines = dimensions
    cells = rows * columns
    if not (1 <= rows <= SHARE_PREVIEW_MAX_ROWS and 1 <= columns <= SHARE_PREVIEW_MAX_COLUMNS and 1 <= mines < cells):
        raise ValueError('Unsupported preview dimensions')
    if bitmap is not None:
        bitmap = bytes(bitmap)
        if len(bitmap) != (cells + 7) // 8 or (cells % 8 and bitmap[-1] >> (cells % 8)):
            raise ValueError('Invalid preview bitmap size or padding')
        if sum(byte.bit_count() for byte in bitmap) != mines:
            raise ValueError('Invalid preview mine count')
    return PreviewBoard(level, rows, columns, mines, bitmap)


def completed_cells(board: PreviewBoard) -> list[list[int]]:
    if board.bitmap is None:
        raise ValueError('Preview board is missing')
    cells = [[0] * board.columns for _ in range(board.rows)]
    for index in range(board.rows * board.columns):
        if board.bitmap[index // 8] & (1 << (index % 8)):
            row, column = divmod(index, board.columns)
            cells[row][column] = -1
            for neighbor_row in range(max(0, row - 1), min(board.rows, row + 2)):
                for neighbor_column in range(max(0, column - 1), min(board.columns, column + 2)):
                    if cells[neighbor_row][neighbor_column] != -1:
                        cells[neighbor_row][neighbor_column] += 1
    return cells


@lru_cache(maxsize=1)
def _tiles():
    coordinates = ((0, 2), (0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (2, 1), (3, 1), (2, 3), (1, 2))
    with Image.open(Path(__file__).with_name('share_preview_assets') / 'WinmineXP.png') as source:
        source = source.convert('RGB')
        return tuple(source.crop((column * SHARE_PREVIEW_CELL_SIZE, row * SHARE_PREVIEW_CELL_SIZE, (column + 1) * SHARE_PREVIEW_CELL_SIZE, (row + 1) * SHARE_PREVIEW_CELL_SIZE)) for column, row in coordinates)


def _encode_png(image: Image.Image) -> bytes:
    with BytesIO() as output:
        image.convert('P', palette=Image.Palette.ADAPTIVE, colors=16).save(output, format='PNG', optimize=True)  # noqa: DJM100 Pillow image, not a model.
        return output.getvalue()


def render_preview(board: PreviewBoard) -> bytes:
    image = Image.new('RGB', board.image_size)
    tiles = _tiles()
    for row_index, row in enumerate(completed_cells(board)):
        for column_index, cell in enumerate(row):
            image.paste(tiles[9 if cell == -1 else cell], (column_index * SHARE_PREVIEW_CELL_SIZE, row_index * SHARE_PREVIEW_CELL_SIZE))
    return _encode_png(image)


def render_placeholder() -> bytes:
    image = Image.new('RGB', PLACEHOLDER_SIZE)
    tile = _tiles()[10]
    for row in range(0, PLACEHOLDER_SIZE[1], SHARE_PREVIEW_CELL_SIZE):
        for column in range(0, PLACEHOLDER_SIZE[0], SHARE_PREVIEW_CELL_SIZE):
            image.paste(tile, (column, row))
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 48, 132, 144), fill='#c0c0c0', outline='#808080', width=2)
    draw.text((96, 96), '?', font=ImageFont.load_default(size=72), fill='#808080', anchor='mm')
    return _encode_png(image)


def preview_directory() -> Path:
    return Path(settings.MEDIA_ROOT) / 'thumbnail'


def write_preview(path: Path, png: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, prefix='preview-', suffix='.tmp', delete=False) as output:
            temporary = Path(output.name)
            output.write(png)
        temporary.chmod(0o644)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                logger.exception('Failed to remove preview temporary file: %s', temporary)


def ensure_preview(video_id: int, board: PreviewBoard) -> tuple[str, bool]:
    filename = board.filename(video_id)
    path = preview_directory() / filename
    try:
        exists = stat.S_ISREG(path.lstat().st_mode)
        if not exists:
            raise OSError('Preview path is not a regular file')
    except FileNotFoundError:
        if board.bitmap is None:
            raise FileNotFoundError('Run prepare_share_preview before serving placeholders') from None
        write_preview(path, render_preview(board))
        exists = False
    try:
        os.utime(path)
    except OSError:
        logger.exception('Failed to update preview access time: %s', path)
    return filename, not exists


def delete_preview(video_id: int, level: str, bitmap: bytes | None) -> bool:
    if bitmap is None:
        return False
    try:
        filename = preview_board(level, bitmap).filename(video_id)
        (preview_directory() / filename).unlink()
    except (FileNotFoundError, ValueError):
        return False
    except OSError:
        logger.exception('Failed to remove preview for deleted video: id=%s', video_id)
        return False
    return True


def _cached_files():
    files = []
    try:
        with os.scandir(preview_directory()) as entries:
            for entry in entries:
                if not CACHE_FILENAME.fullmatch(entry.name):
                    continue
                try:
                    if entry.is_file(follow_symlinks=False):
                        files.append((Path(entry.path), entry.stat(follow_symlinks=False).st_mtime_ns))
                except FileNotFoundError:
                    continue
                except OSError:
                    logger.exception('Failed to inspect preview cache entry: %s', entry.path)
    except FileNotFoundError:
        return []
    return files


def prune_previews(*, count_only=False) -> dict[str, int]:
    files = _cached_files()
    deleted = 0
    if not count_only and len(files) >= SHARE_PREVIEW_CACHE_LIMIT:
        for path, _ in sorted(files, key=lambda item: item[1]):
            if deleted >= len(files) - SHARE_PREVIEW_CACHE_TARGET:
                break
            try:
                if stat.S_ISREG(path.lstat().st_mode):
                    path.unlink()
                    deleted += 1
            except FileNotFoundError:
                continue
            except OSError:
                logger.exception('Failed to prune preview cache entry: %s', path)
    return {'before': len(files), 'deleted': deleted, 'remaining': len(_cached_files())}
