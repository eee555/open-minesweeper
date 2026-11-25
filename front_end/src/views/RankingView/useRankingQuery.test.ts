import { describe, expect, it, vi } from 'vitest';
import { createSSRApp, effectScope, nextTick, watch } from 'vue';
import { createMemoryHistory, createRouter } from 'vue-router';

import { queryChoice, queryInteger, queryNF, useRankingQuery } from './useRankingQuery';

async function setup(url: string) {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/top', component: { render: () => null } }, { path: '/pb', component: { render: () => null } }] });
    await router.push(url);
    const app = createSSRApp({ render: () => null });
    app.use(router);
    const scope = effectScope();
    const options = app.runWithContext(() => scope.run(() => useRankingQuery<{ sort: string; detail: string; nf: boolean; page: number; page_size: number }>(
        { sort: 'et', detail: 'et', nf: false, page: 1, page_size: 20 },
        (query, defaults) => ({
            sort: queryChoice(query.sort, ['bt', 'et'], defaults.sort),
            detail: queryChoice(query.detail, ['bt', 'et'], defaults.detail),
            nf: queryNF(query.nf),
            page: queryInteger(query.page, defaults.page),
            page_size: queryChoice(query.page_size, [20, 50, 100], defaults.page_size),
        }),
        ['sort', 'nf', 'page_size'],
    )));
    if (!options) throw new Error('Ranking scope not initialized');
    return { router, scope, ...options };
}

describe('ranking URL options', () => {
    it('supports arbitrary start indices and resets them on sorting without introducing page numbers', async () => {
        const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/path', component: { render: () => null } }] });
        await router.push('/path?sort=b_path&start=27&page_size=50');
        const app = createSSRApp({ render: () => null });
        app.use(router);
        const scope = effectScope();
        try {
            const options = app.runWithContext(() => scope.run(() => useRankingQuery(
                { sort: 'sum_epath', start: 1, page_size: 20 },
                (query, defaults) => ({ sort: queryChoice(query.sort, ['b_path', 'sum_epath'], defaults.sort), start: queryInteger(query.start, defaults.start), page_size: queryChoice(query.page_size, [20, 50, 100], defaults.page_size) }),
                ['sort', 'page_size'],
            )));
            if (!options) throw new Error('Ranking scope not initialized');
            expect(options.fields.start.value).toBe(27);
            await options.update({ sort: 'sum_epath' });
            expect(options.fields.start.value).toBe(1);
            await options.update({ start: 12, page_size: 100 });
            expect(router.currentRoute.value.query).toEqual({ sort: 'sum_epath', start: '12', page_size: '100' });
        } finally {
            scope.stop();
        }
    });

    it('reads a deep link, batches related changes and restores pagination through history', async () => {
        const { router, scope, fields, update } = await setup('/top?sort=bt&detail=et&nf=1&page=3&page_size=50');
        try {
            expect(Object.fromEntries(Object.entries(fields).map(([key, value]) => [key, value.value]))).toEqual({ sort: 'bt', detail: 'et', nf: true, page: 3, page_size: 50 });
            const refreshed = vi.fn();
            const stop = watch([fields.sort, fields.page, fields.page_size], refreshed);
            await update({ sort: 'et', detail: 'et' });
            await nextTick();
            expect(refreshed).toHaveBeenCalledTimes(1);
            expect(router.currentRoute.value.query).toEqual({ sort: 'et', detail: 'et', nf: '1', page: '1', page_size: '50' });
            await new Promise<void>((resolve) => {
                const remove = router.afterEach(() => {
                    remove(); resolve();
                });
                router.back();
            });
            expect(fields.sort.value).toBe('bt');
            expect(fields.page.value).toBe(3);
            await new Promise<void>((resolve) => {
                const remove = router.afterEach(() => {
                    remove(); resolve();
                });
                router.forward();
            });
            expect(fields.sort.value).toBe('et');
            expect(fields.page.value).toBe(1);
            await update({ page: 3 });
            await update({ page_size: 100 });
            expect(fields.page.value).toBe(1);
            expect(fields.page_size.value).toBe(100);
            stop();
        } finally {
            scope.stop();
        }
    });

    it('preserves page on detail changes and ignores query changes on an inactive cached page', async () => {
        const { router, scope, fields, update } = await setup('/top?sort=bt&page=3&source=shared');
        try {
            await update({ detail: 'bt' });
            expect(fields.page.value).toBe(3);
            expect(router.currentRoute.value.query.source).toBe('shared');
            await router.push('/pb?sort=et&page=7');
            expect(fields.sort.value).toBe('bt');
            expect(fields.page.value).toBe(3);
            await update({ page: 5 });
            expect(router.currentRoute.value.path).toBe('/pb');
            expect(router.currentRoute.value.query.page).toBe('7');
        } finally {
            scope.stop();
        }
    });

    it('falls back for invalid, repeated and out-of-range values', async () => {
        const { scope, fields } = await setup('/top?sort=bad&sort=bt&nf=bad&page=-1&page_size=999');
        try {
            expect(fields.sort.value).toBe('et');
            expect(fields.nf.value).toBe(false);
            expect(fields.page.value).toBe(1);
            expect(fields.page_size.value).toBe(20);
            expect(queryInteger('382', 1, 381)).toBe(1);
            expect(queryInteger('1.5', 1)).toBe(1);
        } finally {
            scope.stop();
        }
    });
});
