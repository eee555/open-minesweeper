import assert from 'node:assert/strict';
import { test } from 'node:test';
import { getLocaleRedirect } from '../theme/locale-routing.ts';
import { getLocalizedPages } from '../localized-pages.ts';

import type { LocalizedPages } from '../locales.ts';

const pages: LocalizedPages = {
    es: ['', 'guide/minesweeper/stat'],
    zh: ['', 'guide/minesweeper/stat', 'guide/development/cache'],
    en: ['', 'guide/', 'guide/minesweeper/stat'],
};

for (const [path, language, expected] of [
    ['/docs/', 'es-ES', '/docs/es/'],
    ['/docs/guide/minesweeper/stat?from=menu#stnb', 'es-MX', '/docs/es/guide/minesweeper/stat?from=menu#stnb'],
    ['/docs/?lang=es', 'en', '/docs/es/?lang=es'],
    ['/docs/es/guide/minesweeper/stat?lang=zh', 'zh', undefined],
    ['/docs/guide/development/cache', 'es', '/docs/es/guide/development/cache'],
    ['/docs/', 'zh-CN', '/docs/zh/'],
    ['/docs', 'en-US', '/docs/en/'],
    ['/docs/index.html', 'fr-FR', '/docs/en/'],
    ['/docs/guide/minesweeper/stat?from=menu#stnb', 'en-US', '/docs/en/guide/minesweeper/stat?from=menu#stnb'],
    ['/docs/guide/minesweeper/stat', 'zh-TW', '/docs/zh/guide/minesweeper/stat'],
    ['/docs/guide/minesweeper/stat.html', 'en', '/docs/en/guide/minesweeper/stat'],
    ['/docs/guide/minesweeper/stat/', 'en', '/docs/en/guide/minesweeper/stat'],
    ['/docs/guide/', 'zh', '/docs/zh/guide/'],
    ['/docs/guide/index.html', 'en', '/docs/en/guide/'],
    ['/docs/?lang=zh', 'en', '/docs/zh/?lang=zh'],
    ['/docs/?lang=en', 'zh', '/docs/en/?lang=en'],
    ['/docs/?lang=unknown', 'zh', '/docs/zh/?lang=unknown'],
    ['/docs/zh/', 'en', undefined],
    ['/docs/en/', 'zh', undefined],
    ['/docs/zh/guide/minesweeper/stat?lang=en', 'en', undefined],
    ['/docs/en/guide/minesweeper/stat', 'zh', undefined],
    ['/docs/guide/development/cache#redis', 'en', '/docs/en/guide/development/cache#redis'],
    ['/docs/guide/development/cache?lang=en#redis', 'zh', '/docs/en/guide/development/cache?lang=en#redis'],
    ['/docs/en/guide/development/cache?from=switch#redis', 'en', undefined],
    ['/docs/zh/guide/?from=switch#intro', 'en', undefined],
    ['/docs/unknown', 'en', undefined],
    ['/docs/en/unknown', 'zh', undefined],
    ['/docs/logo.png', 'en', undefined],
    ['/other/guide/minesweeper/stat', 'en', undefined],
    ['/docs-other/', 'en', undefined],
] as const) {
    test(`${language}: ${path}`, () => {
        const result = getLocaleRedirect(new URL(path, 'https://example.com'), '/docs/', pages, language);
        assert.equal(result, expected);
        if (result) assert.equal(getLocaleRedirect(new URL(result, 'https://example.com'), '/docs/', pages, language), undefined);
    });
}

for (const base of ['/', '/saolei_website/']) {
    test(`uses the deployment base ${base}`, () => {
        assert.equal(getLocaleRedirect(new URL(`${base}guide/minesweeper/stat#stnb`, 'https://example.com'), base, pages, 'en'), `${base}en/guide/minesweeper/stat#stnb`);
    });
}

test('provides a Spanish counterpart for every guide, including development pages', () => {
    const actual = getLocalizedPages();
    assert.deepEqual(actual.es, [...new Set([...actual.zh, ...actual.en])].sort());
    assert.ok(actual.zh.includes(''));
    assert.ok(actual.en.includes(''));
    assert.ok(actual.zh.includes('guide/minesweeper/stat'));
    assert.ok(actual.en.includes('guide/minesweeper/stat'));
    assert.ok(actual.zh.includes('guide/development/management-commands'));
    assert.ok(!actual.en.includes('guide/development/management-commands'));
});
