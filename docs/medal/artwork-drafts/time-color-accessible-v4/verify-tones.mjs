/** Check the actual exported transfer tables against source brightness; no image files are modified. */
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import assert from 'node:assert/strict';

const root = dirname(fileURLToPath(import.meta.url));
const workspace = resolve(root, '../../../..');
const require = createRequire(join(workspace, 'front_end/package.json'));
const { buildSync } = require('esbuild');
const bundle = buildSync({ entryPoints: [join(root, 'tone.ts')], bundle: true, write: false, format: 'esm', platform: 'node' }).outputFiles[0].text;
const { toneTable, sampleTable } = await import('data:text/javascript;base64,' + Buffer.from(bundle).toString('base64'));
for (const channel of [0, 0.1, 0.3, 0.6, 1]) {
    const table = toneTable(channel);
    assert.equal(table.length, 256);
    assert(table.every((v, i) => v >= 0 && v <= 1 && (i === 0 || v >= table[i - 1])));
    assert(Math.abs(sampleTable(table, 0.75) - channel) < 0.001);
    assert(Math.abs(sampleTable(table, 0.9) - (channel + (1 - channel) * 0.02)) < 0.001);
}
const python = 'C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const histogram = JSON.parse(execFileSync(python, ['-c', `from PIL import Image
import json,sys
h=[0]*256
im=Image.open(sys.argv[1]).convert('RGBA')
for r,g,b,a in im.get_flattened_data():
 if a>128:h[round(.213*r+.715*g+.072*b)]+=1
print(json.dumps(h))`, join(workspace, 'front_end/src/assets/medal-templates/breakthrough.png')], { encoding: 'utf8' }));
const palette = JSON.parse(readFileSync(join(root, 'review.json'), 'utf8')).default_palette.colors;
const total = histogram.reduce((a, b) => a + b, 0);
function rgb(hex) { return [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255); }
const results = palette.map(color => {
    const selected = rgb(color);
    const modes = {};
    for (const finish of ['previous', 'body']) {
        const tables = selected.map(c => toneTable(c, finish));
        let near = 0, brightened = 0;
        histogram.forEach((count, index) => {
            const output = tables.map(table => sampleTable(table, index / 255));
            const difference = output.map((v, c) => v - selected[c]);
            if (Math.hypot(...difference) * 255 <= 24) near += count;
            const direction = selected.map(c => 1 - c);
            const white = difference.reduce((sum, v, c) => sum + v * direction[c], 0) / direction.reduce((sum, v) => sum + v * v, 0);
            if (white > 0.2) brightened += count;
        });
        modes[finish] = { near_selected_percent: +(near / total * 100).toFixed(2), white_mix_over_20_percent: +(brightened / total * 100).toFixed(2) };
    }
    assert(modes.body.near_selected_percent > modes.previous.near_selected_percent);
    assert(modes.body.white_mix_over_20_percent < modes.previous.white_mix_over_20_percent / 2);
    return { color, ...modes };
});
const report = { method: 'Actual SVG transfer table sampling over source grayscale histogram; alpha > 128; no browser screenshot',
    near_definition: 'Euclidean encoded RGB distance <= 24 from selected color',
    white_mix_definition: 'Projection of output-minus-selected RGB onto direction toward white, above 0.2',
    limitation: 'Source-brightness diagnostic; not semantic face segmentation or final browser rasterization',
    source_opaque_pixels: total, tables_bounded_monotonic: true, main_face_tracks_selected: true, palette_results: results };
writeFileSync(join(root, 'exports/tone-verification.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report));
