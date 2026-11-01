import { MedalSeries } from '@/utils/medal_const';

export type MedalDifficulty = 'b' | 'i' | 'e';
export interface MedalAppearance {
    series: string;
    difficulty: MedalDifficulty;
    groups: number[][];
}

// Explicit score groups, from easy to hard. Colors express score groups within each definition.
// These are display decisions, not percentiles or changes to award thresholds.
const time = {
    b: [[20, 15, 12], [10, 8], [6, 5], [4, 3], [2, 1]],
    i: [[150, 100, 80], [60, 50], [40, 30], [25, 20, 15], [12, 10]],
    e: [[300, 200, 150], [120, 100], [90, 80], [70, 60], [50, 40, 30]],
};
const speed = {
    b: [[1, 1.5, 2], [2.5, 3], [4, 5], [6, 8], [10, 12]],
    i: [[1, 1.5], [2, 2.5], [3, 4], [5, 6], [8]],
    e: [[1, 1.5], [2], [2.5, 3], [4, 5], [6]],
};
const speedNF = {
    b: [[1, 1.5, 2], [2.5, 3], [4, 5], [6, 8], [9]],
    i: [[1, 1.5], [2, 2.5], [3, 4], [5, 6], [7]],
    e: [[1], [1.5, 2], [2.5, 3], [4], [5]],
};
const mastery = [[10, 15, 20], [30, 40], [50, 60], [80, 100], [150, 200, 300]];
const precisionNF = [[0.5, 0.7], [0.8], [0.9], [0.95], [1]];
const precisionFL = {
    b: [[0.5, 0.7], [0.8, 1], [1.2, 1.5], [1.8, 2], [2.3, 2.5]],
    i: [[0.5, 0.7], [0.8, 1], [1.2, 1.4], [1.6, 1.8], [1.9]],
    e: [[0.5, 0.7], [0.8, 1], [1.2], [1.4, 1.5], [1.6]],
};

export const MEDAL_APPEARANCES: Record<string, MedalAppearance> = {};
function define(prefix: string, series: string, levels: Record<MedalDifficulty, number[][]>, scale = 1) {
    for (const difficulty of ['b', 'i', 'e'] as const) {
        MEDAL_APPEARANCES[`${prefix}.${difficulty}`] = { series, difficulty, groups: levels[difficulty].map((group) => group.map((stage) => Math.round(stage * scale))) };
    }
}
define('ability.time', MedalSeries.BREAKTHROUGH, time, 1000);
define('ability.time.nf', MedalSeries.FLAGLESS_BREAKTHROUGH, time, 1000);
define('ability.bvs', MedalSeries.SPEED, speed, 10000);
define('ability.bvs.nf', MedalSeries.FLAGLESS_SPEED, speedNF, 10000);
define('ability.stnb', MedalSeries.MASTERY, { b: mastery, i: mastery, e: mastery });
define('ability.stnb.nf', MedalSeries.FLAGLESS_MASTERY, { b: mastery, i: mastery, e: mastery });
define('ability.thrp.nf', MedalSeries.FLAGLESS_PRECISION, { b: precisionNF, i: precisionNF, e: precisionNF }, 100000);
define('ability.thrp.fl', MedalSeries.FLAGGED_PRECISION, precisionFL, 100000);

export function medalScoreTier(code: string, stage: number | null): number | undefined {
    if (stage === null || !Object.hasOwn(MEDAL_APPEARANCES, code)) return undefined;
    const index = MEDAL_APPEARANCES[code].groups.findIndex((group) => group.includes(stage));
    return index < 0 ? undefined : index + 1;
}

export function medalAppearance(series: string, code: string): MedalAppearance | undefined {
    const appearance = Object.hasOwn(MEDAL_APPEARANCES, code) ? MEDAL_APPEARANCES[code] : undefined;
    return appearance?.series === series ? appearance : undefined;
}

export function medalBodyPlacement(series: string): { left: number; top: number; size: number } {
    if (series === MedalSeries.MASTERY || series === MedalSeries.FLAGLESS_MASTERY) return { left: 13, top: 13, size: 74 };
    if (series === MedalSeries.FLAGLESS_PRECISION || series === MedalSeries.FLAGGED_PRECISION) return { left: 10, top: 10, size: 80 };
    return { left: 0, top: 0, size: 100 };
}

/** Hand-registered fixed-color NF badge regions in the original 320px template canvas. */
export function medalFixedBadge(series: string): { cx: number; cy: number; r: number } | undefined {
    if (series === MedalSeries.FLAGLESS_BREAKTHROUGH) return { cx: 237, cy: 230, r: 54 };
    if (series === MedalSeries.FLAGLESS_SPEED) return { cx: 243, cy: 232, r: 54 };
    if (series === MedalSeries.FLAGLESS_MASTERY) return { cx: 243, cy: 236, r: 55 };
    if (series === MedalSeries.FLAGLESS_PRECISION) return { cx: 242, cy: 237, r: 56 };
    return undefined;
}
