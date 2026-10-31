import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import type { Plugin } from 'vite';

export function msrcNotices(): Plugin {
    const root = new URL('../node_modules/@putianyi888/msrc/', import.meta.url);
    const metadata = JSON.parse(readFileSync(new URL('package.json', root), 'utf8')) as { version: string };
    return {
        name: 'msrc-distribution-notices',
        apply: 'build',
        generateBundle() {
            for (const filename of ['LICENSE', 'THIRD_PARTY_NOTICES.md']) {
                this.emitFile({ type: 'asset', fileName: `assets/vendor/msrc-${metadata.version}/${filename}`, source: readFileSync(fileURLToPath(new URL(filename, root))) });
            }
        },
    };
}
