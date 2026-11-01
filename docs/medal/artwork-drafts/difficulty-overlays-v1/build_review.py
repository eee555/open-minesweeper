"""Review reusable overlay assets and shared placement; never bake stars into base assets."""
from pathlib import Path
import json
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[3]
sys.path.insert(0, str(WORKSPACE / 'front_end/scripts'))
from build_medal_art import prepare, save_art

SIZES = (32, 40, 48, 64, 72)


def font(size, bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/' + ('msyhbd.ttc' if bold else 'msyh.ttc'), size)


def label(draw, xy, value, size=18, color='#263442', bold=False):
    draw.text(xy, value, font=font(size, bold), fill=color)


def opened(path):
    with Image.open(ROOT / path) as source:
        return source.convert('RGBA')


def layers(family, level, size, production=False):
    body = Image.new('RGBA', (size, size))
    length, offset = round(size * .79), round(size * .21)
    body.alpha_composite(opened(family['source'] if production else family['review_source']).resize((length, length), Image.Resampling.LANCZOS), (offset, offset))
    marker = Image.new('RGBA', (size, size))
    length = round(size * .36)
    marker.alpha_composite(opened(level['source']).resize((length, length), Image.Resampling.LANCZOS), (0, 0))
    return body, marker


def composite(family, level, size):
    body, marker = layers(family, level, size)
    return Image.alpha_composite(body, marker)


def palette(dark):
    return ('#101722', '#e9edf4', '#a7b5c7', '#344356') if dark else ('#f7f7f3', '#263442', '#586b7e', '#d7dfe5')


def time_sheet(data, dark=False):
    bg, fg, muted, line = palette(dark)
    canvas = Image.new('RGBA', (1440, 1040), bg)
    draw = ImageDraw.Draw(canvas)
    label(draw, (60, 28), 'OPENMS / SHARED DIFFICULTY OVERLAYS', 15, muted)
    label(draw, (60, 66), 'Time 破境 · 独立星级资源合成', 34, fg, True)
    label(draw, (60, 120), '初级一星 / 中级二星 / 高级三星：上方一颗，下方两颗。', 20, muted)
    for index, level in enumerate(data['levels']):
        x = 60 + index * 440
        canvas.alpha_composite(composite(data['families'][0], level, 360), (x + 25, 180))
        label(draw, (x + 130, 560), level['name'], 28, fg, True)
        label(draw, (x + 118, 607), f"{level['stars']} 颗五角星", 19, muted)
        cursor = x + 24
        for size in SIZES:
            canvas.alpha_composite(composite(data['families'][0], level, size), (cursor, 725 - size))
            label(draw, (cursor, 741), f'{size}px', 13, muted)
            cursor += size + 15
    draw.line((60, 804, 1380, 804), fill=line)
    label(draw, (60, 835), '位置：星级左上角 36% 方形区；主体在右下侧 79% 方形区，避免系列之间互相遮挡。', 19, fg)
    label(draw, (60, 880), '同一三张星级图供全部单难度称号复用，主体文件内不烘焙星星。', 18, muted)
    label(draw, (60, 923), '本稿验证组合位置，尚未接入站点。三阶精工与跨难度称号不自动附加高级三星。', 18, muted)
    return canvas.convert('RGB')


def coverage_sheet(data, dark=False):
    bg, fg, muted, line = palette(dark)
    canvas = Image.new('RGBA', (1440, 2320), bg)
    draw = ImageDraw.Draw(canvas)
    label(draw, (60, 28), 'OPENMS / ALL IMPLEMENTED SINGLE-DIFFICULTY FAMILIES', 15, muted)
    label(draw, (60, 66), '统一位置验证 · 8 类 × 3 难度', 34, fg, True)
    label(draw, (60, 122), '星级独立叠加，覆盖 time / 3BV/s / STNB / NF / FL；浅深背景与 32 / 48 / 72px。', 18, muted)
    for index, family in enumerate(data['families']):
        y = 190 + index * 250
        draw.line((60, y - 12, 1380, y - 12), fill=line)
        label(draw, (60, y + 22), family['name'], 24, fg, True)
        label(draw, (60, y + 65), family['code_prefix'], 14, muted)
        for j, level in enumerate(data['levels']):
            x = 390 + j * 330
            canvas.alpha_composite(composite(family, level, 144), (x, y))
            label(draw, (x + 45, y + 150), level['name'], 19, fg, True)
            for shift, size in zip((0, 75, 168), (32, 48, 72)):
                canvas.alpha_composite(composite(family, level, size), (x + shift, y + 228 - size))
    label(draw, (60, 2223), '当前 24 种组合已检查主体与星级的 alpha 重叠。未来新增单难度图案沿用同一角标区并重新检查。', 18, muted)
    return canvas.convert('RGB')


def resource_sheet(data, dark=False):
    bg, fg, muted, line = palette(dark)
    canvas = Image.new('RGBA', (1440, 730), bg)
    draw = ImageDraw.Draw(canvas)
    label(draw, (60, 28), 'OPENMS / THREE INDEPENDENT TRANSPARENT PNG ASSETS', 15, muted)
    label(draw, (60, 66), '独立星级资源 · 共用方形画布', 34, fg, True)
    label(draw, (60, 122), '保留空白区域决定定位；使用时整体缩放，不按各自有色区域重新裁切。', 20, muted)
    for index, level in enumerate(data['levels']):
        x = 60 + index * 440
        draw.rectangle((x + 30, 190, x + 350, 510), outline=line)
        canvas.alpha_composite(opened(level['source']).resize((320, 320), Image.Resampling.LANCZOS), (x + 30, 190))
        label(draw, (x + 118, 542), f"{level['name']} · {level['stars']} 星", 25, fg, True)
        label(draw, (x + 90, 588), Path(level['source']).name, 17, muted)
    label(draw, (60, 660), '每张资源只含星星和真实透明通道；高级三星为上方一颗、下方两颗的三角排列。', 19, muted)
    return canvas.convert('RGB')


def medal_html(family, level, size):
    return f'''<span class="medal" style="--size:{size}px" role="img" aria-label="{level['name']}{family['name']}"><img class="body" src="{family['review_source']}" alt=""><img class="marker" src="{level['source']}" alt=""></span>'''


def page(data):
    time_cards = []
    resource_cards = []
    for level in data['levels']:
        sizes = ''.join(f'<figure>{medal_html(data["families"][0], level, s)}<figcaption>{s}px</figcaption></figure>' for s in SIZES)
        time_cards.append(f'''<article><h2>{level['name']} · {level['stars']} 星</h2><div class="hero">{medal_html(data['families'][0], level, 280)}</div><div class="sizes">{sizes}</div></article>''')
        resource_cards.append(f'''<article><h2>{level['name']} · {level['stars']} 星</h2><img class="resource" src="{level['source']}" alt="独立{level['stars']}星资源"><a href="{level['source']}" download>下载独立透明 PNG</a> · <a href="{Path(level['source']).with_suffix('.webp').as_posix()}" download>64px WebP</a></article>''')
    rows = []
    for family in data['families']:
        medals = ''.join(f'''<div><strong>{level['name']}</strong>{medal_html(family, level, 128)}<div class="sizes">{''.join(f'<figure>{medal_html(family,level,s)}<figcaption>{s}px</figcaption></figure>' for s in (32,48,72))}</div></div>''' for level in data['levels'])
        rows.append(f'''<article class="family"><div><h2>{family['name']}</h2><p class="muted">{family['code_prefix']}</p></div>{medals}</article>''')
    html = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>独立星级资源与全系列位置验证</title><style>
:root{--bg:#f7f7f3;--paper:#fff;--fg:#263442;--muted:#586b7e;--line:#d7dfe5;color-scheme:light}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.65 'Microsoft YaHei','Segoe UI',sans-serif}body.dark{--bg:#101722;--paper:#172231;--fg:#e9edf4;--muted:#a7b5c7;--line:#344356;color-scheme:dark}main{max-width:1480px;margin:auto;padding:40px 32px}.eyebrow{font-size:12px;letter-spacing:.12em;color:var(--muted)}h1{font-size:32px;margin:14px 0}h2{font-size:21px;margin:0}.muted,footer{color:var(--muted)}p{margin:7px 0}button{font:inherit;cursor:pointer;color:inherit}.tools{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}button{padding:8px 16px;background:var(--paper);border:1px solid var(--line);border-radius:5px}button[aria-pressed=true]{outline:2px solid var(--fg);outline-offset:2px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px}article{min-width:0;background:var(--paper);border:1px solid var(--line);padding:22px;border-radius:7px;text-align:center}.hero{display:flex;justify-content:center;margin:22px 0}.medal{position:relative;display:inline-block;width:var(--size);height:var(--size);flex-shrink:0;vertical-align:middle}.medal img{position:absolute;object-fit:contain;pointer-events:none}.medal .body{left:21%;top:21%;width:79%;height:79%}.medal .marker{left:0;top:0;width:36%;height:36%}.guides .medal::before,.guides .medal::after{content:'';position:absolute;border:1px dashed var(--muted);z-index:3;pointer-events:none}.guides .medal::before{left:21%;top:21%;width:79%;height:79%}.guides .medal::after{left:0;top:0;width:36%;height:36%}.sizes{display:flex;gap:12px;justify-content:center;align-items:flex-end;overflow-x:auto;padding:16px 0}.sizes figure{display:flex;flex-direction:column;align-items:center;gap:8px;margin:0;flex-shrink:0}.sizes figcaption{font-size:11px;color:var(--muted)}.family{display:grid;grid-template-columns:240px repeat(3,minmax(0,1fr));gap:16px;align-items:center;margin-bottom:18px}.family .medal{display:block;margin:10px auto}.family .sizes{gap:6px}.resource{display:block;width:min(100%,300px);aspect-ratio:1;object-fit:contain;border:1px dashed var(--line);margin:24px auto}a{color:inherit;text-underline-offset:3px}.policy{margin:24px 0;padding:18px 0;border-block:1px solid var(--line)}footer{border-top:1px solid var(--line);margin-top:30px;padding-top:22px;font-size:13px}.links{display:flex;gap:20px;flex-wrap:wrap}[hidden]{display:none!important}@media(max-width:1050px){.family{grid-template-columns:1fr 1fr 1fr}.family>div:first-child{grid-column:1/-1}.grid{gap:12px}article{padding:12px}.hero .medal{--size:220px!important}.sizes{justify-content:flex-start}.family .sizes{justify-content:center}}@media(max-width:720px){main{padding:24px 16px}h1{font-size:26px}.grid{grid-template-columns:1fr}.hero .medal{--size:280px!important}.sizes{justify-content:center}.family{grid-template-columns:1fr}.family>div:first-child{grid-column:auto}}
</style></head><body><main><header><div class="eyebrow">OPENMS / REUSABLE DIFFICULTY OVERLAYS</div><h1>独立星级资源 · 统一左上角位置</h1><p>初级一星，中级二星，高级三星；三星排列为上方一颗、下方两颗。</p><p class="muted">三张透明资源独立保存，由展示层叠加；八类单难度图案共用同一位置。</p></header><div class="tools"><button id="time-btn" aria-pressed="true">Time 对照</button><button id="coverage-btn" aria-pressed="false">全部 8 类位置验证</button><button id="resources-btn" aria-pressed="false">独立资源</button><button id="theme" aria-pressed="false">深色背景</button><button id="guides" aria-pressed="false">显示占位边界</button></div><section id="time-view" class="grid">__TIME__</section><section id="coverage-view" hidden>__ROWS__</section><section id="resources-view" class="grid" hidden>__RESOURCES__</section><div class="policy"><h2>统一位置与适用范围</h2><p>星级区：左 0%、上 0%、宽高 36%。主体区：左 21%、上 21%、宽高 79%，按透明边界裁切后居中显示。</p><p class="muted">现有 8 类 × 3 难度共 24 种组合均检查了主体与星级的像素重叠。32px 下可比较星数，单颗星的金属细节需看较大尺寸。</p><p>未来带单一初／中／高级的收集、计数、收藏、隐藏和赛事单项称号也复用该资源与角标区；新主体图必须重新做位置验收。</p><p class="muted">三阶精工、跨难度合计和比较、无单一难度称号不自动附加三星；赛事金属仍表示名次。未来类别尚无本套源图，本稿未冒充已完成其美术验收。</p></div><footer><div class="links"><a href="time-light.png">Time 浅色图</a><a href="time-dark.png">Time 深色图</a><a href="coverage-light.png">全系列浅色图</a><a href="coverage-dark.png">全系列深色图</a><a href="resources-light.png">独立资源总览</a><a href="README.md">资源与位置规范</a><a href="generation-record.json">生成提示词</a><a href="placement-check.json">位置检查记录</a></div><p>本轮保存独立源资源并确认布局提案；尚未改动站点组件、正式发布图或成绩配色。</p></footer></main><script>const $=id=>document.getElementById(id);for(const key of ['time','coverage','resources']){$(key+'-btn').onclick=()=>{for(const view of ['time','coverage','resources']){$(view+'-view').hidden=view!==key;$(view+'-btn').setAttribute('aria-pressed',String(view===key))}}}for(const [id,cls] of [['theme','dark'],['guides','guides']]){$(id).onclick=()=>$(id).setAttribute('aria-pressed',String(document.body.classList.toggle(cls)))}</script></body></html>'''
    return html.replace('__TIME__', ''.join(time_cards)).replace('__ROWS__', ''.join(rows)).replace('__RESOURCES__', ''.join(resource_cards))


def check_placement(data):
    checks = []
    for size in (*SIZES, 320):
        for family in data['families']:
            for level in data['levels']:
                body, marker = layers(family, level, size, production=True)
                body_mask = body.getchannel('A').point(lambda v: 255 if v > 32 else 0)
                marker_mask = marker.getchannel('A').point(lambda v: 255 if v > 32 else 0)
                count = ImageChops.multiply(body_mask, marker_mask).histogram()[255]
                checks.append({'size': size, 'family': family['slug'], 'level': level['code'], 'overlap_pixels': count})
    report = {'alpha_threshold': 32, 'sizes': [*SIZES, 320], 'combinations_per_size': 24, 'all_clear': all(c['overlap_pixels'] == 0 for c in checks), 'checks': checks}
    (ROOT / 'placement-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert report['all_clear'], [c for c in checks if c['overlap_pixels']]


if __name__ == '__main__':
    data = json.loads((ROOT / 'review.json').read_text(encoding='utf-8'))
    resource_budget = []
    for level in data['levels']:
        target = ROOT / Path(level['source']).with_suffix('.webp')
        opened(level['source']).resize((64, 64), Image.Resampling.LANCZOS).save(target, format='WEBP', quality=50, alpha_quality=45, method=6)
        resource_budget.append({'level': level['code'], 'source': target.relative_to(ROOT).as_posix(), 'size': [64, 64], 'bytes': target.stat().st_size})
    assert all(item['bytes'] <= 2048 for item in resource_budget)
    (ROOT / 'resource-budget.json').write_text(json.dumps({'exports': resource_budget, 'total_bytes': sum(item['bytes'] for item in resource_budget)}, indent=2) + '\n', encoding='utf-8')
    for family in data['families']:
        base = prepare(WORKSPACE / family['canonical_template'])
        base.save(ROOT / family['review_source'])
        save_art(base, ROOT / family['source'])
    check_placement(data)
    for dark, name in ((False, 'light'), (True, 'dark')):
        time_sheet(data, dark).save(ROOT / f'time-{name}.png')
        coverage_sheet(data, dark).save(ROOT / f'coverage-{name}.png')
        resource_sheet(data, dark).save(ROOT / f'resources-{name}.png')
    (ROOT / 'index.html').write_text(page(data), encoding='utf-8')
    print('Built 3 independent resources, 24 shared placements, 6 sheets and HTML review; all 144 overlap checks clear.')
