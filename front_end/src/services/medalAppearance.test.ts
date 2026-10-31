import { describe, expect, it } from 'vitest';

import { MEDAL_APPEARANCES, medalAppearance, medalBodyPlacement, medalFixedBadge, medalScoreTier } from './medalAppearance';
import { defaultMedalPalette, medalPaletteColor } from './medalPalette';

describe('shared medal appearance', () => {
    it('covers all 8 single-difficulty families and 3 difficulties with explicit score groups', () => {
        expect(Object.keys(MEDAL_APPEARANCES)).toHaveLength(24);
        for (const [code, appearance] of Object.entries(MEDAL_APPEARANCES)) {
            expect(appearance.groups).toHaveLength(5);
            const thresholds = appearance.groups.flat();
            expect(new Set(thresholds).size).toBe(thresholds.length);
            for (const [index, group] of appearance.groups.entries()) for (const stage of group) expect(medalScoreTier(code, stage)).toBe(index + 1);
            expect(medalScoreTier(code, 0)).toBeUndefined();
            expect(medalScoreTier(code, 123456789)).toBeUndefined();
            expect(medalScoreTier(code, null)).toBeUndefined();
        }
    });
    it('keeps time and increasing metrics in the correct direction and retains the reviewed beginner mapping', () => {
        for (const [code, appearance] of Object.entries(MEDAL_APPEARANCES)) {
            const values = appearance.groups.flat();
            for (let index = 1; index < values.length; index++) expect(code.startsWith('ability.time.') ? values[index] < values[index - 1] : values[index] > values[index - 1]).toBe(true);
        }
        expect(medalScoreTier('ability.time.b', 12000)).toBe(1);
        expect(medalScoreTier('ability.time.b', 10000)).toBe(2);
        expect(medalScoreTier('ability.time.e', 120000)).toBe(2);
        expect(medalScoreTier('ability.thrp.nf.e', 95000)).toBe(4);
    });
    it('uses explicit definitions for stars and never mistakes three-level completion or code suffixes for Expert', () => {
        expect(medalAppearance('b', 'ability.time.b')?.difficulty).toBe('b');
        expect(medalAppearance('m', 'ability.time.b')).toBeUndefined();
        expect(medalAppearance('tn', 'ability.thrp.nf.three')).toBeUndefined();
        expect(medalAppearance('b', 'future.code.e')).toBeUndefined();
        expect(medalScoreTier('__proto__', 1)).toBeUndefined();
    });
    it('uses the same color for a score tier across difficulties and honors exact personal overrides', () => {
        const config = defaultMedalPalette();
        expect(medalPaletteColor(config, medalScoreTier('ability.time.b', 10000), 'ability.time.b', 10000)).toBe(config.colors[1]);
        expect(medalPaletteColor(config, medalScoreTier('ability.time.e', 120000), 'ability.time.e', 120000)).toBe(config.colors[1]);
        config.stages['ability.time.e'] = { 120000: '#123456' };
        expect(medalPaletteColor(config, 2, 'ability.time.e', 120000)).toBe('#123456');
        expect(medalPaletteColor(config, 2, 'ability.time.b', 10000)).toBe(config.colors[1]);
    });
    it('reserves fixed-color NF badges and applies the approved body placements', () => {
        for (const series of ['bn', 'sn', 'mn', 'pn']) expect(medalFixedBadge(series)).toBeDefined();
        for (const series of ['b', 's', 'm', 'pf', 'tn']) expect(medalFixedBadge(series)).toBeUndefined();
        expect(medalBodyPlacement('b')).toEqual({ left: 0, top: 0, size: 100 });
        expect(medalBodyPlacement('m')).toEqual({ left: 13, top: 13, size: 74 });
    });
});
