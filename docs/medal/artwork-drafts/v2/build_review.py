"""Assemble review layouts from image_gen outputs without changing their art.

Only copies, display thumbnails and contact sheets are made here. New art and
all image edits are produced with the built-in image_gen tool. Production
templates, released WebP assets and runtime components are never written.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import html
import json

ROOT = Path(__file__).resolve().parent
SIZES = [32, 40, 48, 64, 72]
CONCEPTS = {
    'breakthrough': '保留穿破圆章的上升折线箭头，减少碎片与多重外圈。',
    'speed': '保留横贯圆章的弧形速度轨迹与分离尾迹。',
    'mastery': '保留中心方形亮格和向外放射的光芒。',
    'breakthrough-nf': '保留折线上升箭头与右下角圆形禁旗副章。',
    'speed-nf': '保留弧形速度轨迹与右下角圆形禁旗副章。',
    'mastery-nf': '保留中心方形亮格、光芒与圆形禁旗副章。',
    'precision-nf': '保留四向内聚箭头、中心方格、目标圆环与禁旗副章。',
    'precision': '保留四向内聚箭头、中心方格与分段目标圆环。',
    'precision-nf-three': '保留三枚方格光芒圆章的三角组合，以及禁旗副章。',
    'precision-three': '保留三枚方格光芒圆章的三角组合与蓝青差异。',
    'registered': '保留竖向折角证件、头像与圆形认证勾章。',
    'reviewed': '保留胶片齿孔、播放三角与圆形审核勾章。',
    'levels': '保留由近到远的三层雷盘，以及每层的红旗。',
    'levels-nf': '保留由近到远的三层无旗雷盘。',
    'modes': '保留六面环绕的雷盘与蓝色格子。',
    'saolei': '保留旧雷盘窗口、迁移箭头与蓝色站点徽标。',
    'shareholder': '保留历史档案盒、前金后蓝的记录卡与站点徽标。',
}


def font(size, bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/' + ('msyhbd.ttc' if bold else 'msyh.ttc'), size)


def label(d, xy, s, size=18, color='#273442', bold=False, anchor=None):
    d.text(xy, s, font=font(size, bold), fill=color, anchor=anchor)


def place(sheet, source, x, y, size):
    with Image.open(source) as source_image:
        image = source_image.convert('RGBA').resize((size, size), Image.Resampling.LANCZOS)
    sheet.paste(image, (x, y), image)


def overview(items, dark=False):
    bg, paper, line, fg, muted = ('#101722', '#172231', '#344356', '#e6eaf1', '#a7b5c7') if dark else ('#f7f7f3', '#ffffff', '#dfe4e8', '#273442', '#637286')
    im = Image.new('RGB', (1440, 1530), bg)
    d = ImageDraw.Draw(im)
    label(d, (64, 35), 'OPENMS / ORIGINAL-CORE MEDAL STUDY', 15, muted)
    label(d, (64, 76), '保留原图核心 · 基础模板 v2', 36, fg, True)
    label(d, (64, 137), '17 个系列 · 保留勋章质感 · 精简底纹与外围装饰 · 全部待检阅', 18, muted)
    d.line((64, 188, 1376, 188), fill=line)
    for i, item in enumerate(items):
        x, y = 64 + i % 5 * 266, 224 + i // 5 * 300
        d.rounded_rectangle((x, y, x+248, y+280), 10, paper, line)
        label(d, (x+16, y+12), f"{item['id']} / {item['category']}", 14, muted)
        place(im, ROOT/item['source'], x+40, y+38, 168)
        label(d, (x+124, y+214), item['name'], 18, fg, True, 'mt')
        place(im, ROOT/item['source'], x+74, y+243, 32)
        place(im, ROOT/item['source'], x+124, y+235, 40)
        label(d, (x+178, y+247), '32 / 40', 10, muted)
    label(d, (64, 1465), '沿用原图色调供造型检阅；成绩配色及正式接入仍等待模板确认。', 17, muted)
    return im


def comparison(items):
    im = Image.new('RGB', (1560, 2140), '#f7f7f3')
    d = ImageDraw.Draw(im)
    label(d, (60, 36), '原版与 v2 并排对照', 34, bold=True)
    label(d, (60, 94), '每组左侧为原版发布图，右侧为保留核心后的 v2；两者按相同尺寸展示。', 18, '#637286')
    for i, item in enumerate(items):
        x, y = 60+i%3*500, 158+i//3*318
        d.rounded_rectangle((x, y, x+480, y+298), 10, '#ffffff', '#dfe4e8')
        label(d, (x+18, y+13), f"{item['id']}  {item['name']}", 20, bold=True)
        place(im, ROOT/item['original'], x+50, y+57, 144)
        place(im, ROOT/item['source'], x+282, y+57, 144)
        label(d, (x+122, y+212), '原版', 16, '#637286', anchor='mt')
        label(d, (x+354, y+212), 'v2 待检阅', 16, '#637286', anchor='mt')
        place(im, ROOT/item['original'], x+105, y+251, 32)
        place(im, ROOT/item['source'], x+337, y+251, 32)
    label(d, (60, 2090), '原版未修改。v1 抽象图标方案已弃用；v2 仍未替换正式资源。', 16, '#637286')
    return im


def size_sheet(items, dark=False):
    bg, line, fg, muted = ('#101722', '#344356', '#e6eaf1', '#a7b5c7') if dark else ('#ffffff', '#e1e6eb', '#273442', '#637286')
    im = Image.new('RGB', (1320, 2110), bg)
    d = ImageDraw.Draw(im)
    label(d, (60, 32), '保留原图核心 · v2 实际尺寸', 30, fg, True)
    label(d, (60, 86), '统一沿用原图金蓝色调，仅检阅造型；100% 缩放下检查实际像素。', 17, muted)
    centers = [500,660,820,980,1140]
    for cx, size in zip(centers, SIZES):
        label(d, (cx,142), f'{size}px',17,muted,anchor='mt')
    for i, item in enumerate(items):
        y = 180+i*108
        d.line((60,y,1260,y),fill=line)
        label(d,(60,y+27),f"{item['id']}  {item['name']}",19,fg,True)
        label(d,(60,y+61),item['slug'],13,muted)
        for cx,size in zip(centers,SIZES):
            place(im,ROOT/item['source'],cx-size//2,y+54-size//2,size)
    label(d,(60,2050),'v2 · 全部待检阅 · 未进入成绩配色与正式接入',16,muted)
    return im


def html_page(items):
    cards, compares, sizes = [], [], []
    for item in items:
        name = html.escape(item['name'])
        cards.append(f'''<article class="tile"><div class="meta">{item['id']} / {item['category']}<span>待检阅</span></div><button class="art" data-id="{item['id']}" aria-label="放大查看{name}"><img src="{item['source']}" alt="{name} v2"></button><h3>{name}</h3><p>{item['concept']}</p><div class="bottom"><img src="{item['source']}" width="32" height="32" alt=""><span>32px</span><a href="{item['source']}" download>模板 PNG ↗</a></div></article>''')
        compares.append(f'''<article class="compare"><h3>{item['id']} / {name}</h3><div class="pair"><figure><img src="{item['original']}" alt="{name}原版"><figcaption>原版</figcaption></figure><figure><button class="art" data-id="{item['id']}" aria-label="对照查看{name}"><img src="{item['source']}" alt="{name} v2"></button><figcaption>v2 待检阅</figcaption></figure></div><p>{item['concept']}</p></article>''')
        cells=''.join(f'<div class="sample"><span>{size}px</span><img src="{item["source"]}" width="{size}" height="{size}" alt="{name} {size}px"></div>' for size in SIZES)
        sizes.append(f'<article class="size-row"><h3>{item["id"]} / {name}</h3>{cells}</article>')
    data = json.dumps(items,ensure_ascii=False).replace('</','<\\/')
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>勋章模板 v2 · 保留原图核心</title><style>
:root{--bg:#f7f7f3;--paper:#fff;--text:#273442;--muted:#637286;--line:#dfe4e8;color-scheme:light}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 'Microsoft YaHei','Segoe UI',sans-serif}.dark{--bg:#101722;--paper:#172231;--text:#e6eaf1;--muted:#a7b5c7;--line:#344356;color-scheme:dark}main{max-width:1480px;margin:auto;padding:40px 48px}header{border-bottom:1px solid var(--line);padding-bottom:22px}.eyebrow{font-size:12px;letter-spacing:2px;color:var(--muted)}h1{font-size:32px;line-height:1.4;margin:12px 0}header p{color:var(--muted);margin:7px 0}.status{float:right;border:1px solid var(--line);border-radius:20px;padding:3px 12px;font-size:13px}.toolbar{display:flex;gap:10px;justify-content:space-between;flex-wrap:wrap;padding:18px 0;position:sticky;top:0;background:var(--bg);z-index:2;border-bottom:1px solid var(--line)}button,a{touch-action:manipulation}button{font:inherit;cursor:pointer}button:focus-visible,a:focus-visible{outline:2px solid var(--text);outline-offset:3px}.controls{display:flex;gap:6px;flex-wrap:wrap}.controls button,dialog button{color:var(--text);background:var(--paper);border:1px solid var(--line);border-radius:6px;padding:7px 12px}.controls button[aria-pressed=true]{background:var(--text);color:var(--bg)}a{color:inherit;text-underline-offset:4px}.grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;margin-top:24px}.tile,.compare{background:var(--paper);border:1px solid var(--line);border-radius:9px;padding:14px;min-width:0}.meta{font-size:11px;color:var(--muted);display:flex;justify-content:space-between}.art{display:block;border:0;background:transparent;padding:0;margin:12px auto;color:inherit;max-width:100%}.tile .art{width:168px;height:168px}.art img{width:100%;height:100%;object-fit:contain;display:block}h3{font-size:16px;margin:9px 0}p{margin:6px 0}.tile p,.compare p{font-size:12px;color:var(--muted);min-height:42px}.bottom{display:flex;align-items:center;gap:7px;border-top:1px solid var(--line);padding-top:10px;color:var(--muted);font-size:11px}.bottom a{margin-left:auto}.comparisons{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-top:24px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}.pair figure{margin:4px 0;text-align:center;min-width:0}.pair img{width:144px;height:144px;max-width:100%;object-fit:contain}.pair .art{width:144px;height:144px;margin:0 auto}.pair figcaption{font-size:12px;color:var(--muted);margin:9px 0}.gray img{filter:grayscale(1)}.sizes-wrap{overflow:auto}.sizes{min-width:850px}.size-row{display:grid;grid-template-columns:minmax(240px,1.5fr) repeat(5,minmax(100px,1fr));align-items:center;gap:12px;padding:20px 0;border-bottom:1px solid var(--line);min-height:122px}.sample{display:flex;min-height:102px;align-items:center;justify-content:center;flex-direction:column;gap:9px}.sample span{font-size:11px;color:var(--muted)}.sample img{flex-shrink:0}.caption{color:var(--muted);font-size:13px;margin:20px 0}[hidden]{display:none!important}footer{border-top:1px solid var(--line);margin-top:28px;padding-top:20px;color:var(--muted);font-size:12px}.links{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:12px}dialog{background:var(--paper);color:var(--text);border:1px solid var(--line);border-radius:12px;width:min(900px,calc(100% - 32px));padding:26px}dialog::backdrop{background:#0009}.dialog-head{display:flex;justify-content:space-between;align-items:center}.dialog-pair{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:22px 0;text-align:center}.dialog-pair img{width:100%;max-width:320px;height:auto;aspect-ratio:1;object-fit:contain}.dialog-pair figure{margin:0}.dialog-pair figcaption{color:var(--muted);font-size:13px}.dialog-note{color:var(--muted)}
@media(max-width:1200px){.grid{grid-template-columns:repeat(4,minmax(0,1fr))}.comparisons{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:900px){main{padding:28px 24px}.grid{grid-template-columns:repeat(3,minmax(0,1fr))}.tile .art{width:144px;height:144px}}@media(max-width:650px){main{padding:22px 14px}h1{font-size:25px}.status{float:none;display:inline-block;margin-bottom:14px}.grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.tile{padding:10px}.tile .art{width:128px;height:128px}.comparisons{grid-template-columns:1fr}.toolbar{position:static}.dialog-pair{gap:10px}.tile p{min-height:58px}.bottom{flex-wrap:wrap}.bottom a{margin-left:0}}@media(max-width:360px){.tile .art{width:112px;height:112px}}
</style></head><body><main><header><span class="status">v2 · 17 / 17 待检阅</span><div class="eyebrow">OPENMS / ORIGINAL-CORE MEDAL STUDY</div><h1>保留原图核心 · 基础模板 v2</h1><p>保留原勋章的主体、构图与材质，只收减底纹、多重边框及细碎光效。</p><p>当前沿用原图色调检阅造型，成绩配色与正式接入仍在等待模板确认。点击图片可放大并排对照。</p><p><a href="../v3/">最新：查看完整 17 枚去外框模板 →</a></p></header><div class="toolbar"><div class="controls" aria-label="视图"><button id="compare-btn" aria-pressed="true">原图对照</button><button id="overview-btn" aria-pressed="false">全部模板</button><button id="sizes-btn" aria-pressed="false">实际尺寸</button></div><div class="controls" aria-label="显示"><button id="theme-btn" aria-pressed="false">深色背景</button><button id="gray-btn" aria-pressed="false">灰度检查</button></div></div><section id="compare-view"><p class="caption">左侧为原版发布图，右侧为 v2。保留同一组编号，方便逐枚反馈。</p><div class="comparisons">''' + ''.join(compares) + '''</div></section><section id="overview-view" hidden><div class="grid">''' + ''.join(cards) + '''</div></section><section id="sizes-view" hidden><p class="caption">32 / 40 / 48 / 64 / 72px；浏览器缩放为 100% 时检查实际像素。</p><div class="sizes-wrap"><div class="sizes">''' + ''.join(sizes) + '''</div></div></section><footer><div class="links"><a href="overview-light.png">浅色总览</a><a href="overview-dark.png">深色总览</a><a href="comparison.png">原图对照长图</a><a href="sizes-light.png">实际尺寸长图</a><a href="README.md">源文件与检阅说明</a><a href="generation-record.json" download>编辑提示词记录</a></div><p>v1 抽象图标方向已弃用。v2 全部待检阅，未替换正式资源。可直接按编号反馈哪些主体或细节需要保留、收减。</p></footer><dialog id="detail"><div class="dialog-head"><strong id="detail-name"></strong><button id="close-btn">关闭</button></div><div class="dialog-pair"><figure><img id="detail-old" alt="原版"><figcaption>原版发布图</figcaption></figure><figure><img id="detail-new" alt="v2"><figcaption>v2 原图编辑模板 · 待检阅</figcaption></figure></div><p class="dialog-note" id="detail-note"></p><a id="detail-download" download>下载 v2 透明 PNG 原图</a></dialog><script>const items=''' + data + ''';const $=id=>document.getElementById(id);for(const key of ['compare','overview','sizes']){$(key+'-btn').onclick=()=>{for(const view of ['compare','overview','sizes']){$(view+'-view').hidden=view!==key;$(view+'-btn').setAttribute('aria-pressed',String(view===key))}}}for(const [id,cls] of [['theme-btn','dark'],['gray-btn','gray']]){$(id).onclick=()=>$(id).setAttribute('aria-pressed',String(document.body.classList.toggle(cls)))}document.querySelectorAll('[data-id]').forEach(btn=>btn.onclick=()=>{const item=items.find(x=>x.id===btn.dataset.id);$('detail-name').textContent=item.id+' / '+item.name;$('detail-old').src=item.original;$('detail-new').src=item.source;$('detail-note').textContent=item.concept;$('detail-download').href=item.source;$('detail').showModal()});$('close-btn').onclick=()=>$('detail').close();</script></main></body></html>'''


def main():
    old = json.loads((ROOT.parent/'review.json').read_text(encoding='utf-8'))
    record = json.loads((ROOT/'generation-record.json').read_text(encoding='utf-8'))
    generated = {x['slug']: x for x in record['images']}
    items = [dict(id=x['id'],slug=x['slug'],series=x['series'],name=x['name'],category=x['category'],concept=CONCEPTS[x['slug']],version='v2',source=f"templates/{x['slug']}.png",original=f"originals/{x['slug']}.webp",original_template=generated[x['slug']]['original_template'],status='待检阅',feedback='') for x in old]
    existing = ROOT/'review.json'
    if existing.exists():
        previous = {x['slug']:x for x in json.loads(existing.read_text(encoding='utf-8'))}
        for item in items:
            if item['slug'] in previous:
                item.update({key:previous[item['slug']].get(key,item[key]) for key in ['status','feedback']})
    existing.write_text(json.dumps(items,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'index.html').write_text(html_page(items),encoding='utf-8')
    for dark, suffix in [(False,'light'),(True,'dark')]:
        overview(items,dark).save(ROOT/f'overview-{suffix}.png')
        size_sheet(items,dark).save(ROOT/f'sizes-{suffix}.png')
    comparison(items).save(ROOT/'comparison.png')
    with Image.open(ROOT/'sizes-light.png') as image:
        image.convert('L').convert('RGB').save(ROOT/'sizes-grayscale.png')
    print('Built v2 review: 17 unchanged image_gen source PNGs, side-by-side references, 6 sheets, HTML and checklist.')


if __name__ == '__main__':
    main()
