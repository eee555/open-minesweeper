import { createRequire } from 'node:module';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { readFileSync, writeFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const root = dirname(fileURLToPath(import.meta.url));
const require = createRequire(join(resolve(root, '../../../..'), 'front_end/package.json'));
const bundle = require('esbuild').buildSync({ entryPoints: [join(root, 'tone.ts')], bundle: true, write: false, format: 'esm' }).outputFiles[0].text;
const { toneTable, sampleTable } = await import('data:text/javascript;base64,' + Buffer.from(bundle).toString('base64'));
const finishes = ['body', 'metal', 'previous'];
for (const finish of finishes) for (const channel of [0, 0.1, 0.3, 0.6, 1]) {
    const table = toneTable(channel, finish);
    assert(table.every((value, index) => value >= 0 && value <= 1 && (index === 0 || value >= table[index - 1])));
}
for (const channel of [0, 0.1, 0.3, 0.6]) {
    for (const brightness of [0.75, 0.82, 0.9, 0.96]) {
        const [body, metal, previous] = finishes.map(finish => sampleTable(toneTable(channel, finish), brightness));
        assert(body < metal && metal < previous);
    }
    const facetRange = finish => sampleTable(toneTable(channel, finish), 0.96) - sampleTable(toneTable(channel, finish), 0.82);
    assert(facetRange('metal') > facetRange('body') * 4);
}
const palette = JSON.parse(readFileSync(join(root, 'review.json'), 'utf8')).default_palette.colors;
const examples = palette.map(color => {
    const channels = [1, 3, 5].map(i => parseInt(color.slice(i, i + 2), 16) / 255);
    return { color, samples: finishes.map(finish => ({ finish, rgb_at_90_percent_source_brightness: channels.map(channel => Math.round(sampleTable(toneTable(channel, finish), 0.9) * 255)) })) };
});
const report = { default_finish: 'metal', source: 'tone.ts', all_tables_bounded_monotonic: true, moderate_highlight_levels_between_previous_versions: true, facet_brightness_range_restored: true, method: 'numerical sampling of actual transfer tables; not browser visual verification', examples };
writeFileSync(join(root, 'exports/finish-verification.json'), JSON.stringify(report, null, 2) + '\n');
console.log('Verified: moderate highlights between both previous treatments, continuous facet range, bounded monotonic channels.');
