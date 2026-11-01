export type Finish = 'body' | 'previous';

// Source brightness, fraction of the selected color, fraction of white.
// Broad faces stay near the selected color; only the very brightest source areas gain strong highlights.
const knots = [
    [0, 0, 0], [0.08, 0.16, 0], [0.2, 0.4, 0], [0.4, 0.67, 0],
    [0.6, 0.88, 0], [0.75, 1, 0], [0.9, 1, 0.02], [0.96, 1, 0.05],
    [0.98, 1, 0.18], [0.99, 1, 0.4], [1, 1, 0.75],
] as const;

export function toneTable(channel: number, finish: Finish = 'body'): number[] {
    if (finish === 'previous') return [0, channel * 0.28, channel * 0.62, channel, channel + (1 - channel) * 0.45, 1];
    return Array.from({ length: 256 }, (_, index) => {
        const brightness = index / 255;
        const upper = Math.max(1, knots.findIndex(([position]) => position >= brightness));
        const start = knots[upper - 1];
        const end = knots[upper];
        const amount = (brightness - start[0]) / (end[0] - start[0]);
        const shade = start[1] + (end[1] - start[1]) * amount;
        const white = start[2] + (end[2] - start[2]) * amount;
        const value = channel * shade;
        return value * (1 - white) + white;
    });
}

export function sampleTable(table: readonly number[], brightness: number): number {
    const position = Math.max(0, Math.min(1, brightness)) * (table.length - 1);
    const left = Math.floor(position);
    const right = Math.min(left + 1, table.length - 1);
    return table[left] + (table[right] - table[left]) * (position - left);
}
