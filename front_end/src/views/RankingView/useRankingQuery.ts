import { computed, shallowRef, watch } from 'vue';
import type { WritableComputedRef } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import type { LocationQuery, LocationQueryValue, Router } from 'vue-router';

type QueryValue = LocationQueryValue | LocationQueryValue[] | undefined;
type RankingOptions = Record<string, string | number | boolean> & { page_size: number } & ({ page: number } | { start: number });
type RankingFields<T> = { [K in keyof T]: WritableComputedRef<T[K]> };
type Navigate = ReturnType<Router['push']> | undefined;

export function queryChoice<T extends string | number>(value: QueryValue, choices: readonly T[], fallback: T): T {
    return choices.find((choice) => typeof value === 'string' && String(choice) === value) ?? fallback;
}

export function queryInteger(value: QueryValue, fallback: number, maximum = Math.floor(Number.MAX_SAFE_INTEGER / 100)): number {
    const number = typeof value === 'string' ? Number(value) : NaN;
    return Number.isSafeInteger(number) && number > 0 && number <= maximum ? number : fallback;
}

export function queryNF(value: QueryValue): boolean {
    return value === '1' || value === 'true';
}

export function useRankingQuery<T extends RankingOptions>(defaults: T, parse: (query: LocationQuery, defaults: T) => T, resetPageOn: (keyof T)[]): { fields: RankingFields<T>; update: (patch: Partial<T>, replace?: boolean) => Navigate } {
    const route = useRoute();
    const router = useRouter();
    const { path } = route;
    const query = shallowRef(route.query);
    const state = computed(() => parse(query.value, defaults));
    const keys = Object.keys(defaults) as (keyof T)[];
    const positionKey = 'start' in defaults ? 'start' : 'page';

    // Cached ranking pages must not react to another page's query parameters.
    watch(() => route.fullPath, () => {
        if (route.path === path) query.value = route.query;
    }, { flush: 'sync' });

    function update(patch: Partial<T>, replace = false): Navigate {
        if (route.path !== path || !keys.some((key) => key in patch && patch[key] !== state.value[key])) return;
        const next = { ...state.value, ...patch };
        if (!(positionKey in patch) && resetPageOn.some((key) => key in patch && patch[key] !== state.value[key])) Object.assign(next, { [positionKey]: 1 });
        const nextQuery = { ...route.query };
        for (const key of keys) {
            const value = next[key];
            nextQuery[String(key)] = typeof value === 'boolean' ? value ? '1' : '0' : String(value);
        }
        return router[replace ? 'replace' : 'push']({ path, query: nextQuery, hash: route.hash });
    }

    const fields = Object.fromEntries(keys.map((key) => [key, computed({
        get: () => state.value[key],
        set: (value: T[typeof key]) => {
            void update({ [key]: value } as Partial<T>);
        },
    })])) as RankingFields<T>;
    return { fields, update };
}
