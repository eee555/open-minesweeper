import { bin, bisectRight, range } from 'd3-array';
import type { Bin } from 'd3-array';

import type { TrainingReplay } from './replay';

export interface SpeedSample {
    timeMs: number;
    mouseSpeed: number;
    clickSpeed: number;
}

/** A trailing one-second window, including zero activity before timing starts. */
export function replaySpeeds(replay: TrainingReplay): SpeedSample[] {
    const { durationMs } = replay;
    const events = replay.events.filter((event) => event.positionKnown);
    const times = events.map((event) => event.timeMs);
    const clicks = events.filter((event) => event.trigger === 'left').map((event) => event.timeMs);
    const distances = [0];
    for (let index = 1; index < events.length; index++) {
        const previous = events[index - 1];
        const event = events[index];
        distances.push(distances[index - 1] + Math.hypot(event.row - previous.row, event.column - previous.column));
    }
    function distanceAt(ms: number): number {
        const index = bisectRight(times, ms) - 1;
        if (index < 0) return 0;
        const next = events[index + 1];
        if (next === undefined || next.timeMs === times[index]) return distances[index];
        const fraction = (ms - times[index]) / (next.timeMs - times[index]);
        return distances[index] + fraction * (distances[index + 1] - distances[index]);
    }
    const sampleTimes = new Set([0, durationMs, ...replay.chords.map((chord) => chord.chordMs)]);
    for (let time = 50; time < durationMs; time += 50) sampleTimes.add(time);
    return [...sampleTimes].sort((a, b) => a - b).map((timeMs) => ({
        timeMs,
        mouseSpeed: distanceAt(timeMs) - distanceAt(timeMs - 1000),
        clickSpeed: bisectRight(clicks, timeMs) - bisectRight(clicks, timeMs - 1000),
    }));
}

export function leftClickDurations(replay: TrainingReplay): number[] {
    const durations: number[] = [];
    let down: number | null = null;
    for (const event of replay.events) {
        if (event.cancelled) down = null;
        else if (event.action === 'lc') down = event.timeMs;
        else if (event.action === 'lr') {
            // The first release starts this game and has no timed press to pair with.
            if (event.trigger === 'left' && down !== null) durations.push(event.timeMs - down);
            down = null;
        }
    }
    return durations;
}

export function clickDurationBins(replay: TrainingReplay): Bin<number, number>[] {
    const durations = leftClickDurations(replay);
    const maximum = durations.reduce((largest, duration) => Math.max(largest, duration), 0);
    const step = 10; // Milliseconds: every bin is exactly 0.01 seconds wide.
    const upper = (Math.floor(maximum / step) + 1) * step;
    return bin().domain([0, upper]).thresholds(range(step, upper, step))(durations);
}
