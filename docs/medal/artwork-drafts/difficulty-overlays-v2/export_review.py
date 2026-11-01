"""Save the reviewed page as a self-contained HTML and a source archive."""
from pathlib import Path
from html.parser import HTMLParser
import base64
import hashlib
import json
import mimetypes
import re
import zipfile

ROOT = Path(__file__).resolve().parent
EXPORTS = ROOT / 'exports'
ATTRIBUTE = re.compile(r'\b(src|href)="([^"]+)"')


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def main():
    EXPORTS.mkdir(exist_ok=True)
    source = (ROOT / 'index.html').read_text(encoding='utf-8')
    assets = {}
    records = []

    def embed(match):
        attr, ref = match.groups()
        if ref.startswith(('#', 'data:', 'blob:')):
            return match.group(0)
        path = (ROOT / ref).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError(f'Unresolved asset: {ref}')
        if ref not in assets:
            payload = path.read_bytes()
            mime = mimetypes.guess_type(ref)[0] or 'application/octet-stream'
            if path.suffix in ('.md', '.json'):
                mime = 'text/plain;charset=utf-8'
            assets[ref] = {'mime': mime, 'base64': base64.b64encode(payload).decode('ascii')}
            records.append({'path': ref, 'bytes': len(payload), 'sha256': sha(payload)})
        return f'data-offline-{attr}="{ref}"'

    offline = ATTRIBUTE.sub(embed, source)
    loader = '''<script id="offline-assets" type="application/json">__ASSETS__</script><script>
(() => {
 const assets = JSON.parse(document.getElementById('offline-assets').textContent);
 const urls = new Map();
 for (const [path, item] of Object.entries(assets)) {
  const bytes = Uint8Array.from(atob(item.base64), c => c.charCodeAt(0));
  urls.set(path, URL.createObjectURL(new Blob([bytes], {type:item.mime})));
 }
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
    offline = offline.replace('</body>', loader + '</body>')
    html_path = EXPORTS / 'difficulty-overlays-preview-offline.html'
    html_path.write_text(offline, encoding='utf-8')

    class Audit(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                if key in ('src', 'href'):
                    assert value.startswith(('data:', 'blob:', '#')), (tag, key, value)

    Audit().feed(offline)
    for ref, item in assets.items():
        assert base64.b64decode(item['base64']) == (ROOT / ref).read_bytes()

    archive = EXPORTS / 'difficulty-overlays-preview.zip'
    prefix = 'difficulty-overlays-preview/'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(prefix + 'offline.html', html_path.read_bytes())
        z.writestr(prefix + 'OPEN-FIRST.txt', 'Open offline.html directly. No server is required. The site directory preserves the source files.\n')
        for path in sorted(ROOT.rglob('*')):
            relative = path.relative_to(ROOT)
            if path.is_file() and not any(part in ('exports', '__pycache__') for part in relative.parts) and path.suffix != '.pyc':
                z.write(path, prefix + 'site/' + relative.as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert z.read(prefix + 'offline.html') == html_path.read_bytes()
        for record in records:
            assert sha(z.read(prefix + 'site/' + record['path'])) == record['sha256']

    manifest = {
        'exported_on': '2026-10-31', 'version': 'difficulty-overlays-v2',
        'source_sha256': sha((ROOT / 'index.html').read_bytes()),
        'embedded_assets': records,
        'offline_html': {'filename': html_path.name, 'bytes': html_path.stat().st_size, 'sha256': sha(html_path.read_bytes())},
        'archive': {'filename': archive.name, 'bytes': archive.stat().st_size, 'sha256': sha(archive.read_bytes())},
        'requires_local_server': False,
        'verification': ['All embedded payloads match source bytes', 'No external or relative HTML src/href dependencies', 'ZIP CRC and archived linked assets verified'],
    }
    (EXPORTS / 'export-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Saved offline HTML ({html_path.stat().st_size} bytes), ZIP ({archive.stat().st_size} bytes); {len(assets)} embedded assets verified.')


if __name__ == '__main__':
    main()
