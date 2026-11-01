"""Arrange all 17 unmodified image_gen outputs for shape review only."""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SIZES = [32,40,48,64,72]


def font(n, bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/'+('msyhbd.ttc' if bold else 'msyh.ttc'),n)


def put_text(d, xy, value, n=18, color='#273442', bold=False, anchor=None):
    d.text(xy,value,font=font(n,bold),fill=color,anchor=anchor)


def place(canvas, source, x, y, size):
    with Image.open(ROOT/source) as raw:
        image=raw.convert('RGBA').resize((size,size),Image.Resampling.LANCZOS)
    canvas.paste(image,(x,y),image)


def sheet(items,dark=False):
    bg,paper,line,fg,muted=('#101722','#172231','#344356','#e6eaf1','#a7b5c7') if dark else ('#f7f7f3','#fff','#dfe4e8','#273442','#637286')
    height=196+((len(items)+1)//2)*460+114
    image=Image.new('RGB',(1440,height),bg)
    d=ImageDraw.Draw(image)
    put_text(d,(64,35),'OPENMS / FRAMELESS MEDAL STUDY',15,muted)
    put_text(d,(64,76),'去外框全套模板 · 保留核心与质感',34,fg,True)
    put_text(d,(64,133),'17 枚完整对照 · 左 v2，右去外框 · 尚未制作成绩配色或正式接入',18,muted)
    for i,item in enumerate(items):
        x,y=64+i%2*672,196+i//2*460
        d.rounded_rectangle((x,y,x+640,y+434),10,paper,line)
        put_text(d,(x+22,y+17),f"{item['id']} / {item['name']}",21,fg,True)
        place(image,item['before'],x+61,y+58,192)
        place(image,item['source'],x+387,y+58,192)
        put_text(d,(x+157,y+263),'v2 有外框',15,muted,anchor='mt')
        put_text(d,(x+483,y+263),f"去外框 · {item['status']}",15,muted,anchor='mt')
        d.line((x+22,y+301,x+618,y+301),fill=line)
        for cx,size in zip([x+90,x+198,x+306,x+414,x+532],SIZES):
            place(image,item['source'],cx-size//2,y+350-size//2,size)
            put_text(d,(cx,y+395),f'{size}px',12,muted,anchor='mt')
    put_text(d,(64,height-65),'17 枚全部已同意并保存为正式源模板。保留主体及必要副章，去掉统一大圆底座。',17,muted)
    return image


def overview(items,dark=False):
    bg,paper,line,fg,muted=('#101722','#172231','#344356','#e6eaf1','#a7b5c7') if dark else ('#f7f7f3','#fff','#dfe4e8','#273442','#637286')
    image=Image.new('RGB',(1440,1530),bg)
    d=ImageDraw.Draw(image)
    put_text(d,(64,35),'OPENMS / FRAMELESS MEDAL COLLECTION',15,muted)
    put_text(d,(64,76),'去外框全套模板 · v3',36,fg,True)
    put_text(d,(64,136),'17 个系列 · 原图核心与立体质感 · 17 枚全部已同意并保存',18,muted)
    for i,item in enumerate(items):
        x,y=64+i%5*266,224+i//5*300
        d.rounded_rectangle((x,y,x+248,y+280),10,paper,line)
        put_text(d,(x+16,y+12),f"{item['id']} / {item['category']}",14,muted)
        place(image,item['source'],x+40,y+38,168)
        put_text(d,(x+124,y+214),item['name'],18,fg,True,'mt')
        place(image,item['source'],x+74,y+243,32)
        place(image,item['source'],x+124,y+235,40)
        put_text(d,(x+178,y+247),'32 / 40',10,muted)
    put_text(d,(64,1465),'沿用原图色调供基础造型检阅；正式成绩配色及站点接入仍待后续确认。',17,muted)
    return image


def size_sheet(items,dark=False):
    bg,line,fg,muted=('#101722','#344356','#e6eaf1','#a7b5c7') if dark else ('#fff','#e1e6eb','#273442','#637286')
    image=Image.new('RGB',(1320,2110),bg)
    d=ImageDraw.Draw(image)
    put_text(d,(60,32),'去外框全套模板 · 实际尺寸',30,fg,True)
    put_text(d,(60,86),'32 / 40 / 48 / 64 / 72px；100% 缩放下检查实际像素。',17,muted)
    centers=[500,660,820,980,1140]
    for cx,size in zip(centers,SIZES):
        put_text(d,(cx,142),f'{size}px',17,muted,anchor='mt')
    for i,item in enumerate(items):
        y=180+i*108
        d.line((60,y,1260,y),fill=line)
        put_text(d,(60,y+27),f"{item['id']} / {item['name']}",19,fg,True)
        put_text(d,(60,y+61),item['slug'],13,muted)
        for cx,size in zip(centers,SIZES):
            place(image,item['source'],cx-size//2,y+54-size//2,size)
    put_text(d,(60,2050),'v3 · 17 个系列 · 尚未制定正式成绩配色或接入站点',16,muted)
    return image


def page(items):
    cards=[]
    gallery=[]
    size_rows=[]
    for item in items:
        samples=''.join(f'<figure><img src="{item["source"]}" width="{size}" height="{size}" alt="{size}px"><figcaption>{size}px</figcaption></figure>' for size in SIZES)
        cards.append(f'''<article><h2>{item['id']} / {item['name']} <span>{item['status']}</span></h2><div class="pair"><figure><button class="enlarge" data-id="{item['id']}" aria-label="放大对照{item['name']}"><img src="{item['before']}" alt="v2 有外框"></button><figcaption>v2 有外框</figcaption></figure><figure><button class="enlarge" data-id="{item['id']}" aria-label="放大去外框{item['name']}"><img src="{item['source']}" alt="去外框模板"></button><figcaption>去外框 · {item['status']}</figcaption></figure></div><div class="sizes">{samples}</div><a href="{item['source']}" download>下载透明 PNG 原图</a></article>''')
        gallery.append(f'''<article class="gallery-tile"><div class="gallery-meta"><span>{item['id']} / {item['category']}</span><span>{item['status']}</span></div><button class="enlarge" data-id="{item['id']}" aria-label="查看{item['name']}对照"><img src="{item['source']}" alt="{item['name']}"></button><h2>{item['name']}</h2><div class="gallery-bottom"><img src="{item['source']}" width="32" height="32" alt="32px"><span>32px</span><a href="{item['source']}" download>PNG 原图 ↗</a></div></article>''')
        size_rows.append(f'<article class="size-row"><h2>{item["id"]} / {item["name"]}</h2><div class="sizes">{samples}</div></article>')
    data=json.dumps(items,ensure_ascii=False)
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>勋章去外框全套模板 v3</title><style>
:root{--bg:#f7f7f3;--paper:#fff;--text:#273442;--muted:#637286;--line:#dfe4e8;color-scheme:light}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 'Microsoft YaHei','Segoe UI',sans-serif}body.dark{--bg:#101722;--paper:#172231;--text:#e6eaf1;--muted:#a7b5c7;--line:#344356;color-scheme:dark}main{max-width:1320px;padding:40px;margin:auto}.eyebrow{font-size:12px;letter-spacing:2px;color:var(--muted)}h1{font-size:30px;margin:12px 0}header p{margin:5px 0;color:var(--muted)}.tools{display:flex;gap:10px;align-items:center;justify-content:space-between;margin:22px 0;border-block:1px solid var(--line);padding:14px 0}a{color:inherit;text-underline-offset:4px}button{cursor:pointer;font:inherit}button:focus-visible,a:focus-visible{outline:2px solid var(--text);outline-offset:4px}.tools button,dialog button{padding:7px 12px;color:var(--text);background:var(--paper);border:1px solid var(--line);border-radius:6px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}article{min-width:0;padding:20px;background:var(--paper);border:1px solid var(--line);border-radius:9px}h2{margin:0 0 14px;font-size:18px}h2 span{float:right;color:var(--muted);font-weight:400;font-size:12px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}.pair figure{min-width:0;text-align:center;margin:0}.enlarge{width:100%;max-width:220px;aspect-ratio:1;display:block;border:0;background:transparent;margin:auto;padding:0}.enlarge img{width:100%;height:100%;object-fit:contain}.pair figcaption{font-size:13px;margin:10px 0;color:var(--muted)}.sizes{display:flex;align-items:flex-end;justify-content:space-around;gap:8px;border-block:1px solid var(--line);padding:14px 0;margin:14px 0}.sizes figure{margin:0;display:flex;flex-direction:column;align-items:center;justify-content:end;gap:10px}.sizes img{object-fit:contain}.sizes figcaption{font-size:11px;color:var(--muted)}article>a{font-size:12px;color:var(--muted)}footer{margin-top:28px;padding-top:20px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}footer p{margin:6px 0}.links{display:flex;gap:18px;flex-wrap:wrap}dialog{width:min(850px,calc(100% - 32px));border:1px solid var(--line);border-radius:10px;padding:24px;color:var(--text);background:var(--paper)}dialog::backdrop{background:#0009}.dialog-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}.dialog-pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}.dialog-pair figure{margin:0;text-align:center;min-width:0}.dialog-pair img{width:100%;aspect-ratio:1;object-fit:contain}.dialog-pair figcaption{color:var(--muted);font-size:13px}@media(max-width:900px){main{padding:26px 20px}.grid{grid-template-columns:1fr}h1{font-size:26px}}@media(max-width:500px){main{padding:22px 12px}article{padding:14px}.pair{gap:12px}.sizes{gap:4px}.sizes img{max-width:100%;height:auto}h2{font-size:16px}}

[hidden]{display:none!important}.view-buttons{display:flex;gap:6px;flex-wrap:wrap}.view-buttons button[aria-pressed=true]{background:var(--text);color:var(--bg)}.gallery-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px}.gallery-tile{padding:14px}.gallery-tile .enlarge{width:168px;max-width:100%;height:168px;margin:12px auto}.gallery-tile h2{font-size:16px;margin:10px 0}.gallery-meta,.gallery-bottom{display:flex;align-items:center;gap:7px;color:var(--muted);font-size:11px}.gallery-meta{justify-content:space-between}.gallery-bottom{border-top:1px solid var(--line);padding-top:10px}.gallery-bottom a{margin-left:auto}.gray img{filter:grayscale(1)}.size-list{overflow:auto}.size-row{display:flex;align-items:center;gap:20px;min-width:860px;margin-bottom:10px}.size-row h2{width:240px;flex-shrink:0;font-size:16px;margin:0}.size-row .sizes{flex:1;border:0;margin:0;padding:0;min-height:100px}.tools{flex-wrap:wrap}@media(max-width:1200px){.gallery-grid{grid-template-columns:repeat(4,minmax(0,1fr))}}@media(max-width:900px){.gallery-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:650px){.gallery-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.gallery-tile{padding:10px}.gallery-tile .enlarge{width:128px;height:128px}.gallery-bottom{flex-wrap:wrap}.gallery-bottom a{margin-left:0}}
</style></head><body><main><header><div class="eyebrow">OPENMS / FRAMELESS MEDAL STUDY</div><h1>去外框全套模板 · v3</h1><p>全套 17 个系列已同意并保存为正式源模板；保留主体厚度与原图色调。</p><p>17 枚已全部替换旧源模板。点击图片查看 v2／去外框对照。</p></header><div class="tools"><div class="view-buttons"><button id="gallery-btn" aria-pressed="true">全部 17 枚</button><button id="compare-btn" aria-pressed="false">v2 对照</button><button id="size-btn" aria-pressed="false">实际尺寸</button></div><div class="view-buttons"><button id="theme" aria-pressed="false">深色背景</button><button id="gray" aria-pressed="false">灰度检查</button></div></div><section id="gallery-view" class="gallery-grid">''' + ''.join(gallery) + '''</section><section id="compare-view" class="grid" hidden>''' + ''.join(cards) + '''</section><section id="size-view" class="size-list" hidden>''' + ''.join(size_rows) + '''</section><footer><div class="links"><a href="overview-light.png">浅色总览</a><a href="overview-dark.png">深色总览</a><a href="sizes-grayscale.png">灰度尺寸长图</a><a href="comparison-light.png">浅色对照长图</a><a href="comparison-dark.png">深色对照长图</a><a href="README.md">源文件与说明</a><a href="generation-record.json" download>编辑提示词记录</a></div><p>17 枚已保存为正式源模板，旧源图已留档。尚未制作成绩配色或更新站点发布图。</p><p>尺寸行在浏览器缩放 100% 时对应实际像素。</p></footer><dialog id="detail"><div class="dialog-head"><strong id="name"></strong><button id="close">关闭</button></div><div class="dialog-pair"><figure><img id="old" alt="v2 有外框"><figcaption>v2 有外框</figcaption></figure><figure><img id="new" alt="去外框样例"><figcaption>去外框样例</figcaption></figure></div></dialog><script>const items=''' + data + ''';const $=id=>document.getElementById(id);for(const key of ['gallery','compare','size']){$(key+'-btn').onclick=()=>{for(const view of ['gallery','compare','size']){$(view+'-view').hidden=view!==key;$(view+'-btn').setAttribute('aria-pressed',String(view===key))}};}for(const [id,cls] of [['theme','dark'],['gray','gray']]){$(id).onclick=()=>$(id).setAttribute('aria-pressed',String(document.body.classList.toggle(cls)))}document.querySelectorAll('[data-id]').forEach(b=>b.onclick=()=>{const x=items.find(i=>i.id===b.dataset.id);$('name').textContent=x.id+' / '+x.name;$('old').src=x.before;$('new').src=x.source;$('detail').showModal()});$('close').onclick=()=>$('detail').close();</script></main></body></html>'''


if __name__=='__main__':
    items=json.loads((ROOT/'review.json').read_text(encoding='utf-8'))
    for dark,name in [(False,'light'),(True,'dark')]:
        sheet(items,dark).save(ROOT/f'comparison-{name}.png')
        overview(items,dark).save(ROOT/f'overview-{name}.png')
        size_sheet(items,dark).save(ROOT/f'sizes-{name}.png')
    with Image.open(ROOT/'sizes-light.png') as source:
        source.convert('L').convert('RGB').save(ROOT/'sizes-grayscale.png')
    (ROOT/'index.html').write_text(page(items),encoding='utf-8')
    print('Built all 17 frameless templates: HTML review, two overview sheets, two comparison sheets and three size sheets.')
