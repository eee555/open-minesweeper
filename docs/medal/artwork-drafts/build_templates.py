"""Build the isolated v1 medal review assets; does not write production files.

Requires Pillow and Node.js with sharp. Pass --node and --sharp when using
the bundled Codex runtime. All SVG geometry is authored here at 64 x 64.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
VERSION = 'v1'
INK = '#475569'
SIZES = [32, 40, 48, 64, 72, 128, 160]

# Large, open silhouettes. A consistent 5-unit line becomes 2.5px at 32px.
DOOR = '<path d="M31 11H12v42h19"/><path d="M27 32h28M45 22l10 10-10 10"/>'
BOLT = '<path fill="currentColor" stroke="none" d="M34 7 11 36h18l-6 21 31-32H36l7-18Z"/>'
STAR = '<path fill="currentColor" stroke="none" d="m32 5 8 19 19 8-19 8-8 19-8-19-19-8 19-8Z"/>'
TARGET = '<circle cx="32" cy="32" r="16"/><path d="M32 7v14m0 22v14M7 32h14m22 0h14"/><circle cx="32" cy="32" r="4" fill="currentColor" stroke="none"/>'
STEPS = '<path fill="currentColor" stroke="none" d="M8 54V40h15V26h15V11h18v43Z"/>'
ID_CARD = '<rect x="8" y="13" width="48" height="38" rx="5"/><circle cx="23" cy="27" r="5"/><path d="M15 42c0-9 16-9 16 0m8-16h9m-9 13h9"/>'
VIDEO = '<rect x="8" y="12" width="45" height="39" rx="5"/><path fill="currentColor" stroke="none" d="m22 22 15 10-15 10Z"/>'
MODES = '<circle cx="18" cy="18" r="9" fill="currentColor" stroke="none"/><rect x="37" y="9" width="18" height="18" rx="3" fill="currentColor" stroke="none"/><path fill="currentColor" stroke="none" d="M9 55V36l19 19Zm37-22 12 12-12 12-12-12Z"/>'
LINK = '<path d="m25 21 6-6a12 12 0 0 1 17 17l-6 6m-3 5-6 6a12 12 0 0 1-17-17l6-6M23 41l18-18"/>'
SEED = '<path d="M32 55V31m-12 25h24"/><path fill="currentColor" stroke="none" d="M32 36C14 36 8 24 9 12c15-1 25 7 23 24Zm0-8C32 14 43 7 56 9c1 14-8 23-24 23Z"/>'


def mark(body: str, kind: str, key: str) -> str:
    """One 24-unit marker, with transparent knockout under it."""
    mask_id = f'clear-{key}'
    base = f'<defs><mask id="{mask_id}"><rect width="64" height="64" fill="white" stroke="none"/><rect x="39" y="37" width="25" height="27" fill="black" stroke="none"/></mask></defs><g mask="url(#{mask_id})"><g transform="scale(.82)">{body}</g></g>'
    if kind == 'nf':
        # A crossed flag is a single combined NF symbol, not lettering.
        marker = '<g stroke-width="4"><path d="M45 60V41h15l-5 6 5 6H45"/><path d="m41 58 20-20"/></g>'
    elif kind == 'fl':
        marker = '<path stroke-width="4" d="M45 60V40h15l-5 6 5 6H45"/>'
    elif kind == 'check':
        marker = '<path stroke-width="6" d="m39 49 7 7 14-17"/>'
    else:
        raise ValueError(kind)
    return base + marker


def triple(kind: str, key: str) -> str:
    # Open rings stay transparent; interrupted connectors do not run through them.
    rings = '<path d="M29 17h6M23 25l5 10m13-10-5 10"/><circle cx="20" cy="17" r="9"/><circle cx="44" cy="17" r="9"/><circle cx="32" cy="43" r="9"/>'
    return mark(rings, kind, key)


TEMPLATES = [
    ('breakthrough', 'b', '破境', '能力', '断开的门框与穿过缺口的箭头。', DOOR),
    ('speed', 's', '神速', '能力', '单个宽折角闪电，保留明显的横向缺口。', BOLT),
    ('mastery', 'm', '通明', '能力', '四角光芒，以对称实心轮廓识别。', STAR),
    ('breakthrough-nf', 'bn', '盲扫破境', '能力', '破境主符号，右下角为统一断旗标记。', mark(DOOR, 'nf', 'bn')),
    ('speed-nf', 'sn', '盲扫神速', '能力', '神速主符号，右下角为统一断旗标记。', mark(BOLT, 'nf', 'sn')),
    ('mastery-nf', 'mn', '盲扫通明', '能力', '通明主符号，右下角为统一断旗标记。', mark(STAR, 'nf', 'mn')),
    ('precision-nf', 'pn', '盲扫精工', '能力', '圆形准星，配断旗标记。', mark(TARGET, 'nf', 'pn')),
    ('precision', 'pf', '标旗精工', '能力', '圆形准星，配完整旗帜标记。', mark(TARGET, 'fl', 'pf')),
    ('precision-nf-three', 'tn', '三阶盲扫精工', '能力', '三个相连的圆形节点，配断旗标记。', triple('nf', 'tn')),
    ('precision-three', 'tf', '三阶标旗精工', '能力', '三个相连的圆形节点，配完整旗帜标记。', triple('fl', 'tf')),
    ('registered', 'r', '实名在册', '新手', '身份卡上的头像与两条资料线。', ID_CARD),
    ('reviewed', 'v', '录像过审', '新手', '录像播放框与右下角审核勾。', mark(VIDEO, 'check', 'v')),
    ('levels', 'l', '扫雷新秀', '新手', '三个高度逐级上升的实心台阶。', STEPS),
    ('levels-nf', 'ln', '盲扫新秀', '新手', '三阶台阶，配统一断旗标记。', mark(STEPS, 'nf', 'ln')),
    ('modes', 'o', '走马观花', '新手', '圆、方、三角、菱形代表多种模式。', MODES),
    ('saolei', 'a', '旧迹新篇', '新手', '相扣的两个链环，表示账号关联。', LINK),
    ('shareholder', 'h', '原始股东', '其他', '双叶种子与根基线，表示早期扎根。', SEED),
]


def svg(key: str, name: str, body: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" color="{INK}" role="img" aria-labelledby="title-{key}">
  <title id="title-{key}">{html.escape(name)} 基础模板 {VERSION}</title>
  <g fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">
    {body}
  </g>
</svg>
'''


def font(size: int, bold: bool = False):
    fonts = Path('C:/Windows/Fonts')
    path = fonts / ('msyhbd.ttc' if bold else 'msyh.ttc')
    return ImageFont.truetype(str(path), size)


def text(draw, pos, content, size=18, fill='#182230', bold=False, anchor=None):
    draw.text(pos, content, font=font(size, bold), fill=fill, anchor=anchor)


def overview(items, renders: Path, dark=False):
    bg, panel, line, fg, muted = ('#101722', '#172231', '#334155', '#E2E8F0', '#A3B1C3') if dark else ('#F7F7F3', '#FFFFFF', '#DFE3E5', '#23303E', '#657487')
    im = Image.new('RGB', (1440, 1390), bg)
    d = ImageDraw.Draw(im)
    text(d, (64, 38), 'OPENMS  /  MEDAL TEMPLATES', 16, muted)
    text(d, (64, 76), '勋章基础模板', 38, fg, True)
    text(d, (64, 133), '第一轮检阅 · 17 个系列 · 同色图形比较 · v1', 19, muted)
    text(d, (1376, 91), '待检阅', 18, muted, anchor='ra')
    d.line((64, 186, 1376, 186), fill=line, width=1)
    theme = 'dark' if dark else 'light'
    for group, subset, top in [('能力系列', items[:10], 220), ('新手与其他系列', items[10:], 800)]:
        text(d, (64, top), group, 21, fg, True)
        text(d, (1376, top + 3), f'{len(subset):02d} TEMPLATES', 14, muted, anchor='ra')
        y0 = top + 46
        for i, item in enumerate(subset):
            col, row = i % 5, i // 5
            x, y = 64 + col * 266, y0 + row * 248
            d.rounded_rectangle((x, y, x+248, y+230), radius=10, fill=panel, outline=line)
            text(d, (x+18, y+13), item['id'], 15, muted)
            art = Image.open(renders / f"{item['slug']}-{theme}-128.png").convert('RGBA')
            im.paste(art, (x+60, y+36), art)
            text(d, (x+124, y+169), item['name'], 18, fg, True, 'mt')
            tiny = Image.open(renders / f"{item['slug']}-{theme}-32.png").convert('RGBA')
            im.paste(tiny, (x+85, y+197), tiny)
            text(d, (x+126, y+203), '32px', 13, muted)
    text(d, (64, 1348), '示意色仅用于比较轮廓；成绩配色与页面接入待基础模板确认后继续。', 16, muted)
    return im


def size_sheet(items, renders: Path, dark=False):
    bg, line, fg, muted = ('#101722', '#334155', '#E2E8F0', '#A3B1C3') if dark else ('#FFFFFF', '#E2E6EB', '#23303E', '#657487')
    im = Image.new('RGB', (1320, 2110), bg)
    d = ImageDraw.Draw(im)
    text(d, (60, 35), '勋章基础模板 · 实际像素对照', 30, fg, True)
    text(d, (60, 86), '优先检查 32px 下的主符号与玩法标记。页面缩放设为 100% 查看。', 17, muted)
    centers = [500, 660, 820, 980, 1140]
    for x, size in zip(centers, SIZES[:5]):
        text(d, (x, 143), f'{size}px', 17, muted, anchor='mt')
    text(d, (60, 143), '系列 / 模板编号', 17, muted)
    theme = 'dark' if dark else 'light'
    for i, item in enumerate(items):
        y = 180 + i * 108
        d.line((60, y, 1260, y), fill=line)
        text(d, (60, y+26), f"{item['id']}  {item['name']}", 19, fg, True)
        text(d, (60, y+60), item['slug'], 13, muted)
        for x, size in zip(centers, SIZES[:5]):
            art = Image.open(renders / f"{item['slug']}-{theme}-{size}.png").convert('RGBA')
            im.paste(art, (x-size//2, y+54-size//2), art)
    text(d, (60, 2050), 'v1 · 全部待检阅 · 不含正式成绩档次配色', 16, muted)
    return im


def inline_svg(art, suffix):
    # Every embedded copy gets its own title and mask IDs.
    for identifier in re.findall(r'\bid="([^"]+)"', art):
        art = art.replace(f'id="{identifier}"', f'id="{identifier}-{suffix}"')
        art = art.replace(f'#{identifier})', f'#{identifier}-{suffix})')
        art = art.replace(f'aria-labelledby="{identifier}"', f'aria-labelledby="{identifier}-{suffix}"')
    return art


def review_html(items):
    cards, rows = [], []
    for item in items:
        art = (ROOT / item['source']).read_text(encoding='utf-8')
        large = inline_svg(art, 'large')
        tiny = inline_svg(art, 'tiny')
        cards.append(f'''<article class="tile" data-id="{item['id']}">
          <div class="tile-top"><span>{item['id']} / {item['category']}</span><span>待检阅</span></div>
          <button class="art-button" data-open="{item['id']}" aria-label="放大查看{item['name']}">{large}</button>
          <h3>{item['name']}</h3><p class="concept">{item['concept']}</p>
          <div class="tile-bottom"><span class="tiny">{tiny}</span><span>32px 实际尺寸</span><a href="{item['source']}" download>SVG 源文件 ↗</a></div>
        </article>''')
        samples = ''.join(f'<div class="size-cell"><span>{size}px</span><div style="width:{size}px;height:{size}px">{inline_svg(art, f"size-{size}")}</div></div>' for size in SIZES[:5])
        rows.append(f'<article class="size-row"><div class="size-name"><span>{item["id"]}</span><h3>{item["name"]}</h3></div>{samples}</article>')
    ability = ''.join(cards[:10])
    novice = ''.join(cards[10:])
    data = json.dumps(items, ensure_ascii=False).replace('</', '<\\/')
    return '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenMS 勋章基础模板检阅 v1</title>
<style>
:root{color-scheme:light;--bg:#f7f7f3;--paper:#fff;--ink:#475569;--text:#23303e;--muted:#677588;--line:#dfe3e5;--hover:#eef1f2}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 'Microsoft YaHei','Segoe UI',sans-serif}
body.dark{color-scheme:dark;--bg:#101722;--paper:#172231;--ink:#cbd5e1;--text:#e2e8f0;--muted:#a3b1c3;--line:#334155;--hover:#253449}
button,a{touch-action:manipulation}button{font:inherit;cursor:pointer}button:focus-visible,a:focus-visible{outline:2px solid var(--ink);outline-offset:4px}a{color:inherit;text-underline-offset:4px}
.wrap{max-width:1440px;margin:auto;padding:48px 48px 32px}.eyebrow{font-size:12px;letter-spacing:2px;color:var(--muted)}header{padding-bottom:28px;border-bottom:1px solid var(--line)}
h1{font-size:34px;line-height:1.3;margin:14px 0}header p{margin:8px 0;color:var(--muted)}.meta{float:right;font-size:13px;margin-top:8px;border:1px solid var(--line);border-radius:20px;padding:3px 12px}
.toolbar{position:sticky;top:0;z-index:2;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:18px 0;background:var(--bg);border-bottom:1px solid var(--line)}
.controls{display:flex;gap:6px;flex-wrap:wrap}.controls button{border:1px solid var(--line);border-radius:6px;padding:7px 12px;color:var(--text);background:var(--paper)}.controls button[aria-pressed=true]{background:var(--text);color:var(--bg);border-color:var(--text)}
.section-head{display:flex;align-items:baseline;justify-content:space-between;margin:28px 0 14px}.section-head h2{font-size:18px;margin:0}.section-head span{font-size:12px;letter-spacing:1px;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px}.tile{min-width:0;background:var(--paper);border:1px solid var(--line);border-radius:9px;padding:14px}.tile-top{font-size:11px;display:flex;justify-content:space-between;color:var(--muted)}
.art-button{display:block;width:100%;height:160px;border:0;background:transparent;color:var(--ink);padding:16px}.art-button:hover{background:var(--hover);border-radius:5px}.art-button svg{width:128px;height:128px}
svg{display:block;color:inherit;width:100%;height:100%;overflow:visible}.art-button,.tiny,.size-cell,.dialog-art{color:var(--ink)}h3{font-size:16px;margin:12px 0 6px}.concept{font-size:12px;color:var(--muted);min-height:40px;margin:0 0 12px}.tile-bottom{display:flex;align-items:center;gap:6px;border-top:1px solid var(--line);padding-top:10px;font-size:10px;color:var(--muted);flex-wrap:wrap}.tiny{width:32px;height:32px;flex-shrink:0}.tile-bottom a{margin-left:auto}
body.gray .art-button,body.gray .tiny,body.gray .size-cell,body.gray .dialog-art{filter:grayscale(1)}body.blind h3,body.blind .concept,body.blind .size-name h3{visibility:hidden}
[hidden]{display:none!important}.size-row{display:grid;grid-template-columns:minmax(220px,1.5fr) repeat(5,minmax(100px,1fr));gap:12px;border-bottom:1px solid var(--line);align-items:center;padding:18px 0;min-height:120px}.size-name span{font-size:12px;color:var(--muted)}.size-cell{display:flex;align-items:center;flex-direction:column;gap:10px;min-height:105px;justify-content:center}.size-cell>span{font-size:11px;color:var(--muted)}.sizes-scroll{overflow-x:auto}.sizes-inner{min-width:840px}
footer{color:var(--muted);font-size:12px;margin-top:32px;padding-top:20px;border-top:1px solid var(--line)}footer p{margin:5px 0}.filelinks{display:flex;gap:18px;flex-wrap:wrap;margin:14px 0}dialog{background:var(--paper);color:var(--text);border:1px solid var(--line);border-radius:12px;width:min(620px,calc(100% - 32px));padding:28px}dialog::backdrop{background:#0008}.dialog-top{display:flex;justify-content:space-between;align-items:center}.dialog-top button{border:1px solid var(--line);background:transparent;color:var(--text);padding:5px 10px;border-radius:5px}.dialog-art{width:256px;height:256px;margin:24px auto}.dialog-info{color:var(--muted)}.dialog-info a{display:inline-block;margin-top:10px}
@media(max-width:1200px){.grid{grid-template-columns:repeat(4,minmax(0,1fr))}.wrap{padding:32px}}@media(max-width:920px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}.wrap{padding:24px}.art-button{height:144px;padding:8px}}@media(max-width:650px){.grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.wrap{padding:20px 14px}h1{font-size:27px}.meta{float:none;display:inline-block}.toolbar{position:static}.tile{padding:10px}.art-button{height:128px;padding:8px}.art-button svg{width:112px;height:112px;margin:auto}.tile-bottom a{margin-left:0}.dialog-art{width:220px;height:220px}.concept{min-height:58px}}
@media(prefers-reduced-motion:no-preference){.art-button{transition:background .15s}}
</style></head><body><main class="wrap">
<header><span class="meta">v1 · 17 / 17 待检阅</span><div class="eyebrow">OPENMS / MEDAL TEMPLATES</div><h1>勋章基础模板</h1><p>先看轮廓，再看小尺寸。统一示意色，暂不表达成绩档次。</p><p>点击图形可放大查看；反馈时直接告诉我编号，例如「04 的断旗标记太复杂」。</p></header>
<div class="toolbar"><div class="controls" aria-label="预览视图"><button id="overview-btn" aria-pressed="true">全部模板</button><button id="sizes-btn" aria-pressed="false">实际尺寸对照</button></div><div class="controls" aria-label="显示选项"><button id="theme-btn" aria-pressed="false">深色背景</button><button id="gray-btn" aria-pressed="false">灰度检查</button><button id="blind-btn" aria-pressed="false">隐藏名称</button></div></div>
<div id="overview"><div class="section-head"><h2>能力系列</h2><span>10 TEMPLATES</span></div><section class="grid">''' + ability + '''</section><div class="section-head"><h2>新手与其他系列</h2><span>07 TEMPLATES</span></div><section class="grid">''' + novice + '''</section></div>
<div id="sizes" hidden><div class="section-head"><h2>32 / 40 / 48 / 64 / 72px</h2><span>100% 浏览器缩放下为实际像素</span></div><div class="sizes-scroll"><div class="sizes-inner">''' + ''.join(rows) + '''</div></div></div>
<footer><div class="filelinks"><a href="overview-light.png">浅色总览 PNG</a><a href="overview-dark.png">深色总览 PNG</a><a href="sizes-grayscale.png">灰度尺寸对照 PNG</a><a href="review.json" download>逐枚检阅清单 JSON</a></div><p>全部模板当前均为待检阅。正式成绩配色、档位映射与站点资源替换，将在你明确同意后继续。</p><p>SVG 为可编辑、透明背景的几何图形，图形内不含系列名或成绩数字。预览页在本地运行，无外部字体和网络请求。</p></footer>
<dialog id="detail"><div class="dialog-top"><strong id="detail-name"></strong><button id="close-btn">关闭</button></div><div class="dialog-art" id="detail-art"></div><div class="dialog-info"><p id="detail-concept"></p><span>放大尺寸 256px · 原始视图框 64 × 64</span><br><a id="detail-download" download>下载此枚 SVG</a></div></dialog>
<script>const items=''' + data + ''';
const $=id=>document.getElementById(id);
function view(sizes){$('overview').hidden=sizes;$('sizes').hidden=!sizes;$('overview-btn').setAttribute('aria-pressed',String(!sizes));$('sizes-btn').setAttribute('aria-pressed',String(sizes))}
$('overview-btn').onclick=()=>view(false);$('sizes-btn').onclick=()=>view(true);
for(const [id,cls] of [['theme-btn','dark'],['gray-btn','gray'],['blind-btn','blind']]){$(id).onclick=()=>{const on=document.body.classList.toggle(cls);$(id).setAttribute('aria-pressed',String(on))}}
document.querySelectorAll('[data-open]').forEach(button=>{button.onclick=()=>{const item=items.find(x=>x.id===button.dataset.open);$('detail-name').textContent=item.id+' / '+item.name;$('detail-art').replaceChildren(button.querySelector('svg').cloneNode(true));$('detail-concept').textContent=item.concept;$('detail-download').href=item.source;$('detail').showModal()}});
$('close-btn').onclick=()=>$('detail').close();$('detail').addEventListener('click',e=>{if(e.target===$('detail')){const r=$('detail').getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)$('detail').close()}});
</script></main></body></html>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--node', default='node')
    ap.add_argument('--sharp', default='sharp')
    ap.add_argument('--rebuild-v1', action='store_true', help='Explicitly rebuild the superseded v1 study')
    args = ap.parse_args()
    if not args.rebuild_v1:
        ap.error('v1 is superseded. Use v2/build_review.py for current previews; --rebuild-v1 is required for the historical generator.')
    (ROOT / 'svg').mkdir(exist_ok=True)
    (ROOT / 'png').mkdir(exist_ok=True)
    items = []
    for i, (slug, series, name, category, concept, body) in enumerate(TEMPLATES, 1):
        p = ROOT / 'svg' / f'{slug}.svg'
        p.write_text(svg(slug, name, body), encoding='utf-8')
        items.append(dict(id=f'{i:02}', slug=slug, series=series, name=name, category=category, concept=concept, version=VERSION, source=f'svg/{slug}.svg'))
    review_path = ROOT / 'review.json'
    previous = json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else []
    feedback = {item['slug']: item for item in previous}
    review = [dict(item, status=feedback.get(item['slug'], {}).get('status', '待检阅'), feedback=feedback.get(item['slug'], {}).get('feedback', '')) for item in items]
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (ROOT / 'index.html').write_text(review_html(items), encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='medal-review-') as tmp:
        renders = Path(tmp)
        subprocess.run([args.node, str(ROOT / 'render_svg.cjs'), args.sharp, str(ROOT / 'svg'), str(renders)], check=True)
        for dark, suffix in [(False, 'light'), (True, 'dark')]:
            overview(items, renders, dark).save(ROOT / f'overview-{suffix}.png')
            size_sheet(items, renders, dark).save(ROOT / f'sizes-{suffix}.png')
        with Image.open(ROOT / 'sizes-light.png') as im:
            im.convert('L').convert('RGB').save(ROOT / 'sizes-grayscale.png')
        for item in items:
            shutil.copy2(renders / f"{item['slug']}-light-160.png", ROOT / 'png' / f"{item['slug']}.png")
    print(f'Generated {len(items)} SVG templates, 17 transparent PNGs, 5 review sheets, index.html and review.json')


if __name__ == '__main__':
    main()
