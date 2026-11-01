import type { Plugin } from 'vite';
import { viteSingleFile } from 'vite-plugin-singlefile';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { singleFileWithLicenses } from '../../scripts/offline-build';

vi.mock('vite-plugin-singlefile', () => ({ viteSingleFile: vi.fn() }));

describe('single-file license collection ordering', () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });

    it('runs a function-style bundle hook after license collection', () => {
        const handler = vi.fn();
        const plugin: Plugin = { name: 'vite:singlefile', generateBundle: handler };
        vi.mocked(viteSingleFile).mockReturnValue(plugin);

        expect(singleFileWithLicenses()).toBe(plugin);
        expect(plugin.generateBundle).toEqual({ order: 'post', handler });
    });

    it('preserves object-style hook options and its handler while enforcing post order', () => {
        const handler = vi.fn();
        const hook = { order: 'pre' as const, sequential: true, handler };
        const plugin: Plugin = { name: 'vite:singlefile', generateBundle: hook };
        vi.mocked(viteSingleFile).mockReturnValue(plugin);

        expect(singleFileWithLicenses()).toBe(plugin);
        expect(plugin.generateBundle).toEqual({ ...hook, order: 'post' });
    });
});
