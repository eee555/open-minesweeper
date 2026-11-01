"""Display the unmodified imagegen star-count drafts at matching canvas sizes."""
from pathlib import Path
import json

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SIZES = (32, 40, 48, 64, 72)


def text(draw, position, value, size, color, bold=False):
    face = 'msyhbd.ttc' if bold else 'msyh.ttc'
    draw.text(position, value, font=ImageFont.truetype(f'C:/Windows/Fonts/{face}', size), fill=color)


def place(canvas, source, position, size):
    # Presentation scaling only: keep every generated source and its alpha intact.
    with Image.open(ROOT / source) as raw:
        image = raw.convert('RGBA')
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
    x, y = position
    canvas.alpha_composite(image, (x + (size - image.width) // 2, y + (size - image.height) // 2))


def sheet(items, dark=False):
    bg, fg, muted, line = ('#101722', '#e9edf4', '#a7b5c7', '#344356') if dark else ('#f7f7f3', '#263442', '#586b7e', '#d7dfe5')
    canvas = Image.new('RGBA', (1440, 1040), bg)
    draw = ImageDraw.Draw(canvas)
    text(draw, (60, 28), 'OPENMS / TIME STAR DIFFICULTY STUDY 01', 15, muted)
    text(draw, (60, 66), 'Time 破境 · 左上角星级标记', 34, fg, True)
    text(draw, (60, 120), '同一金色模板：初级一颗星 / 中级两颗星 / 高级三颗星。', 20, muted)
    for index, item in enumerate(items):
        x = 60 + index * 440
        place(canvas, item['source'], (x + 25, 182), 360)
        text(draw, (x + 130, 560), item['name'], 28, fg, True)
        text(draw, (x + 105, 607), f"{item['shape']}", 19, muted)
        cursor = x + 24
        for size in SIZES:
            place(canvas, item['source'], (cursor, 725 - size), size)
            text(draw, (cursor, 741), f'{size}px', 13, muted)
            cursor += size + 15
    draw.line((60, 804, 1380, 804), fill=line, width=1)
    text(draw, (60, 832), '观察重点：32–72px 下能否辨认星星数量，星级标记是否与破境主体协调。', 20, fg)
    text(draw, (60, 880), '本轮只展示 time 的难度区别，不叠加成绩色档、Sub 数值或 NF 副章。', 18, muted)
    text(draw, (60, 922), '审阅稿保留在独立目录，未替换已确认源模板或站点发布资源。', 18, muted)
    return canvas.convert('RGB')


def page(items):
    cards = []
    for item in items:
        sizes = ''.join(f'<figure><img src="{item["source"]}" width="{size}" height="{size}" alt="{item["name"]} {size}px"><figcaption>{size}px</figcaption></figure>' for size in SIZES)
        cards.append(f'''<article><h2>{item['name']}</h2><p class="muted">{item['shape']}</p><button class="enlarge" data-slug="{item['slug']}" aria-label="放大{item['name']}样例"><img src="{item['source']}" alt="{item['name']} time 破境勋章"></button><div class="sizes">{sizes}</div><a href="{item['source']}" download>下载透明 PNG 原图</a></article>''')
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Time 难度区别 · 左上角星级方案</title><style>
:root{--bg:#f7f7f3;--paper:#fff;--fg:#263442;--muted:#586b7e;--line:#d7dfe5;color-scheme:light}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.65 'Microsoft YaHei','Segoe UI',sans-serif}body.dark{--bg:#101722;--paper:#172231;--fg:#e9edf4;--muted:#a7b5c7;--line:#344356;color-scheme:dark}main{max-width:1440px;margin:auto;padding:40px 32px}.eyebrow{font-size:12px;letter-spacing:.12em;color:var(--muted)}h1{font-size:32px;margin:14px 0}h2{font-size:23px;margin:0}.muted,footer{color:var(--muted)}p{margin:6px 0}button{font:inherit;cursor:pointer;color:inherit}.tools{display:flex;gap:12px;margin:24px 0}button.tool{padding:8px 16px;background:var(--paper);border:1px solid var(--line);border-radius:5px}button[aria-pressed=true]{outline:2px solid var(--fg);outline-offset:2px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px}article{min-width:0;background:var(--paper);border:1px solid var(--line);padding:22px;border-radius:7px;text-align:center}.enlarge{width:100%;aspect-ratio:1;padding:0;margin:10px auto 20px;background:transparent;border:0;display:block}.enlarge img{width:100%;height:100%;object-fit:contain}.sizes{display:flex;gap:8px;justify-content:space-evenly;align-items:flex-end;overflow-x:auto;padding:18px 0;border-block:1px solid var(--line);margin-bottom:18px}.sizes figure{display:flex;flex-direction:column;align-items:center;gap:8px;margin:0;flex-shrink:0}.sizes img{object-fit:contain}.sizes figcaption,article>a{font-size:12px;color:var(--muted)}a{color:inherit;text-underline-offset:3px}footer{border-top:1px solid var(--line);margin-top:30px;padding-top:22px;font-size:13px}.links{display:flex;gap:20px;flex-wrap:wrap}dialog{width:min(820px,calc(100% - 32px));color:var(--fg);background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:24px}dialog::backdrop{background:#0009}.dialog-head{display:flex;justify-content:space-between;align-items:center}dialog img{width:100%;height:65vh;object-fit:contain}dialog button{background:var(--paper);border:1px solid var(--line);padding:6px 16px;border-radius:4px}@media(max-width:1050px){.grid{gap:12px}article{padding:12px}.sizes{justify-content:flex-start}}@media(max-width:650px){main{padding:24px 16px}h1{font-size:26px}.grid{grid-template-columns:1fr}.enlarge{max-width:350px}.sizes{justify-content:space-evenly}}
</style></head><body><main><header><div class="eyebrow">OPENMS / TIME STAR DIFFICULTY STUDY 01</div><h1>Time 破境 · 左上角星级方案</h1><p>沿用同一金色模板，左上角横排：初级一颗星、中级两颗星、高级三颗星。</p><p class="muted">点击放大；下方提供 32 / 40 / 48 / 64 / 72px 对照。</p></header><div class="tools"><button class="tool" id="theme" aria-pressed="false">深色背景</button></div><section class="grid">''' + ''.join(cards) + '''</section><footer><div class="links"><a href="overview-light.png">浅色对照图</a><a href="overview-dark.png">深色对照图</a><a href="../v3/templates/breakthrough.png">原始确认模板</a><a href="README.md">源图与说明</a><a href="generation-record.json">生成提示词</a></div><p>观察重点：小尺寸下能否分清一／二／三颗星，星星与箭头的视觉关系。浏览器缩放 100% 时尺寸行对应 CSS 像素。</p><p>仅为方案审阅稿，尚未替换正式模板或站点资源。</p></footer></main><dialog id="detail"><div class="dialog-head"><strong id="detail-title"></strong><button id="close">关闭</button></div><img id="detail-image" alt="放大勋章"><a id="download" download>下载透明 PNG 原图</a></dialog><script>const items=''' + json.dumps(items, ensure_ascii=False) + ''';const $=id=>document.getElementById(id);$('theme').onclick=()=>$('theme').setAttribute('aria-pressed',String(document.body.classList.toggle('dark')));document.querySelectorAll('[data-slug]').forEach(button=>button.onclick=()=>{const item=items.find(i=>i.slug===button.dataset.slug);$('detail-title').textContent=item.name+' · '+item.shape;$('detail-image').src=item.source;$('download').href=item.source;$('detail').showModal()});$('close').onclick=()=>$('detail').close();</script></body></html>'''


if __name__ == '__main__':
    items = json.loads((ROOT / 'review.json').read_text(encoding='utf-8'))
    for dark, name in ((False, 'light'), (True, 'dark')):
        sheet(items, dark).save(ROOT / f'overview-{name}.png')
    (ROOT / 'index.html').write_text(page(items), encoding='utf-8')
    print('Built 3 difficulty comparisons: light/dark sheets and review page.')
