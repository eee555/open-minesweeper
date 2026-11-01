import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join } from 'node:path';
import { createHash } from 'node:crypto';

const root = dirname(fileURLToPath(import.meta.url));
const workspace = resolve(root, '../../../..');
const require = createRequire(join(workspace, 'front_end/package.json'));
const { buildSync } = require('esbuild');
const original = JSON.parse(readFileSync(join(root, '../time-b-color-v1/review.json'), 'utf8'));
const files = {
    base: 'front_end/src/assets/medal-templates/breakthrough.png',
    star1: 'front_end/src/assets/medal-overlays/difficulty/one-star.png',
    star2: 'front_end/src/assets/medal-overlays/difficulty/two-stars.png',
    star3: 'front_end/src/assets/medal-overlays/difficulty/three-stars.png',
};
const assets = {}, records = [];
for (const [id, path] of Object.entries(files)) {
    const bytes = readFileSync(join(workspace, path));
    assets[id] = { mime: 'image/png', base64: bytes.toString('base64') };
    records.push({ id, path, bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') });
}
const stages = original.medals.map(({ stage, label, tier }) => ({ stage, label, tier: Number(tier.slice(4)) }));
const result = buildSync({ entryPoints: [join(root, 'preview.ts')], bundle: true, write: false, format: 'iife', platform: 'browser', target: 'es2022', charset: 'utf8' });
const script = result.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const payload = JSON.stringify({ stages, assets }).replace(/</g, '\\u003c');
const template = readFileSync(join(root, 'template.html'), 'utf8');
const html = template.replace('__REVIEW_DATA__', () => payload).replace('__APP_CODE__', () => script);
mkdirSync(join(root, 'exports'), { recursive: true });
writeFileSync(join(root, 'index.html'), html);
writeFileSync(join(root, 'exports/time-color-accessible-preview-offline.html'), html);
const metadata = {
    version: 'time-color-accessible-v5', status: '柔和金属着色模板已同意并设为默认；门槛映射单独待定', date: '2026-11-01',
    default_palette: { reference: 'User-directed five-hue palette adjusted with CVD simulations', names: ['深蓝', '中蓝', '浅紫', '浅橙', '中红'], colors: ['#244A86', '#4C91C7', '#CCB8E3', '#F2CE9B', '#B34A55'] },
    code: 'ability.time.b', stages, mapping_status: original.mapping_status,
    customization: { global_score_tiers: 5, exact_threshold_overrides: true, priority: 'code + stage override, then reviewed score tier', storage_key: 'medal-appearance-colors-v1', version: 1, viewer_only: true },
    artwork: { method: 'soft metal tonal curve with continuous moderate highlights; original full-canvas source and independent difficulty overlay; no source PNG alteration', tone_source: 'front_end/src/services/medalMaterial.ts', tone_samples_per_channel: 256, default_finish: 'metal', approved_material: 'soft-metal-v1', approved_on: '2026-11-01', historical_comparison_finishes: ['body', 'previous'], comparison: 'three live finishes for tier 1', marker_css: { left: '4%', top: '0%', width: '36%', height: '36%' } },
    simulation: { model: 'Machado, Oliveira and Fernandes 2009, severity 1.0, linear RGB', modes: ['normal', 'protanopia', 'deuteranopia', 'tritanopia', 'gray'], limitation: 'approximation for review; no universal color-discrimination or compliance certification' },
    runtime_integration: 'shared preference service implemented; production components and final tier mappings pending design review',
    sources: ['https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html', 'https://pubmed.ncbi.nlm.nih.gov/19834201/'],
};
writeFileSync(join(root, 'review.json'), JSON.stringify(metadata, null, 2) + '\n');
const manifest = { version: metadata.version, assets: records, html: { bytes: Buffer.byteLength(html), sha256: createHash('sha256').update(html).digest('hex') }, standalone: true, app_script_bytes: Buffer.byteLength(script) };
writeFileSync(join(root, 'exports/export-manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
console.log(`Built offline accessible review: 5 editable tiers, ${stages.length} thresholds, ${records.length} original assets, ${Buffer.byteLength(html)} bytes.`);
