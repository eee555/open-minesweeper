import { MS_Mode } from './ms_const';
import type { VideoAbstract } from './videoabstract';

export const WeeklyTournamentFormat = {
    Classic: 'c', NF: 'n', QWC: 'q', QWCNF: 'f',
} as const;
export type WeeklyTournamentFormat = typeof WeeklyTournamentFormat[keyof typeof WeeklyTournamentFormat];

export const weeklyFormatNames = {
    c: { zh: '经典', en: 'Classic', es: 'Clásico' },
    n: { zh: 'NF', en: 'NF', es: 'NF' },
    q: { zh: '强无猜', en: 'Hardcore NG', es: 'Sin adivinar estricto' },
    f: { zh: '强无猜NF', en: 'Hardcore NG NF', es: 'Sin adivinar estricto NF' },
} as const;

export function matchesWeeklyFormat(video: Pick<VideoAbstract, 'mode' | 'right_ce'>, format: WeeklyTournamentFormat): boolean {
    switch (format) {
        case WeeklyTournamentFormat.Classic: return video.mode === MS_Mode.Standard;
        case WeeklyTournamentFormat.NF: return video.mode === MS_Mode.Standard && video.right_ce === 0;
        case WeeklyTournamentFormat.QWC: return video.mode === MS_Mode.HardcoreNG;
        case WeeklyTournamentFormat.QWCNF: return video.mode === MS_Mode.HardcoreNG && video.right_ce === 0;
    }
    return false;
}
