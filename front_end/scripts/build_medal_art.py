"""用勋章模板生成每种外观一张金色透明 WebP。

铜和银由前端按同一套换色公式从这张金色底图算出。档位数字由 MedalArt.vue 用 CSS 绘制。
发布文件固定为128x128透明WebP、单张不超过8KiB。新增模板后必须运行test_medal_art.py。
规则见docs/medal/软件架构.md的“勋章图片生成与资源预算”。
运行：back_end/saolei/.venv/Scripts/python.exe front_end/scripts/build_medal_art.py
"""
from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / 'src' / 'assets' / 'medal-templates'
OUTPUT_DIR = ROOT / 'public' / 'assets' / 'medals'
SIZE = 320
# 页面最大显示72px；128px源图在高像素密度屏幕上更清晰，同时仍远小于模板原图。
EXPORT_SIZE = 128
MAX_IMAGE_BYTES = 8 * 1024


def is_background(red, green, blue, kind):
    if kind == 'black':
        return red < 28 and green < 28 and blue < 28
    if max(red, green, blue) - min(red, green, blue) > 16:
        return False
    average = (red + green + blue) / 3
    return 110 <= average <= 220


def clear_background(image, kind):
    rgba = image.convert('RGBA')
    width, height = rgba.size
    pixels = rgba.load()
    seen = bytearray(width * height)
    queue = deque()

    def push(x, y):
        index = y * width + x
        if seen[index]:
            return
        red, green, blue, _alpha = pixels[x, y]
        if not is_background(red, green, blue, kind):
            return
        seen[index] = 1
        queue.append((x, y))

    for x in range(width):
        push(x, 0)
        push(x, height - 1)
    for y in range(height):
        push(0, y)
        push(width - 1, y)
    while queue:
        x, y = queue.popleft()
        pixels[x, y] = (0, 0, 0, 0)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                push(nx, ny)
    for _pass in range(8):
        pending = []
        for y in range(height):
            for x in range(width):
                red, green, blue, alpha = pixels[x, y]
                if alpha == 0 or not is_background(red, green, blue, kind):
                    continue
                neighbors = ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                if any(0 <= nx < width and 0 <= ny < height and pixels[nx, ny][3] == 0 for nx, ny in neighbors):
                    pending.append((x, y))
        for x, y in pending:
            pixels[x, y] = (0, 0, 0, 0)
        if not pending:
            break
    return rgba


def fit_square(image, size):
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    canvas.paste(image, ((size - image.width) // 2, (size - image.height) // 2), image)
    return canvas


def prepare(path, kind):
    image = clear_background(Image.open(path), kind)
    box = image.getbbox()
    if box:
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


def clean_output():
    if not OUTPUT_DIR.exists():
        return
    for path in OUTPUT_DIR.rglob('*'):
        if path.is_file():
            path.unlink()
    for path in sorted((path for path in OUTPUT_DIR.rglob('*') if path.is_dir()), reverse=True):
        path.rmdir()


def write_single(base, folder):
    save_art(base, OUTPUT_DIR / f'{folder}.webp')


def main():
    clean_output()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    templates = (
        ('breakthrough.png', 'black', 'breakthrough'),
        ('breakthrough-nf.png', 'black', 'breakthrough-nf'),
        ('speed.png', 'black', 'speed'),
        ('speed-nf.png', 'black', 'speed-nf'),
        ('mastery.png', 'black', 'mastery'),
        ('mastery-nf.png', 'black', 'mastery-nf'),
        ('precision.png', 'checker', 'precision'),
        ('precision-nf.png', 'checker', 'precision-nf'),
        ('precision-nf-three.png', 'checker', 'precision-nf-three'),
        ('precision-three.jpg', 'black', 'precision-three'),
        ('registered.png', 'black', 'registered'),
        ('reviewed.png', 'checker', 'reviewed'),
        ('levels.png', 'black', 'levels'),
        ('levels-nf.png', 'checker', 'levels-nf'),
        ('modes.png', 'black', 'modes'),
        ('saolei.png', 'black', 'saolei'),
        ('shareholder.png', 'black', 'shareholder'),
    )
    count = 0
    for filename, background, folder in templates:
        path = TEMPLATE_DIR / filename
        if not path.exists():
            continue
        write_single(prepare(path, background), folder)
        count += 1
        print(folder, count)
    print('total', count)


if __name__ == '__main__':
    main()
