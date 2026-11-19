import { readFileSync } from 'node:fs';

import { Parser } from 'expr-eval';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { createEvaluationContext } from './counter';

import { load_video_file } from '@/utils/fileIO';

function loadReplay() {
    const bytes = Uint8Array.from(readFileSync(new URL('../../../cypress/fixtures/52200.evf', import.meta.url))).buffer;
    return load_video_file(bytes, '52200.evf');
}

afterEach(() => vi.restoreAllMocks());

describe('player counter metrics', () => {
    it('reads new metrics from the current playback position and analyses probabilities once per replay', () => {
        const video = loadReplay();
        try {
            video.current_time = 1;
            const position = video.current_event_id;
            const analyse = vi.spyOn(video, 'analyse_for_features');
            const context = createEvaluationContext(video);
            const parser = new Parser();
            expect(parser.evaluate('bbbv_solved_left + bbbv_solved_chord', context)).toBe(video.bbbv_solved);
            expect(parser.evaluate('c_path / 16 + e_path / 16', context)).toBe((video.c_path + video.e_path) / 16);
            expect(analyse).not.toHaveBeenCalled();

            expect(parser.evaluate('luck', context)).toBeCloseTo(10 ** -video.pluck, 12);
            expect(video.current_event_id).toBe(position);
            video.current_time = Infinity;
            const nextContext = createEvaluationContext(video);
            expect(parser.evaluate('bbbv_solved_left + bbbv_solved_chord', nextContext)).toBe(52);
            expect(parser.evaluate('c_path', nextContext)).toBeCloseTo(1618.9947645820548, 8);
            expect(parser.evaluate('e_path', nextContext)).toBeCloseTo(1651.1081618566245, 8);
            expect(parser.evaluate('luck', nextContext)).toBeCloseTo(0.8296620984297842, 12);
            expect(parser.evaluate('expected_bbbv_solved_per_attempt', nextContext)).toBeCloseTo(43.31276701991905, 10);
            expect(parser.evaluate('expected_bbbv_solved_per_win', nextContext)).toBeCloseTo(52.205309971243224, 10);
            expect(parser.evaluate('expected_time_per_attempt', nextContext)).toBeCloseTo(8.926418243355666, 10);
            expect(parser.evaluate('expected_time_per_win', nextContext)).toBeCloseTo(10.759100916204106, 10);
            expect(parser.evaluate('pluck', nextContext)).toBeCloseTo(0.08109874939134086, 12);
            expect(analyse).toHaveBeenCalledExactlyOnceWith(['pluck']);
        } finally {
            video.free();
        }
    });

    it('keeps probability analysis lazy and preserves nonfinite values', () => {
        const video = loadReplay();
        try {
            const analyse = vi.spyOn(video, 'analyse_for_features');
            const context = createEvaluationContext(video);
            const parser = new Parser();
            expect(parser.evaluate('1 ? left : luck', context)).toBe(video.left);
            expect(analyse).not.toHaveBeenCalled();
            parser.evaluate('expected_time_per_win', context);
            expect(analyse).toHaveBeenCalledExactlyOnceWith(['pluck']);
            vi.spyOn(video, 'expected_time_per_win', 'get').mockReturnValue(Infinity);
            vi.spyOn(video, 'luck', 'get').mockReturnValue(NaN);
            expect(parser.evaluate('expected_time_per_win', context)).toBe(Infinity);
            expect(parser.evaluate('luck', context)).toBeNaN();
        } finally {
            video.free();
        }
    });
});
