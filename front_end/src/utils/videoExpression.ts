import { Parser } from 'expr-eval';
import type { Expression, Values } from 'expr-eval';

import type { VideoAbstract, VideoAbstractData } from './videoabstract';

export const videoExpressionFields = ['id', 'upload_time', 'end_time', 'level', 'mode', 'timems', 'bv', 'state', 'software', 'cl', 'ce', 'right_ce', 'path', 'pluck', 'player_id', 'file_size', 'ongoing_tournament'] as const satisfies readonly (keyof VideoAbstract & keyof VideoAbstractData)[];

const parser = new Parser({ allowMemberAccess: false, operators: { assignment: false, fndef: false } });
const fields = new Set<string>(videoExpressionFields);

class MissingVideoField extends Error {}

export interface CompiledVideoExpression {
    expression?: Expression;
    error: string;
}

export interface VideoExpressionResult {
    value: unknown;
    missing: boolean;
    error: string;
}

export function compileVideoExpression(expr: string): CompiledVideoExpression {
    try {
        const expression = parser.parse(expr);
        const unknown = expression.variables().filter((field) => !fields.has(field));
        if (unknown.length > 0) throw new Error(`Unknown field: ${unknown.join(', ')}`);
        return { expression, error: '' };
    } catch (error) {
        return { error: error instanceof Error ? error.message : String(error) };
    }
}

/** source is provided for partial tooltip records so constructor defaults cannot invent data. */
export function createVideoExpressionContext(video: VideoAbstract, source?: Partial<VideoAbstractData>): Values {
    const values = Object.create(null) as Values;
    function available(field: keyof VideoAbstractData): boolean {
        const value: unknown = source === undefined
            ? Reflect.get(video, field)
            : field === 'upload_time' ? source.upload_time ?? source.time : field === 'player_id' ? source.player_id ?? source.player : source[field];
        return value !== undefined && value !== null && !(typeof value === 'number' && Number.isNaN(value));
    }
    for (const field of videoExpressionFields) {
        Object.defineProperty(values, field, { enumerable: true,
            get: () => {
                if (!available(field)) throw new MissingVideoField(field);
                if (field === 'level') return typeof video.level === 'string' ? video.level : video.level.code;
                if (field === 'upload_time' || field === 'end_time') return video[field]?.getTime() ?? NaN;
                return video[field];
            } });
    }
    return values;
}

export function evaluateVideoExpression(compiled: CompiledVideoExpression, context: Values): VideoExpressionResult {
    if (compiled.expression === undefined) return { value: NaN, missing: false, error: compiled.error };
    try {
        const value: unknown = compiled.expression.evaluate(context);
        return { value, missing: value === null || value === undefined, error: '' };
    } catch (error) {
        return { value: NaN, missing: error instanceof MissingVideoField, error: error instanceof Error ? error.message : String(error) };
    }
}
