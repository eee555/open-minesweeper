import { describe, expect, it } from 'vitest';

import { VideoAbstract } from './videoabstract';
import type { VideoAbstractData } from './videoabstract';

function makeVideo(overrides: Partial<VideoAbstractData> = {}) {
    return new VideoAbstract({
        level: 'e',
        mode: '00',
        timems: 10000,
        bv: 100,
        software: 'e',
        ...overrides,
    });
}

describe('VideoAbstract', () => {
    it('preserves right_ce from Redis records independently of mode', () => {
        const video = VideoAbstract.fromVideoRedisInfo(1, {
            state: 'c',
            software: 'e',
            time: '2026-01-01T00:00:00Z',
            player_id: 1,
            level: 'b',
            mode: '05',
            timems: 1000,
            bv: 10,
            identifier: '',
            right_ce: 0,
        });
        expect(video.right_ce).toBe(0);
        expect(video.mode).toBe('05');
    });

    it('Normalizes missing optional stats to NaN', () => {
        const video = makeVideo({
            cl: null,
            ce: undefined,
            path: null,
            pluck: undefined,
        });

        expect(isNaN(video.cl)).toBe(true);
        expect(isNaN(video.ce)).toBe(true);
        expect(isNaN(video.path)).toBe(true);
        expect(isNaN(video.pluck)).toBe(true);
        expect(isNaN(video.ioe)).toBe(true);
        expect(isNaN(video.corr)).toBe(true);
        expect(video.displayStat('ioe')).toBe('NaN');
        expect(video.displayStat('path')).toBe('NaN');
    });

    it('Computes optional stats directly when source values are present', () => {
        const video = makeVideo({
            cl: 200,
            ce: 50,
            path: 32,
            pluck: 1.25,
        });

        expect(video.ioe).toBe(0.5);
        expect(video.thrp).toBe(2);
        expect(video.corr).toBe(0.25);
        expect(video.cls).toBe(20);
        expect(video.ces).toBe(5);
        expect(video.npath).toBe(2);
        expect(video.mov).toBe(0.2);
        expect(video.iome).toBe(50);
        expect(video.displayStat('iome')).toBe('50.000');
    });
});
