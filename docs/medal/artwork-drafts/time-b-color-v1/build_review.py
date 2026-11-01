"""Arrange unmodified imagegen color studies with live threshold labels for review."""
from pathlib import Path
import json

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SIZES = (32, 40, 48, 64, 72)


def font(size, bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/' + ('msyhbd.ttc' if bold else 'msyh.ttc'), size)


def text(draw, xy, value, size=18, color='#263442', bold=False):
    draw.text(xy, value, font=font(size, bold), fill=color)


def place(canvas, path, xy, size):
    # Presentation resizing/compositing only; never overwrite the generated source.
    with Image.open(ROOT / path) as source:
        thumb = source.convert('RGBA')
        thumb.thumbnail((size, size), Image.Resampling.LANCZOS)
    x, y = xy
    canvas.alpha_composite(thumb, (x + (size - thumb.width) // 2, y + (size - thumb.height) // 2))


def sheet(data, dark=False):
    bg, fg, muted, line = ('#101722', '#e9edf4', '#b0bfd1', '#344356') if dark else ('#f7f7f3', '#263442', '#56677a', '#d7dfe5')
    canvas = Image.new('RGBA', (1600, 1300), bg)
    draw = ImageDraw.Draw(canvas)
    text(draw, (60, 32), 'OPENMS / BEGINNER TIME / COLOR REVIEW 01', 15, muted)
    text(draw, (60, 70), '初级破境 · 全部 11 档配色审阅', 36, fg, True)
    text(draw, (60, 128), 'SubX = 用时严格小于 X 秒；同色档复用同一造型，精确门槛由文字表达。', 19, muted)
    for n, tier in enumerate(data['palette']):
        x = 60 + n * 300
        place(canvas, tier['source'], (x, 188), 230)
        text(draw, (x + 20, 428), f"{tier['name']} / {tier['id']}", 22, fg, True)
        text(draw, (x + 20, 465), tier['target_hex'], 17, muted)
        text(draw, (x + 20, 496), ' / '.join('Sub' + str(v) for v in tier['seconds']), 17, muted)
    draw.line((60, 555, 1540, 555), fill=line, width=1)
    text(draw, (60, 580), '完整门槛阶梯 · 72px 图案', 25, fg, True)
    for n, medal in enumerate(data['medals']):
        x = 60 + n * 134
        place(canvas, medal['source'], (x + 21, 640), 72)
        text(draw, (x + 14, 732), medal['label'], 20, fg, True)
        text(draw, (x + 22, 770), medal['color_name'], 16, muted)
    draw.line((60, 825, 1540, 825), fill=line, width=1)
    text(draw, (60, 848), '尺寸检查 · 32 / 40 / 48 / 64 / 72px', 25, fg, True)
    for n, tier in enumerate(data['palette']):
        x = 60 + n * 300
        text(draw, (x, 900), tier['name'], 20, fg, True)
        cursor = x
        for size in SIZES:
            place(canvas, tier['source'], (cursor, 955 + 72 - size), size)
            text(draw, (cursor, 1040), str(size), 13, muted)
            cursor += size + 8
    text(draw, (60, 1135), '分界为本轮审阅提案：以 Sub10 / Sub6 / Sub4 / Sub2 为换色节点，并非已确认的能力标准。', 18, muted)
    text(draw, (60, 1172), '图案沿用已确认的 v3 去外框模板；图片仅换色，名称与门槛不烘焙进源图。', 18, muted)
    text(draw, (60, 1209), '本稿仅供审阅，未修改正式模板、发放门槛、运行时配色或站点发布资源。', 18, muted)
    return canvas.convert('RGB')


def page(data):
    stages = []
    for medal in data['medals']:
        stages.append(f'''<button class="stage" data-tier="{medal['tier']}" data-label="{medal['label']}"><img src="{medal['source']}" width="72" height="72" alt="初级破境 {medal['label']}"><strong>{medal['label']}</strong><small>初级 · {medal['color_name']}</small></button>''')
    colors = []
    for tier in data['palette']:
        labels = ' / '.join(f'Sub{v}' for v in tier['seconds'])
        samples = ''.join(f'<figure><img src="{tier["source"]}" width="{s}" height="{s}" alt="{s}px {tier["name"]}"><figcaption>{s}px</figcaption></figure>' for s in SIZES)
        colors.append(f'''<article><div class="label"><h3>{tier['name']}</h3><span>{tier['id']} · {tier['target_hex']}</span></div><button class="large" data-tier="{tier['id']}" data-label="{labels}" aria-label="放大{tier['name']}模板"><img src="{tier['source']}" alt="{tier['name']}破境透明原图"></button><p class="thresholds">{labels}</p><div class="sizes">{samples}</div><a href="{tier['source']}" download>下载透明 PNG</a></article>''')
    template = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>初级 time · 11 档配色审阅</title><style>
:root{--bg:#f7f7f3;--paper:#fff;--fg:#263442;--muted:#56677a;--line:#d7dfe5;color-scheme:light}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.65 'Microsoft YaHei','Segoe UI',sans-serif}body.dark{--bg:#101722;--paper:#172231;--fg:#e9edf4;--muted:#b0bfd1;--line:#344356;color-scheme:dark}body.gray img{filter:grayscale(1)}main{max-width:1550px;margin:auto;padding:42px 36px}h1{font-size:34px;margin:14px 0}h2{font-size:22px;margin:0 0 10px}h3{font-size:19px;margin:0}p{margin:8px 0}.eyebrow,small,.note,footer{color:var(--muted)}.eyebrow{letter-spacing:.12em;font-size:12px}.tools{display:flex;gap:10px;flex-wrap:wrap;margin:28px 0}button{font:inherit;color:inherit;cursor:pointer}button,a{touch-action:manipulation}button.tool{padding:8px 16px;background:var(--paper);border:1px solid var(--line);border-radius:5px}button[aria-pressed=true]{outline:2px solid var(--fg);outline-offset:2px}.section{padding:28px 0;border-top:1px solid var(--line)}.track{display:grid;grid-template-columns:repeat(11,minmax(110px,1fr));overflow:auto;margin-top:26px;padding-bottom:10px}.stage{border:0;background:transparent;display:flex;flex-direction:column;align-items:center;gap:9px;padding:14px 10px}.stage img{object-fit:contain}.stage strong{font-size:18px}.stage:hover,.stage:focus-visible{outline:1px solid var(--muted);outline-offset:-2px}.palette{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:18px;margin-top:24px}article{border:1px solid var(--line);border-radius:7px;background:var(--paper);padding:18px;min-width:0}.label span{color:var(--muted);font-size:12px}.large{display:block;margin:18px auto 10px;background:transparent;border:0;width:100%;padding:0;aspect-ratio:1}.large img{width:100%;height:100%;object-fit:contain}.thresholds{text-align:center;font-size:14px}.sizes{display:flex;justify-content:space-between;gap:4px;overflow:auto;align-items:flex-end;margin:20px 0;border-top:1px solid var(--line);padding-top:18px}.sizes figure{margin:0;display:flex;flex-direction:column;align-items:center;gap:7px}.sizes img{object-fit:contain}.sizes figcaption{font-size:11px;color:var(--muted)}a{color:inherit;text-underline-offset:3px}article>a{font-size:12px;color:var(--muted)}.compare{display:flex;align-items:center;gap:26px;flex-wrap:wrap}.compare figure{margin:12px 0;text-align:center}.compare img{width:140px;height:140px;object-fit:contain}.compare figcaption{font-size:12px;color:var(--muted)}footer{border-top:1px solid var(--line);padding-top:20px;font-size:13px}.links{display:flex;gap:18px;flex-wrap:wrap}dialog{color:var(--fg);background:var(--paper);border:1px solid var(--line);border-radius:8px;width:min(750px,calc(100% - 32px));padding:24px}dialog::backdrop{background:#0009}.dialog-head{display:flex;justify-content:space-between;align-items:center;gap:12px}dialog img{display:block;width:100%;max-height:65vh;object-fit:contain;margin:12px auto}dialog button{background:var(--paper);border:1px solid var(--line);padding:5px 14px;border-radius:4px}@media(max-width:1300px){.palette{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:780px){main{padding:26px 18px}h1{font-size:27px}.palette{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:500px){.palette{grid-template-columns:1fr}.large{max-width:260px}.sizes{justify-content:space-evenly}}
</style></head><body><main><header><div class="eyebrow">OPENMS / BEGINNER TIME / COLOR REVIEW 01</div><h1>初级破境 · 全部 11 档配色审阅</h1><p>沿用已确认的去外框箭头，以青绿 → 蓝 → 紫 → 橙 → 玫红表示成绩档次。</p><p class="note">门槛分组为本轮审阅提案；尚未修改发放规则或接入站点。</p></header><div class="tools"><button class="tool" id="theme" aria-pressed="false">深色背景</button><button class="tool" id="gray" aria-pressed="false">灰度检查</button></div><section class="section"><h2>完整 11 档 · 72px</h2><p class="note">SubX 表示用时严格小于 X 秒；同色档复用同一造型。点击任一档放大查看。</p><div class="track">STAGES</div></section><section class="section"><h2>五种具体配色与实际尺寸</h2><p class="note">换色节点暂取 Sub10、Sub6、Sub4、Sub2。色值规定主色方向，亮面与暗面保留材质变化。</p><div class="palette">COLORS</div></section><section class="section"><h2>与确认模板对照</h2><div class="compare"><figure><img src="../v3/templates/breakthrough.png" alt="已确认的金色造型模板"><figcaption>已确认的 v3 基础造型</figcaption></figure><p class="note">沿用上升折线、箭头和周围碎片，移除统一外框的方向保持不变。<br>五种颜色均为 imagegen 直接编辑稿；本轮重点审阅色相、明暗质感、小尺寸辨识和分界。</p></div></section><footer><div class="links"><a href="overview-light.png">浅色总览</a><a href="overview-dark.png">深色总览</a><a href="review.json">逐档映射</a><a href="generation-record.json">生成提示词</a><a href="README.md">说明</a></div><p>仅供审阅。32 / 40 / 48 / 64 / 72px 在浏览器缩放 100% 时对应 CSS 像素。精确名称和门槛由文字显示，不烘焙进图案。</p></footer></main><dialog id="detail"><div class="dialog-head"><strong id="detail-title"></strong><button id="close">关闭</button></div><img id="detail-image" alt="放大配色勋章"><a id="download" download>下载该色透明 PNG 原图</a></dialog><script>
const palette=DATA;const $=id=>document.getElementById(id);for(const [id,cls] of [['theme','dark'],['gray','gray']]){$(id).onclick=()=>$(id).setAttribute('aria-pressed',String(document.body.classList.toggle(cls)))}document.querySelectorAll('[data-tier]').forEach(button=>button.onclick=()=>{const tier=palette.find(t=>t.id===button.dataset.tier);$('detail-title').textContent='初级破境 · '+button.dataset.label+' · '+tier.name;$('detail-image').src=tier.source;$('download').href=tier.source;$('detail').showModal()});$('close').onclick=()=>$('detail').close();$('detail').addEventListener('click',event=>{if(event.target===$('detail')){const rect=$('detail').getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)$('detail').close()}});
</script></body></html>'''
    return template.replace('STAGES', ''.join(stages)).replace('COLORS', ''.join(colors)).replace('DATA', json.dumps(data['palette'], ensure_ascii=False))


if __name__ == '__main__':
    data = json.loads((ROOT / 'review.json').read_text(encoding='utf-8'))
    for dark, name in ((False, 'light'), (True, 'dark')):
        sheet(data, dark).save(ROOT / f'overview-{name}.png')
    (ROOT / 'index.html').write_text(page(data), encoding='utf-8')
    print('Built 11-stage beginner time review with 5 color sources and light/dark sheets.')
