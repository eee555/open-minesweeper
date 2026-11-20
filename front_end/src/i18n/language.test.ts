import { describe, expect, it } from 'vitest';

import { resolveContentLanguage } from './language';

describe('resolveContentLanguage', () => {
    it.each([['es', 'es'], ['es-MX', 'es'], ['ES-es', 'es'], ['zh-TW', 'zh-cn'], ['en-US', 'en'], ['fr', 'en']])('resolves %s to %s', (language, expected) => {
        expect(resolveContentLanguage(language)).toBe(expected);
    });
});
