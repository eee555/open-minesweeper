"""用透明 PNG 勋章模板生成每种外观一张金色透明 WebP。

成绩颜色由前端柔和金属曲线实现，难度使用独立星级。档位数字由 MedalArt.vue 用 CSS 绘制。
发布文件固定为128x128透明WebP、单张不超过8KiB。新增模板后必须运行test_medal_art.py。
规则见docs/medal/软件架构.md的“勋章图片生成与资源预算”。
运行：back_end/saolei/.venv/Scripts/python.exe front_end/scripts/build_medal_art.py
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / 'src' / 'assets' / 'medal-templates'
OUTPUT_DIR = ROOT / 'public' / 'assets' / 'medals'
SIZE = 320
# 页面最大显示72px；128px源图在高像素密度屏幕上更清晰，同时仍远小于模板原图。
EXPORT_SIZE = 128
MAX_IMAGE_BYTES = 8 * 1024
ABILITY_TEMPLATES = {'breakthrough', 'breakthrough-nf', 'speed', 'speed-nf', 'mastery', 'mastery-nf', 'precision', 'precision-nf'}
TEMPLATES = (
    'breakthrough', 'breakthrough-nf', 'speed', 'speed-nf', 'mastery', 'mastery-nf',
    'precision', 'precision-nf', 'precision-nf-three', 'precision-three',
    'registered', 'reviewed', 'levels', 'levels-nf', 'modes', 'saolei', 'shareholder',
)


def fit_square(image, size):
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    # RGBA 直接复制，避免再次用自身作遮罩将半透明边缘的 alpha 平方。
    canvas.paste(image, ((size - image.width) // 2, (size - image.height) // 2))
    return canvas


def prepare(path, preserve_canvas=False):
    with Image.open(path) as source:
        if source.format != 'PNG' or 'A' not in source.getbands() or source.getchannel('A').getextrema()[0] == 255:
            raise ValueError(f'{path}: medal templates must be PNGs with an existing transparent alpha channel')
        image = source.convert('RGBA')
    box = image.getbbox()
    if not box:
        raise ValueError(f'{path}: medal template is empty')
    if not preserve_canvas:
        image = image.crop(box)
    return fit_square(image, SIZE)


def save_encoded(image, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format='WEBP', quality=50, alpha_quality=45, method=6)
    size = path.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise ValueError(f'{path.relative_to(ROOT)} is {size} bytes; medal images must not exceed {MAX_IMAGE_BYTES} bytes')


def save_art(image, path):
    save_encoded(image.resize((EXPORT_SIZE, EXPORT_SIZE), Image.Resampling.LANCZOS), path)


def main():
    # Keep the approved ability canvas: badge masks and shared stars use those coordinates.
    prepared = [(prepare(TEMPLATE_DIR / f'{name}.png', preserve_canvas=name in ABILITY_TEMPLATES), name) for name in TEMPLATES]
    overlays = TEMPLATE_DIR.parent / 'medal-overlays' / 'difficulty'
    stars = [(prepare(overlays / name, preserve_canvas=True), code) for name, code in [('one-star.png', 'b'), ('two-stars.png', 'i'), ('three-stars.png', 'e')]]
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    # Validate every export and aggregate budget before replacing the published files.
    with TemporaryDirectory(prefix='medal-art-', dir=OUTPUT_DIR.parent) as directory:
        stage = Path(directory)
        for image, name in prepared:
            save_art(image, stage / f'{name}.webp')
        (stage / 'difficulty').mkdir()
        for image, code in stars:
            target = stage / 'difficulty' / f'{code}.webp'
            image.resize((64, 64), Image.Resampling.LANCZOS).save(target, format='WEBP', quality=50, alpha_quality=45, method=6)
            if target.stat().st_size > 2048:
                raise ValueError(f'{target.name}: star overlay exceeds 2KiB')
        files = list(stage.rglob('*.webp'))
        if sum(path.stat().st_size for path in files) > 160 * 1024:
            raise ValueError('Medal library exceeds 160KiB')
        if 6 * max(path.stat().st_size for path in stage.glob('*.webp')) > 44 * 1024:
            raise ValueError('Six medal bodies exceed 44KiB')
        for source in files:
            target = OUTPUT_DIR / source.relative_to(stage)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        # This directory is exclusively owned by this generator. Remove superseded files
        # only after the complete replacement set has passed validation and been copied.
        expected = {path.relative_to(stage) for path in files}
        for old in OUTPUT_DIR.rglob('*'):
            if old.is_file() and old.relative_to(OUTPUT_DIR) not in expected:
                old.unlink()

    print(f'Published {len(prepared)} shared bodies and {len(stars)} shared stars; no per-threshold or per-color image files.')


if __name__ == '__main__':
    main()
