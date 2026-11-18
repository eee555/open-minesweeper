import version from '../../../local-minigame/version.json';

export const trainingGames = ['left-click', 'multi-touch', 'flag-chord', 'missing-cell', 'reaction'] as const;
export type TrainingGame = typeof trainingGames[number];

const densityLabels: Record<string, string> = { 50: '1/2', 75: '3/4', 87.5: '7/8' };
export function minigameDensityLabel(game: TrainingGame, density: string | null | undefined): string {
    return game === 'reaction' && density != null ? `${density}%` : densityLabels[density ?? ''] ?? '';
}

export const offlineDownloadFilename = `OpenMinesweeperMinigames-${version.version}.zip`;
export const offlineDownloadUrl = `${import.meta.env.BASE_URL}assets/${offlineDownloadFilename}`;
