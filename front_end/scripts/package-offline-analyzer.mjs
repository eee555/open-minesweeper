import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import MarkdownIt from 'markdown-it';

import { validateInlineHtml, writeBundledLicenses, writeOfflineArchive } from './offline-package.mjs';

const frontend = fileURLToPath(new URL('../', import.meta.url));
const output = join(frontend, 'dist-offline-analyzer');
const versionFile = await readFile(join(frontend, 'local-analyzer', 'version.json'), 'utf8');
const { version } = JSON.parse(versionFile);
if (typeof version !== 'string' || !/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/u.test(version)) throw new Error('Analyzer version must use MAJOR.MINOR.PATCH');
const html = await readFile(join(output, 'index.html'), 'utf8');
const packagedDocuments = new Set(['index.html', 'help', 'README.txt', 'version.json', 'LICENSE', 'COPYRIGHT.txt', 'THIRD_PARTY_LICENSES.json', 'THIRD_PARTY_LICENSES.txt', 'licenses']);
const standaloneAssets = (await readdir(output)).filter((name) => !packagedDocuments.has(name));
if (standaloneAssets.length > 0) throw new Error(`Unbundled assets: ${standaloneAssets.join(', ')}`);
const resourceUrls = validateInlineHtml(html);
if (!html.includes('data:application/wasm;base64,')) throw new Error('WASM was not inlined');
const favicon = html.match(/<link\b(?=[^>]*\brel=["']icon["'])[^>]*\bhref=(["'])(.*?)\1/iu)?.[2];
if (!favicon || !/^data:image\/svg\+xml[;,]/iu.test(favicon)) throw new Error('Analyzer favicon was not inlined');

const projectLicense = await readFile(join(frontend, '..', 'LICENSE'), 'utf8');
await writeFile(join(output, 'LICENSE'), projectLicense);
await writeFile(join(output, 'COPYRIGHT.txt'), await readFile(join(frontend, 'local-analyzer', 'COPYRIGHT.txt')));
const dependencyLicenses = JSON.parse(await readFile(join(output, 'THIRD_PARTY_LICENSES.json'), 'utf8'));
if (dependencyLicenses.length === 0) throw new Error('Bundled dependency license list is empty');
const msToollib = dependencyLicenses.find((entry) => entry.name === 'ms-toollib');
if (msToollib && !msToollib.text) {
    if (msToollib.version !== '1.6.0') throw new Error('Recheck the ms-toollib license fallback for the new version');
    msToollib.identifier = 'MIT';
    msToollib.text = (await readFile(join(frontend, 'licenses', 'ms-toollib', 'LICENSE'), 'utf8')).trim();
    msToollib.source = 'https://github.com/eee555/ms-toollib/blob/fe5d57322f23ad91aacec78a9b0ca2e8da5651f0/LICENSE';
}
await writeBundledLicenses(output, dependencyLicenses);
await mkdir(join(output, 'licenses'), { recursive: true });
for (const [source, destination] of [
    ['src/styles/theme/LICENSE.element-plus.txt', 'LICENSE.element-plus-theme.txt'],
    ['src/styles/theme/LICENSE.element-plus.txt', 'LICENSE.element-plus-parameters.txt'],
    ['licenses/LICENSE.primeuix-parameters.txt', 'LICENSE.primeuix-parameters.txt'],
    ['node_modules/primeicons/LICENSE', 'LICENSE.primeicons.txt'],
    ['licenses/ms-toollib/LICENSE', 'LICENSE.ms-toollib.txt'],
]) await writeFile(join(output, 'licenses', destination), await readFile(join(frontend, source)));

const markdown = new MarkdownIt({ html: false, linkify: true });
for (const language of ['zh', 'en']) {
    const source = join(frontend, '..', 'vitepress_doc', language, 'guide', 'replay-expressions.md');
    const text = (await readFile(source, 'utf8')).replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/u, '');
    const help = join(output, 'help', ...(language === 'en' ? ['en'] : []), 'guide', 'replay-expressions.html');
    await mkdir(dirname(help), { recursive: true });
    await writeFile(help, `<!doctype html><html lang="${language === 'zh' ? 'zh-CN' : 'en'}"><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${language === 'zh' ? '录像表达式参考' : 'Replay expression reference'}</title><style>body{font:16px/1.6 system-ui,sans-serif;margin:24px auto;padding:0 16px;max-width:1100px}table{border-collapse:collapse;display:block;overflow:auto}th,td{border:1px solid #999;padding:4px 8px}code{background:#8882;padding:2px 4px}a{color:#337ecc}@media(prefers-color-scheme:dark){html{color-scheme:dark}a{color:#79bbff}}</style><body>${markdown.render(text)}</body></html>`);
}
await writeFile(join(output, 'README.txt'), await readFile(join(frontend, 'local-analyzer', 'README.txt')));
await writeFile(join(output, 'version.json'), versionFile);

const packageName = `OpenMinesweeperVideoAnalyzer-${version}.zip`;
const { zipPath, downloadPath } = await writeOfflineArchive(frontend, output, packageName);
console.log(`Offline HTML: ${join(output, 'index.html')} (${html.length} characters)`);
console.log(`Inlined CSS resource URLs: ${resourceUrls.length}; no external scripts/styles/assets`);
console.log(`Offline package: ${zipPath}`);
console.log(`Analyzer version: ${version}`);
console.log(`Website download: ${downloadPath}`);
console.log(`Copyright notices: project MIT, ${dependencyLicenses.length} bundled dependencies, CSS and font notices`);
