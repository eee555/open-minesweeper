import { describe, expect, it } from 'vitest';

import { createSubReporter } from './analysisProgress';

describe('analysis progress sub-reporter', () => {
    it('maps local progress into the assigned range', async () => {
        const values: [number, number][] = [];
        const reporter = createSubReporter((done, total) => {
            values.push([done, total]);
            return Promise.resolve();
        }, 0.25, 0.5);
        await reporter(0, 10);
        await reporter(5, 10);
        await reporter(10, 10);
        expect(values).toEqual([[0.25, 1], [0.5, 1], [0.75, 1]]);
    });
});
