import type { BoardRenderInput } from '@putianyi888/vue3-minesweeper-board';

import type { BoardExportState } from './boardExportFrame';
import type { ReplayMouseTraceEvent } from './mouseTrace';
import { readReplayCursor } from './replayCursor';
import { mouseTraceRange } from './replayMouseTrace';
import type { ReplayVideo } from './replayParser';

import { PiecewiseColorScheme } from '@/utils/colors';
import type { PiecewiseColorSchemeInterface } from '@/utils/colors';
import { replayPressedBackground } from '@/utils/replayBoardPress';

export interface ExportBoardSettings {
    size: number;
    globalVisible: boolean;
    probabilityVisible: boolean;
    traceVisible: boolean;
    globalOpacity: number;
    probabilityOpacity: number;
    traceOpacity: number;
    traceTailSeconds: number;
    trace: Omit<Exclude<NonNullable<NonNullable<BoardRenderInput['layers']>['mouseTrace']>, boolean | undefined>, 'events'>;
    probabilityColors: PiecewiseColorSchemeInterface;
    cursor: { size: number; anchor: { x: number; y: number } } | null;
}

export type ExportReplayState = Omit<BoardExportState, 'cursor'> & { cursor: { x: number; y: number; size: number } | null };

export function createExportStateReader(replay: ReplayVideo, settings: ExportBoardSettings, events: ReplayMouseTraceEvent[]): (ms: number) => ExportReplayState {
    const scheme = PiecewiseColorScheme.createFromTheme(settings.probabilityColors);
    const globalBoard = settings.globalVisible ? replay.board as number[][] : null;
    return (ms: number) => {
        replay.current_time = ms >= replay.rtime_ms ? Infinity : ms / 1000;
        const position = readReplayCursor(replay);
        const board = replay.game_board as number[][];
        const background = replayPressedBackground(board, replay.mouse_state, position);
        return {
            input: { board,
                size: settings.size,
                layers: {
                    ...background === undefined ? {} : { background: { board: background } },
                    probability: settings.probabilityVisible ? { board: replay.game_board_poss as number[][], color: (value: number) => scheme.getColor(value * 100) } : false,
                    mouseTrace: settings.traceVisible ? { ...settings.trace, events, ...mouseTraceRange(events, ms, settings.traceTailSeconds, replay.current_event_id) } : false,
                } } satisfies BoardRenderInput,
            globalBoard,
            globalOpacity: settings.globalOpacity,
            probabilityOpacity: settings.probabilityOpacity,
            traceOpacity: settings.traceOpacity,
            cursor: position !== null && settings.cursor !== null
                ? {
                    x: position.columnIndex * settings.size - settings.cursor.size * settings.cursor.anchor.x,
                    y: position.rowIndex * settings.size - settings.cursor.size * settings.cursor.anchor.y,
                    size: settings.cursor.size,
                }
                : null,
        };
    };
}
