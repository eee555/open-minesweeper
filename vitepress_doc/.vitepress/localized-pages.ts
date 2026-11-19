import { readdirSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

export function getLocalizedPages() {
    return Object.fromEntries(['zh', 'en', 'es'].map((locale) => {
        const directory = fileURLToPath(new URL(`../${locale}/`, import.meta.url));
        const pages = readdirSync(directory, { recursive: true, withFileTypes: true })
            .filter((entry) => entry.isFile() && entry.name.endsWith('.md'))
            .map((entry) => relative(directory, join(entry.parentPath, entry.name)).replaceAll('\\', '/').replace(/(^|\/)index\.md$/, '$1').replace(/\.md$/, ''))
            .sort();
        return [locale, pages];
    })) as Record<'zh' | 'en' | 'es', string[]>;
}
