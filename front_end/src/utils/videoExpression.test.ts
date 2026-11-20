import { describe, expect, it } from 'vitest';

import { VideoAbstract } from './videoabstract';
import { compileVideoExpression, createVideoExpressionContext, evaluateVideoExpression, videoExpressionFields } from './videoExpression';

const makeVideo = (level = 'e') => new VideoAbstract({ id: 7, level, mode: '00', timems: 40000, bv: 100, software: 'a', right_ce: 0, upload_time: new Date('2026-01-01T00:00:00Z') });

describe('video summary expressions', () => {
    it('covers instance fields without exposing getters or methods', () => {
        const video = makeVideo();
        const names = Object.keys(video);
        expect([...videoExpressionFields].sort()).toEqual(names.sort());
        expect(compileVideoExpression('displayStat(timems)').expression).toBeUndefined();
        for (const field of Object.getOwnPropertyNames(VideoAbstract.prototype).filter((name) => name !== 'constructor')) {
            expect(compileVideoExpression(field).expression).toBeUndefined();
            expect(Object.hasOwn(createVideoExpressionContext(video), field)).toBe(false);
        }
    });

    it('reads basic fields lazily and sees changes to the same video', () => {
        const video = makeVideo();
        const context = createVideoExpressionContext(video);
        const expression = compileVideoExpression('bv / (timems / 1000)');
        expect(evaluateVideoExpression(expression, context).value).toBe(2.5);
        video.timems = 20000;
        expect(evaluateVideoExpression(expression, context).value).toBe(5);
        Object.defineProperty(video, 'pluck', { get: () => {
            throw new Error('unavailable');
        } });
        expect(evaluateVideoExpression(expression, context).value).toBe(5);
        expect(evaluateVideoExpression(compileVideoExpression('pluck'), context).value).toBeNaN();
    });

    it('uses code strings for custom levels and supports booleans and lazy conditionals', () => {
        const context = createVideoExpressionContext(makeVideo('c16_30_150'));
        expect(evaluateVideoExpression(compileVideoExpression('level'), context).value).toBe('c16_30_150');
        expect(evaluateVideoExpression(compileVideoExpression('level == \'c16_30_150\' and right_ce == 0'), context).value).toBe(true);
        expect(compileVideoExpression('level.row').expression).toBeUndefined();
        expect(evaluateVideoExpression(compileVideoExpression('upload_time'), context).value).toBe(Date.parse('2026-01-01T00:00:00Z'));
    });

    it.each(['bv +', 'unknown', 'bv = 1', 'f(x) = x', 'level.constructor'])('returns NaN for invalid expression %s', (expr) => {
        expect(evaluateVideoExpression(compileVideoExpression(expr), createVideoExpressionContext(makeVideo())).value).toBeNaN();
    });

    it('does not invent metadata or zero-valued inputs for partial tooltip records', () => {
        const source = { timems: 0, bv: 0 };
        const video = makeVideo();
        video.timems = 0;
        video.bv = 0;
        const context = createVideoExpressionContext(video, source);
        expect(evaluateVideoExpression(compileVideoExpression('bv'), context)).toMatchObject({ value: 0, missing: false });
        expect(evaluateVideoExpression(compileVideoExpression('upload_time'), context).missing).toBe(true);
        expect(evaluateVideoExpression(compileVideoExpression('right_ce == 0'), context).missing).toBe(true);
        expect(evaluateVideoExpression(compileVideoExpression('bv == 0 ? bv : right_ce == 0'), context).value).toBe(0);
    });
});
