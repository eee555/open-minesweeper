import { describe, expect, it } from 'vitest';

import { columnKey, evaluateVideoColumn, formatVideoColumnResult, isVideoColumns, prepareVideoColumn } from './columns';
import type { VideoColumn } from './columns';
import { sortVideos } from './videoListData';

import { VideoAbstract } from '@/utils/videoabstract';
import { createVideoExpressionContext } from '@/utils/videoExpression';

function result(column: VideoColumn, value: unknown, description = false) {
    return formatVideoColumnResult(column, { value, error: '', missing: value === undefined }, description);
}

describe('configurable video columns', () => {
    it('formats bytes in both displays and keeps the raw numeric sort value', () => {
        const column: VideoColumn = { id: 'size', type: 'bytes', key: 'Size', expr: 'file_size' };
        expect(isVideoColumns([column])).toBe(true);
        expect(isVideoColumns([{ ...column, width: 1 }], true)).toBe(true);
        for (const description of [false, true]) {
            expect(result(column, 0, description)).toMatchObject({ text: '0 B', sortValue: 0 });
            expect(result(column, 1536, description)).toMatchObject({ text: '1.50 KB', sortValue: 1536 });
            expect(result(column, 1048576, description)).toMatchObject({ text: '1.00 MB', sortValue: 1048576 });
            for (const value of [-1, NaN, Infinity, '1024', false]) expect(result(column, value, description).text).toBe('NaN');
        }
        const videos = [2048, 900].map((file_size, id) => new VideoAbstract({ id, file_size, level: 'e', mode: '00', software: 'a', timems: 1000, bv: 1 }));
        const prepared = prepareVideoColumn(column);
        expect(sortVideos(videos, 1, (video) => evaluateVideoColumn(prepared, createVideoExpressionContext(video)).sortValue).map((video) => video.file_size)).toEqual([900, 2048]);
    });

    it('validates columns, precision, unique keys and description widths', () => {
        expect(isVideoColumns([])).toBe(true);
        for (const type of ['upload_time', 'data.-1f', 'data.2.5f', 'data.101f', 'data.2e', 'bool.3f']) {
            expect(isVideoColumns([{ id: 'value', type, key: 'value', expr: 'bv' }])).toBe(false);
        }
        expect(isVideoColumns([{ id: 'bv', type: 'data', key: 'value', expr: 'bv' }, { id: 'nf', type: 'bool', key: 'value', expr: 'right_ce == 0' }])).toBe(false);
        expect(isVideoColumns([{ type: 'state' }, { type: 'state' }])).toBe(false);
        for (const width of [undefined, '2', 0, 4, 1.5]) expect(isVideoColumns([{ id: 'x', type: 'data', key: 'x', expr: 'bv', width }], true)).toBe(false);
        const column = { id: 'stable', type: 'data', key: 'First', expr: 'bv' };
        for (const id of [undefined, null, '', ' ', 1]) expect(isVideoColumns([{ ...column, id }])).toBe(false);
        expect(isVideoColumns([column, { ...column, type: 'bool', key: 'Second' }])).toBe(false);
        expect(isVideoColumns([column, { ...column, id: 'another', key: 'Second' }])).toBe(true);
    });

    it('formats numbers without changing their sort values or identity', () => {
        const column: VideoColumn = { id: 'speed', type: 'data.3f', key: 'speed', expr: 'bv / (timems / 1000)' };
        expect(result(column, 12.3)).toMatchObject({ text: '12.300', sortValue: 12.3 });
        expect(result({ ...column, type: 'data.0f' }, 12.7).text).toBe('13');
        expect(columnKey(column)).toBe(columnKey({ ...column, type: 'data.1f' }));
        expect(columnKey(column)).toBe(columnKey({ ...column, key: '速度' }));
        expect(columnKey(column)).toBe(columnKey({ ...column, expr: 'bv' }));
        expect(columnKey(column)).not.toBe(columnKey({ ...column, id: 'other' }));
        expect(result(column, '12.3').text).toBe('NaN');
        expect(result(column, Infinity).text).toBe('Infinity');
        expect(result(column, NaN).text).toBe('NaN');
    });

    it('keeps dates and booleans typed and preserves zero/false', () => {
        const date: VideoColumn = { id: 'when', type: 'date', key: 'when', expr: 'end_time' };
        expect(result(date, 0).sortValue).toBe(0);
        expect(result(date, '2026-01-01T00:00:00Z').sortValue).toBe(Date.parse('2026-01-01T00:00:00Z'));
        for (const value of [null, undefined, 'invalid', NaN, true]) expect(result(date, value).text).toBe('NaN');
        const bool: VideoColumn = { id: 'nf', type: 'bool', key: 'NF', expr: 'right_ce == 0' };
        expect(result(bool, false)).toMatchObject({ bool: false });
        expect(result(bool, true)).toMatchObject({ bool: true });
        for (const value of [0, 1, 'false', NaN]) expect(result(bool, value).bool).toBeUndefined();
    });

    it('allows general tooltip data while formatted data still requires a number', () => {
        const column: VideoColumn = { id: 'value', type: 'data', key: 'value', expr: 'level' };
        expect(result(column, false, true).text).toBe('false');
        expect(result(column, [1, 2], true).text).toContain('2');
        expect(result(column, { value: 3 }, true).text).toContain('"value"');
        expect(result(column, 'e', true).text).toBe('e');
        expect(result(column, 'e').text).toBe('NaN');
        expect(result({ ...column, type: 'data.3f' }, 'e', true).text).toBe('NaN');
    });

    it('sorts evaluated expressions rather than their labels or rounded display values', () => {
        const videos = [1, 2, 3].map((id) => new VideoAbstract({ id, software: 'a', mode: '00', level: 'e', bv: id === 3 ? NaN : id, timems: 1000 }));
        const prepared = prepareVideoColumn({ id: 'inverse', type: 'data.0f', key: 'bv', expr: '-bv / 100' });
        const value = (video: VideoAbstract) => evaluateVideoColumn(prepared, createVideoExpressionContext(video)).sortValue;
        expect(sortVideos(videos, 1, value).map((video) => video.id)).toEqual([2, 1, 3]);
        expect(sortVideos(videos, -1, value).map((video) => video.id)).toEqual([1, 2, 3]);
    });
});
