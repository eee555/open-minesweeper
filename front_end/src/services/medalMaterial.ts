/** Approved on 2026-11-01. Shared default material; viewer colors are supplied separately. */
export const DEFAULT_MEDAL_MATERIAL = 'soft-metal-v1';
export const MEDAL_TONE_SAMPLES = 256;

// Source brightness, selected-color multiplier, white blend.
export const SOFT_METAL_KNOTS = [
    [0, 0, 0], [0.08, 0.16, 0], [0.2, 0.4, 0], [0.4, 0.67, 0],
    [0.6, 0.9, 0], [0.72, 1, 0], [0.82, 1, 0.1], [0.9, 1, 0.22],
    [0.96, 1, 0.36], [0.985, 1, 0.54], [1, 1, 0.78],
] as const;

export function softMetalToneTable(channel: number): number[] {
    return Array.from({ length: MEDAL_TONE_SAMPLES }, (_, index) => {
        const brightness = index / (MEDAL_TONE_SAMPLES - 1);
        const upper = Math.max(1, SOFT_METAL_KNOTS.findIndex(([position]) => position >= brightness));
        const start = SOFT_METAL_KNOTS[upper - 1];
        const end = SOFT_METAL_KNOTS[upper];
        const amount = (brightness - start[0]) / (end[0] - start[0]);
        const shade = start[1] + (end[1] - start[1]) * amount;
        const white = start[2] + (end[2] - start[2]) * amount;
        return channel * shade * (1 - white) + white;
    });
}
