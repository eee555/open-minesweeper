import { describe, expect, it } from 'vitest';

import { defaultVideoSortField, isVideoColumns, videoColumnLabel } from './columns';
import { defaultVideoColumns, defaultVideoDescription, presetColumn, videoColumnPresets } from './presets';

import i18n from '@/i18n';
import { VideoAbstract } from '@/utils/videoabstract';
import { compileVideoExpression, createVideoExpressionContext, evaluateVideoExpression } from '@/utils/videoExpression';

describe('video column presets and defaults', () => {
    it('builds valid independent defaults and keeps every preset expression compilable', () => {
        for (const scope of ['fixed-player', 'mixed-players'] as const) {
            const columns = defaultVideoColumns(scope);
            expect(isVideoColumns(columns)).toBe(true);
            expect(columns.some((column) => column.type === 'player')).toBe(scope === 'mixed-players');
            const snapshot = [...columns];
            columns.pop();
            expect(defaultVideoColumns(scope)).toEqual(snapshot);
        }
        expect(isVideoColumns(defaultVideoDescription(), true)).toBe(true);
        expect(videoColumnPresets).not.toContain('timems');
        expect(presetColumn('file_size')).toMatchObject({ type: 'bytes', expr: 'file_size' });
        for (const field of videoColumnPresets) {
            const column = presetColumn(field);
            if ('expr' in column) expect(compileVideoExpression(column.expr).error, field).toBe('');
        }
    });

    it.each(['b', 'i', 'e', 'c16_30_150'])('keeps numeric presets consistent with business metrics for %s', (level) => {
        const video = new VideoAbstract({ id: 7, level, mode: '00', software: 'a', timems: 40000, bv: 100, cl: 130, ce: 110, right_ce: 0, path: 12345, pluck: 0.025 });
        const context = createVideoExpressionContext(video);
        for (const field of ['time', 'bvs', 'qg', 'rqp', 'stnb', 'ioe', 'thrp', 'corr', 'cls', 'ces', 'npath', 'mov', 'iome'] as const) {
            const column = presetColumn(field);
            if (!('expr' in column)) throw new Error('Expected an expression preset');
            const evaluated = evaluateVideoExpression(compileVideoExpression(column.expr), context);
            expect(evaluated.error, field).toBe('');
            if (Number.isFinite(video[field])) expect(evaluated.value).toBeCloseTo(video[field], 10);
            else expect(evaluated.value).toBe(video[field]);
        }
    });

    it('evaluates local identity and NF directly from basic fields', () => {
        const video = VideoAbstract.fromArbiterCsv({ level: 'e', mode: '00', software: 'a', timems: 40000, bv: 100, right_ce: 0, end_time: new Date('2026-01-01T00:00:00Z') });
        const context = createVideoExpressionContext(video);
        for (const [field, expected] of [['rowKey', video.rowKey], ['isLocal', true], ['isNF', true]] as const) {
            const column = presetColumn(field);
            if (!('expr' in column)) throw new Error('Expected an expression preset');
            expect(evaluateVideoExpression(compileVideoExpression(column.expr), context).value).toBe(expected);
            expect(compileVideoExpression(field).expression).toBeUndefined();
        }
    });

    it('assigns names in the active language while preserving literal saved names and default sorting', () => {
        const originalLocale = i18n.global.locale.value;
        try {
            i18n.global.locale.value = 'zh-cn';
            const column = presetColumn('upload_time');
            expect(column).toEqual({ type: 'date', key: '上传时间', expr: 'upload_time' });
            expect(defaultVideoSortField([column])).toBe('date:上传时间');
            expect(videoColumnLabel({ type: 'data', key: 'time', expr: 'bv' })).toBe('time');
            i18n.global.locale.value = 'en';
            expect(videoColumnLabel(column)).toBe('上传时间');
            expect(defaultVideoSortField([column])).toBe('date:上传时间');
            expect(presetColumn('upload_time')).toMatchObject({ key: 'Upload Time' });
            expect(presetColumn('bv')).toMatchObject({ key: 'Bv', expr: 'bv' });
        } finally {
            i18n.global.locale.value = originalLocale;
        }
    });
});
