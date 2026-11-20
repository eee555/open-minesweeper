import { isFixedColumnType, videoFieldLabel } from './columns';
import type { ExpressionColumnType, VideoColumn, VideoColumnScope, VideoDescriptionItem } from './columns';

import { MS_State } from '@/utils/ms_const';
import { STNB_COEFFICIENTS } from '@/utils/stnb';
import { VideoAbstract } from '@/utils/videoabstract';
import { videoExpressionFields } from '@/utils/videoExpression';

interface ExpressionPreset { type: ExpressionColumnType; expr?: string }

export const defaultExpressionPreset = { type: 'data.3f', expr: 'timems / 1000' } satisfies ExpressionPreset;

const expressionPresets: Record<string, ExpressionPreset> = {
    isLocal: { type: 'bool', expr: `state == '${MS_State.Local}'` },
    rowKey: { type: 'data', expr: `state == '${MS_State.Local}' ? 'local:' || floor(end_time / 1000) || ':' || timems : 'server:' || id` },
    isNF: { type: 'bool', expr: 'right_ce == 0' },
    time: defaultExpressionPreset,
    bvs: { type: 'data.3f', expr: 'bv / (timems / 1000)' },
    qg: { type: 'data.3f', expr: '(timems / 1000) ^ 1.7 / bv' },
    rqp: { type: 'data.3f', expr: '(timems / 1000) * (timems / 1000 - 1) / bv' },
    stnb: { type: 'data.1f', expr: `(level == 'b' ? ${STNB_COEFFICIENTS.b} : level == 'i' ? ${STNB_COEFFICIENTS.i} : level == 'e' ? ${STNB_COEFFICIENTS.e} : 0 / 0) / ((timems / 1000) ^ 1.7 / bv)` },
    ioe: { type: 'data.3f', expr: 'bv / cl' },
    thrp: { type: 'data.3f', expr: 'bv / ce' },
    corr: { type: 'data.3f', expr: 'ce / cl' },
    cls: { type: 'data.3f', expr: 'cl / (timems / 1000)' },
    ces: { type: 'data.3f', expr: 'ce / (timems / 1000)' },
    npath: { type: 'data.1f', expr: 'path / 16' },
    mov: { type: 'data.3f', expr: '(path / 16) / (timems / 1000)' },
    iome: { type: 'data.3f', expr: 'bv / (path / 16)' },
    upload_time: { type: 'date' },
    end_time: { type: 'date' },
    id: { type: 'data' },
    timems: { type: 'data' },
    bv: { type: 'data' },
    cl: { type: 'data' },
    ce: { type: 'data' },
    file_size: { type: 'bytes' },
    path: { type: 'data.0f' },
};

export const videoColumnPresets = [...new Set([...videoExpressionFields, ...Object.keys(expressionPresets)])].filter((field) => field !== 'timems');

export function presetColumn(field: string): VideoColumn {
    if (isFixedColumnType(field)) return { type: field };
    const preset: ExpressionPreset = Object.hasOwn(expressionPresets, field) ? expressionPresets[field] : { type: 'data.3f' };
    return { type: preset.type, key: videoFieldLabel(field), expr: preset.expr ?? field };
}

const defaultFields: Record<VideoColumnScope, readonly string[]> = {
    'fixed-player': ['state', 'upload_time', 'software', 'level', 'mode', 'time', 'bv', 'bvs', 'ioe', 'thrp', 'path', 'file_size'],
    'mixed-players': ['state', 'upload_time', 'player', 'software', 'mode', 'level', 'time', 'bv', 'bvs', 'ioe', 'thrp'],
};

export function defaultVideoColumns(scope: VideoColumnScope): VideoColumn[] {
    return defaultFields[scope].map(presetColumn);
}

export function defaultVideoDescription(): VideoDescriptionItem[] {
    return ['upload_time', 'end_time', 'time', 'bv', 'stnb', 'bvs', 'cls', 'ces', 'ioe', 'thrp', 'corr'].map((field) => ({ ...presetColumn(field), width: field === 'upload_time' || field === 'end_time' ? 3 : 1 }));
}

export const videoColumnPreview = new VideoAbstract({
    id: 0,
    player_id: 0,
    state: MS_State.Official,
    software: 'a',
    level: 'e',
    mode: '00',
    upload_time: '2026-10-23T08:00:00Z',
    end_time: '2026-10-22T12:34:56Z',
    timems: 40000,
    bv: 100,
    cl: 130,
    ce: 110,
    right_ce: 0,
    path: 51234.5,
    pluck: 0.025,
    file_size: 32768,
    ongoing_tournament: false,
});
