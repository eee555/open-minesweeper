import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { validateInlineHtml, writeBundledLicenses, writeOfflineArchive } from './offline-package.mjs';

const frontend = fileURLToPath(new URL('../', import.meta.url));
const output = join(frontend, 'dist-offline-minigame');
const source = join(frontend, 'local-minigame');
const versionFile = await readFile(join(source, 'version.json'), 'utf8');
const { version } = JSON.parse(versionFile);
if (typeof version !== 'string' || !/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/u.test(version)) throw new Error('Minigame version must use MAJOR.MINOR.PATCH');
const html = await readFile(join(output, 'index.html'), 'utf8');
const packagedDocuments = new Set(['index.html', 'README.txt', 'version.json', 'LICENSE', 'COPYRIGHT.txt', 'THIRD_PARTY_LICENSES.json', 'THIRD_PARTY_LICENSES.txt', 'licenses']);
const standaloneAssets = (await readdir(output)).filter((name) => !packagedDocuments.has(name));
if (standaloneAssets.length > 0) throw new Error(`Unbundled assets: ${standaloneAssets.join(', ')}`);
const resourceUrls = validateInlineHtml(html);
if (!html.includes('data:image/svg+xml')) throw new Error('Board textures were not inlined');
if (!html.includes('data:application/wasm')) throw new Error('Replay compression WASM was not inlined');

const dependencyLicenses = JSON.parse(await readFile(join(output, 'THIRD_PARTY_LICENSES.json'), 'utf8'));
if (dependencyLicenses.some((entry) => entry.name === 'ms-toollib')) throw new Error('Minigame unexpectedly bundles ms-toollib');
await writeBundledLicenses(output, dependencyLicenses);
await writeFile(join(output, 'LICENSE'), await readFile(join(frontend, '..', 'LICENSE')));
for (const name of ['README.txt', 'COPYRIGHT.txt']) await writeFile(join(output, name), await readFile(join(source, name)));
await writeFile(join(output, 'version.json'), versionFile);
await mkdir(join(output, 'licenses'), { recursive: true });
for (const [path, name] of [
    ['src/styles/theme/LICENSE.element-plus.txt', 'LICENSE.element-plus-theme.txt'],
    ['node_modules/primeicons/LICENSE', 'LICENSE.primeicons.txt'],
    ['node_modules/7z-wasm/License.txt', 'LICENSE.7z-wasm.txt'],
    ['node_modules/7z-wasm/unRarLicense.txt', 'LICENSE.unrar.txt'],
]) await writeFile(join(output, 'licenses', name), await readFile(join(frontend, path)));

const { zipPath, downloadPath } = await writeOfflineArchive(frontend, output, `OpenMinesweeperMinigames-${version}.zip`);
console.log(`Offline HTML: ${join(output, 'index.html')} (${html.length} characters)`);
console.log(`Inlined CSS resource URLs: ${resourceUrls.length}; no external scripts/styles/assets`);
console.log(`Offline package: ${zipPath}`);
console.log(`Website download: ${downloadPath}`);
console.log(`Bundled dependency licenses: ${dependencyLicenses.length}; inline 7z WASM, no ms-toollib`);
