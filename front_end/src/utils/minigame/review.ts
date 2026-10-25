import { flagChordModes } from './flagChordTraining';
import type { TrainingGame } from './games';
import { leftClickModes, multiTouchModes } from './leftClickTraining';
import { missingCellModes } from './missingCellTraining';
import type { MissingCellMode, MissingCellRoundResult } from './missingCellTraining';
import { decodeMissingCellRounds } from './recording';
import { rebuildTrainingReplay } from './replay';
import type { AnyTrainingReplay } from './replay';
import { rebuildTouchReplay } from './touchReplay';

export interface MissingCellReplay {
    game: 'missing-cell';
    mode: MissingCellMode;
    rounds: MissingCellRoundResult[];
    durationMs: number;
}

export type MinigameReplay = AnyTrainingReplay | MissingCellReplay;

/** Reuse the local replay decoders; mode and score come from the selected ranking. */
export function rebuildMinigameReplay(game: TrainingGame, rankingKey: string, source: unknown, scoreMs: number): MinigameReplay {
    if (game === 'left-click' || game === 'multi-touch') {
        const mode = (game === 'left-click' ? leftClickModes : multiTouchModes).find((item) => item.rankingKey === rankingKey);
        if (mode !== undefined) return game === 'multi-touch' ? rebuildTouchReplay(mode, source, scoreMs) : rebuildTrainingReplay({ game, mode }, source, scoreMs);
    } else if (game === 'flag-chord') {
        const mode = flagChordModes.find((item) => `flag-chord-${item.key}-v1` === rankingKey);
        if (mode !== undefined) return rebuildTrainingReplay({ game, mode }, source, scoreMs);
    } else {
        const mode = missingCellModes.find((item) => `missing-cell-${item.key}-v1` === rankingKey);
        if (mode !== undefined) return { game, mode, rounds: decodeMissingCellRounds(mode, source), durationMs: scoreMs };
    }
    throw new Error('Unknown minigame replay ranking');
}
