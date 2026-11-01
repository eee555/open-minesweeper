"""Export the existing color review, including its zoom dialog, to one offline HTML."""
from pathlib import Path
from html.parser import HTMLParser
import base64
import hashlib
import json
import mimetypes
import re

ROOT = Path(__file__).resolve().parent
EXPORTS = ROOT / 'exports'


def main():
    EXPORTS.mkdir(exist_ok=True)
    original = (ROOT / 'index.html').read_text(encoding='utf-8')
    assets = {}
    records = []

    def embed(match):
        attr, ref = match.groups()
        path = (ROOT / ref).resolve()
        if not path.is_relative_to(ROOT.parent) or not path.is_file():
            raise ValueError(f'Unresolved asset: {ref}')
        if ref not in assets:
            payload = path.read_bytes()
            mime = mimetypes.guess_type(ref)[0] or 'application/octet-stream'
            if path.suffix in ('.md', '.json'):
                mime = 'text/plain;charset=utf-8'
            assets[ref] = {'mime': mime, 'base64': base64.b64encode(payload).decode('ascii')}
            records.append({'path': ref, 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()})
        return f'data-offline-{attr}="{ref}"'

    offline = re.sub(r'\b(src|href)="([^"]+)"', embed, original)
    # The original dialog assigns image URLs on click; redirect those through the same cache.
    old = ';const $=id=>document.getElementById(id);'
    assert offline.count(old) == 1
    offline = offline.replace(old, ';for(const tier of palette)tier.source=window.reviewAssetUrls.get(tier.source)' + old)
    old = "$('download').href=tier.source;"
    assert offline.count(old) == 1
    offline = offline.replace(old, old + "$('download').download=tier.id+'.png';")
    loader = '''<script id="offline-assets" type="application/json">__ASSETS__</script><script>
(() => {
 const assets = JSON.parse(document.getElementById('offline-assets').textContent);
 const urls = new Map();
 for (const [path, item] of Object.entries(assets)) {
  const bytes = Uint8Array.from(atob(item.base64), c => c.charCodeAt(0));
  urls.set(path, URL.createObjectURL(new Blob([bytes], {type:item.mime})));
 }
 window.reviewAssetUrls = urls;
 for (const attr of ['src', 'href']) {
  for (const el of document.querySelectorAll('[data-offline-'+attr+']')) {
   const path = el.getAttribute('data-offline-'+attr);
   el.setAttribute(attr, urls.get(path));
   if (attr === 'href') {
    if (el.hasAttribute('download')) el.setAttribute('download', path.split('/').pop());
    else {el.setAttribute('target','_blank');el.setAttribute('rel','noopener');}
   }
  }
 }
})();</script>'''.replace('__ASSETS__', json.dumps(assets, ensure_ascii=True, separators=(',', ':')))
    # Load the cache before the original interaction script executes.
    assert offline.count('<script>') == 1
    offline = offline.replace('<script>', loader + '<script>', 1)

    class Audit(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                if key in ('src', 'href'):
                    assert value.startswith(('data:', 'blob:', '#')), (tag, key, value)

    Audit().feed(offline)
    for ref, item in assets.items():
        assert base64.b64decode(item['base64']) == (ROOT / ref).read_bytes()
    target = EXPORTS / 'time-color-preview-offline.html'
    target.write_text(offline, encoding='utf-8')
    manifest = {
        'version': 'time-b-color-v1', 'exported_on': '2026-10-31',
        'source_sha256': hashlib.sha256((ROOT / 'index.html').read_bytes()).hexdigest(),
        'embedded_assets': records, 'requires_local_server': False,
        'offline_html': {'filename': target.name, 'bytes': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()},
        'verification': ['All embedded payloads match source bytes', 'No external or relative HTML src/href dependencies'],
    }
    (EXPORTS / 'export-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Saved offline color review: {len(assets)} embedded assets, {target.stat().st_size} bytes.')


if __name__ == '__main__':
    main()
