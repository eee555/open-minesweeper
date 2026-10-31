import { describe, expect, it } from 'vitest';

import { defaultMedalPalette, loadMedalPalette, medalPaletteColor, parseMedalPalette, saveMedalPalette } from './medalPalette';

describe('viewer medal palette', () => {
    it('keeps independent defaults and resolves explicit tiers without deriving them from difficulty', () => {
        const first = defaultMedalPalette();
        first.colors[0] = '#FFFFFF';
        const config = defaultMedalPalette();
        expect(config.colors[0]).toBe('#244A86');
        expect(medalPaletteColor(config, 2, 'ability.time.b', 10000)).toBe(config.colors[1]);
        expect(medalPaletteColor(config, 2, 'ability.time.e', 10000)).toBe(config.colors[1]);
        for (const tier of [undefined, 0, 6, NaN, 1.5]) expect(medalPaletteColor(config, tier, 'future.code', 1234)).toBeUndefined();
    });

    it('lets exact code and threshold overrides take priority while preserving the tier mapping', () => {
        const config = defaultMedalPalette();
        config.stages['ability.time.b'] = { 10000: '#123456' };
        expect(medalPaletteColor(config, 2, 'ability.time.b', 10000)).toBe('#123456');
        expect(medalPaletteColor(config, 2, 'ability.time.b', 8000)).toBe(config.colors[1]);
        expect(medalPaletteColor(config, 2, 'ability.time.i', 10000)).toBe(config.colors[1]);
        expect(medalPaletteColor(config, 2, 'ability.time.b', null)).toBe(config.colors[1]);
    });

    it('normalizes a valid imported palette and drops unrelated metadata', () => {
        const input = { ...defaultMedalPalette(), thresholds: [999], stages: { 'ability.time.b': { 20000: ' #abcdef ' } } };
        const parsed = parseMedalPalette(JSON.stringify(input));
        expect(parsed.stages['ability.time.b']['20000']).toBe('#ABCDEF');
        expect(parsed).not.toHaveProperty('thresholds');
    });

    it('rejects partial palettes, injected styles, invalid thresholds, versions and oversized imports', () => {
        for (const change of [
            { colors: ['#FFFFFF'] }, { version: 2 }, { stages: { 'ability.time.b': { 0: '#FFFFFF' } } },
            { stages: { 'ability.time.b': { 20000: 'red;display:none' } } }, { stages: JSON.parse('{"__proto__":{"20000":"#FFFFFF"}}') },
        ]) expect(() => parseMedalPalette(JSON.stringify({ ...defaultMedalPalette(), ...change }))).toThrow();
        expect(() => parseMedalPalette(' '.repeat(65537))).toThrow();
        expect(() => parseMedalPalette('{bad json')).toThrow();
    });

    it('reports storage failures without discarding the active preferences or claiming a save', () => {
        const unavailable = { getItem() {
            throw new Error('denied');
        },
        setItem() {
            throw new Error('quota');
        } };
        expect(loadMedalPalette(unavailable).status).toBe('unavailable');
        const config = defaultMedalPalette();
        config.colors[0] = '#123456';
        expect(saveMedalPalette(unavailable, config)).toBe(false);
        expect(config.colors[0]).toBe('#123456');
        expect(loadMedalPalette(undefined).status).toBe('unavailable');
    });

    it('round trips preferences and recovers from corrupt stored content', () => {
        let stored: string | null = null;
        const storage = { getItem: () => stored,
            setItem: (_key: string, value: string) => {
                stored = value;
            } };
        expect(loadMedalPalette(storage).status).toBe('default');
        const config = defaultMedalPalette();
        config.colors[2] = '#345678';
        expect(saveMedalPalette(storage, config)).toBe(true);
        expect(loadMedalPalette(storage)).toEqual({ config, status: 'saved' });
        stored = 'invalid';
        expect(loadMedalPalette(storage)).toEqual({ config: defaultMedalPalette(), status: 'invalid' });
    });
});
